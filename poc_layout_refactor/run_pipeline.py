from __future__ import annotations

import argparse
from pathlib import Path

from src.candidate_builder import (
    build_precise_table_regions,
    build_raw_candidates,
    merge_candidate_regions,
)
from src.cropper import crop_candidates_from_highdpi, crop_layout_boxes_from_highdpi
from src.layout_detect import LayoutDetector
from src.pdf_render import render_pdf_page
from src.roi_builder import build_rois, crop_roi_images
from src.utils import (
    build_summary,
    ensure_dir,
    load_config,
    safe_stem,
    write_debug_report,
    write_json,
)
from src.visualize import draw_pixel_boxes, draw_ratio_boxes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline PDF drawing layout detection pipeline."
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
        help="Path to config.yaml.",
    )
    return parser.parse_args()


def run_pipeline(pdf_path: str | Path, output_root: str | Path, config_path: str | Path) -> Path:
    config = load_config(config_path)
    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf}")

    run_dir = ensure_dir(Path(output_root) / safe_stem(pdf))
    page_number = 1

    page_info = render_pdf_page(
        pdf_path=pdf,
        output_dir=run_dir,
        page_number=page_number,
        low_dpi=int(config.get("low_dpi", 150)),
        high_dpi=int(config.get("high_dpi", 400)),
    )
    write_json(run_dir / "page_info.json", page_info)

    rois = build_rois(
        page_width_px=page_info["low_width_px"],
        page_height_px=page_info["low_height_px"],
        page_number=page_number,
        orientation=page_info["orientation"],
    )
    roi_images = crop_roi_images(page_info["low_image"]["path"], rois, run_dir)
    write_json(
        run_dir / "roi_definitions.json",
        {
            "page": page_number,
            "orientation": page_info["orientation"],
            "coordinate_format": "page_ratio",
            "rois": roi_images,
        },
    )

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
    write_json(run_dir / "full_page_layout_raw.json", full_layout)
    draw_ratio_boxes(
        page_info["low_image"]["path"],
        full_layout["boxes"],
        run_dir / "full_page_layout_overlay.png",
    )

    roi_layouts = []
    for roi in roi_images:
        layout = detector.detect_image(
            roi["image_path"],
            page_bbox_ratio=roi["bbox_ratio"],
            roi_name=roi["name"],
        )
        roi_layouts.append(layout)
        write_json(run_dir / f"roi_{roi['name']}_layout_raw.json", layout)
        draw_pixel_boxes(
            roi["image_path"],
            layout["boxes"],
            run_dir / f"roi_{roi['name']}_layout_overlay.png",
        )

    layout_crops = []
    layout_crop_dir = ensure_dir(run_dir / "layout_detections")
    layout_crops.extend(
        crop_layout_boxes_from_highdpi(
            page_info["high_image"]["path"],
            full_layout,
            layout_crop_dir,
            "full_page",
        )
    )
    for layout in roi_layouts:
        roi_name = layout.get("roi_name") or "roi"
        layout_crops.extend(
            crop_layout_boxes_from_highdpi(
                page_info["high_image"]["path"],
                layout,
                layout_crop_dir,
                f"roi_{roi_name}",
            )
        )
    write_json(
        run_dir / "layout_detected_regions.json",
        {"coordinate_format": "page_ratio", "regions": layout_crops},
    )

    precise_tables = build_precise_table_regions(
        full_layout=full_layout,
        roi_layouts=roi_layouts,
        config=config,
        page_number=page_number,
    )
    draw_ratio_boxes(
        page_info["low_image"]["path"],
        precise_tables,
        run_dir / "precise_table_regions_overlay.png",
        bbox_field="expanded_bbox_ratio",
    )
    cropped_precise_tables = crop_candidates_from_highdpi(
        page_info["high_image"]["path"],
        precise_tables,
        run_dir / "precise_tables",
    )
    write_json(
        run_dir / "precise_table_regions.json",
        {"coordinate_format": "page_ratio", "regions": cropped_precise_tables},
    )

    raw_candidates = build_raw_candidates(
        full_layout=full_layout,
        roi_layouts=roi_layouts,
        rois=roi_images,
        config=config,
        page_number=page_number,
    )
    write_json(
        run_dir / "candidate_regions_raw.json",
        {"coordinate_format": "page_ratio", "candidates": raw_candidates},
    )

    merged_candidates = merge_candidate_regions(raw_candidates, config)
    draw_ratio_boxes(
        page_info["low_image"]["path"],
        merged_candidates,
        run_dir / "candidate_regions_overlay.png",
        bbox_field="expanded_bbox_ratio",
    )

    cropped_candidates = crop_candidates_from_highdpi(
        page_info["high_image"]["path"],
        merged_candidates,
        run_dir / "candidates",
    )
    write_json(
        run_dir / "candidate_regions_merged.json",
        {"coordinate_format": "page_ratio", "candidates": cropped_candidates},
    )

    summary = build_summary(
        pdf_path=pdf,
        output_dir=run_dir,
        page_info=page_info,
        full_layout=full_layout,
        roi_layouts=roi_layouts,
        candidates=cropped_candidates,
    )
    write_json(run_dir / "summary.json", summary)
    write_debug_report(
        run_dir / "debug_report.md",
        pdf_path=pdf,
        output_dir=run_dir,
        page_info=page_info,
        candidates=cropped_candidates,
    )
    return run_dir


def main() -> None:
    args = parse_args()
    output_dir = run_pipeline(args.pdf, args.output, args.config)
    print(f"Pipeline finished. Output: {output_dir}")


if __name__ == "__main__":
    main()
