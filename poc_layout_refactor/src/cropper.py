from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import bbox_ratio_to_pixels, ensure_dir


def crop_candidates_from_highdpi(
    highdpi_image_path: str | Path,
    candidates: list[dict[str, Any]],
    output_dir: str | Path,
) -> list[dict[str, Any]]:
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - depends on local install
        raise RuntimeError(
            "Pillow is required to crop candidate images. Install dependencies with "
            "`pip install -r requirements.txt` inside poc_layout_refactor."
        ) from exc

    output = ensure_dir(output_dir)
    updated_candidates: list[dict[str, Any]] = []

    with Image.open(highdpi_image_path) as image:
        width, height = image.size
        for candidate in candidates:
            bbox_ratio = candidate.get("expanded_bbox_ratio") or candidate["bbox_ratio"]
            bbox_px = bbox_ratio_to_pixels(bbox_ratio, width, height)
            crop = image.crop(bbox_px)
            crop_path = output / f"candidate_{candidate['region_id']}.png"
            crop.save(crop_path)

            updated = dict(candidate)
            updated["crop_image_path"] = str(crop_path)
            updated["crop_bbox_px_highdpi"] = list(bbox_px)
            updated["crop_width_px"] = crop.width
            updated["crop_height_px"] = crop.height
            updated_candidates.append(updated)

    return updated_candidates


def crop_layout_boxes_from_highdpi(
    highdpi_image_path: str | Path,
    layout_result: dict[str, Any],
    output_dir: str | Path,
    name_prefix: str,
) -> list[dict[str, Any]]:
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - depends on local install
        raise RuntimeError(
            "Pillow is required to crop layout detection images. Install dependencies "
            "with `pip install -r requirements.txt` inside poc_layout_refactor."
        ) from exc

    output = ensure_dir(output_dir)
    crops: list[dict[str, Any]] = []
    boxes = layout_result.get("boxes", [])
    with Image.open(highdpi_image_path) as image:
        width, height = image.size
        for index, box in enumerate(boxes, start=1):
            bbox_ratio = box["bbox_ratio"]
            bbox_px = bbox_ratio_to_pixels(bbox_ratio, width, height)
            crop = image.crop(bbox_px)
            label = box.get("label", "layout")
            crop_path = output / f"{name_prefix}_{index:03d}_{label}.png"
            crop.save(crop_path)
            crops.append(
                {
                    "source": name_prefix,
                    "box_id": box.get("box_id"),
                    "label": label,
                    "score": box.get("score"),
                    "bbox_ratio": bbox_ratio,
                    "crop_image_path": str(crop_path),
                    "crop_bbox_px_highdpi": list(bbox_px),
                    "crop_width_px": crop.width,
                    "crop_height_px": crop.height,
                }
            )
    return crops
