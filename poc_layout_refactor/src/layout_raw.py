"""Flatten PP-DocLayout raw detections (full page + ROIs) for unfiltered dumping.

The output of this module is `layout_boxes_raw.json`. It deliberately performs
no business filtering, deduplication or merging.
"""

from __future__ import annotations

from typing import Any

from .utils import bbox_ratio_to_pixels, clamp_bbox_ratio, normalize_label, round_bbox


def flatten_layout_boxes_raw(
    full_layout: dict[str, Any],
    roi_layouts: list[dict[str, Any]],
    page_number: int = 1,
) -> list[dict[str, Any]]:
    """Return a flat list of every PP-DocLayout box across full-page + ROIs.

    Each entry contains: raw_id, page, source, roi_name, label, raw_label,
    score, bbox_pixel (in detection image coords), bbox_ratio (page_ratio).
    """
    rows: list[dict[str, Any]] = []
    counter = 0

    def _emit(box: dict[str, Any], source: str, roi_name: str | None) -> None:
        nonlocal counter
        counter += 1
        bbox_ratio = clamp_bbox_ratio(box["bbox_ratio"])
        bbox_pixel = box.get("bbox_px")
        rows.append(
            {
                "raw_id": f"raw_{counter:04d}",
                "page": page_number,
                "source": source,
                "roi_name": roi_name,
                "raw_label": box.get("raw_label") or box.get("label"),
                "label": normalize_label(box.get("label")),
                "score": float(box.get("score", 0.0)),
                "bbox_pixel": round_bbox(bbox_pixel, digits=2) if bbox_pixel else None,
                "bbox_ratio_local": box.get("bbox_ratio_local"),
                "bbox_ratio": bbox_ratio,
                "model_box_id": box.get("box_id"),
            }
        )

    for box in full_layout.get("boxes", []):
        _emit(box, source="full_page", roi_name=None)
    for layout in roi_layouts:
        roi_name = layout.get("roi_name")
        for box in layout.get("boxes", []):
            _emit(box, source="roi", roi_name=roi_name)

    return rows


def project_raw_to_page_pixels(
    raw_rows: list[dict[str, Any]],
    page_width_px: int,
    page_height_px: int,
) -> list[dict[str, Any]]:
    """Project every raw row's bbox_ratio to absolute page pixel coords.

    Returned dicts include `bbox_px` keyed entry for ``draw_pixel_boxes``-style
    visualisation, while keeping the original fields.
    """
    projected: list[dict[str, Any]] = []
    for row in raw_rows:
        item = dict(row)
        bbox_ratio = row["bbox_ratio"]
        x1, y1, x2, y2 = bbox_ratio_to_pixels(bbox_ratio, page_width_px, page_height_px)
        item["bbox_px"] = [x1, y1, x2, y2]
        projected.append(item)
    return projected
