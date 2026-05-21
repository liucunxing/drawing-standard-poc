from __future__ import annotations

from collections import defaultdict
from typing import Any

from .utils import (
    bbox_area,
    bbox_center,
    bbox_iou,
    clamp_bbox_ratio,
    expand_bbox_ratio,
    horizontal_gap_ratio,
    horizontal_overlap_ratio,
    is_right_side_bbox,
    normalize_label,
    overlap_over_smaller,
    priority_rank,
    round_bbox,
    union_bboxes,
    vertical_gap_ratio,
    vertical_overlap_ratio,
)


def build_raw_candidates(
    full_layout: dict[str, Any],
    roi_layouts: list[dict[str, Any]],
    rois: list[dict[str, Any]],
    config: dict[str, Any],
    page_number: int = 1,
) -> list[dict[str, Any]]:
    keep_labels = {normalize_label(label) for label in config.get("keep_labels", [])}
    threshold = float(config.get("layout_threshold", 0.2))
    right_column = _find_roi_bbox(rois, "right_column")
    candidates: list[dict[str, Any]] = []
    counters: defaultdict[str, int] = defaultdict(int)

    for box in full_layout.get("boxes", []):
        candidate = _layout_box_to_candidate(
            box=box,
            source="layout_full",
            roi_name=None,
            keep_labels=keep_labels,
            threshold=threshold,
            right_column=right_column,
            config=config,
            page_number=page_number,
            counters=counters,
        )
        if candidate:
            candidates.append(candidate)

    for layout in roi_layouts:
        roi_name = layout.get("roi_name")
        for box in layout.get("boxes", []):
            candidate = _layout_box_to_candidate(
                box=box,
                source="layout_roi",
                roi_name=roi_name,
                keep_labels=keep_labels,
                threshold=threshold,
                right_column=right_column,
                config=config,
                page_number=page_number,
                counters=counters,
            )
            if candidate:
                candidates.append(candidate)

    candidates.extend(_fixed_roi_candidates(rois, config, page_number))
    return candidates


def merge_candidate_regions(
    raw_candidates: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    layout_candidates = [
        item for item in raw_candidates if item.get("source") != "fixed_roi"
    ]
    fixed_roi_candidates = [
        item for item in raw_candidates if item.get("source") == "fixed_roi"
    ]
    merged_layout = _merge_layout_candidates(layout_candidates, config)

    final_candidates = _dedupe_fixed_rois(merged_layout, fixed_roi_candidates)
    final_candidates = sorted(
        final_candidates,
        key=lambda item: (
            -priority_rank(item.get("priority", "medium")),
            item["bbox_ratio"][1],
            item["bbox_ratio"][0],
            -bbox_area(item["bbox_ratio"]),
        ),
    )

    for index, item in enumerate(final_candidates, start=1):
        previous_id = item.get("region_id")
        item["source_region_id"] = previous_id
        item["region_id"] = f"page_{item.get('page', 1)}_candidate_{index:03d}"
    return final_candidates


def build_precise_table_regions(
    full_layout: dict[str, Any],
    roi_layouts: list[dict[str, Any]],
    config: dict[str, Any],
    page_number: int = 1,
) -> list[dict[str, Any]]:
    threshold = float(config.get("precise_table_threshold", 0.5))
    margin = float(config.get("precise_table_margin", 0.02))
    regions: list[dict[str, Any]] = []

    for box in full_layout.get("boxes", []):
        region = _layout_box_to_precise_table(
            box=box,
            source="layout_full",
            roi_name=None,
            threshold=threshold,
            margin=margin,
            page_number=page_number,
        )
        if region:
            regions.append(region)

    for layout in roi_layouts:
        roi_name = layout.get("roi_name")
        for box in layout.get("boxes", []):
            region = _layout_box_to_precise_table(
                box=box,
                source="layout_roi",
                roi_name=roi_name,
                threshold=threshold,
                margin=margin,
                page_number=page_number,
            )
            if region:
                regions.append(region)

    regions = _dedupe_precise_tables(
        regions, float(config.get("precise_table_dedupe_iou_threshold", 0.9))
    )
    regions = sorted(
        regions,
        key=lambda item: (
            item["bbox_ratio"][1],
            item["bbox_ratio"][0],
            -float(item.get("score", 0.0)),
        ),
    )
    for index, item in enumerate(regions, start=1):
        item["region_id"] = f"page_{page_number}_precise_table_{index:03d}"
    return regions


def _layout_box_to_precise_table(
    box: dict[str, Any],
    source: str,
    roi_name: str | None,
    threshold: float,
    margin: float,
    page_number: int,
) -> dict[str, Any] | None:
    label = normalize_label(box.get("label"))
    score = float(box.get("score", 0.0))
    if label != "table" or score < threshold:
        return None
    bbox_ratio = clamp_bbox_ratio(box["bbox_ratio"])
    return {
        "region_id": "",
        "page": page_number,
        "source": source,
        "roi_name": roi_name,
        "labels": ["table"],
        "score": round(score, 6),
        "priority": "high",
        "bbox_ratio": bbox_ratio,
        "expanded_bbox_ratio": expand_bbox_ratio(bbox_ratio, margin),
        "model_box_id": box.get("box_id"),
    }


def _dedupe_precise_tables(
    regions: list[dict[str, Any]], iou_threshold: float
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for region in sorted(
        regions,
        key=lambda item: (-float(item.get("score", 0.0)), bbox_area(item["bbox_ratio"])),
    ):
        duplicate = False
        for existing in kept:
            if bbox_iou(region["bbox_ratio"], existing["bbox_ratio"]) >= iou_threshold:
                duplicate = True
                break
        if not duplicate:
            kept.append(dict(region))
    return kept


def _layout_box_to_candidate(
    box: dict[str, Any],
    source: str,
    roi_name: str | None,
    keep_labels: set[str],
    threshold: float,
    right_column: list[float] | None,
    config: dict[str, Any],
    page_number: int,
    counters: defaultdict[str, int],
) -> dict[str, Any] | None:
    label = normalize_label(box.get("label"))
    score = float(box.get("score", 0.0))
    if score < threshold:
        return None
    if label == "number":
        return None
    if label not in keep_labels:
        if not (
            label == "image"
            and config.get("keep_image_in_right_column", True)
            and is_right_side_bbox(box["bbox_ratio"], right_column)
        ):
            return None

    prefix = roi_name or "full"
    counters[prefix] += 1
    bbox_ratio = clamp_bbox_ratio(box["bbox_ratio"])
    labels = [label]
    priority = _layout_priority(label, bbox_ratio, roi_name, right_column)
    margin = _margin_for_labels(labels, config)
    return {
        "region_id": f"page_{page_number}_{prefix}_{counters[prefix]:03d}",
        "page": page_number,
        "source": source,
        "roi_name": roi_name,
        "labels": labels,
        "score": round(score, 6),
        "priority": priority,
        "bbox_ratio": bbox_ratio,
        "expanded_bbox_ratio": expand_bbox_ratio(bbox_ratio, margin),
        "model_box_id": box.get("box_id"),
    }


def _fixed_roi_candidates(
    rois: list[dict[str, Any]],
    config: dict[str, Any],
    page_number: int,
) -> list[dict[str, Any]]:
    margin = float(config.get("margin_roi", 0.05))
    candidates = []
    high_priority_names = {"right_column", "right_middle", "right_bottom"}
    for roi in rois:
        name = roi["name"]
        bbox_ratio = clamp_bbox_ratio(roi["bbox_ratio"])
        candidates.append(
            {
                "region_id": f"page_{page_number}_fixed_{name}",
                "page": page_number,
                "source": "fixed_roi",
                "roi_name": name,
                "labels": ["fixed_roi"],
                "score": 1.0,
                "priority": "high" if name in high_priority_names else "medium",
                "bbox_ratio": bbox_ratio,
                "expanded_bbox_ratio": expand_bbox_ratio(bbox_ratio, margin),
            }
        )
    return candidates


def _merge_layout_candidates(
    candidates: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    if not candidates:
        return []

    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left_index in range(len(candidates)):
        for right_index in range(left_index + 1, len(candidates)):
            if _should_merge(candidates[left_index], candidates[right_index], config):
                union(left_index, right_index)

    groups: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, candidate in enumerate(candidates):
        groups[find(index)].append(candidate)

    merged = [_merge_one_group(group, config) for group in groups.values()]
    return merged


def _should_merge(
    left: dict[str, Any], right: dict[str, Any], config: dict[str, Any]
) -> bool:
    left_bbox = left["bbox_ratio"]
    right_bbox = right["bbox_ratio"]
    dedupe_iou = float(config.get("dedupe_iou_threshold", 0.75))
    merge_iou = float(config.get("merge_iou_threshold", 0.18))
    if bbox_iou(left_bbox, right_bbox) >= dedupe_iou:
        return True
    if bbox_iou(left_bbox, right_bbox) >= merge_iou:
        return True
    if overlap_over_smaller(left_bbox, right_bbox) >= 0.85:
        return True

    same_roi = left.get("roi_name") and left.get("roi_name") == right.get("roi_name")
    if same_roi and _is_nearby(left_bbox, right_bbox, config):
        return True

    if _both_right_side(left_bbox, right_bbox) and _is_vertical_stack(
        left_bbox, right_bbox, config
    ):
        return True

    if _both_bottom_band(left_bbox, right_bbox) and _is_horizontal_row(
        left_bbox, right_bbox, config
    ):
        return True

    return False


def _is_nearby(
    left_bbox: list[float], right_bbox: list[float], config: dict[str, Any]
) -> bool:
    return (
        horizontal_overlap_ratio(left_bbox, right_bbox) >= 0.25
        and vertical_gap_ratio(left_bbox, right_bbox)
        <= float(config.get("merge_vertical_gap_ratio", 0.035))
    ) or (
        vertical_overlap_ratio(left_bbox, right_bbox) >= 0.25
        and horizontal_gap_ratio(left_bbox, right_bbox)
        <= float(config.get("merge_horizontal_gap_ratio", 0.025))
    )


def _is_vertical_stack(
    left_bbox: list[float], right_bbox: list[float], config: dict[str, Any]
) -> bool:
    return (
        horizontal_overlap_ratio(left_bbox, right_bbox) >= 0.35
        and vertical_gap_ratio(left_bbox, right_bbox)
        <= float(config.get("merge_vertical_gap_ratio", 0.035))
    )


def _is_horizontal_row(
    left_bbox: list[float], right_bbox: list[float], config: dict[str, Any]
) -> bool:
    return (
        vertical_overlap_ratio(left_bbox, right_bbox) >= 0.35
        and horizontal_gap_ratio(left_bbox, right_bbox)
        <= float(config.get("merge_horizontal_gap_ratio", 0.025))
    )


def _merge_one_group(group: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    if len(group) == 1:
        candidate = dict(group[0])
        candidate["contributing_regions"] = [group[0]["region_id"]]
        return candidate

    bbox_ratio = union_bboxes(item["bbox_ratio"] for item in group)
    labels = _merge_labels(group)
    priority = max((item.get("priority", "medium") for item in group), key=priority_rank)
    roi_names = sorted(
        {item.get("roi_name") for item in group if item.get("roi_name") is not None}
    )
    margin = _margin_for_labels(labels, config)
    return {
        "region_id": group[0]["region_id"],
        "page": group[0].get("page", 1),
        "source": "merged_layout",
        "roi_name": roi_names[0] if len(roi_names) == 1 else None,
        "roi_names": roi_names,
        "labels": labels,
        "score": round(max(float(item.get("score", 0.0)) for item in group), 6),
        "priority": priority,
        "bbox_ratio": bbox_ratio,
        "expanded_bbox_ratio": expand_bbox_ratio(bbox_ratio, margin),
        "contributing_regions": [item["region_id"] for item in group],
    }


def _merge_labels(group: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for item in group:
        for label in item.get("labels", []):
            if label not in labels:
                labels.append(label)
    return labels


def _dedupe_fixed_rois(
    merged_layout: list[dict[str, Any]],
    fixed_rois: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    final = [dict(item) for item in merged_layout]
    for roi in fixed_rois:
        required_fallback = roi.get("roi_name") in {
            "right_column",
            "right_middle",
            "right_bottom",
        }
        duplicate = any(
            bbox_iou(roi["bbox_ratio"], item["bbox_ratio"]) > 0.9 for item in final
        )
        if required_fallback or not duplicate:
            final.append(dict(roi))
    return final


def _layout_priority(
    label: str,
    bbox_ratio: list[float],
    roi_name: str | None,
    right_column: list[float] | None,
) -> str:
    if label == "image":
        return "low"
    if roi_name in {"right_column", "right_top", "right_middle", "right_bottom"}:
        return "high"
    if is_right_side_bbox(bbox_ratio, right_column):
        return "high"
    _, center_y = bbox_center(bbox_ratio)
    if center_y >= 0.70:
        return "medium"
    return "medium"


def _margin_for_labels(labels: list[str], config: dict[str, Any]) -> float:
    if "fixed_roi" in labels or "image" in labels:
        return float(config.get("margin_roi", 0.05))
    if "table" in labels:
        return float(config.get("margin_table", 0.05))
    if any(label in labels for label in ("text", "aside_text", "figure_title")):
        return float(config.get("margin_text", 0.08))
    return float(config.get("margin_roi", 0.05))


def _find_roi_bbox(rois: list[dict[str, Any]], name: str) -> list[float] | None:
    for roi in rois:
        if roi.get("name") == name:
            return roi.get("bbox_ratio")
    return None


def _both_right_side(left_bbox: list[float], right_bbox: list[float]) -> bool:
    left_center, _ = bbox_center(left_bbox)
    right_center, _ = bbox_center(right_bbox)
    return left_center >= 0.55 and right_center >= 0.55


def _both_bottom_band(left_bbox: list[float], right_bbox: list[float]) -> bool:
    _, left_center = bbox_center(left_bbox)
    _, right_center = bbox_center(right_bbox)
    return left_center >= 0.68 and right_center >= 0.68
