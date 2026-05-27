from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .utils import bbox_ratio_to_pixels, ensure_dir


def _safe_name_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text or "x"


def _stable_crop_filename(candidate: dict[str, Any], fallback_index: int) -> str:
    index = int(candidate.get("candidate_index") or fallback_index)
    source = _safe_name_token(candidate.get("source") or "candidate")
    roi = _safe_name_token(candidate.get("roi_name") or "")
    labels = candidate.get("labels") or []
    label_token = _safe_name_token("_".join(labels) if labels else "")
    parts = [f"candidate_{index:03d}", source]
    if roi:
        parts.append(roi)
    if label_token:
        parts.append(label_token)
    return "_".join(parts) + ".png"


def crop_candidates_from_highdpi(
    highdpi_image_path: str | Path,
    merged_candidate_json_path: str | Path,
    output_dir: str | Path,
) -> list[dict[str, Any]]:
    """Crop only merged final candidates from the high-DPI page image.

    The high-DPI image is the only allowed crop source. Overlay images must
    never be used for cropping. File names are stable per candidate index.
    """
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - dependency
        raise RuntimeError(
            "Pillow is required to crop candidate images. Install dependencies with "
            "`pip install -r requirements.txt` inside poc_layout_refactor."
        ) from exc
    Image.MAX_IMAGE_PIXELS = None

    payload = json.loads(Path(merged_candidate_json_path).read_text(encoding="utf-8"))
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("merged candidate JSON must contain a `candidates` list")

    source_image = Path(highdpi_image_path)
    if "highdpi" not in source_image.name and "high_dpi" not in source_image.name:
        # Defensive: refuse to crop from anything that does not look like the
        # high-DPI image (e.g. an overlay). The pipeline always passes the
        # canonical filename so this should only ever happen from misuse.
        raise ValueError(
            f"crop source must be the high-DPI image, got: {source_image.name}"
        )

    output = ensure_dir(output_dir)
    for old_crop in output.glob("candidate_*.png"):
        old_crop.unlink()
    updated_candidates: list[dict[str, Any]] = []
    with Image.open(source_image) as image:
        width, height = image.size
        for idx, candidate in enumerate(candidates, start=1):
            bbox_ratio = candidate.get("expanded_bbox_ratio") or candidate["bbox_ratio"]
            bbox_px = bbox_ratio_to_pixels(bbox_ratio, width, height)
            crop = image.crop(bbox_px)
            crop_path = output / _stable_crop_filename(candidate, idx)
            crop.save(crop_path)

            updated = dict(candidate)
            updated["candidate_index"] = int(updated.get("candidate_index") or idx)
            updated["crop_image_path"] = str(crop_path)
            updated["crop_bbox_px_highdpi"] = list(bbox_px)
            updated["crop_width_px"] = crop.width
            updated["crop_height_px"] = crop.height
            updated["crop_source"] = "high_dpi_page_image"
            updated_candidates.append(updated)
    return updated_candidates
