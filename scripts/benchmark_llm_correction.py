"""Compare the legacy full-document contract with bounded row patches.

This is a local payload/rule benchmark.  It deliberately uses a fake
OpenAI-compatible response so it never sends document content to a network or
pretends to reproduce customer GPU inference latency.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace


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
LEGACY_USER_PREFIX = (
    "你是一位专业的OCR后处理专家。请严格修复下面HTML/Markdown表格中的列错位错误。"
    "检查法兰标准、公称尺寸DN、法兰类型代号，并直接输出修复后的完整文档。\n"
)


def build_document(row_count: int) -> str:
    header = (
        "<tr><td>管口号</td><td>公称尺寸DN</td>"
        "<td>法兰标准</td><td>法兰类型代号</td></tr>"
    )
    rows = []
    for index in range(row_count):
        if index == row_count - 1:
            standard, flange_type = "HG/T 20592-200", "9 内螺纹"
        elif index % 10 == 0:
            standard, flange_type = "HG/T 20592-200", "9 IF"
        else:
            standard, flange_type = "HG/T 20592-2009", "IF"
        rows.append(
            f"<tr><td>N{index + 1}</td><td>50</td><td>{standard}</td>"
            f"<td>{flange_type}</td></tr>"
        )
    return "# 管口表\n<table>" + header + "".join(rows) + "</table>\n"


class FakeCompletions:
    def __init__(self) -> None:
        self.calls = []
        self.response_chars = 0

    def create(self, **kwargs):
        self.calls.append(kwargs)
        user_prompt = kwargs["messages"][1]["content"]
        payload = json.loads(user_prompt.split("输入行（JSON）：\n", 1)[1])
        row = payload["rows"][0]
        response_text = json.dumps(
            {
                "patches": [
                    {
                        "row_id": row["row_id"],
                        "cells": {
                            "法兰标准": "HG/T 20592-2009",
                            "法兰类型代号": "内螺纹",
                        },
                    }
                ]
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.response_chars += len(response_text)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=response_text))],
            usage=None,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=200)
    args = parser.parse_args()
    if args.rows < 2:
        parser.error("--rows must be at least 2")

    document = build_document(args.rows)
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    config = LLMCorrectionConfig(
        enabled=True,
        base_url="http://127.0.0.1:9999/v1",
        api_key="EMPTY",
        model="qwen-benchmark-placeholder",
        provider="qwen-vllm",
        disable_thinking=True,
        max_output_tokens=512,
        timeout_seconds=10.0,
        max_retries=0,
        max_rows_per_request=20,
    )

    result = correct_nozzle_table_md(document, config=config, client=client)
    legacy_prompt_chars = len(LEGACY_SYSTEM_PROMPT) + len(LEGACY_USER_PREFIX) + len(document)
    optimized_prompt_chars = sum(
        len(message["content"])
        for call in completions.calls
        for message in call["messages"]
    )
    legacy_completion_chars = len(document)
    optimized_completion_chars = completions.response_chars

    report = {
        "mode": "local_payload_and_rule_benchmark_no_model_inference",
        "rows": args.rows,
        "document_chars": len(document),
        "legacy": {
            "prompt_chars": legacy_prompt_chars,
            "expected_completion_chars": legacy_completion_chars,
            "contract": "full_document_in_full_document_out",
        },
        "optimized": {
            "prompt_chars": optimized_prompt_chars,
            "completion_chars": optimized_completion_chars,
            "llm_requests": result.metrics.llm_requests,
            "llm_candidate_rows": result.metrics.llm_candidate_rows,
            "rule_fixes": result.metrics.rule_fixes,
            "patched_cells": result.metrics.patched_cells,
            "local_total_duration_ms": result.metrics.duration_ms,
            "contract": "ambiguous_rows_in_validated_json_patches_out",
        },
        "reduction": {
            "prompt_chars_percent": round(
                (1 - optimized_prompt_chars / legacy_prompt_chars) * 100,
                2,
            ),
            "completion_chars_percent": round(
                (1 - optimized_completion_chars / legacy_completion_chars) * 100,
                2,
            ),
        },
        "changed": result.changed,
        "needs_review_rows": result.metrics.needs_review_rows,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
