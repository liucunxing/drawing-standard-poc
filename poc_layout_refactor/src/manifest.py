"""Stage 1 manifest + debug report writers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import bbox_area, ensure_dir


def build_stage1_manifest(
    *,
    pdf_path: str | Path,
    output_dir: str | Path,
    page_info: dict[str, Any],
    raw_layout_boxes: list[dict[str, Any]],
    candidate_raw: list[dict[str, Any]],
    candidate_merged: list[dict[str, Any]],
    dropped: list[dict[str, Any]],
    merge_strategy: str,
    zones_config_path: str,
    output_files: list[str],
) -> dict[str, Any]:
    pdf = Path(pdf_path)
    drop_summary: dict[str, int] = {}
    for entry in dropped:
        key = f"{entry.get('stage')}::{entry.get('reason')}"
        drop_summary[key] = drop_summary.get(key, 0) + 1

    union_area = _union_area([item.get("expanded_bbox_ratio") or item["bbox_ratio"] for item in candidate_merged])
    avg_area = (
        sum(bbox_area(item.get("expanded_bbox_ratio") or item["bbox_ratio"]) for item in candidate_merged)
        / len(candidate_merged)
        if candidate_merged
        else 0.0
    )

    return {
        "pdf_name": pdf.name,
        "pdf_path": str(pdf),
        "output_dir": str(output_dir),
        "zones_config_path": zones_config_path,
        "page_count": page_info.get("page_count", 1),
        "pages_processed": [page_info.get("page", 1)],
        "orientation": page_info.get("orientation"),
        "low_dpi": page_info.get("low_dpi"),
        "high_dpi": page_info.get("high_dpi"),
        "page_size_pt": {
            "width": page_info.get("page_width_pt"),
            "height": page_info.get("page_height_pt"),
        },
        "image_size_px": {
            "low": [page_info.get("low_width_px"), page_info.get("low_height_px")],
            "high": [page_info.get("high_width_px"), page_info.get("high_height_px")],
        },
        "merge_strategy": merge_strategy,
        "num_raw_layout_boxes": len(raw_layout_boxes),
        "num_candidate_raw": len(candidate_raw),
        "num_candidate_merged": len(candidate_merged),
        "num_candidate_layout_box": sum(1 for c in candidate_merged if c.get("source") in ("layout_box", "merged")),
        "num_candidate_roi_fallback": sum(1 for c in candidate_merged if c.get("source") == "roi_fallback"),
        "num_dropped": len(dropped),
        "drop_reason_summary": drop_summary,
        "candidate_area_union_ratio": round(union_area, 6),
        "average_candidate_area_ratio": round(avg_area, 6),
        "output_files": sorted(output_files),
    }


def _union_area(bboxes: list[list[float]]) -> float:
    """Approximate union area via 1000x1000 raster scan (good enough for QA).

    Implemented as an additive area minus pairwise intersections (inclusion-
    exclusion truncated to pairs) for small N; for larger N falls back to a
    rasterized estimate.
    """
    if not bboxes:
        return 0.0
    n = len(bboxes)
    if n <= 12:
        return _inclusion_exclusion_union(bboxes)
    # Rasterise.
    grid = 400
    mask = bytearray(grid * grid)
    for x1, y1, x2, y2 in bboxes:
        gx1 = max(0, int(x1 * grid))
        gy1 = max(0, int(y1 * grid))
        gx2 = min(grid, int(x2 * grid + 0.999))
        gy2 = min(grid, int(y2 * grid + 0.999))
        for gy in range(gy1, gy2):
            base = gy * grid
            for gx in range(gx1, gx2):
                mask[base + gx] = 1
    return sum(mask) / (grid * grid)


def _inclusion_exclusion_union(bboxes: list[list[float]]) -> float:
    from itertools import combinations
    from .utils import intersection_bbox

    total = 0.0
    for r in range(1, len(bboxes) + 1):
        sign = 1 if r % 2 == 1 else -1
        for combo in combinations(bboxes, r):
            inter = combo[0]
            for box in combo[1:]:
                inter = intersection_bbox(inter, box)
                if inter is None:
                    break
            if inter is None:
                continue
            total += sign * bbox_area(inter)
    return max(0.0, total)


# ---------------------------------------------------------------------------
# debug_report.md writer
# ---------------------------------------------------------------------------


def write_debug_report(path: str | Path, manifest: dict[str, Any], candidates: list[dict[str, Any]]) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    lines: list[str] = []
    lines.append("# Stage 1 Layout Detection Debug Report")
    lines.append("")
    lines.append("## Input")
    lines.append("")
    lines.append(f"- PDF: `{manifest.get('pdf_path')}`")
    lines.append(f"- Output dir: `{manifest.get('output_dir')}`")
    lines.append(f"- zones.yaml: `{manifest.get('zones_config_path')}`")
    lines.append("")
    lines.append("## Page")
    lines.append("")
    lines.append(f"- Page count: {manifest.get('page_count')}")
    lines.append(f"- Pages processed: {manifest.get('pages_processed')}")
    lines.append(f"- Orientation: {manifest.get('orientation')}")
    lines.append(f"- Low DPI: {manifest.get('low_dpi')}  |  High DPI: {manifest.get('high_dpi')}")
    img = manifest.get("image_size_px", {})
    lines.append(f"- Low image px: {img.get('low')}")
    lines.append(f"- High image px: {img.get('high')}")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- Raw layout boxes: **{manifest.get('num_raw_layout_boxes')}**")
    lines.append(f"- Candidate (raw): **{manifest.get('num_candidate_raw')}**")
    lines.append(f"- Candidate (merged): **{manifest.get('num_candidate_merged')}**")
    lines.append(f"  - layout / merged: {manifest.get('num_candidate_layout_box')}")
    lines.append(f"  - roi_fallback: {manifest.get('num_candidate_roi_fallback')}")
    lines.append(f"- Dropped boxes: **{manifest.get('num_dropped')}**")
    lines.append(f"- merge_strategy: `{manifest.get('merge_strategy')}`")
    lines.append(f"- candidate_area_union_ratio: {manifest.get('candidate_area_union_ratio')}")
    lines.append(f"- average_candidate_area_ratio: {manifest.get('average_candidate_area_ratio')}")
    lines.append("")
    lines.append("## Drop reason distribution")
    lines.append("")
    summary = manifest.get("drop_reason_summary") or {}
    if not summary:
        lines.append("_No drops recorded._")
    else:
        lines.append("| stage::reason | count |")
        lines.append("| --- | ---: |")
        for key, count in sorted(summary.items(), key=lambda kv: -kv[1]):
            lines.append(f"| `{key}` | {count} |")
    lines.append("")
    lines.append("## Candidate list")
    lines.append("")
    if candidates:
        lines.append("| region_id | source | roi | labels | score | bbox_ratio | crop |")
        lines.append("| --- | --- | --- | --- | ---: | --- | --- |")
        for item in candidates:
            score = item.get("score")
            score_text = f"{score:.4f}" if isinstance(score, (int, float)) else ""
            crop_name = Path(item.get("crop_image_path") or "").name
            labels = ",".join(item.get("labels") or [])
            lines.append(
                "| {rid} | {src} | {roi} | {lbl} | {score} | `{bbox}` | `{crop}` |".format(
                    rid=item.get("region_id"),
                    src=item.get("source") or "",
                    roi=item.get("roi_name") or "",
                    lbl=labels,
                    score=score_text,
                    bbox=item.get("expanded_bbox_ratio") or item.get("bbox_ratio"),
                    crop=crop_name,
                )
            )
    else:
        lines.append("_No candidates emitted._")
    lines.append("")
    lines.append("## Output files")
    lines.append("")
    for name in manifest.get("output_files") or []:
        lines.append(f"- `{name}`")
    lines.append("")
    lines.append("## Phase 1 limitations")
    lines.append("")
    lines.append("- No OCR is performed; candidates are only image regions.")
    lines.append("- No table structure parsing yet.")
    lines.append("- No standard-number extraction yet.")
    lines.append("- No standard library comparison yet.")
    lines.append("- Conservative merge keeps acceptable overlap; downstream OCR must")
    lines.append("  deduplicate using extracted text rather than relying on this stage.")
    lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")
