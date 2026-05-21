from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import bbox_ratio_to_pixels, clamp_bbox_ratio, ensure_dir


PORTRAIT_ROIS: dict[str, list[float]] = {
    "right_column": [0.58, 0.02, 0.98, 0.95],
    "right_top": [0.58, 0.02, 0.98, 0.35],
    "right_middle": [0.58, 0.30, 0.98, 0.65],
    "right_bottom": [0.58, 0.60, 0.98, 0.98],
    "bottom_band": [0.05, 0.72, 0.98, 0.98],
}

LANDSCAPE_ROIS: dict[str, list[float]] = {
    "right_column": [0.62, 0.02, 0.98, 0.95],
    "right_top": [0.62, 0.02, 0.98, 0.35],
    "right_middle": [0.62, 0.30, 0.98, 0.65],
    "right_bottom": [0.62, 0.60, 0.98, 0.98],
    "bottom_band": [0.05, 0.70, 0.98, 0.98],
}


def build_rois(
    page_width_px: int,
    page_height_px: int,
    page_number: int = 1,
    orientation: str | None = None,
) -> list[dict[str, Any]]:
    resolved_orientation = orientation or (
        "landscape" if page_width_px >= page_height_px else "portrait"
    )
    definitions = (
        LANDSCAPE_ROIS if resolved_orientation == "landscape" else PORTRAIT_ROIS
    )
    rois: list[dict[str, Any]] = []
    for name, bbox in definitions.items():
        bbox_ratio = clamp_bbox_ratio(bbox)
        rois.append(
            {
                "name": name,
                "page": page_number,
                "orientation": resolved_orientation,
                "bbox_ratio": bbox_ratio,
                "bbox_px_lowdpi": list(
                    bbox_ratio_to_pixels(bbox_ratio, page_width_px, page_height_px)
                ),
            }
        )
    return rois


def crop_roi_images(
    image_path: str | Path,
    rois: list[dict[str, Any]],
    output_dir: str | Path,
) -> list[dict[str, Any]]:
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - depends on local install
        raise RuntimeError(
            "Pillow is required to crop ROI images. Install dependencies with "
            "`pip install -r requirements.txt` inside poc_layout_refactor."
        ) from exc

    output = ensure_dir(output_dir)
    updated_rois: list[dict[str, Any]] = []
    with Image.open(image_path) as image:
        width, height = image.size
        for roi in rois:
            bbox_px = bbox_ratio_to_pixels(roi["bbox_ratio"], width, height)
            crop = image.crop(bbox_px)
            crop_path = output / f"roi_{roi['name']}.png"
            crop.save(crop_path)
            updated = dict(roi)
            updated["image_path"] = str(crop_path)
            updated["image_width_px"] = crop.width
            updated["image_height_px"] = crop.height
            updated["bbox_px_lowdpi"] = list(bbox_px)
            updated_rois.append(updated)
    return updated_rois
