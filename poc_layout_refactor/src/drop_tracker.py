"""Drop tracking for Phase 1 candidate governance.

Every box/region that is filtered, deduplicated or merged into another one
must be recorded here. The goal is "no silent drops". Each entry is later
serialised to `dropped_candidates.json`.
"""

from __future__ import annotations

from typing import Any, Iterable


class DropTracker:
    """Collects drop events with structured reasons."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    def record(
        self,
        region: dict[str, Any],
        stage: str,
        reason: str,
        related: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "region_id": region.get("region_id") or region.get("raw_id"),
            "stage": stage,
            "reason": reason,
            "source": region.get("source"),
            "roi_name": region.get("roi_name"),
            "labels": list(region.get("labels") or ([region.get("label")] if region.get("label") else [])),
            "score": region.get("score"),
            "bbox_ratio": region.get("bbox_ratio"),
        }
        if related is not None:
            entry["related_region_id"] = related.get("region_id") or related.get("raw_id")
            entry["related_bbox_ratio"] = related.get("bbox_ratio")
        if extra:
            entry.update(extra)
        self._entries.append(entry)

    def record_many(
        self,
        regions: Iterable[dict[str, Any]],
        stage: str,
        reason: str,
        related: dict[str, Any] | None = None,
    ) -> None:
        for region in regions:
            self.record(region, stage=stage, reason=reason, related=related)

    @property
    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def reason_summary(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for entry in self._entries:
            key = f"{entry['stage']}::{entry['reason']}"
            summary[key] = summary.get(key, 0) + 1
        return summary

    def __len__(self) -> int:
        return len(self._entries)
