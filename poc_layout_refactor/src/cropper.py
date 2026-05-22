from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .utils import bbox_ratio_to_pixels, ensure_dir


def crop_candidates_from_highdpi(
    highdpi_image_path: str | Path,
    merged_candidate_json_path: str | Path,
    output_dir: str | Path,
) -> list[dict[str, Any]]:
    """Crop only merged final candidates from the high-DPI page image."""
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - depends on local install
        raise RuntimeError(
            "Pillow is required to crop candidate images. Install dependencies with "
            "`pip install -r requirements.txt` inside poc_layout_refactor."
        ) from exc

    payload = json.loads(Path(merged_candidate_json_path).read_text(encoding="utf-8"))
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("merged candidate JSON must contain a `candidates` list")

    output = ensure_dir(output_dir)
    for old_crop in output.glob("candidate_*.png"):
        old_crop.unlink()
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
