"""Backward-compatible entry point for nozzle-table correction.

The misspelled module name is retained because historical customer branches
import ``fix_nozzle_table_md`` from here. Configuration and implementation now
live in :mod:`nozzle_markdown_corrector`; no endpoint or credential is embedded
in source code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.services.nozzle_markdown_corrector import correct_nozzle_table_md


def fix_nozzle_table_md(md_content: str) -> str:
    """Return corrected Markdown while preserving the historical API."""

    return correct_nozzle_table_md(md_content).content


def _main() -> int:
    parser = argparse.ArgumentParser(description="修正 MinerU 管口表 Markdown 列漂移")
    parser.add_argument("input", type=Path, help="输入 Markdown 文件")
    parser.add_argument("output", type=Path, help="输出 Markdown 文件")
    args = parser.parse_args()

    source = args.input.read_text(encoding="utf-8")
    result = correct_nozzle_table_md(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.content, encoding="utf-8")
    print(json.dumps(result.metrics.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
