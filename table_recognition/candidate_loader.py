"""Load Phase 2 final candidates for Phase 3 table recognition."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_METADATA_FILE = "candidate_regions_merged.json"


@dataclass(frozen=True)
class CandidateTask:
    """A Phase 2 final candidate plus Phase 3 processing decision."""

    metadata: dict[str, Any]
    source_image_path: Path
    should_process: bool
    candidate_kind: str | None
    skip_reason: str | None

    @property
    def region_id(self) -> str:
        return str(self.metadata.get("region_id", "unknown_region"))

    @property
    def candidate_index(self) -> int | None:
        value = self.metadata.get("candidate_index")
        return value if isinstance(value, int) else None

    @property
    def zone(self) -> str | None:
        value = self.metadata.get("zone")
        return str(value) if value is not None else None

    @property
    def labels(self) -> list[str]:
        labels = self.metadata.get("labels", [])
        if not isinstance(labels, list):
            return []
        return [str(label) for label in labels]

    def engine_metadata(self) -> dict[str, Any]:
        payload = dict(self.metadata)
        payload["candidate_kind"] = self.candidate_kind
        payload["resolved_crop_image_path"] = str(self.source_image_path)
        return payload


@dataclass(frozen=True)
class CandidateLoadResult:
    input_dir: Path
    metadata_path: Path
    tasks: list[CandidateTask]
    raw_metadata: dict[str, Any]


def load_candidate_tasks(input_dir: str | Path) -> CandidateLoadResult:
    """Load candidate tasks from a Phase 2 output directory."""

    resolved_input_dir = Path(input_dir).resolve()
    metadata_path = resolved_input_dir / REQUIRED_METADATA_FILE
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing candidate metadata: {metadata_path}")

    with metadata_path.open("r", encoding="utf-8") as handle:
        raw_metadata = json.load(handle)

    candidates = raw_metadata.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError(f"Expected 'candidates' array in {metadata_path}")

    tasks = [
        _build_task(candidate, resolved_input_dir)
        for candidate in candidates
        if isinstance(candidate, dict)
    ]

    return CandidateLoadResult(
        input_dir=resolved_input_dir,
        metadata_path=metadata_path,
        tasks=tasks,
        raw_metadata=raw_metadata,
    )


def _build_task(candidate: dict[str, Any], input_dir: Path) -> CandidateTask:
    labels = candidate.get("labels", [])
    normalized_labels = {
        str(label).strip().lower()
        for label in labels
        if str(label).strip()
    } if isinstance(labels, list) else set()

    is_table = "table" in normalized_labels
    zone = str(candidate.get("zone", "")).strip()
    candidate_kind = "title_block" if zone == "title_block" and is_table else None
    if is_table and candidate_kind is None:
        candidate_kind = "table"

    source_image_path = resolve_crop_image_path(candidate.get("crop_image_path"), input_dir)
    skip_reason = None if is_table else "labels_do_not_include_table"

    return CandidateTask(
        metadata=dict(candidate),
        source_image_path=source_image_path,
        should_process=is_table,
        candidate_kind=candidate_kind,
        skip_reason=skip_reason,
    )


def resolve_crop_image_path(raw_path: Any, input_dir: Path) -> Path:
    """Resolve JSON crop paths that may use Windows separators or Phase 2 roots."""

    if raw_path is None:
        return input_dir / "candidates" / "missing_crop_image_path"

    raw_text = str(raw_path).strip()
    if not raw_text:
        return input_dir / "candidates" / "missing_crop_image_path"

    normalized = raw_text.replace("\\", "/")
    candidate_path = Path(normalized)
    if candidate_path.is_absolute():
        return candidate_path

    search_paths = [
        input_dir / candidate_path,
        input_dir.parent.parent / candidate_path,
        input_dir / "candidates" / candidate_path.name,
    ]

    for path in search_paths:
        if path.exists():
            return path.resolve()

    if normalized.startswith("output/"):
        return (input_dir.parent.parent / candidate_path).resolve()

    return (input_dir / candidate_path).resolve()
