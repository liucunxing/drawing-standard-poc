"""Load and access the Phase 1 zones.yaml configuration.

This module is the single accessor for ROI definitions, candidate filters,
invalid regions and merge strategy. Other modules must not hardcode ROI
coordinates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import clamp_bbox_ratio


DEFAULT_ZONES_PATH = Path(__file__).resolve().parent.parent / "config" / "zones.yaml"


def load_zones_config(path: str | Path | None = None) -> dict[str, Any]:
    """Read zones.yaml and return a normalised dict.

    The returned dict always contains:
      - portrait / landscape: {roi_definitions: {name: bbox_ratio}}
      - candidate: dict
      - invalid_regions: {name: {bbox: bbox_ratio, reason: str}}
      - roi_fallback: {always_emit: [roi_name, ...]}
      - source_path: absolute path to the loaded file
    """
    try:
        import yaml
    except Exception as exc:  # pragma: no cover - dependency
        raise RuntimeError(
            "PyYAML is required to read zones.yaml. Install dependencies with "
            "`pip install -r requirements.txt` inside poc_layout_refactor."
        ) from exc

    target = Path(path) if path else DEFAULT_ZONES_PATH
    if not target.exists():
        raise FileNotFoundError(f"zones.yaml not found: {target}")
    with target.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}

    portrait = _normalise_orientation_block(data.get("portrait"))
    landscape = _normalise_orientation_block(data.get("landscape"))
    candidate = dict(data.get("candidate") or {})
    invalid = _normalise_invalid_regions(data.get("invalid_regions") or {})
    fallback = dict(data.get("roi_fallback") or {})
    fallback.setdefault("always_emit", [])

    return {
        "portrait": portrait,
        "landscape": landscape,
        "candidate": candidate,
        "invalid_regions": invalid,
        "roi_fallback": fallback,
        "source_path": str(target),
    }


def get_roi_definitions(zones: dict[str, Any], orientation: str) -> dict[str, list[float]]:
    block = zones.get(orientation) or zones.get("landscape") or zones.get("portrait") or {}
    return block.get("roi_definitions", {})


def _normalise_orientation_block(block: Any) -> dict[str, Any]:
    block = dict(block or {})
    rois = block.get("roi_definitions") or {}
    block["roi_definitions"] = {
        str(name): clamp_bbox_ratio(bbox) for name, bbox in rois.items()
    }
    return block


def _normalise_invalid_regions(regions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalised: dict[str, dict[str, Any]] = {}
    for name, item in regions.items():
        if not isinstance(item, dict):
            continue
        bbox = item.get("bbox")
        if not bbox:
            continue
        normalised[str(name)] = {
            "bbox": clamp_bbox_ratio(bbox),
            "reason": str(item.get("reason") or name),
        }
    return normalised
