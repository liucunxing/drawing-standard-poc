"""Run a local, synthetic A/B benchmark against an OpenAI-compatible Qwen server.

It never reads or writes customer documents and emits only aggregate metrics,
synthetic model responses, and hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "drawing-standard-poc"))

from backend.app.services.nozzle_markdown_corrector import (  # noqa: E402
    LLMCorrectionConfig,
    correct_nozzle_table_md,
)


LEGACY_SYSTEM_PROMPT = (
    "你是一个严谨的OCR文档修复助手。你只执行用户明确指定的修复规则，"
    "绝不修改规则外的任何内容，绝不擅自推测或润色。"
)
LEGACY_TEMPLATE = """你是一位专业的OCR后处理专家。请严格修复下面HTML/Markdown表格中的**列错位**错误。

## 错误模式（仅限以下3种漂移现象）
1. **末尾字符右漂**："法兰标准"列末尾的字符（通常是年份的最后一位数字，如'8'、'9'、'0'等）被错误截断，漂移到了同行的"法兰类型代号"列开头，使其变成了类似"9 IF"、"8IF"、"0 IF"的形式。
2. **开头字符左漂**："法兰标准"列开头的字符（通常是标准代号的首字母，如'H'）被错误截断，漂移到了同行的前一列"公称尺寸DN"末尾，使其变成了类似"50 H"、"40 G"的形式（即DN列末尾出现了不应有的字母）。
3. **首尾双漂**：同一行可能同时存在上述两种漂移。

## 修复规则（必须遵守）
- 规则1：检查"法兰类型代号"列。如果该列的值以**单个数字**开头（如"9 IF"、"8IF"），将这个开头的数字移回"法兰标准"列的末尾，然后删除"法兰类型代号"列中的该数字前缀（保留原有空格格式）。
- 规则2：检查"公称尺寸DN"列。如果该列的值以**单个字母**结尾（如"50 H"、"40 G"），将这个末尾的字母移回"法兰标准"列的开头，然后删除"公称尺寸DN"列中的该字母后缀，恢复为纯数字。
- 规则3：检查"法兰标准"列。如果值以"G/T"开头（缺失首字母'H'），在开头补回该字母，使其恢复为"HG/T..."。
- 规则4：检查"法兰标准"列。如果值以"-200"结尾（缺失年份最后一位），根据同行"法兰类型代号"列开头漂移过来的数字补全年份。
- **禁令**：严禁修改文档中任何其他内容；严禁改动HTML标签、表格结构、rowspan/colspan属性；严禁推测、润色或补全任何未提及的单元格；严禁将正确的年份（如2008、2010）强制改为2009。

## 待修复文档
{md_content}

## 输出要求
直接输出修复后的完整文档内容，不要添加任何解释、说明或代码块标记（```），保持原始格式。
"""


def build_documents(row_count: int) -> tuple[str, str]:
    header = (
        "<tr><td>管口号</td><td>公称尺寸DN</td>"
        "<td>法兰标准</td><td>法兰类型代号</td></tr>"
    )
    source_rows: list[str] = []
    expected_rows: list[str] = []
    for index in range(row_count):
        if index == row_count - 1:
            standard, flange_type = "HG/T 20592-200", "9 内螺纹"
        elif index % 10 == 0:
            standard, flange_type = "HG/T 20592-200", "9 IF"
        else:
            standard, flange_type = "HG/T 20592-2009", "IF"
        source_rows.append(
            f"<tr><td>N{index + 1}</td><td>50</td><td>{standard}</td>"
            f"<td>{flange_type}</td></tr>"
        )
        expected_rows.append(
            f"<tr><td>N{index + 1}</td><td>50</td><td>HG/T 20592-2009</td>"
            f"<td>{'内螺纹' if index == row_count - 1 else 'IF'}</td></tr>"
        )
    prefix = "# 管口表\n<table>" + header
    suffix = "</table>\n"
    return prefix + "".join(source_rows) + suffix, prefix + "".join(expected_rows) + suffix


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def token_count(server_root: str, content: str) -> int:
    payload = json.dumps({"content": content}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        server_root.rstrip("/") + "/tokenize",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    return len(body["tokens"])


def response_metrics(response: Any, elapsed_seconds: float) -> dict[str, Any]:
    payload = response.model_dump()
    message = response.choices[0].message
    return {
        "elapsed_seconds": round(elapsed_seconds, 3),
        "finish_reason": response.choices[0].finish_reason,
        "usage": payload.get("usage"),
        "timings": payload.get("timings"),
        "content_chars": len(message.content or ""),
        "reasoning_chars": len(getattr(message, "reasoning_content", None) or ""),
    }


def run_legacy(args: argparse.Namespace, disable_thinking: bool) -> dict[str, Any]:
    from openai import OpenAI

    source, expected = build_documents(args.rows)
    client = OpenAI(
        api_key="local-benchmark",
        base_url=args.base_url,
        timeout=args.timeout,
        max_retries=0,
    )
    request: dict[str, Any] = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": LEGACY_SYSTEM_PROMPT},
            {"role": "user", "content": LEGACY_TEMPLATE.format(md_content=source)},
        ],
        "temperature": 0.0,
        "max_tokens": args.legacy_max_tokens,
    }
    if disable_thinking:
        request["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}

    started = time.perf_counter()
    response = client.chat.completions.create(**request)
    elapsed = time.perf_counter() - started
    content = response.choices[0].message.content or ""
    metrics = response_metrics(response, elapsed)
    metrics.update(
        {
            "mode": "legacy_no_think" if disable_thinking else "legacy_default_thinking",
            "rows": args.rows,
            "source_chars": len(source),
            "expected_chars": len(expected),
            "output_sha256": sha256_text(content),
            "expected_sha256": sha256_text(expected),
            "exact_match": content == expected,
            "contains_code_fence": "```" in content,
        }
    )
    return metrics


def run_optimized(args: argparse.Namespace) -> dict[str, Any]:
    from openai import OpenAI

    source, expected = build_documents(args.rows)
    config = LLMCorrectionConfig(
        enabled=True,
        base_url=args.base_url,
        api_key="local-benchmark",
        model=args.model,
        provider="qwen-vllm",
        disable_thinking=True,
        max_output_tokens=512,
        timeout_seconds=args.timeout,
        max_retries=0,
        max_rows_per_request=20,
    )
    delegate = OpenAI(
        api_key="local-benchmark",
        base_url=args.base_url,
        timeout=args.timeout,
        max_retries=0,
    )

    class RecordingCompletions:
        def __init__(self) -> None:
            self.response: Any = None

        def create(self, **kwargs: Any) -> Any:
            self.response = delegate.chat.completions.create(**kwargs)
            return self.response

    recorder = RecordingCompletions()
    client = type("RecordingClient", (), {})()
    client.chat = type("RecordingChat", (), {})()
    client.chat.completions = recorder

    started = time.perf_counter()
    result = correct_nozzle_table_md(source, config=config, client=client)
    elapsed = time.perf_counter() - started
    raw_response = recorder.response
    raw_content = raw_response.choices[0].message.content if raw_response else ""
    return {
        "mode": "optimized_row_patch",
        "rows": args.rows,
        "elapsed_seconds": round(elapsed, 3),
        "source_chars": len(source),
        "output_chars": len(result.content),
        "output_sha256": sha256_text(result.content),
        "expected_sha256": sha256_text(expected),
        "exact_match": result.content == expected,
        "changed": result.changed,
        "correction_metrics": result.metrics.to_dict(),
        "raw_llm_content": raw_content,
        "raw_llm_finish_reason": (
            raw_response.choices[0].finish_reason if raw_response else None
        ),
        "raw_llm_timings": (
            raw_response.model_dump().get("timings") if raw_response else None
        ),
    }


def run_token_plan(args: argparse.Namespace) -> dict[str, Any]:
    plans = []
    for row_count in args.plan_rows:
        source, expected = build_documents(row_count)
        legacy_user = LEGACY_TEMPLATE.format(md_content=source)
        plans.append(
            {
                "rows": row_count,
                "source_chars": len(source),
                "legacy_prompt_raw_tokens": token_count(
                    args.server_root, LEGACY_SYSTEM_PROMPT + "\n" + legacy_user
                ),
                "expected_output_raw_tokens": token_count(args.server_root, expected),
            }
        )
    return {"mode": "token_plan_no_inference", "plans": plans}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("token-plan", "legacy-think", "legacy-no-think", "optimized"),
    )
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--plan-rows", type=int, nargs="+", default=[5, 10, 20, 50, 100, 200])
    parser.add_argument("--server-root", default="http://127.0.0.1:18111")
    parser.add_argument("--base-url", default="http://127.0.0.1:18111/v1")
    parser.add_argument("--model", default="qwen3.5-9b")
    parser.add_argument("--legacy-max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()
    if args.rows < 2:
        parser.error("--rows must be at least 2")

    if args.mode == "token-plan":
        report = run_token_plan(args)
    elif args.mode == "legacy-think":
        report = run_legacy(args, disable_thinking=False)
    elif args.mode == "legacy-no-think":
        report = run_legacy(args, disable_thinking=True)
    else:
        report = run_optimized(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
