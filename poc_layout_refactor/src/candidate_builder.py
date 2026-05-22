from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence

from .utils import (
    bbox_area,
    bbox_center,
    bbox_iou,
    clamp_bbox_ratio,
    expand_bbox_ratio,
    horizontal_overlap_ratio,
    intersection_area,
    is_right_side_bbox,
    normalize_label,
    overlap_over_smaller,
    union_bboxes,
    vertical_gap_ratio,
)

RIGHT_TABLE_ZONES = {
    "right_top_table",
    "right_middle_table",
    "right_bottom_material_table",
    "right_bottom_nozzle_table",
}
TEXT_LABELS = {"text", "aside_text"}
TABLE_ZONE_LABELS = {"table", "image", "figure_title"}
ZONE_OUTPUT_ORDER = [
    "right_top_table",
    "right_middle_requirement_text",
    "right_middle_table",
    "right_bottom_material_table",
    "right_bottom_nozzle_table",
    "title_block",
    "bottom_bom_table",
]
# The title block is checked before lower-right table zones so its boxes stay
# independent even when lower-right detections overlap it.
ZONE_ASSIGNMENT_ORDER = [
    "title_block",
    "right_top_table",
    "right_middle_requirement_text",
    "right_middle_table",
    "right_bottom_material_table",
    "right_bottom_nozzle_table",
    "bottom_bom_table",
]


def build_raw_candidates(
    full_layout: dict[str, Any],
    roi_layouts: list[dict[str, Any]],
    rois: list[dict[str, Any]],
    config: dict[str, Any],
    page_number: int = 1,
) -> list[dict[str, Any]]:
    """Convert kept layout boxes into filtered, zone-assigned raw candidates."""
    keep_labels = {normalize_label(label) for label in config.get("keep_labels", [])}
    threshold = float(config.get("layout_threshold", 0.2))
    zone_specs = _build_zone_specs(rois)
    right_column = _find_roi_bbox(rois, "right_column")
    candidates: list[dict[str, Any]] = []
    counters: defaultdict[str, int] = defaultdict(int)

    layouts = [(full_layout, "layout_full", None)]
    layouts.extend((layout, "layout_roi", layout.get("roi_name")) for layout in roi_layouts)

    for layout, source, roi_name in layouts:
        for box in layout.get("boxes", []):
            candidate = _layout_box_to_candidate(
                box=box,
                source=source,
                roi_name=roi_name,
                keep_labels=keep_labels,
                threshold=threshold,
                right_column=right_column,
                zone_specs=zone_specs,
                config=config,
                page_number=page_number,
                counters=counters,
            )
            if candidate:
                candidates.append(candidate)
    return candidates


def merge_candidate_regions(
    raw_candidates: list[dict[str, Any]],
    config: dict[str, Any],
    rois: list[dict[str, Any]] | None = None,
    page_number: int = 1,
) -> list[dict[str, Any]]:
    """Build a compact final candidate set by merging only within business zones."""
    zone_specs = _build_zone_specs(rois or [])
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in raw_candidates:
        zone_name = item.get("zone")
        if zone_name in zone_specs and _passes_candidate_filters(item["bbox_ratio"], config):
            grouped[zone_name].append(dict(item))

    final_candidates: list[dict[str, Any]] = []
    for zone_name in ZONE_OUTPUT_ORDER:
        zone = zone_specs[zone_name]
        zone_candidates = _process_zone(grouped.get(zone_name, []), zone, config)
        if not zone_candidates and zone.get("fallback", False):
            zone_candidates = [_build_zone_fallback(zone, config, page_number)]
        final_candidates.extend(zone_candidates[: int(zone["limit"])])

    final_candidates = _dedupe_candidates(
        final_candidates,
        float(config.get("candidate_final_iou_threshold", 0.5)),
        zone_specs,
    )
    final_candidates = [
        candidate
        for candidate in final_candidates
        if _passes_candidate_filters(candidate["bbox_ratio"], config)
    ]
    final_candidates = _cap_final_candidates(final_candidates, zone_specs, config)
    final_candidates.sort(key=lambda item: _output_sort_key(item, zone_specs))

    for index, item in enumerate(final_candidates, start=1):
        item["source_region_id"] = item.get("region_id")
        item["region_id"] = f"page_{item.get('page', page_number)}_candidate_{index:03d}"
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


def _layout_box_to_candidate(
    box: dict[str, Any],
    source: str,
    roi_name: str | None,
    keep_labels: set[str],
    threshold: float,
    right_column: list[float] | None,
    zone_specs: dict[str, dict[str, Any]],
    config: dict[str, Any],
    page_number: int,
    counters: defaultdict[str, int],
) -> dict[str, Any] | None:
    label = normalize_label(box.get("label"))
    score = float(box.get("score", 0.0))
    bbox_ratio = clamp_bbox_ratio(box["bbox_ratio"])
    if score < threshold or label == "number":
        return None
    if label not in keep_labels:
        keep_right_image = (
            label == "image"
            and config.get("keep_image_in_right_column", True)
            and is_right_side_bbox(bbox_ratio, right_column)
        )
        if not keep_right_image:
            return None
    if not _passes_candidate_filters(bbox_ratio, config):
        return None

    zone_name, zone_match = _assign_zone(label, bbox_ratio, zone_specs, config)
    if zone_name is None:
        return None

    counters[zone_name] += 1
    labels = [label]
    business_rank = _business_rank(labels, zone_name, bbox_ratio, source, right_column)
    return {
        "region_id": f"page_{page_number}_{zone_name}_raw_{counters[zone_name]:03d}",
        "page": page_number,
        "source": source,
        "roi_name": roi_name,
        "zone": zone_name,
        "labels": labels,
        "score": round(score, 6),
        "business_rank": business_rank,
        "priority": _priority_from_rank(business_rank),
        "bbox_ratio": bbox_ratio,
        "expanded_bbox_ratio": expand_bbox_ratio(bbox_ratio, _margin_for_labels(labels, config)),
        "width_ratio": round(bbox_ratio[2] - bbox_ratio[0], 6),
        "height_ratio": round(bbox_ratio[3] - bbox_ratio[1], 6),
        "area_ratio": round(bbox_area(bbox_ratio), 6),
        "zone_match_ratio": round(zone_match, 6),
        "model_box_id": box.get("box_id"),
    }


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
        if any(bbox_iou(region["bbox_ratio"], existing["bbox_ratio"]) >= iou_threshold for existing in kept):
            continue
        kept.append(dict(region))
    return kept


def _process_zone(
    candidates: list[dict[str, Any]],
    zone: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    candidates = _dedupe_candidates_by_containment(candidates, zone)
    candidates = _dedupe_candidates(
        candidates,
        float(config.get("candidate_zone_iou_threshold", 0.5)),
        {zone["name"]: zone},
    )
    candidates = _merge_zone_neighbors(candidates, zone, config)
    candidates = _dedupe_candidates_by_containment(candidates, zone)
    candidates = _dedupe_candidates(
        candidates,
        float(config.get("candidate_zone_iou_threshold", 0.5)),
        {zone["name"]: zone},
    )
    candidates = [
        item
        for item in candidates
        if _passes_candidate_filters(item["bbox_ratio"], config)
        and _zone_match_ratio(item["bbox_ratio"], zone) >= float(config.get("candidate_zone_min_fit_ratio", 0.8))
    ]
    candidates.sort(key=lambda item: _preference_key(item, zone))
    return candidates


def _merge_zone_neighbors(
    candidates: list[dict[str, Any]],
    zone: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    pending = [dict(candidate) for candidate in candidates]
    changed = True
    while changed:
        changed = False
        pending.sort(key=lambda item: (item["bbox_ratio"][1], item["bbox_ratio"][0]))
        for left_index, left in enumerate(pending):
            for right_index in range(left_index + 1, len(pending)):
                right = pending[right_index]
                if not _should_merge_in_zone(left, right, config):
                    continue
                merged = _merge_zone_pair(left, right, zone, config)
                if merged is None:
                    continue
                pending = [
                    item
                    for index, item in enumerate(pending)
                    if index not in {left_index, right_index}
                ]
                pending.append(merged)
                changed = True
                break
            if changed:
                break
    return pending


def _should_merge_in_zone(
    left: dict[str, Any],
    right: dict[str, Any],
    config: dict[str, Any],
) -> bool:
    left_family = _candidate_family(left)
    right_family = _candidate_family(right)
    if left_family != right_family:
        return False
    if bbox_iou(left["bbox_ratio"], right["bbox_ratio"]) > 0:
        return True
    return (
        horizontal_overlap_ratio(left["bbox_ratio"], right["bbox_ratio"])
        >= float(config.get("candidate_merge_horizontal_overlap", 0.45))
        and vertical_gap_ratio(left["bbox_ratio"], right["bbox_ratio"])
        <= float(config.get("candidate_merge_vertical_gap_ratio", 0.035))
    )


def _merge_zone_pair(
    left: dict[str, Any],
    right: dict[str, Any],
    zone: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    bbox_ratio = union_bboxes([left["bbox_ratio"], right["bbox_ratio"]])
    if not _passes_candidate_filters(bbox_ratio, config):
        return None
    zone_match = _zone_match_ratio(bbox_ratio, zone)
    if zone_match < float(config.get("candidate_zone_min_fit_ratio", 0.8)):
        return None

    labels = _merge_labels([left, right])
    rank = min(int(left.get("business_rank", 7)), int(right.get("business_rank", 7)))
    roi_names = sorted({item.get("roi_name") for item in (left, right) if item.get("roi_name")})
    return {
        "region_id": left["region_id"],
        "page": left.get("page", right.get("page", 1)),
        "source": "merged_layout",
        "roi_name": roi_names[0] if len(roi_names) == 1 else None,
        "roi_names": roi_names,
        "zone": zone["name"],
        "labels": labels,
        "score": round(max(float(left.get("score", 0.0)), float(right.get("score", 0.0))), 6),
        "business_rank": rank,
        "priority": _priority_from_rank(rank),
        "bbox_ratio": bbox_ratio,
        "expanded_bbox_ratio": expand_bbox_ratio(bbox_ratio, _margin_for_labels(labels, config)),
        "width_ratio": round(bbox_ratio[2] - bbox_ratio[0], 6),
        "height_ratio": round(bbox_ratio[3] - bbox_ratio[1], 6),
        "area_ratio": round(bbox_area(bbox_ratio), 6),
        "zone_match_ratio": round(zone_match, 6),
        "contributing_regions": _contributing_regions(left) + _contributing_regions(right),
    }


def _dedupe_candidates_by_containment(
    candidates: list[dict[str, Any]],
    zone: dict[str, Any],
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: _preference_key(item, zone)):
        if any(overlap_over_smaller(candidate["bbox_ratio"], existing["bbox_ratio"]) >= 0.9 for existing in kept):
            continue
        kept.append(dict(candidate))
    return kept


def _dedupe_candidates(
    candidates: list[dict[str, Any]],
    iou_threshold: float,
    zone_specs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: _global_preference_key(item, zone_specs)):
        if any(bbox_iou(candidate["bbox_ratio"], existing["bbox_ratio"]) > iou_threshold for existing in kept):
            continue
        kept.append(dict(candidate))
    return kept


def _cap_final_candidates(
    candidates: list[dict[str, Any]],
    zone_specs: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    max_count = int(config.get("candidate_max_count", 8))
    if len(candidates) <= max_count:
        return candidates
    kept = sorted(candidates, key=lambda item: _global_preference_key(item, zone_specs))[:max_count]
    return kept


def _build_zone_fallback(
    zone: dict[str, Any],
    config: dict[str, Any],
    page_number: int,
) -> dict[str, Any]:
    bbox_ratio = clamp_bbox_ratio(zone["bbox_ratio"])
    rank = 7
    return {
        "region_id": f"page_{page_number}_{zone['name']}_fallback",
        "page": page_number,
        "source": "fallback_roi",
        "roi_name": zone["fallback_roi_name"],
        "zone": zone["name"],
        "labels": ["fallback_roi"],
        "score": 0.0,
        "business_rank": rank,
        "priority": _priority_from_rank(rank),
        "bbox_ratio": bbox_ratio,
        "expanded_bbox_ratio": expand_bbox_ratio(bbox_ratio, float(config.get("margin_roi", 0.05))),
        "width_ratio": round(bbox_ratio[2] - bbox_ratio[0], 6),
        "height_ratio": round(bbox_ratio[3] - bbox_ratio[1], 6),
        "area_ratio": round(bbox_area(bbox_ratio), 6),
        "zone_match_ratio": 1.0,
        "fallback_reason": "zone_without_valid_layout_box",
    }


def _assign_zone(
    label: str,
    bbox_ratio: list[float],
    zone_specs: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> tuple[str | None, float]:
    center_x, center_y = bbox_center(bbox_ratio)
    min_fit = float(config.get("candidate_zone_min_fit_ratio", 0.8))
    for zone_name in ZONE_ASSIGNMENT_ORDER:
        zone = zone_specs[zone_name]
        if label not in zone["labels"]:
            continue
        zx1, zy1, zx2, zy2 = zone["bbox_ratio"]
        if not (zx1 <= center_x <= zx2 and zy1 <= center_y <= zy2):
            continue
        match = _zone_match_ratio(bbox_ratio, zone)
        if match >= min_fit:
            return zone_name, match
    return None, 0.0


def _passes_candidate_filters(bbox_ratio: Sequence[float], config: dict[str, Any]) -> bool:
    x1, y1, x2, y2 = clamp_bbox_ratio(bbox_ratio)
    width = x2 - x1
    height = y2 - y1
    if bbox_area([x1, y1, x2, y2]) > float(config.get("candidate_max_area_ratio", 0.35)):
        return False
    if height < float(config.get("candidate_min_height_ratio", 0.03)):
        return False
    if width < float(config.get("candidate_min_width_ratio", 0.03)):
        return False
    if y1 <= 0.05 and height < 0.05:
        return False
    if x1 <= 0.08 and width < 0.08:
        return False
    return True


def _business_rank(
    labels: list[str],
    zone_name: str,
    bbox_ratio: list[float],
    source: str,
    right_column: list[float] | None,
) -> int:
    if source == "fallback_roi":
        return 7
    label_set = set(labels)
    if zone_name == "title_block":
        return 4
    if "table" in label_set and zone_name in RIGHT_TABLE_ZONES:
        return 1
    if label_set & TEXT_LABELS and is_right_side_bbox(bbox_ratio, right_column):
        return 2
    if "table" in label_set and zone_name == "bottom_bom_table":
        return 3
    if "figure_title" in label_set:
        return 5
    if "image" in label_set and is_right_side_bbox(bbox_ratio, right_column):
        return 6
    return 6


def _priority_from_rank(rank: int) -> str:
    if rank <= 3:
        return "high"
    if rank <= 5:
        return "medium"
    return "low"


def _build_zone_specs(rois: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    right_column = _find_roi_bbox(rois, "right_column") or [0.60, 0.02, 0.98, 0.95]
    right_x1 = float(right_column[0])
    right_x2 = min(0.995, max(0.98, float(right_column[2])))
    right_table_x1 = min(0.80, right_x1 + 0.15)
    material_x1 = max(0.48, right_x1 - 0.08)

    specs = {
        "right_top_table": {
            "bbox_ratio": [right_table_x1, 0.02, right_x2, 0.38],
            "labels": set(TABLE_ZONE_LABELS),
            "limit": 1,
            "fallback_roi_name": "right_top",
        },
        "right_middle_requirement_text": {
            "bbox_ratio": [right_x1, 0.28, right_table_x1, 0.52],
            "labels": {"text", "aside_text", "figure_title"},
            "limit": 2,
            "fallback_roi_name": "right_middle",
        },
        "right_middle_table": {
            "bbox_ratio": [right_table_x1, 0.28, right_x2, 0.69],
            "labels": set(TABLE_ZONE_LABELS),
            "limit": 1,
            "fallback_roi_name": "right_middle",
        },
        "right_bottom_material_table": {
            "bbox_ratio": [material_x1, 0.50, right_table_x1, 0.995],
            "labels": set(TABLE_ZONE_LABELS),
            "limit": 1,
            "fallback_roi_name": "right_bottom",
        },
        "right_bottom_nozzle_table": {
            "bbox_ratio": [right_table_x1, 0.50, right_x2, 0.89],
            "labels": set(TABLE_ZONE_LABELS),
            "limit": 1,
            "fallback_roi_name": "right_bottom",
        },
        "title_block": {
            "bbox_ratio": [right_table_x1, 0.87, right_x2, 0.995],
            "labels": {"table", "text", "aside_text", "figure_title"},
            "limit": 1,
            "fallback_roi_name": "right_bottom",
        },
        "bottom_bom_table": {
            "bbox_ratio": [max(0.20, material_x1 - 0.14), 0.68, right_table_x1, 0.995],
            "labels": set(TABLE_ZONE_LABELS),
            "limit": 1,
            "fallback_roi_name": "bottom_band",
        },
    }
    for name, spec in specs.items():
        spec["name"] = name
        spec["bbox_ratio"] = clamp_bbox_ratio(spec["bbox_ratio"])
        spec["fallback"] = name != "bottom_bom_table"
    return specs


def _zone_match_ratio(bbox_ratio: list[float], zone: dict[str, Any]) -> float:
    area = bbox_area(bbox_ratio)
    return intersection_area(bbox_ratio, zone["bbox_ratio"]) / area if area > 0 else 0.0


def _preference_key(item: dict[str, Any], zone: dict[str, Any]) -> tuple[Any, ...]:
    return (
        int(item.get("business_rank", 7)),
        -float(item.get("zone_match_ratio", _zone_match_ratio(item["bbox_ratio"], zone))),
        -bbox_area(item["bbox_ratio"]),
        -float(item.get("score", 0.0)),
        _source_rank(item),
    )


def _global_preference_key(
    item: dict[str, Any],
    zone_specs: dict[str, dict[str, Any]],
) -> tuple[Any, ...]:
    zone = zone_specs.get(item.get("zone"), {"name": "", "bbox_ratio": item["bbox_ratio"]})
    return _preference_key(item, zone) + (_zone_order(item.get("zone")),)


def _output_sort_key(item: dict[str, Any], zone_specs: dict[str, dict[str, Any]]) -> tuple[Any, ...]:
    return (
        _zone_order(item.get("zone")),
        int(item.get("business_rank", 7)),
        item["bbox_ratio"][1],
        item["bbox_ratio"][0],
        _global_preference_key(item, zone_specs),
    )


def _source_rank(item: dict[str, Any]) -> int:
    if item.get("source") == "fallback_roi":
        return 3
    if item.get("source") == "merged_layout":
        return 1
    if item.get("source") == "layout_roi":
        return 0
    return 2


def _zone_order(zone_name: str | None) -> int:
    try:
        return ZONE_OUTPUT_ORDER.index(str(zone_name))
    except ValueError:
        return len(ZONE_OUTPUT_ORDER)


def _candidate_family(candidate: dict[str, Any]) -> str:
    labels = set(candidate.get("labels", []))
    if "table" in labels:
        return "table"
    if labels & TEXT_LABELS or "figure_title" in labels:
        return "text"
    if "image" in labels:
        return "image"
    return "fallback"


def _merge_labels(candidates: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for candidate in candidates:
        for label in candidate.get("labels", []):
            if label not in labels:
                labels.append(label)
    return labels


def _contributing_regions(candidate: dict[str, Any]) -> list[str]:
    regions = candidate.get("contributing_regions")
    return list(regions) if regions else [candidate["region_id"]]


def _margin_for_labels(labels: list[str], config: dict[str, Any]) -> float:
    if "fallback_roi" in labels or "image" in labels:
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
