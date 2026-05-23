"""Phase 1 candidate governance.

Pipeline order (with drop tracking on every step):

    layout_boxes_raw -> raw candidates  (label/size/invalid_region filter)
                     -> + roi_fallback candidates (always emitted)
                     -> conservative merge / dedupe
                     -> final candidates with stable region_id

The Phase 1 contract:
  * No silent drops -- every removal is recorded via DropTracker.
  * No business prioritisation -- we do not pick "more important" candidates.
  * Overlap is acceptable -- duplicates are cheaper than missing standards.
"""

from __future__ import annotations

from typing import Any, Sequence

from .drop_tracker import DropTracker
from .utils import (
    bbox_area,
    bbox_iou,
    clamp_bbox_ratio,
    expand_bbox_ratio,
    is_right_side_bbox,
    normalize_label,
    overlap_over_smaller,
    union_bboxes,
)


# ---------------------------------------------------------------------------
# Raw candidate construction (PP-DocLayout boxes -> candidate dicts)
# ---------------------------------------------------------------------------


def build_raw_candidates(
    raw_layout_boxes: list[dict[str, Any]],
    zones_config: dict[str, Any],
    rois: list[dict[str, Any]],
    drop_tracker: DropTracker,
    page_number: int = 1,
) -> list[dict[str, Any]]:
    """Convert PP-DocLayout raw rows into Phase 1 candidate dicts.

    Filters applied (all logged via drop_tracker):
      1. Label-based filter (keep_labels + keep_image_in_right_column).
      2. Size filter (min/max area, width, height).
      3. Invalid region filter (top_axis, left_logo, ...).
    """
    candidate_cfg = zones_config.get("candidate", {}) or {}
    keep_labels = {normalize_label(label) for label in candidate_cfg.get("keep_labels", [])}
    filter_labels = {normalize_label(label) for label in candidate_cfg.get("filter_labels", [])}
    keep_image_right = bool(candidate_cfg.get("keep_image_in_right_column", True))
    invalid_regions = zones_config.get("invalid_regions", {}) or {}

    right_column = _find_roi_bbox(rois, "right_column")
    candidates: list[dict[str, Any]] = []
    counter = 0

    for row in raw_layout_boxes:
        label = normalize_label(row.get("label"))
        score = float(row.get("score", 0.0))
        bbox_ratio = clamp_bbox_ratio(row["bbox_ratio"])
        base_for_drop = {
            "region_id": row.get("raw_id"),
            "source": "layout_box",
            "roi_name": row.get("roi_name"),
            "labels": [label],
            "score": score,
            "bbox_ratio": bbox_ratio,
        }

        # 1. Label filter
        if label in filter_labels:
            drop_tracker.record(base_for_drop, stage="filter", reason=f"label_{label}_blacklisted")
            continue
        label_kept = label in keep_labels
        if not label_kept:
            if label == "image" and keep_image_right and is_right_side_bbox(bbox_ratio, right_column):
                label_kept = True
            else:
                drop_tracker.record(base_for_drop, stage="filter", reason=f"label_{label}_not_in_keep_labels")
                continue

        # 2. Invalid region filter
        invalid_reason, invalid_name = _invalid_region_match(bbox_ratio, invalid_regions)
        if invalid_reason:
            drop_tracker.record(
                base_for_drop,
                stage="filter",
                reason=invalid_reason,
                extra={"invalid_region": invalid_name},
            )
            continue

        # 3. Size filter
        size_reason = _size_filter_reason(bbox_ratio, candidate_cfg)
        if size_reason:
            drop_tracker.record(base_for_drop, stage="filter", reason=size_reason)
            continue

        counter += 1
        candidates.append(
            _build_candidate_record(
                region_id=f"page_{page_number}_candidate_raw_{counter:03d}",
                page_number=page_number,
                source="layout_box",
                roi_name=row.get("roi_name"),
                labels=[label],
                score=score,
                bbox_ratio=bbox_ratio,
                config=candidate_cfg,
                source_box_ids=[row.get("raw_id")],
            )
        )
    return candidates


# ---------------------------------------------------------------------------
# ROI fallback (always emit)
# ---------------------------------------------------------------------------


def build_roi_fallback_candidates(
    rois: list[dict[str, Any]],
    zones_config: dict[str, Any],
    page_number: int = 1,
) -> list[dict[str, Any]]:
    """Always emit one fallback candidate per configured ROI.

    These run in parallel with the layout-derived candidates and are not
    contingent on detection being empty.
    """
    candidate_cfg = zones_config.get("candidate", {}) or {}
    always = list((zones_config.get("roi_fallback") or {}).get("always_emit", []))

    fallbacks: list[dict[str, Any]] = []
    for index, name in enumerate(always, start=1):
        roi_bbox = _find_roi_bbox(rois, name)
        if not roi_bbox:
            continue
        fallbacks.append(
            _build_candidate_record(
                region_id=f"page_{page_number}_roi_fallback_{name}",
                page_number=page_number,
                source="roi_fallback",
                roi_name=name,
                labels=["roi_fallback"],
                score=None,
                bbox_ratio=roi_bbox,
                config=candidate_cfg,
                source_box_ids=[],
                priority="fallback",
                fallback_index=index,
            )
        )
    return fallbacks


# ---------------------------------------------------------------------------
# Conservative merge
# ---------------------------------------------------------------------------


def merge_candidates(
    candidates: list[dict[str, Any]],
    zones_config: dict[str, Any],
    drop_tracker: DropTracker,
) -> list[dict[str, Any]]:
    """Apply the configured merge_strategy. Default is conservative.

    Strategies:
      - none:         return input as-is (still goes through final dedupe).
      - conservative: merge only when IoU >= merge_iou_threshold and labels match.
      - union:        legacy behaviour (horizontal_overlap + vertical_gap).
    """
    candidate_cfg = zones_config.get("candidate", {}) or {}
    strategy = str(candidate_cfg.get("merge_strategy", "conservative")).lower()
    if strategy == "none":
        return [dict(item) for item in candidates]
    if strategy == "union":
        return _merge_union(candidates, candidate_cfg, drop_tracker)
    if strategy != "conservative":
        # Unknown strategy -> behave conservatively but record nothing strange.
        strategy = "conservative"
    return _merge_conservative(candidates, candidate_cfg, drop_tracker)


def _merge_conservative(
    candidates: list[dict[str, Any]],
    candidate_cfg: dict[str, Any],
    drop_tracker: DropTracker,
) -> list[dict[str, Any]]:
    threshold = float(candidate_cfg.get("merge_iou_threshold", 0.85))
    pending = [dict(item) for item in candidates]
    changed = True
    while changed:
        changed = False
        for i in range(len(pending)):
            for j in range(i + 1, len(pending)):
                left, right = pending[i], pending[j]
                if not _same_label_family(left, right):
                    continue
                if left.get("source") == "roi_fallback" or right.get("source") == "roi_fallback":
                    # Never merge roi_fallback away in Phase 1 -- it stays as a
                    # belt-and-braces region for downstream OCR.
                    continue
                if bbox_iou(left["bbox_ratio"], right["bbox_ratio"]) < threshold:
                    continue
                merged = _merge_pair(left, right, candidate_cfg)
                drop_tracker.record(
                    right,
                    stage="merge",
                    reason=f"merged_into_{merged['region_id']}_iou_ge_{threshold:.2f}",
                    related=merged,
                    extra={
                        "before_bbox_ratio": right["bbox_ratio"],
                        "after_bbox_ratio": merged["bbox_ratio"],
                    },
                )
                drop_tracker.record(
                    left,
                    stage="merge",
                    reason=f"merged_into_{merged['region_id']}_iou_ge_{threshold:.2f}",
                    related=merged,
                    extra={
                        "before_bbox_ratio": left["bbox_ratio"],
                        "after_bbox_ratio": merged["bbox_ratio"],
                    },
                )
                pending = [
                    item for index, item in enumerate(pending) if index not in (i, j)
                ]
                pending.append(merged)
                changed = True
                break
            if changed:
                break
    return pending


def _merge_union(
    candidates: list[dict[str, Any]],
    candidate_cfg: dict[str, Any],
    drop_tracker: DropTracker,
) -> list[dict[str, Any]]:
    """Aggressive legacy merge (kept for opt-in experimentation only)."""
    horizontal_overlap = float(candidate_cfg.get("union_horizontal_overlap", 0.45))
    vertical_gap = float(candidate_cfg.get("union_vertical_gap_ratio", 0.035))
    from .utils import horizontal_overlap_ratio, vertical_gap_ratio

    pending = [dict(item) for item in candidates]
    changed = True
    while changed:
        changed = False
        for i in range(len(pending)):
            for j in range(i + 1, len(pending)):
                left, right = pending[i], pending[j]
                if not _same_label_family(left, right):
                    continue
                if left.get("source") == "roi_fallback" or right.get("source") == "roi_fallback":
                    continue
                if bbox_iou(left["bbox_ratio"], right["bbox_ratio"]) <= 0 and (
                    horizontal_overlap_ratio(left["bbox_ratio"], right["bbox_ratio"]) < horizontal_overlap
                    or vertical_gap_ratio(left["bbox_ratio"], right["bbox_ratio"]) > vertical_gap
                ):
                    continue
                merged = _merge_pair(left, right, candidate_cfg)
                drop_tracker.record_many(
                    [left, right], stage="merge", reason="union_strategy_merge", related=merged
                )
                pending = [
                    item for index, item in enumerate(pending) if index not in (i, j)
                ]
                pending.append(merged)
                changed = True
                break
            if changed:
                break
    return pending


# ---------------------------------------------------------------------------
# Final dedupe
# ---------------------------------------------------------------------------


def dedupe_candidates(
    candidates: list[dict[str, Any]],
    zones_config: dict[str, Any],
    drop_tracker: DropTracker,
) -> list[dict[str, Any]]:
    """Remove near-duplicate candidates (very high IoU only).

    roi_fallback candidates are never removed here.
    """
    candidate_cfg = zones_config.get("candidate", {}) or {}
    threshold = float(candidate_cfg.get("dedupe_iou_threshold", 0.95))

    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            0 if item.get("source") == "roi_fallback" else 1,
            -float(item.get("score") or 0.0),
            -bbox_area(item["bbox_ratio"]),
        ),
    )
    kept: list[dict[str, Any]] = []
    for candidate in sorted_candidates:
        if candidate.get("source") == "roi_fallback":
            kept.append(candidate)
            continue
        duplicate_of: dict[str, Any] | None = None
        for existing in kept:
            if existing.get("source") == "roi_fallback":
                continue
            if bbox_iou(candidate["bbox_ratio"], existing["bbox_ratio"]) >= threshold:
                duplicate_of = existing
                break
        if duplicate_of is not None:
            drop_tracker.record(
                candidate,
                stage="dedupe",
                reason=f"duplicated_by_iou_ge_{threshold:.2f}",
                related=duplicate_of,
            )
            continue
        kept.append(candidate)
    return kept


# ---------------------------------------------------------------------------
# Finalise / assign stable region ids
# ---------------------------------------------------------------------------


def finalise_candidates(
    candidates: list[dict[str, Any]],
    page_number: int = 1,
) -> list[dict[str, Any]]:
    """Sort candidates and assign stable, traceable region ids.

    Sort order: by source bucket then by y, x. roi_fallback comes last so that
    their numeric index keeps a stable suffix-style id.
    """
    def _bucket(item: dict[str, Any]) -> int:
        return 1 if item.get("source") == "roi_fallback" else 0

    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            _bucket(item),
            item["bbox_ratio"][1],
            item["bbox_ratio"][0],
        ),
    )
    finalised: list[dict[str, Any]] = []
    for index, item in enumerate(sorted_candidates, start=1):
        new_item = dict(item)
        new_item["source_region_id"] = item.get("region_id")
        new_item["region_id"] = f"page_{page_number}_candidate_{index:03d}"
        new_item["candidate_index"] = index
        finalised.append(new_item)
    return finalised


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_candidate_record(
    region_id: str,
    page_number: int,
    source: str,
    roi_name: str | None,
    labels: list[str],
    score: float | None,
    bbox_ratio: list[float],
    config: dict[str, Any],
    source_box_ids: list[str | None],
    priority: str | None = None,
    fallback_index: int | None = None,
) -> dict[str, Any]:
    margin = _margin_for_labels(labels, config)
    bbox_ratio = clamp_bbox_ratio(bbox_ratio)
    expanded = expand_bbox_ratio(bbox_ratio, margin)
    width = bbox_ratio[2] - bbox_ratio[0]
    height = bbox_ratio[3] - bbox_ratio[1]
    record: dict[str, Any] = {
        "region_id": region_id,
        "page": page_number,
        "source": source,
        "roi_name": roi_name,
        "labels": list(labels),
        "score": (round(float(score), 6) if score is not None else None),
        "bbox_ratio": bbox_ratio,
        "expanded_bbox_ratio": expanded,
        "expand_margin_ratio": margin,
        "width_ratio": round(width, 6),
        "height_ratio": round(height, 6),
        "area_ratio": round(bbox_area(bbox_ratio), 6),
        "source_box_ids": [bid for bid in source_box_ids if bid],
        "priority": priority or ("fallback" if source == "roi_fallback" else "candidate"),
    }
    if fallback_index is not None:
        record["fallback_index"] = fallback_index
    return record


def _margin_for_labels(labels: list[str], config: dict[str, Any]) -> float:
    margin_cfg = (config or {}).get("margin", {}) or {}
    default = float(margin_cfg.get("default", 0.03))
    if "roi_fallback" in labels:
        return float(margin_cfg.get("roi_fallback", default))
    for label in labels:
        if label in margin_cfg:
            return float(margin_cfg[label])
    return default


def _size_filter_reason(bbox_ratio: Sequence[float], config: dict[str, Any]) -> str | None:
    size_cfg = (config or {}).get("size_filter", {}) or {}
    x1, y1, x2, y2 = clamp_bbox_ratio(bbox_ratio)
    width = x2 - x1
    height = y2 - y1
    if width < float(size_cfg.get("min_width_ratio", 0.02)):
        return "too_small_width"
    if height < float(size_cfg.get("min_height_ratio", 0.02)):
        return "too_small_height"
    if bbox_area([x1, y1, x2, y2]) > float(size_cfg.get("max_area_ratio", 0.92)):
        return "too_large_area"
    return None


def _invalid_region_match(
    bbox_ratio: Sequence[float], invalid_regions: dict[str, Any]
) -> tuple[str | None, str | None]:
    for name, item in invalid_regions.items():
        invalid_bbox = item.get("bbox")
        if not invalid_bbox:
            continue
        # If the candidate sits >=80% inside an invalid region, treat as drop.
        overlap = overlap_over_smaller(bbox_ratio, invalid_bbox)
        if overlap >= 0.8 and bbox_area(bbox_ratio) <= bbox_area(invalid_bbox) * 1.2:
            return item.get("reason", name), name
    return None, None


def _same_label_family(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_labels = set(left.get("labels") or [])
    right_labels = set(right.get("labels") or [])
    if not left_labels or not right_labels:
        return False
    return bool(left_labels & right_labels)


def _merge_pair(
    left: dict[str, Any],
    right: dict[str, Any],
    candidate_cfg: dict[str, Any],
) -> dict[str, Any]:
    bbox_ratio = union_bboxes([left["bbox_ratio"], right["bbox_ratio"]])
    labels: list[str] = []
    for item in (left, right):
        for label in item.get("labels", []):
            if label not in labels:
                labels.append(label)
    margin = _margin_for_labels(labels, candidate_cfg)
    expanded = expand_bbox_ratio(bbox_ratio, margin)
    scores = [item.get("score") for item in (left, right) if item.get("score") is not None]
    contributing = []
    for item in (left, right):
        contributing.append(item.get("region_id"))
        for src in item.get("contributing_regions") or []:
            if src not in contributing:
                contributing.append(src)
    source_ids: list[str] = []
    for item in (left, right):
        for sid in item.get("source_box_ids") or []:
            if sid and sid not in source_ids:
                source_ids.append(sid)
    return {
        "region_id": f"merged_{left.get('region_id')}__{right.get('region_id')}",
        "page": left.get("page", right.get("page", 1)),
        "source": "merged",
        "roi_name": left.get("roi_name") if left.get("roi_name") == right.get("roi_name") else None,
        "labels": labels,
        "score": round(max(scores), 6) if scores else None,
        "bbox_ratio": bbox_ratio,
        "expanded_bbox_ratio": expanded,
        "expand_margin_ratio": margin,
        "width_ratio": round(bbox_ratio[2] - bbox_ratio[0], 6),
        "height_ratio": round(bbox_ratio[3] - bbox_ratio[1], 6),
        "area_ratio": round(bbox_area(bbox_ratio), 6),
        "contributing_regions": contributing,
        "source_box_ids": source_ids,
        "priority": "candidate",
    }


def _find_roi_bbox(rois: list[dict[str, Any]], name: str) -> list[float] | None:
    for roi in rois:
        if roi.get("name") == name:
            return roi.get("bbox_ratio")
    return None
