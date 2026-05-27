"""CLI runner for Phase 3 table recognition."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from table_recognition.candidate_loader import load_candidate_tasks
from table_recognition.engines.base import RecognitionResult
from table_recognition.engines.mock_engine import MockTableRecognitionEngine
from table_recognition.engines.structeqtable_engine import StructEqTableEngine
from table_recognition.output_writer import TableRecognitionOutputWriter


ENGINE_ALIASES = {
    "mock": "mock",
    "structeqtable": "structeqtable",
    "structtable": "structeqtable",
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    engine_name = ENGINE_ALIASES[args.engine]

    try:
        load_result = load_candidate_tasks(args.input_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    engine = build_engine(
        engine_name=engine_name,
        structeqtable_ckpt=args.structeqtable_ckpt,
        structeqtable_output_formats=args.structeqtable_output_formats,
    )
    writer = TableRecognitionOutputWriter(load_result.input_dir, engine_name)

    per_candidate_results: list[dict[str, object]] = []
    for task in load_result.tasks:
        if not task.should_process:
            write_result = writer.write_candidate_result(
                task=task,
                result=None,
                status="skipped",
                skip_reason=task.skip_reason or "skipped",
            )
            per_candidate_results.append(write_result.manifest_entry)
            continue

        if not task.source_image_path.exists():
            write_result = writer.write_candidate_result(
                task=task,
                result=None,
                status="failed",
                error_message=f"Crop image not found: {task.source_image_path}",
            )
            per_candidate_results.append(write_result.manifest_entry)
            continue

        try:
            result = engine.recognize(task.source_image_path, task.engine_metadata())
        except Exception as exc:  # pragma: no cover - defensive guard.
            result = RecognitionResult(
                status="failed",
                error_message=f"{type(exc).__name__}: {exc}",
                engine_message="Unhandled engine exception was captured by CLI runner.",
            )

        write_result = writer.write_candidate_result(
            task=task,
            result=result,
            status=result.status,
        )
        per_candidate_results.append(write_result.manifest_entry)

    manifest_path = writer.write_manifest(load_result, per_candidate_results)
    print_summary(load_result.tasks, per_candidate_results, writer.output_dir, manifest_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Phase 3 table recognition on Phase 2 final candidate crops.",
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Phase 2 output directory, for example poc_layout_refactor/output/sample.",
    )
    parser.add_argument(
        "--engine",
        choices=sorted(ENGINE_ALIASES),
        default="mock",
        help=(
            "Recognition engine. Use 'mock' for deterministic placeholder output. "
            "Use 'structeqtable' for the StructEqTable/StructTable adapter; "
            "'structtable' is accepted as an alias."
        ),
    )
    parser.add_argument(
        "--structeqtable-ckpt",
        default=None,
        help=(
            "Optional StructEqTable checkpoint path or Hugging Face model id. "
            "If omitted, the adapter checks STRUCT_EQTABLE_CKPT_PATH and then "
            "records engine_unavailable instead of downloading/loading a model."
        ),
    )
    parser.add_argument(
        "--structeqtable-output-formats",
        default=None,
        help=(
            "Comma-separated StructEqTable output formats. Defaults to html,markdown,latex. "
            "Can also be set with STRUCT_EQTABLE_OUTPUT_FORMATS."
        ),
    )
    return parser


def build_engine(
    engine_name: str,
    structeqtable_ckpt: str | None = None,
    structeqtable_output_formats: str | None = None,
):
    if engine_name == "mock":
        return MockTableRecognitionEngine()
    if engine_name == "structeqtable":
        return StructEqTableEngine(
            ckpt_path=structeqtable_ckpt,
            output_formats=parse_output_formats(structeqtable_output_formats),
        )
    raise ValueError(f"Unsupported engine: {engine_name}")


def parse_output_formats(raw_value: str | None) -> tuple[str, ...] | None:
    if not raw_value:
        return None
    values = tuple(value.strip().lower() for value in raw_value.split(",") if value.strip())
    return values or None


def print_summary(tasks, per_candidate_results, output_dir: Path, manifest_path: Path) -> None:
    counts: dict[str, int] = {}
    for entry in per_candidate_results:
        status = str(entry.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1

    print("Phase 3 table-recognition summary")
    print(f"total candidates: {len(tasks)}")
    print(f"processed: {counts.get('succeeded', 0)}")
    print(f"skipped: {counts.get('skipped', 0)}")
    print(f"failed: {counts.get('failed', 0)}")
    print(f"unavailable: {counts.get('engine_unavailable', 0)}")
    print(f"output directory: {output_dir}")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    raise SystemExit(main())
