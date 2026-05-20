from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


BBox = Tuple[int, int, int, int]

EXPECTED_SAMPLE_RANGES = {
    "02.194": (6, 12),
    "03.276": (4, 12),
    "14.751": (10, 16),
    "25.918": (3, 12),
}

REQUIRED_ZONE_COVERAGE = {
    "03.276": [
        ("左侧/底部边缘表格带", (0.04, 0.50, 0.70, 0.98)),
    ],
    "14.751": [
        ("底部左侧明细表", (0.04, 0.70, 0.45, 0.98)),
        ("底部中部明细表", (0.35, 0.62, 0.75, 0.98)),
    ],
}

MAX_AREA_RATIO = 0.55
DUPLICATE_IOU_THRESHOLD = 0.72
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


def ratio_bbox(ratios: Tuple[float, float, float, float], page_size: Tuple[int, int]) -> BBox:
    width, height = page_size
    x1, y1, x2, y2 = ratios
    return (int(width * x1), int(height * y1), int(width * x2), int(height * y2))


def covers_zone(bbox: BBox, zone: BBox) -> bool:
    intersection = bbox_intersection(bbox, zone)
    if intersection <= 0:
        return False
    return intersection / min(bbox_area(bbox), bbox_area(zone)) >= 0.18


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

    if page_sizes and bboxes:
        first_page_size = page_sizes[min(page_sizes)]
        for zone_name, zone_ratios in required_zones(filename):
            zone_bbox = ratio_bbox(zone_ratios, first_page_size)
            if not any(covers_zone(bbox, zone_bbox) for _, bbox in bboxes):
                errors.append(f"{filename}: 未覆盖关键区域「{zone_name}」，疑似边缘表格漏检")

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
