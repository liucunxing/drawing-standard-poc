"""Phase 1 layout governance pipeline.

Produces a fully traceable, auditable set of candidate regions per PDF page:

    output/{pdf_name}/
      page_info.json
      page_1_lowdpi.png
      page_1_highdpi.png
      layout_boxes_raw.json
      layout_boxes_raw_overlay.png
      roi_definitions.json
      roi_images/
      candidate_regions_raw.json
      candidate_regions_merged.json
      candidate_regions_overlay.png
      dropped_candidates.json
      stage1_manifest.json
      debug_report.md
      candidates/

Only the high-DPI rendered image is used to produce the final candidate crops.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.candidate_phase1 import (
    build_raw_candidates,
    build_roi_fallback_candidates,
    dedupe_candidates,
    finalise_candidates,
    merge_candidates,
)
from src.candidate_builder import (
    build_raw_candidates as build_zone_raw_candidates,
    merge_candidate_regions as merge_zone_candidate_regions,
)
from src.cropper import crop_candidates_from_highdpi
from src.drop_tracker import DropTracker
from src.layout_detect import LayoutDetector
from src.layout_raw import flatten_layout_boxes_raw, project_raw_to_page_pixels
from src.manifest import build_stage1_manifest, write_debug_report
from src.pdf_render import render_pdf_page
from src.roi_builder import build_rois, crop_roi_images
from src.utils import ensure_dir, load_config, safe_stem, write_json
from src.visualize import draw_pixel_boxes, draw_ratio_boxes
from src.zone_config import load_zones_config


_LEGACY_FILES = (
    "full_page_layout_raw.json",
    "full_page_layout_overlay.png",
    "precise_table_regions.json",
    "precise_table_regions_overlay.png",
    "summary.json",
    "layout_detected_regions.json",
)
_LEGACY_DIRS = ("precise_tables", "layout_detections")


def _clean_legacy_outputs(run_dir: Path) -> None:
    """Remove files produced by the pre-Phase-1 pipeline so the output dir
    only contains the canonical Phase 1 artefacts.

    Safe: only deletes well-known legacy filenames + directories. Never
    touches Phase 1 outputs.
    """
    import shutil

    for name in _LEGACY_FILES:
        path = run_dir / name
        if path.exists():
            path.unlink()
    for name in _LEGACY_DIRS:
        path = run_dir / name
        if path.exists() and path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    # Stray top-level ROI artefacts written by the old pipeline (now under
    # roi_images/).
    for path in run_dir.glob("roi_*.png"):
        if path.is_file():
            path.unlink()
    for path in run_dir.glob("roi_*_layout_*.json"):
        if path.is_file():
            path.unlink()
    for path in run_dir.glob("roi_*_layout_*.png"):
        if path.is_file():
            path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 1 layout governance pipeline (PDF drawings)."
    )
    parser.add_argument("--pdf", required=True, help="Path to a single PDF file.")
    parser.add_argument(
        "--output",
        default="output",
        help="Output root directory. A subdirectory named by the PDF stem is created.",
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).with_name("config.yaml")),
        help="Path to config.yaml (Paddle params + DPI).",
    )
    parser.add_argument(
        "--zones",
        default=str(Path(__file__).resolve().parent / "config" / "zones.yaml"),
        help="Path to config/zones.yaml (ROIs, candidate filters, invalid regions).",
    )
    return parser.parse_args()


def run_pipeline(
    pdf_path: str | Path,
    output_root: str | Path,
    config_path: str | Path,
    zones_path: str | Path | None = None,
) -> Path:
    config = load_config(config_path)
    zones_config = load_zones_config(zones_path)
    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf}")

    run_dir = ensure_dir(Path(output_root) / safe_stem(pdf))
    _clean_legacy_outputs(run_dir)
    page_number = 1

    # 1. Render double-DPI page images.
    page_info = render_pdf_page(
        pdf_path=pdf,
        output_dir=run_dir,
        page_number=page_number,
        low_dpi=int(config.get("low_dpi", 150)),
        high_dpi=int(config.get("high_dpi", 300)),
        reuse_existing=bool(config.get("render_reuse_existing", True)),
        force_render=bool(config.get("render_force", False)),
    )
    page_info["zones_config_path"] = zones_config.get("source_path")
    write_json(run_dir / "page_info.json", page_info)

    # 2. Build ROIs from zones.yaml and crop low-DPI ROI thumbnails.
    rois = build_rois(
        page_width_px=page_info["low_width_px"],
        page_height_px=page_info["low_height_px"],
        page_number=page_number,
        orientation=page_info["orientation"],
        zones_config=zones_config,
    )
    roi_image_dir = ensure_dir(run_dir / "roi_images")
    roi_images = crop_roi_images(page_info["low_image"]["path"], rois, roi_image_dir)
    write_json(
        run_dir / "roi_definitions.json",
        {
            "page": page_number,
            "orientation": page_info["orientation"],
            "coordinate_format": "page_ratio",
            "zones_config_path": zones_config.get("source_path"),
            "rois": roi_images,
        },
    )

    # 3. Run PP-DocLayout on full page and on every ROI image.
    detector = LayoutDetector(
        model_name=str(config.get("layout_model_name", "PP-DocLayout_plus-L")),
        threshold=float(config.get("layout_threshold", 0.2)),
        layout_nms=bool(config.get("layout_nms", True)),
        layout_merge_bboxes_mode=config.get("layout_merge_bboxes_mode", "union"),
        device=str(config.get("layout_device", "cpu")),
        enable_mkldnn=bool(config.get("layout_enable_mkldnn", False)),
        enable_cinn=bool(config.get("layout_enable_cinn", False)),
        cpu_threads=int(config.get("layout_cpu_threads", 4)),
        fallback_on_error=bool(config.get("layout_fallback_on_error", True)),
    )

    full_layout = detector.detect_image(page_info["low_image"]["path"])
    roi_layouts: list = []
    for roi in roi_images:
        layout = detector.detect_image(
            roi["image_path"],
            page_bbox_ratio=roi["bbox_ratio"],
            roi_name=roi["name"],
        )
        roi_layouts.append(layout)

    # 4. Flatten raw layout boxes (no filtering, no dedupe) and persist.
    raw_layout_boxes = flatten_layout_boxes_raw(full_layout, roi_layouts, page_number=page_number)
    write_json(
        run_dir / "layout_boxes_raw.json",
        {
            "coordinate_format": "page_ratio",
            "page": page_number,
            "count": len(raw_layout_boxes),
            "boxes": raw_layout_boxes,
        },
    )
    projected = project_raw_to_page_pixels(
        raw_layout_boxes,
        page_width_px=page_info["low_width_px"],
        page_height_px=page_info["low_height_px"],
    )
    draw_pixel_boxes(
        page_info["low_image"]["path"],
        projected,
        run_dir / "layout_boxes_raw_overlay.png",
    )

    # 5. Build raw candidates (label/size/invalid_region filter, with drop trace).
    drop_tracker = DropTracker()
    candidate_raw = build_raw_candidates(
        raw_layout_boxes=raw_layout_boxes,
        zones_config=zones_config,
        rois=roi_images,
        drop_tracker=drop_tracker,
        page_number=page_number,
    )
    # 6. Always emit roi_fallback candidates in parallel.
    fallback_candidates = build_roi_fallback_candidates(
        rois=roi_images,
        zones_config=zones_config,
        page_number=page_number,
    )
    all_raw_candidates = candidate_raw + fallback_candidates
    write_json(
        run_dir / "candidate_regions_raw.json",
        {
            "coordinate_format": "page_ratio",
            "page": page_number,
            "count": len(all_raw_candidates),
            "candidates": all_raw_candidates,
        },
    )

    # 7. Build final candidates by business zone. The broad Phase-1 raw
    # candidates above remain as audit/debug artefacts; final crops should be a
    # small, stable set of business regions.
    zone_raw_candidates = build_zone_raw_candidates(
        full_layout=full_layout,
        roi_layouts=roi_layouts,
        rois=roi_images,
        config=config,
        page_number=page_number,
    )
    final_candidates = merge_zone_candidate_regions(
        zone_raw_candidates,
        config,
        rois=roi_images,
        page_number=page_number,
    )

    merged_path = run_dir / "candidate_regions_merged.json"
    write_json(
        merged_path,
        {
            "coordinate_format": "page_ratio",
            "page": page_number,
            "merge_strategy": "zone_business",
            "count": len(final_candidates),
            "candidates": final_candidates,
        },
    )
    draw_ratio_boxes(
        page_info["low_image"]["path"],
        final_candidates,
        run_dir / "candidate_regions_overlay.png",
        bbox_field="expanded_bbox_ratio",
    )

    # 8. Crop candidates from the high-DPI page image only.
    cropped_candidates = crop_candidates_from_highdpi(
        page_info["high_image"]["path"],
        merged_path,
        run_dir / "candidates",
    )
    write_json(
        merged_path,
        {
            "coordinate_format": "page_ratio",
            "page": page_number,
            "merge_strategy": "zone_business",
            "count": len(cropped_candidates),
            "candidates": cropped_candidates,
        },
    )

    # 9. Dropped candidates manifest.
    write_json(
        run_dir / "dropped_candidates.json",
        {
            "page": page_number,
            "count": len(drop_tracker),
            "entries": drop_tracker.entries,
            "reason_summary": drop_tracker.reason_summary(),
        },
    )

    # 10. Stage 1 manifest + debug report.
    output_files = sorted(p.name for p in run_dir.glob("*") if p.is_file())
    manifest = build_stage1_manifest(
        pdf_path=pdf,
        output_dir=run_dir,
        page_info=page_info,
        raw_layout_boxes=raw_layout_boxes,
        candidate_raw=all_raw_candidates,
        candidate_merged=cropped_candidates,
        dropped=drop_tracker.entries,
        merge_strategy="zone_business",
        zones_config_path=zones_config.get("source_path", ""),
        output_files=output_files,
    )
    write_json(run_dir / "stage1_manifest.json", manifest)
    write_debug_report(run_dir / "debug_report.md", manifest, cropped_candidates)
    return run_dir


def main() -> None:
    args = parse_args()
    output_dir = run_pipeline(args.pdf, args.output, args.config, args.zones)
    print(f"Pipeline finished. Output: {output_dir}")


if __name__ == "__main__":
    main()
