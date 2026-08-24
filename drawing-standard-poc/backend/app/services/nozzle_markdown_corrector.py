"""Fast, bounded correction for MinerU nozzle-table Markdown.

The historical implementation sent the complete Markdown document to an LLM
and asked the model to generate the complete document again.  This module keeps
the document local, applies the known OCR drift rules deterministically, and
uses an optional OpenAI-compatible LLM only for the small set of ambiguous
rows.  The LLM is allowed to return cell patches, never a rewritten document.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


LOGGER = logging.getLogger(__name__)

DN_COLUMN = "公称尺寸DN"
STANDARD_COLUMN = "法兰标准"
TYPE_COLUMN = "法兰类型代号"
TARGET_COLUMNS = (DN_COLUMN, STANDARD_COLUMN, TYPE_COLUMN)

_TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table\s*>", re.IGNORECASE | re.DOTALL)
_ROW_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr\s*>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(
    r"<t(?P<tag>[dh])\b(?P<attrs>[^>]*)>(?P<inner>.*?)</t(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)
_INCOMPLETE_YEAR_RE = re.compile(r"-(?:19|20)\d\s*$")
_OVERLONG_YEAR_RE = re.compile(r"-(?:19|20)\d{3,}\s*$")
_TYPE_DIGIT_DRIFT_RE = re.compile(r"^\s*(?P<digit>\d)\s*(?P<rest>\D\S.*|\D)\s*$", re.DOTALL)
_COMMON_TYPE_DIGIT_DRIFT_RE = re.compile(
    r"^\s*(?P<digit>\d)\s*(?P<rest>[A-Za-z][A-Za-z0-9./_-]*(?:\s.*)?)\s*$",
    re.DOTALL,
)
_DN_LETTER_DRIFT_RE = re.compile(
    r"^(?P<body>.*\d)\s*(?P<letter>[A-Za-z])\s*$",
    re.DOTALL,
)
_MISSING_H_PREFIX_RE = re.compile(r"^\s*G/T(?=\s|\d|$)", re.IGNORECASE)

_STANDARD_PREFIXES = (
    "AQ",
    "C/TE",
    "GB",
    "GB/T",
    "GBZ/T",
    "HG",
    "HG/T",
    "JB",
    "JB/T",
    "NB/T",
    "Q/SH",
    "SH/T",
    "SY/T",
    "T/ES",
    "TSG",
    "YB/T",
)

_SYSTEM_PROMPT = (
    "你是严谨的OCR表格修复器。只移动明确漂移的字符，不猜测缺失内容，"
    "并且只返回用户要求的JSON对象。"
)
_PATCH_PROMPT_PREFIX = """只检查下列管口表行中的三个字段，禁止修改或补全文档其他内容。

规则：
1. 法兰类型代号开头的单个数字，仅当它是法兰标准缺失年份的末位时，移到法兰标准末尾。
2. 公称尺寸DN末尾的单个字母，仅当它是法兰标准缺失的开头字符时，移到法兰标准开头。
3. 法兰标准以 G/T 开头时可补为 HG/T。
4. 没有足够证据时不要猜测，返回空 patches。

只返回紧凑JSON，格式为：
{"patches":[{"row_id":"t0r1","cells":{"法兰标准":"修正值"}}]}
cells 只能包含 公称尺寸DN、法兰标准、法兰类型代号；不要输出Markdown代码块或解释。
"""


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, min(maximum, int(raw)))
    except ValueError:
        return default


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, min(maximum, float(raw)))
    except ValueError:
        return default


def nozzle_correction_enabled() -> bool:
    """Return whether bounded nozzle correction is enabled for MinerU output."""

    return _env_bool("NOZZLE_CORRECTION_ENABLED", True)


@dataclass(frozen=True)
class LLMCorrectionConfig:
    """Runtime configuration for the optional ambiguous-row fallback."""

    enabled: bool = False
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    provider: str = "qwen-vllm"
    disable_thinking: bool = True
    max_output_tokens: int = 512
    timeout_seconds: float = 60.0
    max_retries: int = 0
    max_rows_per_request: int = 20

    @classmethod
    def from_env(cls) -> "LLMCorrectionConfig":
        return cls(
            enabled=_env_bool("LLM_CORRECTION_ENABLED", False),
            base_url=os.getenv("LLM_BASE_URL", "").strip(),
            api_key=os.getenv("LLM_API_KEY", "").strip(),
            model=os.getenv("LLM_MODEL", "").strip(),
            provider=os.getenv("LLM_PROVIDER", "qwen-vllm").strip().lower(),
            disable_thinking=_env_bool("LLM_DISABLE_THINKING", True),
            max_output_tokens=_env_int("LLM_MAX_OUTPUT_TOKENS", 512, 64, 1024),
            timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", 60.0, 1.0, 300.0),
            max_retries=_env_int("LLM_MAX_RETRIES", 0, 0, 2),
            max_rows_per_request=_env_int("LLM_MAX_ROWS_PER_REQUEST", 20, 1, 100),
        )

    def configuration_error(self) -> Optional[str]:
        if not self.enabled:
            return None
        missing = [
            name
            for name, value in (
                ("LLM_BASE_URL", self.base_url),
                ("LLM_API_KEY", self.api_key),
                ("LLM_MODEL", self.model),
            )
            if not value
        ]
        if missing:
            return "missing_" + "_".join(name.lower() for name in missing)
        return None


@dataclass
class CorrectionMetrics:
    method: str = "unchanged"
    duration_ms: float = 0.0
    input_chars: int = 0
    output_chars: int = 0
    target_tables: int = 0
    inspected_rows: int = 0
    rule_fixes: int = 0
    patched_cells: int = 0
    needs_review_rows: int = 0
    llm_candidate_rows: int = 0
    llm_requests: int = 0
    llm_prompt_chars: int = 0
    llm_response_chars: int = 0
    llm_prompt_tokens: Optional[int] = None
    llm_completion_tokens: Optional[int] = None
    llm_total_tokens: Optional[int] = None
    llm_error_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CorrectionResult:
    content: str
    changed: bool
    metrics: CorrectionMetrics


@dataclass(frozen=True)
class _CellRef:
    inner_start: int
    inner_end: int
    inner_html: str
    text: str
    rowspan: int
    colspan: int

    @property
    def is_plain_text(self) -> bool:
        return "<" not in self.inner_html and ">" not in self.inner_html


@dataclass
class _RowState:
    row_id: str
    cells: Dict[str, _CellRef]
    original: Dict[str, str]
    current: Dict[str, str]
    fix_names: List[str] = field(default_factory=list)


def _plain_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    value = _HTML_TAG_RE.sub("", value)
    return html.unescape(value).replace("\xa0", " ").strip()


def _span_value(attributes: str, name: str) -> int:
    match = re.search(
        rf"\b{name}\s*=\s*(?:[\"'](?P<quoted>\d+)[\"']|(?P<plain>\d+))",
        attributes,
        flags=re.IGNORECASE,
    )
    if not match:
        return 1
    return max(1, int(match.group("quoted") or match.group("plain")))


def _normalized_header(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("（", "(").replace("）", ")").lower()


def _header_column(value: str) -> Optional[str]:
    normalized = _normalized_header(value)
    if normalized in {"公称尺寸dn", "公称尺寸(dn)", "公称尺寸"}:
        return DN_COLUMN
    if normalized == "法兰标准":
        return STANDARD_COLUMN
    if normalized in {"法兰类型代号", "法兰型式代号"}:
        return TYPE_COLUMN
    return None


def _extract_target_rows(markdown: str) -> Tuple[List[_RowState], int]:
    states: List[_RowState] = []
    target_tables = 0

    for table_index, table_match in enumerate(_TABLE_RE.finditer(markdown)):
        table_text = table_match.group(0)
        rows: List[List[_CellRef]] = []

        for row_match in _ROW_RE.finditer(table_text):
            row_inner = row_match.group(1)
            row_inner_start = table_match.start() + row_match.start(1)
            cells: List[_CellRef] = []
            for cell_match in _CELL_RE.finditer(row_inner):
                inner = cell_match.group("inner")
                attributes = cell_match.group("attrs")
                cells.append(
                    _CellRef(
                        inner_start=row_inner_start + cell_match.start("inner"),
                        inner_end=row_inner_start + cell_match.end("inner"),
                        inner_html=inner,
                        text=_plain_text(inner),
                        rowspan=_span_value(attributes, "rowspan"),
                        colspan=_span_value(attributes, "colspan"),
                    )
                )
            if cells:
                rows.append(cells)

        header_index: Optional[int] = None
        column_indexes: Dict[str, int] = {}
        for candidate_index, cells in enumerate(rows):
            # Merged headers require a full logical grid.  Skip them rather
            # than risk applying a patch to the wrong physical cell.
            if any(cell.rowspan != 1 or cell.colspan != 1 for cell in cells):
                continue
            mapping: Dict[str, int] = {}
            for cell_index, cell in enumerate(cells):
                column = _header_column(cell.text)
                if column and column not in mapping:
                    mapping[column] = cell_index
            if all(column in mapping for column in TARGET_COLUMNS):
                header_index = candidate_index
                column_indexes = mapping
                break

        if header_index is None:
            continue

        target_tables += 1
        required_index = max(column_indexes.values())
        for row_index, cells in enumerate(rows[header_index + 1 :], start=header_index + 1):
            if len(cells) <= required_index:
                continue
            selected = {column: cells[index] for column, index in column_indexes.items()}
            if any(cell.rowspan != 1 or cell.colspan != 1 for cell in selected.values()):
                continue
            values = {column: selected[column].text for column in TARGET_COLUMNS}
            states.append(
                _RowState(
                    row_id=f"t{table_index}r{row_index}",
                    cells=selected,
                    original=dict(values),
                    current=dict(values),
                )
            )

    return states, target_tables


def _normalize_g_t_prefix(value: str) -> str:
    match = _MISSING_H_PREFIX_RE.match(value)
    if not match:
        return value
    leading = value[: len(value) - len(value.lstrip())]
    return leading + "H" + value[len(leading) :]


def _has_known_standard_prefix(value: str) -> bool:
    upper = value.lstrip().upper()
    return any(upper.startswith(prefix) for prefix in _STANDARD_PREFIXES)


def _repair_row_with_rules(row: _RowState) -> None:
    dn_value = row.current[DN_COLUMN]
    standard_value = row.current[STANDARD_COLUMN]
    type_value = row.current[TYPE_COLUMN]

    type_match = _COMMON_TYPE_DIGIT_DRIFT_RE.match(type_value)
    if type_match and _INCOMPLETE_YEAR_RE.search(standard_value):
        standard_value = standard_value.rstrip() + type_match.group("digit")
        type_value = type_match.group("rest").strip()
        row.fix_names.append("year_digit_right_drift")

    dn_match = _DN_LETTER_DRIFT_RE.match(dn_value)
    if dn_match:
        candidate = dn_match.group("letter").upper() + standard_value.lstrip()
        candidate = _normalize_g_t_prefix(candidate)
        if _has_known_standard_prefix(candidate):
            dn_value = dn_match.group("body").rstrip()
            standard_value = candidate
            row.fix_names.append("standard_prefix_left_drift")

    normalized_standard = _normalize_g_t_prefix(standard_value)
    if normalized_standard != standard_value:
        standard_value = normalized_standard
        row.fix_names.append("missing_h_prefix")

    row.current[DN_COLUMN] = dn_value
    row.current[STANDARD_COLUMN] = standard_value
    row.current[TYPE_COLUMN] = type_value


def _suspicion_names(values: Mapping[str, str]) -> Set[str]:
    suspicions: Set[str] = set()
    type_match = _TYPE_DIGIT_DRIFT_RE.match(values[TYPE_COLUMN])
    if type_match:
        suspicions.add("type_leading_digit")
    if _DN_LETTER_DRIFT_RE.match(values[DN_COLUMN]):
        suspicions.add("dn_trailing_letter")
    if _INCOMPLETE_YEAR_RE.search(values[STANDARD_COLUMN]):
        suspicions.add("incomplete_year")
    if _MISSING_H_PREFIX_RE.match(values[STANDARD_COLUMN]):
        suspicions.add("missing_h_prefix")
    return suspicions


def _eligible_for_llm(values: Mapping[str, str]) -> bool:
    suspicions = _suspicion_names(values)
    recoverable_year = {
        "type_leading_digit",
        "incomplete_year",
    }.issubset(suspicions)
    return recoverable_year or "dn_trailing_letter" in suspicions


def _chunks(values: Sequence[_RowState], size: int) -> Iterable[Sequence[_RowState]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _thinking_extra_body(config: LLMCorrectionConfig) -> Optional[Dict[str, Any]]:
    if not config.disable_thinking:
        return None
    if config.provider in {"qwen-vllm", "vllm", "qwen-sglang", "sglang"}:
        return {"chat_template_kwargs": {"enable_thinking": False}}
    if config.provider in {"dashscope", "qwen-dashscope"}:
        return {"enable_thinking": False}
    return None


def _build_user_prompt(rows: Sequence[_RowState], config: LLMCorrectionConfig) -> str:
    payload = {
        "rows": [
            {"row_id": row.row_id, "cells": {column: row.current[column] for column in TARGET_COLUMNS}}
            for row in rows
        ]
    }
    no_think = "/no_think\n" if config.disable_thinking and config.provider.startswith("qwen") else ""
    return (
        no_think
        + _PATCH_PROMPT_PREFIX
        + "\n输入行（JSON）：\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _create_client(config: LLMCorrectionConfig) -> Any:
    # Lazy import keeps deterministic local correction independent of the SDK.
    from openai import OpenAI

    return OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout_seconds,
        max_retries=config.max_retries,
    )


def _response_content(response: Any) -> str:
    content = response.choices[0].message.content
    if isinstance(content, str):
        return content
    return str(content or "")


def _usage_value(usage: Any, name: str) -> Optional[int]:
    if usage is None:
        return None
    if isinstance(usage, Mapping):
        value = usage.get(name)
    else:
        value = getattr(usage, name, None)
    return int(value) if isinstance(value, (int, float)) else None


def _accumulate_usage(metrics: CorrectionMetrics, response: Any) -> None:
    usage = getattr(response, "usage", None)
    for metric_name, usage_name in (
        ("llm_prompt_tokens", "prompt_tokens"),
        ("llm_completion_tokens", "completion_tokens"),
        ("llm_total_tokens", "total_tokens"),
    ):
        value = _usage_value(usage, usage_name)
        if value is not None:
            existing = getattr(metrics, metric_name)
            setattr(metrics, metric_name, (existing or 0) + value)


def _parse_patch_response(content: str) -> List[Mapping[str, Any]]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("missing_json_object")
    payload = json.loads(stripped[start : end + 1])
    patches = payload.get("patches") if isinstance(payload, Mapping) else None
    if not isinstance(patches, list):
        raise ValueError("invalid_patches")
    return [item for item in patches if isinstance(item, Mapping)]


def _compact_row(values: Mapping[str, str]) -> str:
    return "".join(re.sub(r"\s+", "", values[column]) for column in TARGET_COLUMNS)


def _safe_patch_value(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 512
        and "<" not in value
        and ">" not in value
        and "\r" not in value
        and "\n" not in value
    )


def _apply_validated_patches(rows: Sequence[_RowState], patches: Sequence[Mapping[str, Any]]) -> int:
    by_id = {row.row_id: row for row in rows}
    accepted = 0

    for patch in patches:
        row_id = patch.get("row_id")
        cells = patch.get("cells")
        row = by_id.get(row_id) if isinstance(row_id, str) else None
        if row is None or not isinstance(cells, Mapping) or not cells:
            continue

        before = dict(row.current)
        before_suspicions = _suspicion_names(before)
        allowed: Set[str] = set()
        if {"type_leading_digit", "incomplete_year"}.issubset(before_suspicions):
            allowed.update({STANDARD_COLUMN, TYPE_COLUMN})
        if "dn_trailing_letter" in before_suspicions:
            allowed.update({DN_COLUMN, STANDARD_COLUMN})

        if any(column not in allowed for column in cells):
            continue
        if any(not _safe_patch_value(value) for value in cells.values()):
            continue

        proposed = dict(before)
        for column, value in cells.items():
            proposed[column] = value.strip()

        # LLM output may move characters between adjacent cells, but may not
        # insert/delete content or manufacture a five-digit year.
        if _compact_row(proposed) != _compact_row(before):
            continue
        if _OVERLONG_YEAR_RE.search(proposed[STANDARD_COLUMN]):
            continue
        after_suspicions = _suspicion_names(proposed)
        if not after_suspicions < before_suspicions:
            continue

        changed_cells = sum(proposed[column] != before[column] for column in TARGET_COLUMNS)
        if changed_cells:
            row.current = proposed
            row.fix_names.append("llm_validated_patch")
            accepted += changed_cells

    return accepted


def _replacement_inner(cell: _CellRef, value: str) -> str:
    match = re.match(r"^(?P<leading>\s*).*?(?P<trailing>\s*)$", cell.inner_html, re.DOTALL)
    if not match:
        return value
    return match.group("leading") + value + match.group("trailing")


def _apply_document_replacements(markdown: str, rows: Sequence[_RowState]) -> Tuple[str, int]:
    replacements: List[Tuple[int, int, str]] = []
    for row in rows:
        for column in TARGET_COLUMNS:
            if row.current[column] == row.original[column]:
                continue
            cell = row.cells[column]
            if not cell.is_plain_text:
                continue
            replacements.append(
                (cell.inner_start, cell.inner_end, _replacement_inner(cell, row.current[column]))
            )

    result = markdown
    for start, end, value in sorted(replacements, reverse=True):
        result = result[:start] + value + result[end:]
    return result, len(replacements)


def _log_metrics(metrics: CorrectionMetrics) -> None:
    LOGGER.info(
        "nozzle_markdown_correction %s",
        json.dumps(metrics.to_dict(), ensure_ascii=False, separators=(",", ":")),
    )


def correct_nozzle_table_md(
    markdown: str,
    *,
    config: Optional[LLMCorrectionConfig] = None,
    client: Any = None,
) -> CorrectionResult:
    """Correct known nozzle-table OCR drift without rewriting the document.

    Deterministic rules always run.  The LLM fallback is opt-in through
    ``LLM_CORRECTION_ENABLED`` and receives only ambiguous row values.  Every
    returned patch is validated locally before it can change the document.
    """

    started = time.perf_counter()
    source = markdown if isinstance(markdown, str) else markdown
    metrics = CorrectionMetrics(input_chars=len(source) if isinstance(source, str) else 0)

    if not isinstance(source, str) or not source:
        metrics.method = "skipped_empty"
        metrics.output_chars = metrics.input_chars
        metrics.duration_ms = round((time.perf_counter() - started) * 1000, 3)
        _log_metrics(metrics)
        return CorrectionResult(content=source, changed=False, metrics=metrics)

    rows, target_tables = _extract_target_rows(source)
    metrics.target_tables = target_tables
    metrics.inspected_rows = len(rows)
    if not rows:
        metrics.method = "skipped_no_supported_rows" if target_tables else "skipped_no_target_table"
        metrics.output_chars = len(source)
        metrics.duration_ms = round((time.perf_counter() - started) * 1000, 3)
        _log_metrics(metrics)
        return CorrectionResult(content=source, changed=False, metrics=metrics)

    for row in rows:
        if all(row.cells[column].is_plain_text for column in TARGET_COLUMNS):
            _repair_row_with_rules(row)
    metrics.rule_fixes = sum(len(row.fix_names) for row in rows)

    unresolved = [row for row in rows if _suspicion_names(row.current)]
    llm_candidates = [
        row
        for row in unresolved
        if _eligible_for_llm(row.current)
        and all(row.cells[column].is_plain_text for column in TARGET_COLUMNS)
    ]
    metrics.needs_review_rows = len(unresolved)
    metrics.llm_candidate_rows = len(llm_candidates)

    llm_patch_cells = 0
    runtime_config = config or LLMCorrectionConfig.from_env()
    if runtime_config.enabled and llm_candidates:
        config_error = runtime_config.configuration_error() if client is None else None
        if config_error:
            metrics.llm_error_type = config_error
        else:
            try:
                runtime_client = client or _create_client(runtime_config)
                for row_chunk in _chunks(llm_candidates, runtime_config.max_rows_per_request):
                    user_prompt = _build_user_prompt(row_chunk, runtime_config)
                    messages = [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ]
                    request: Dict[str, Any] = {
                        "model": runtime_config.model,
                        "messages": messages,
                        "temperature": 0.0,
                        "max_tokens": runtime_config.max_output_tokens,
                    }
                    extra_body = _thinking_extra_body(runtime_config)
                    if extra_body:
                        request["extra_body"] = extra_body

                    metrics.llm_requests += 1
                    metrics.llm_prompt_chars += sum(len(message["content"]) for message in messages)
                    response = runtime_client.chat.completions.create(**request)
                    response_text = _response_content(response)
                    metrics.llm_response_chars += len(response_text)
                    _accumulate_usage(metrics, response)
                    patches = _parse_patch_response(response_text)
                    llm_patch_cells += _apply_validated_patches(row_chunk, patches)
            except Exception as exc:  # fail closed: keep rules/original content
                metrics.llm_error_type = type(exc).__name__
                LOGGER.warning("nozzle_markdown_llm_fallback_failed error_type=%s", type(exc).__name__)

    result, patched_cells = _apply_document_replacements(source, rows)
    metrics.patched_cells = patched_cells
    metrics.needs_review_rows = sum(bool(_suspicion_names(row.current)) for row in rows)

    used_rules = any(name != "llm_validated_patch" for row in rows for name in row.fix_names)
    used_llm = llm_patch_cells > 0
    if used_rules and used_llm:
        metrics.method = "rules+llm_patch"
    elif used_rules:
        metrics.method = "rules"
    elif used_llm:
        metrics.method = "llm_patch"
    elif metrics.needs_review_rows:
        metrics.method = "needs_review"
    else:
        metrics.method = "unchanged"

    metrics.output_chars = len(result)
    metrics.duration_ms = round((time.perf_counter() - started) * 1000, 3)
    _log_metrics(metrics)
    return CorrectionResult(content=result, changed=result != source, metrics=metrics)


__all__ = [
    "CorrectionMetrics",
    "CorrectionResult",
    "LLMCorrectionConfig",
    "correct_nozzle_table_md",
    "nozzle_correction_enabled",
]
