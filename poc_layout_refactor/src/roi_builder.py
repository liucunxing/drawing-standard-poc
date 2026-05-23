from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import bbox_ratio_to_pixels, clamp_bbox_ratio, ensure_dir
from .zone_config import get_roi_definitions, load_zones_config


def build_rois(
    page_width_px: int,
    page_height_px: int,
    page_number: int = 1,
    orientation: str | None = None,
    zones_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build ROI dicts from ``config/zones.yaml`` for the resolved orientation."""
    resolved_orientation = orientation or (
        "landscape" if page_width_px >= page_height_px else "portrait"
    )
    config = zones_config or load_zones_config()
    definitions = get_roi_definitions(config, resolved_orientation)
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
