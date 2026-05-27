"""Write Phase 3 table-recognition artifacts and manifest files."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from table_recognition.candidate_loader import CandidateLoadResult, CandidateTask
from table_recognition.engines.base import RecognitionResult


@dataclass
class CandidateWriteResult:
    manifest_entry: dict[str, Any]


class TableRecognitionOutputWriter:
    def __init__(self, input_dir: Path, engine_name: str) -> None:
        self.input_dir = input_dir.resolve()
        self.engine_name = engine_name
        self.output_dir = self.input_dir / "table_recognition" / engine_name
        self.subdirs = {
            "raw": self.output_dir / "raw",
            "html": self.output_dir / "html",
            "markdown": self.output_dir / "markdown",
            "csv": self.output_dir / "csv",
            "json": self.output_dir / "json",
            "logs": self.output_dir / "logs",
        }
        for directory in self.subdirs.values():
            directory.mkdir(parents=True, exist_ok=True)

    def write_candidate_result(
        self,
        task: CandidateTask,
        result: RecognitionResult | None,
        status: str,
        skip_reason: str = "",
        error_message: str = "",
        engine_message: str = "",
    ) -> CandidateWriteResult:
        output_files: dict[str, str] = {}
        resolved_error = error_message
        resolved_engine_message = engine_message

        if result is not None:
            status = result.status
            resolved_error = result.error_message
            resolved_engine_message = result.engine_message
            output_files = self._write_result_files(task, result)

        entry = {
            "region_id": task.region_id,
            "candidate_index": task.candidate_index,
            "zone": task.zone,
            "labels": task.labels,
            "candidate_kind": task.candidate_kind,
            "source_image_path": str(task.source_image_path),
            "status": status,
            "skip_reason": skip_reason,
            "output_files": output_files,
            "error_message": resolved_error,
            "engine_message": resolved_engine_message,
        }
        return CandidateWriteResult(manifest_entry=entry)

    def write_manifest(
        self,
        load_result: CandidateLoadResult,
        per_candidate_results: list[dict[str, Any]],
    ) -> Path:
        run_id = uuid.uuid4().hex
        status_counts = _count_statuses(per_candidate_results)
        manifest = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_dir": str(load_result.input_dir),
            "candidate_metadata_path": str(load_result.metadata_path),
            "engine": self.engine_name,
            "total_candidates": len(load_result.tasks),
            "processed_count": status_counts.get("succeeded", 0),
            "skipped_count": status_counts.get("skipped", 0),
            "failed_count": status_counts.get("failed", 0),
            "unavailable_count": status_counts.get("engine_unavailable", 0),
            "status_counts": status_counts,
            "per_candidate_results": per_candidate_results,
        }
        manifest_path = self.output_dir / "table_recognition_manifest.json"
        _write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        return manifest_path

    def _write_result_files(self, task: CandidateTask, result: RecognitionResult) -> dict[str, str]:
        stem = _candidate_stem(task)
        files = {
            "raw": self.subdirs["raw"] / f"{stem}.txt",
            "html": self.subdirs["html"] / f"{stem}.html",
            "markdown": self.subdirs["markdown"] / f"{stem}.md",
            "csv": self.subdirs["csv"] / f"{stem}.csv",
            "json": self.subdirs["json"] / f"{stem}.json",
            "log": self.subdirs["logs"] / f"{stem}.log",
        }

        _write_text(files["raw"], result.raw_output)
        _write_text(files["html"], result.html)
        _write_text(files["markdown"], result.markdown)
        _write_text(files["csv"], result.csv_text)
        _write_text(files["json"], json.dumps(result.json_data, ensure_ascii=False, indent=2) + "\n")
        log_text = (
            f"status={result.status}\n"
            f"error_message={result.error_message}\n"
            f"engine_message={result.engine_message}\n"
        )
        _write_text(files["log"], log_text)

        return {key: str(path) for key, path in files.items()}


def _candidate_stem(task: CandidateTask) -> str:
    index = task.candidate_index
    index_text = f"{index:03d}" if isinstance(index, int) else "unknown"
    return _slugify(f"candidate_{index_text}_{task.region_id}")


def _slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "candidate"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")


def _count_statuses(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts
