from __future__ import annotations

import json
import re
from numbers import Real
from pathlib import Path
from typing import Any, Iterable, Sequence

BBox = list[float]


def ensure_dir(path: str | Path) -> Path:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)
    return output


def load_config(path: str | Path) -> dict[str, Any]:
    try:
        import yaml
    except Exception as exc:  # pragma: no cover - depends on local install
        raise RuntimeError(
            "PyYAML is required to read config.yaml. Install dependencies with "
            "`pip install -r requirements.txt` inside poc_layout_refactor."
        ) from exc

    with Path(path).open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return data


def write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def safe_stem(path: str | Path) -> str:
    stem = Path(path).stem.strip()
    stem = re.sub(r"[^\w\-.]+", "_", stem, flags=re.UNICODE)
    return stem or "pdf"


def round_float(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def round_bbox(bbox: Sequence[float], digits: int = 6) -> BBox:
    return [round_float(v, digits) for v in bbox]


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def clamp_bbox_ratio(bbox: Sequence[float]) -> BBox:
    x1, y1, x2, y2 = [clamp(v) for v in bbox]
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    return round_bbox([left, top, right, bottom])


def bbox_pixels_to_ratio(
    bbox_px: Sequence[float], image_width: int, image_height: int
) -> BBox:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image_width and image_height must be positive")
    x1, y1, x2, y2 = bbox_px
    return clamp_bbox_ratio(
        [x1 / image_width, y1 / image_height, x2 / image_width, y2 / image_height]
    )


def bbox_ratio_to_pixels(
    bbox_ratio: Sequence[float], image_width: int, image_height: int
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = clamp_bbox_ratio(bbox_ratio)
    left = int(max(0, min(image_width, round(x1 * image_width))))
    top = int(max(0, min(image_height, round(y1 * image_height))))
    right = int(max(0, min(image_width, round(x2 * image_width))))
    bottom = int(max(0, min(image_height, round(y2 * image_height))))
    left = min(left, max(0, image_width - 1))
    top = min(top, max(0, image_height - 1))
    if right <= left:
        right = min(image_width, left + 1)
    if bottom <= top:
        bottom = min(image_height, top + 1)
    return left, top, right, bottom


def map_local_ratio_to_page_ratio(
    local_bbox_ratio: Sequence[float], container_bbox_ratio: Sequence[float]
) -> BBox:
    cx1, cy1, cx2, cy2 = clamp_bbox_ratio(container_bbox_ratio)
    lx1, ly1, lx2, ly2 = clamp_bbox_ratio(local_bbox_ratio)
    width = cx2 - cx1
    height = cy2 - cy1
    return clamp_bbox_ratio(
        [
            cx1 + lx1 * width,
            cy1 + ly1 * height,
            cx1 + lx2 * width,
            cy1 + ly2 * height,
        ]
    )


def expand_bbox_ratio(bbox: Sequence[float], margin_ratio: float) -> BBox:
    x1, y1, x2, y2 = clamp_bbox_ratio(bbox)
    width = x2 - x1
    height = y2 - y1
    margin_x = width * margin_ratio
    margin_y = height * margin_ratio
    return clamp_bbox_ratio([x1 - margin_x, y1 - margin_y, x2 + margin_x, y2 + margin_y])


def bbox_area(bbox: Sequence[float]) -> float:
    x1, y1, x2, y2 = clamp_bbox_ratio(bbox)
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def intersection_bbox(a: Sequence[float], b: Sequence[float]) -> BBox | None:
    ax1, ay1, ax2, ay2 = clamp_bbox_ratio(a)
    bx1, by1, bx2, by2 = clamp_bbox_ratio(b)
    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)
    if x2 <= x1 or y2 <= y1:
        return None
    return round_bbox([x1, y1, x2, y2])


def intersection_area(a: Sequence[float], b: Sequence[float]) -> float:
    overlap = intersection_bbox(a, b)
    return bbox_area(overlap) if overlap else 0.0


def bbox_iou(a: Sequence[float], b: Sequence[float]) -> float:
    inter = intersection_area(a, b)
    if inter <= 0:
        return 0.0
    union = bbox_area(a) + bbox_area(b) - inter
    return inter / union if union > 0 else 0.0


def overlap_over_smaller(a: Sequence[float], b: Sequence[float]) -> float:
    inter = intersection_area(a, b)
    smaller = min(bbox_area(a), bbox_area(b))
    return inter / smaller if smaller > 0 else 0.0


def union_bboxes(boxes: Iterable[Sequence[float]]) -> BBox:
    normalized = [clamp_bbox_ratio(box) for box in boxes]
    if not normalized:
        raise ValueError("cannot build a union bbox from an empty sequence")
    return clamp_bbox_ratio(
        [
            min(box[0] for box in normalized),
            min(box[1] for box in normalized),
            max(box[2] for box in normalized),
            max(box[3] for box in normalized),
        ]
    )


def horizontal_overlap_ratio(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, _, ax2, _ = clamp_bbox_ratio(a)
    bx1, _, bx2, _ = clamp_bbox_ratio(b)
    overlap = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    smaller = min(ax2 - ax1, bx2 - bx1)
    return overlap / smaller if smaller > 0 else 0.0


def vertical_overlap_ratio(a: Sequence[float], b: Sequence[float]) -> float:
    _, ay1, _, ay2 = clamp_bbox_ratio(a)
    _, by1, _, by2 = clamp_bbox_ratio(b)
    overlap = max(0.0, min(ay2, by2) - max(ay1, by1))
    smaller = min(ay2 - ay1, by2 - by1)
    return overlap / smaller if smaller > 0 else 0.0


def vertical_gap_ratio(a: Sequence[float], b: Sequence[float]) -> float:
    _, ay1, _, ay2 = clamp_bbox_ratio(a)
    _, by1, _, by2 = clamp_bbox_ratio(b)
    if ay2 < by1:
        return by1 - ay2
    if by2 < ay1:
        return ay1 - by2
    return 0.0


def horizontal_gap_ratio(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, _, ax2, _ = clamp_bbox_ratio(a)
    bx1, _, bx2, _ = clamp_bbox_ratio(b)
    if ax2 < bx1:
        return bx1 - ax2
    if bx2 < ax1:
        return ax1 - bx2
    return 0.0


def bbox_center(bbox: Sequence[float]) -> tuple[float, float]:
    x1, y1, x2, y2 = clamp_bbox_ratio(bbox)
    return (x1 + x2) / 2, (y1 + y2) / 2


def normalize_label(label: Any) -> str:
    value = str(label or "").strip().lower()
    value = re.sub(r"[\s\-/]+", "_", value)
    value = re.sub(r"[^a-z0-9_]+", "", value)
    aliases = {
        "sidebar_text": "aside_text",
        "side_text": "aside_text",
        "aside": "aside_text",
        "figure_caption": "figure_title",
        "fig_title": "figure_title",
        "picture_title": "figure_title",
        "page_number": "number",
        "formula_number": "number",
    }
    return aliases.get(value, value)


def is_right_side_bbox(
    bbox: Sequence[float], right_column_bbox: Sequence[float] | None = None
) -> bool:
    if right_column_bbox and overlap_over_smaller(bbox, right_column_bbox) >= 0.2:
        return True
    center_x, _ = bbox_center(bbox)
    return center_x >= 0.58


def priority_rank(priority: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(priority, 1)


def build_summary(
    pdf_path: str | Path,
    output_dir: str | Path,
    page_info: dict[str, Any],
    full_layout: dict[str, Any],
    roi_layouts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_layout_count = len(full_layout.get("boxes", [])) + sum(
        len(layout.get("boxes", [])) for layout in roi_layouts
    )
    return {
        "pdf_file": str(pdf_path),
        "pdf_name": Path(pdf_path).name,
        "output_dir": str(output_dir),
        "page": page_info.get("page", 1),
        "page_orientation": page_info.get("orientation"),
        "page_size": {
            "width_pt": page_info.get("page_width_pt"),
            "height_pt": page_info.get("page_height_pt"),
            "low_width_px": page_info.get("low_width_px"),
            "low_height_px": page_info.get("low_height_px"),
            "high_width_px": page_info.get("high_width_px"),
            "high_height_px": page_info.get("high_height_px"),
        },
        "raw_layout_box_count": raw_layout_count,
        "merged_candidate_count": len(candidates),
        "candidates": [
            {
                "region_id": item["region_id"],
                "zone": item.get("zone"),
                "labels": item.get("labels", []),
                "score": item.get("score"),
                "priority": item.get("priority"),
                "bbox_ratio": item.get("bbox_ratio"),
                "expanded_bbox_ratio": item.get("expanded_bbox_ratio"),
                "image_path": item.get("crop_image_path"),
            }
            for item in candidates
        ],
    }


def write_debug_report(
    path: str | Path,
    pdf_path: str | Path,
    output_dir: str | Path,
    page_info: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> None:
    lines = [
        "# Layout Detection Debug Report",
        "",
        f"- Input PDF: `{pdf_path}`",
        f"- Output path: `{output_dir}`",
        f"- Page: {page_info.get('page', 1)}",
        f"- Orientation: {page_info.get('orientation')}",
        f"- Low DPI image: `page_1_lowdpi.png`",
        f"- High DPI image: `page_1_highdpi.png`",
        f"- Full page layout JSON: `full_page_layout_raw.json`",
        f"- Full page layout overlay: `full_page_layout_overlay.png`",
        f"- Precise table JSON: `precise_table_regions.json`",
        f"- Candidate JSON: `candidate_regions_merged.json`",
        f"- Candidate overlay: `candidate_regions_overlay.png`",
        f"- Candidate crop directory: `candidates/`",
        "",
        "## Candidate Regions",
        "",
        "| region_id | zone | priority | labels | score | bbox_ratio | crop |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for item in candidates:
        labels = ", ".join(item.get("labels", []))
        score = item.get("score")
        score_text = f"{score:.4f}" if isinstance(score, Real) else ""
        crop = item.get("crop_image_path") or ""
        crop_name = Path(crop).name if crop else ""
        lines.append(
            "| {region_id} | {zone} | {priority} | {labels} | {score} | `{bbox}` | `{crop}` |".format(
                region_id=item.get("region_id"),
                zone=item.get("zone", ""),
                priority=item.get("priority"),
                labels=labels,
                score=score_text,
                bbox=item.get("expanded_bbox_ratio") or item.get("bbox_ratio"),
                crop=crop_name,
            )
        )
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
