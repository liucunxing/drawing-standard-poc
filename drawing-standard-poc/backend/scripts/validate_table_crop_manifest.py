from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


BBox = Tuple[int, int, int, int]

EXPECTED_SAMPLE_RANGES = {
    "02.194": (6, 8),
    "03.276": (4, 6),
    "14.751": (6, 10),
    "25.918": (3, 5),
}

REQUIRED_ZONE_COVERAGE = {
    "03.276": [
        ("左下角 T/L1/P1 表", (0.06, 0.86, 0.35, 0.99)),
        ("底部中间 N6-N12 明细表", (0.35, 0.75, 0.69, 0.99)),
    ],
    "14.751": [
        ("底部中部 N1-N6 明细表", (0.35, 0.82, 0.70, 0.99)),
        ("右下角材料/件号明细表", (0.67, 0.66, 0.98, 0.86)),
    ],
}

MAX_BOTTOM_GRID_COUNTS = {
    "02.194": 0,
    "03.276": 2,
    "14.751": 2,
    "25.918": 0,
}

REQUIRED_BBOX_SHAPES = {
    "03.276": [
        ("left-bottom T/L1/P1 schedule", (0.06, 0.86, 0.35, 0.99), 0.18, 0.06),
        ("middle-bottom N6-N12 schedule", (0.35, 0.75, 0.69, 0.99), 0.22, 0.15),
    ],
    "14.751": [
        ("right-bottom material list", (0.67, 0.66, 0.98, 0.86), 0.25, 0.12),
    ],
}

MAX_AREA_RATIO = 0.55
MAX_BOTTOM_GRID_AREA_RATIO = 0.13
DUPLICATE_IOU_THRESHOLD = 0.72
EXCESSIVE_OVERLAP_THRESHOLD = 0.58
EXCESSIVE_OVERLAP_IOU_THRESHOLD = 0.35
CONTAINMENT_THRESHOLD = 0.90
CONTAINMENT_AREA_RATIO = 1.25


def bbox_area(bbox: BBox) -> int:
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


def bbox_intersection(first: BBox, second: BBox) -> int:
    return bbox_area(
        (
            max(first[0], second[0]),
            max(first[1], second[1]),
            min(first[2], second[2]),
            min(first[3], second[3]),
        )
    )


def bbox_iou(first: BBox, second: BBox) -> float:
    intersection = bbox_intersection(first, second)
    union = bbox_area(first) + bbox_area(second) - intersection
    return intersection / union if union > 0 else 0.0


def as_bbox(value: Any) -> BBox:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"非法 bbox: {value}")
    return tuple(int(item) for item in value)


def page_size_by_page(manifest: Dict[str, Any]) -> Dict[int, Tuple[int, int]]:
    sizes = {}
    for page in manifest.get("page_images", []):
        sizes[int(page["page"])] = (int(page["width"]), int(page["height"]))
    return sizes


def expected_range(filename: str) -> Tuple[int, int] | None:
    for key, value in EXPECTED_SAMPLE_RANGES.items():
        if key in filename:
            return value
    return None


def required_zones(filename: str) -> List[Tuple[str, Tuple[float, float, float, float]]]:
    for key, value in REQUIRED_ZONE_COVERAGE.items():
        if key in filename:
            return value
    return []


def max_bottom_grid_count(filename: str) -> int | None:
    for key, value in MAX_BOTTOM_GRID_COUNTS.items():
        if key in filename:
            return value
    return None


def required_bbox_shapes(filename: str) -> List[Tuple[str, Tuple[float, float, float, float], float, float]]:
    for key, value in REQUIRED_BBOX_SHAPES.items():
        if key in filename:
            return value
    return []


def ratio_bbox(ratios: Tuple[float, float, float, float], page_size: Tuple[int, int]) -> BBox:
    width, height = page_size
    x1, y1, x2, y2 = ratios
    return (int(width * x1), int(height * y1), int(width * x2), int(height * y2))


def covers_zone(bbox: BBox, zone: BBox) -> bool:
    intersection = bbox_intersection(bbox, zone)
    if intersection <= 0:
        return False
    return intersection / min(bbox_area(bbox), bbox_area(zone)) >= 0.18


def covers_zone_with_shape(
    bbox: BBox,
    zone: BBox,
    page_size: Tuple[int, int],
    min_width_ratio: float,
    min_height_ratio: float,
) -> bool:
    if not covers_zone(bbox, zone):
        return False
    page_width, page_height = page_size
    if page_width <= 0 or page_height <= 0:
        return False
    return (
        (bbox[2] - bbox[0]) / page_width >= min_width_ratio
        and (bbox[3] - bbox[1]) / page_height >= min_height_ratio
    )


def validate_manifest(path: Path) -> List[str]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    filename = manifest.get("filename", path.name)
    tables = manifest.get("tables", [])
    errors: List[str] = []

    range_value = expected_range(filename)
    if range_value:
        min_count, max_count = range_value
        if len(tables) < min_count:
            errors.append(f"{filename}: 表格数 {len(tables)} 少于样例回归下限 {min_count}")
        if len(tables) > max_count:
            errors.append(f"{filename}: 表格数 {len(tables)} 高于样例回归上限 {max_count}，疑似过检")

    bottom_grid_limit = max_bottom_grid_count(filename)
    if bottom_grid_limit is not None:
        bottom_grid_count = sum(1 for table in tables if table.get("refine_method") == "bottom_grid")
        if bottom_grid_count > bottom_grid_limit:
            errors.append(
                f"{filename}: bottom_grid 补充框 {bottom_grid_count} 个，超过样例回归限制 {bottom_grid_limit}，疑似过检"
            )

    page_sizes = page_size_by_page(manifest)
    bboxes: List[Tuple[int, BBox]] = []
    for table in tables:
        table_index = int(table.get("table_index", len(bboxes) + 1))
        page = int(table.get("page", 1))
        bbox = as_bbox(table.get("bbox"))
        bboxes.append((table_index, bbox))

        page_size = page_sizes.get(page)
        if page_size:
            page_area = page_size[0] * page_size[1]
            area_ratio = bbox_area(bbox) / page_area if page_area else 0
            if area_ratio > MAX_AREA_RATIO:
                errors.append(f"{filename}: 表格 {table_index} 面积占比 {area_ratio:.2f}，疑似整页/整列误检")
            if table.get("refine_method") == "bottom_grid" and area_ratio > MAX_BOTTOM_GRID_AREA_RATIO:
                errors.append(
                    f"{filename}: 表格 {table_index} bottom_grid 面积占比 {area_ratio:.2f}，疑似补漏框过大"
                )

    if page_sizes and bboxes:
        first_page_size = page_sizes[min(page_sizes)]
        for zone_name, zone_ratios in required_zones(filename):
            zone_bbox = ratio_bbox(zone_ratios, first_page_size)
            if not any(covers_zone(bbox, zone_bbox) for _, bbox in bboxes):
                errors.append(f"{filename}: 未覆盖关键区域「{zone_name}」，疑似边缘表格漏检")
        for shape_name, zone_ratios, min_width_ratio, min_height_ratio in required_bbox_shapes(filename):
            zone_bbox = ratio_bbox(zone_ratios, first_page_size)
            if not any(
                covers_zone_with_shape(bbox, zone_bbox, first_page_size, min_width_ratio, min_height_ratio)
                for _, bbox in bboxes
            ):
                errors.append(f"{filename}: 未找到完整的 {shape_name}，疑似表格只截到半截")

    for left_idx, (left_table_index, left_bbox) in enumerate(bboxes):
        for right_table_index, right_bbox in bboxes[left_idx + 1 :]:
            left_area = bbox_area(left_bbox)
            right_area = bbox_area(right_bbox)
            if left_area <= 0 or right_area <= 0:
                continue

            intersection = bbox_intersection(left_bbox, right_bbox)
            if intersection <= 0:
                continue

            iou = bbox_iou(left_bbox, right_bbox)
            containment = intersection / min(left_area, right_area)
            area_ratio = max(left_area, right_area) / min(left_area, right_area)
            if iou >= DUPLICATE_IOU_THRESHOLD:
                errors.append(
                    f"{filename}: 表格 {left_table_index} 和 {right_table_index} IoU={iou:.2f}，疑似重复"
                )
            if containment >= EXCESSIVE_OVERLAP_THRESHOLD and iou >= EXCESSIVE_OVERLAP_IOU_THRESHOLD:
                errors.append(
                    f"{filename}: 表格 {left_table_index} 和 {right_table_index} 重叠占小框 {containment:.2f}，疑似边界拆分过宽"
                )
            if containment >= CONTAINMENT_THRESHOLD and area_ratio >= CONTAINMENT_AREA_RATIO:
                errors.append(
                    f"{filename}: 表格 {left_table_index} 和 {right_table_index} 包含率={containment:.2f}，疑似大框包含小框"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 Paddle 表格裁剪 manifest，检查少检、过检、重复和包含框。")
    parser.add_argument(
        "--manifest-dir",
        default=str(Path(__file__).resolve().parents[1] / "tmp" / "table_crop_debug"),
        help="包含 *_manifest.json 的目录",
    )
    args = parser.parse_args()

    manifest_dir = Path(args.manifest_dir)
    manifest_paths = sorted(manifest_dir.glob("*_manifest.json"))
    if not manifest_paths:
        print(f"没有找到 manifest: {manifest_dir}")
        return 2

    all_errors: List[str] = []
    for manifest_path in manifest_paths:
        errors = validate_manifest(manifest_path)
        if errors:
            all_errors.extend(errors)
        else:
            print(f"OK: {manifest_path.name}")

    if all_errors:
        print("\n回归校验失败：")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("\n回归校验通过：未发现少检、过检、重复或包含框。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
