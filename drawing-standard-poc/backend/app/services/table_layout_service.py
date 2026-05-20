from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable as IterableABC
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4


BBox = Tuple[int, int, int, int]


class TableLayoutService:
    """
    图纸表格识别与精确裁剪服务。

    核心策略：
    1. 使用版面模型找到候选表格区域。
    2. 对候选区域外扩后做图像线条检测，收紧到真实表格边框。
    3. 线条检测失败时回退到模型 bbox，保证流程可用。
    """

    DEFAULT_RENDER_SCALE = 2.0
    DEFAULT_DETECT_SCORE = 0.45
    DEFAULT_CROP_PADDING = 16
    DEFAULT_REFINE_PADDING = 8
    MIN_TABLE_SIDE = 16
    MIN_LINE_COMPONENT_AREA_RATIO = 0.004
    MAX_TABLE_AREA_RATIO = 0.55
    CONTAINER_AREA_RATIO = 0.16
    CONTAINER_HEIGHT_RATIO = 0.62
    WHOLE_PAGE_SIDE_RATIO = 0.88
    DUPLICATE_IOU_THRESHOLD = 0.72
    CONTAINMENT_THRESHOLD = 0.90
    EDGE_FALLBACK_IOU_THRESHOLD = 0.55
    TABLE_LABEL_KEYWORDS = ("table", "表格")

    def __init__(self, base_dir: Optional[Path] = None, layout_engine: Any = None):
        self.base_dir = base_dir or Path(__file__).resolve().parents[2] / "tmp"
        self.upload_dir = self.base_dir / "uploads"
        self.page_images_dir = self.base_dir / "page_images"
        self.table_blocks_dir = self.base_dir / "table_blocks"
        self.markdown_dir = self.base_dir / "markdown"
        self._layout_engine = layout_engine

        for directory in (
            self.upload_dir,
            self.page_images_dir,
            self.table_blocks_dir,
            self.markdown_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def layout_engine(self):
        if self._layout_engine is None:
            self._layout_engine = self._create_layout_engine()
        return self._layout_engine

    def extract_tables_from_uploaded_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        score_threshold: float = DEFAULT_DETECT_SCORE,
        render_scale: float = DEFAULT_RENDER_SCALE,
        crop_padding: int = DEFAULT_CROP_PADDING,
        refine_padding: int = DEFAULT_REFINE_PADDING,
        enable_line_fallback: bool = False,
    ) -> Dict[str, Any]:
        """上传 PDF 的主入口，返回候选表格 bbox 与裁剪图片。"""
        if not pdf_bytes:
            raise ValueError("上传文件内容为空")
        if not filename.lower().endswith(".pdf"):
            raise ValueError("仅支持 PDF 文件")

        score_threshold = self._normalize_ratio(score_threshold, "score_threshold")
        render_scale = self._normalize_render_scale(render_scale)
        crop_padding = self._normalize_pixel(crop_padding, "crop_padding", max_value=512)
        refine_padding = self._normalize_pixel(refine_padding, "refine_padding", max_value=128)

        task_id = uuid4().hex[:12]
        pdf_path = self._save_pdf(pdf_bytes, filename, task_id)
        return self.extract_tables_from_pdf_path(
            pdf_path=pdf_path,
            task_id=task_id,
            filename=filename,
            score_threshold=score_threshold,
            render_scale=render_scale,
            crop_padding=crop_padding,
            refine_padding=refine_padding,
            enable_line_fallback=enable_line_fallback,
        )

    def extract_tables_from_pdf_path(
        self,
        pdf_path: Path,
        task_id: Optional[str] = None,
        filename: Optional[str] = None,
        score_threshold: float = DEFAULT_DETECT_SCORE,
        render_scale: float = DEFAULT_RENDER_SCALE,
        crop_padding: int = DEFAULT_CROP_PADDING,
        refine_padding: int = DEFAULT_REFINE_PADDING,
        enable_line_fallback: bool = False,
    ) -> Dict[str, Any]:
        """本地 PDF 路径入口，便于离线验证和单元测试。"""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        task_id = task_id or uuid4().hex[:12]
        task_page_dir = self.page_images_dir / task_id
        task_table_dir = self.table_blocks_dir / task_id
        task_page_dir.mkdir(parents=True, exist_ok=True)
        task_table_dir.mkdir(parents=True, exist_ok=True)

        page_images: List[Dict[str, Any]] = []
        all_tables: List[Dict[str, Any]] = []

        for page_idx, page_image, page_meta in self._iter_pdf_pages(pdf_path, render_scale):
            page_path = task_page_dir / f"page_{page_idx:03d}.png"
            page_image.save(page_path)
            page_images.append(
                {
                    "page": page_idx,
                    "image_path": str(page_path),
                    "width": page_meta["width"],
                    "height": page_meta["height"],
                    "pdf_width": page_meta["pdf_width"],
                    "pdf_height": page_meta["pdf_height"],
                    "render_scale": render_scale,
                }
            )

            tables = self._detect_tables_on_page(
                page_image=page_image,
                page_image_path=page_path,
                page_idx=page_idx,
                task_table_dir=task_table_dir,
                score_threshold=score_threshold,
                crop_padding=crop_padding,
                refine_padding=refine_padding,
                enable_line_fallback=enable_line_fallback,
            )
            all_tables.extend(tables)

        return {
            "task_id": task_id,
            "filename": Path(filename or pdf_path.name).name,
            "pdf_path": str(pdf_path),
            "render_scale": render_scale,
            "score_threshold": score_threshold,
            "crop_padding": crop_padding,
            "refine_padding": refine_padding,
            "enable_line_fallback": enable_line_fallback,
            "total_pages": len(page_images),
            "total_tables": len(all_tables),
            "page_images": page_images,
            "tables": all_tables,
        }

    def _create_layout_engine(self):
        from paddleocr import LayoutDetection

        return LayoutDetection(model_name="PP-DocLayout_plus-L")

    def _save_pdf(self, pdf_bytes: bytes, filename: str, task_id: str) -> Path:
        safe_name = self._safe_stem(filename)
        save_path = self.upload_dir / f"{safe_name}_{task_id}.pdf"
        save_path.write_bytes(pdf_bytes)
        return save_path

    def _iter_pdf_pages(self, pdf_path: Path, render_scale: float):
        try:
            import fitz  # PyMuPDF
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("缺少 PDF 渲染依赖，请先安装 PyMuPDF 和 Pillow") from exc

        doc = fitz.open(pdf_path)
        try:
            matrix = fitz.Matrix(render_scale, render_scale)
            for page_idx, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                yield (
                    page_idx,
                    image,
                    {
                        "width": image.width,
                        "height": image.height,
                        "pdf_width": float(page.rect.width),
                        "pdf_height": float(page.rect.height),
                    },
                )
        finally:
            doc.close()

    def _detect_tables_on_page(
        self,
        page_image: Image.Image,
        page_image_path: Path,
        page_idx: int,
        task_table_dir: Path,
        score_threshold: float,
        crop_padding: int,
        refine_padding: int,
        enable_line_fallback: bool,
    ) -> List[Dict[str, Any]]:
        output = self.layout_engine.predict(
            input=str(page_image_path),
            batch_size=1,
            layout_nms=True,
        )

        tables: List[Dict[str, Any]] = []
        boxes = self._normalize_layout_boxes(output)
        for box in boxes:
            label = str(box.get("label") or "")
            score = self._to_float(box.get("score"), 0.0)
            if not self._is_table_candidate(label, score, score_threshold):
                continue

            raw_bbox = self._clip_bbox(
                box.get("coordinate"),
                image_size=page_image.size,
                padding=0,
            )
            if raw_bbox is None:
                continue

            if self._is_whole_page_like(raw_bbox, page_image.size):
                continue

            if self._is_container_like(raw_bbox, page_image.size):
                split_bboxes = self._split_container_bbox(page_image, raw_bbox, refine_padding)
                if split_bboxes:
                    for split_bbox in split_bboxes:
                        self._append_table_crop(
                            tables=tables,
                            page_image=page_image,
                            page_idx=page_idx,
                            task_table_dir=task_table_dir,
                            page_image_path=page_image_path,
                            bbox=split_bbox,
                            label=f"{label}_split",
                            score=score,
                            model_bbox=raw_bbox,
                            padded_bbox=raw_bbox,
                            refine_method="container_split",
                        )
                    continue

            padded_bbox = self._expand_bbox(raw_bbox, page_image.size, crop_padding)
            precise_bbox, refine_method = self._refine_table_bbox(page_image, padded_bbox, refine_padding)
            crop_bbox = precise_bbox or padded_bbox

            if crop_bbox[2] - crop_bbox[0] < self.MIN_TABLE_SIDE or crop_bbox[3] - crop_bbox[1] < self.MIN_TABLE_SIDE:
                continue

            self._append_table_crop(
                tables=tables,
                page_image=page_image,
                page_idx=page_idx,
                task_table_dir=task_table_dir,
                page_image_path=page_image_path,
                bbox=crop_bbox,
                label=label,
                score=score,
                model_bbox=raw_bbox,
                padded_bbox=padded_bbox,
                refine_method=refine_method,
            )

        if enable_line_fallback:
            for line_bbox in self._detect_line_table_bboxes(page_image, refine_padding=refine_padding):
                if any(self._bbox_iou(line_bbox, tuple(table["bbox"])) >= self.DUPLICATE_IOU_THRESHOLD for table in tables):
                    continue
                self._append_table_crop(
                    tables=tables,
                    page_image=page_image,
                    page_idx=page_idx,
                    task_table_dir=task_table_dir,
                    page_image_path=page_image_path,
                    bbox=line_bbox,
                    label="line_table_candidate",
                    score=0.0,
                    model_bbox=None,
                    padded_bbox=None,
                    refine_method="line_component",
                )

        for edge_bbox in self._detect_edge_table_bboxes(page_image, refine_padding=refine_padding):
            if any(self._bbox_iou(edge_bbox, tuple(table["bbox"])) >= self.EDGE_FALLBACK_IOU_THRESHOLD for table in tables):
                continue
            self._append_table_crop(
                tables=tables,
                page_image=page_image,
                page_idx=page_idx,
                task_table_dir=task_table_dir,
                page_image_path=page_image_path,
                bbox=edge_bbox,
                label="edge_table_candidate",
                score=0.0,
                model_bbox=None,
                padded_bbox=None,
                refine_method="edge_grid",
            )

        tables = self._remove_duplicate_or_contained_tables(tables)
        return self._save_table_crops(
            tables=tables,
            page_image=page_image,
            page_idx=page_idx,
            task_table_dir=task_table_dir,
            page_image_path=page_image_path,
        )

    def _append_table_crop(
        self,
        tables: List[Dict[str, Any]],
        page_image: Any,
        page_idx: int,
        task_table_dir: Path,
        page_image_path: Path,
        bbox: BBox,
        label: str,
        score: float,
        model_bbox: Optional[BBox],
        padded_bbox: Optional[BBox],
        refine_method: str,
    ) -> None:
        tables.append(
            {
                "label": label,
                "score": score,
                "bbox": list(bbox),
                "model_bbox": list(model_bbox) if model_bbox else None,
                "padded_bbox": list(padded_bbox) if padded_bbox else None,
                "refine_method": refine_method,
                "width": bbox[2] - bbox[0],
                "height": bbox[3] - bbox[1],
            }
        )

    def _save_table_crops(
        self,
        tables: List[Dict[str, Any]],
        page_image: Any,
        page_idx: int,
        task_table_dir: Path,
        page_image_path: Path,
    ) -> List[Dict[str, Any]]:
        finalized: List[Dict[str, Any]] = []
        for table_index, table in enumerate(tables, start=1):
            bbox = tuple(table["bbox"])
            block_name = f"page_{page_idx:03d}_table_{table_index:03d}.png"
            block_path = task_table_dir / block_name
            page_image.crop(bbox).save(block_path)

            finalized.append(
                {
                    **table,
                    "page": page_idx,
                    "table_index": table_index,
                    "table_id": f"p{page_idx:03d}_t{table_index:03d}",
                    "width": bbox[2] - bbox[0],
                    "height": bbox[3] - bbox[1],
                    "image_path": str(block_path),
                    "source_page_image": str(page_image_path),
                }
            )
        return finalized

    def _normalize_layout_boxes(self, output: Any) -> List[Dict[str, Any]]:
        boxes: List[Any] = []
        for item in self._as_sequence(output):
            boxes.extend(self._extract_boxes(item))
        return [box for box in (self._normalize_box(raw_box) for raw_box in boxes) if box]

    def _extract_boxes(self, value: Any) -> List[Any]:
        value = self._to_plain_data(value)
        if isinstance(value, list):
            boxes: List[Any] = []
            for item in value:
                boxes.extend(self._extract_boxes(item))
            return boxes

        if not isinstance(value, dict):
            return []

        direct_boxes = value.get("boxes")
        if isinstance(direct_boxes, list):
            return direct_boxes

        for key in ("res", "result", "data", "layout_result", "layout"):
            nested_boxes = self._extract_boxes(value.get(key))
            if nested_boxes:
                return nested_boxes

        return []

    def _normalize_box(self, raw_box: Any) -> Optional[Dict[str, Any]]:
        raw_box = self._to_plain_data(raw_box)
        if not isinstance(raw_box, dict):
            return None

        coordinate = self._first_present(raw_box, ("coordinate", "bbox", "box", "points"))
        if coordinate is None:
            return None

        return {
            "label": str(self._first_present(raw_box, ("label", "category", "class_name", "name", "type")) or ""),
            "score": self._to_float(self._first_present(raw_box, ("score", "confidence", "prob")), 0.0),
            "coordinate": coordinate,
        }

    def _refine_table_bbox(
        self,
        page_image: Image.Image,
        candidate_bbox: BBox,
        refine_padding: int,
    ) -> Tuple[Optional[BBox], str]:
        """
        在模型候选框内部寻找真实表格线边界。

        返回 None 表示图像线条证据不足，调用方应回退到 padded bbox。
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            return None, "model_bbox_fallback_no_cv2"

        x1, y1, x2, y2 = candidate_bbox
        crop = page_image.crop(candidate_bbox)
        crop_np = np.array(crop.convert("RGB"))
        gray = cv2.cvtColor(crop_np, cv2.COLOR_RGB2GRAY)

        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            12,
        )

        height, width = binary.shape[:2]
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, width // 45), 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, height // 45)))
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=1)
        table_lines = cv2.bitwise_or(horizontal, vertical)
        table_lines = cv2.dilate(table_lines, np.ones((3, 3), dtype=np.uint8), iterations=1)

        contour_bbox = self._largest_contour_bbox(table_lines, min_area_ratio=0.01)
        projection_bbox = self._projection_bbox(table_lines)
        local_bbox = self._merge_refined_bboxes(contour_bbox, projection_bbox)
        if local_bbox is None:
            return None, "model_bbox_fallback_no_lines"

        lx1, ly1, lx2, ly2 = local_bbox
        refined = self._clip_absolute_bbox(
            (
                x1 + lx1 - refine_padding,
                y1 + ly1 - refine_padding,
                x1 + lx2 + refine_padding,
                y1 + ly2 + refine_padding,
            ),
            page_image.size,
        )

        if not self._is_reasonable_refined_bbox(refined, candidate_bbox):
            return None, "model_bbox_fallback_unreasonable_refine"

        return refined, "line_refine"

    def _detect_line_table_bboxes(self, page_image: Any, refine_padding: int) -> List[BBox]:
        """从整页表格线中找局部表格候选，弥补 Paddle 把整页误判成 table 的情况。"""
        try:
            import cv2
            import numpy as np
        except ImportError:
            return []

        crop_np = np.array(page_image.convert("RGB"))
        gray = cv2.cvtColor(crop_np, cv2.COLOR_RGB2GRAY)
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            12,
        )
        height, width = binary.shape[:2]
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(18, width // 70), 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(18, height // 70)))
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=1)
        table_lines = cv2.bitwise_or(horizontal, vertical)
        table_lines = cv2.dilate(table_lines, np.ones((3, 3), dtype=np.uint8), iterations=1)

        contours, _ = cv2.findContours(table_lines, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        page_area = width * height
        candidates: List[BBox] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            bbox = self._clip_absolute_bbox(
                (x - refine_padding, y - refine_padding, x + w + refine_padding, y + h + refine_padding),
                page_image.size,
            )
            area_ratio = self._bbox_area(bbox) / page_area if page_area else 0
            if area_ratio < self.MIN_LINE_COMPONENT_AREA_RATIO or area_ratio > self.MAX_TABLE_AREA_RATIO:
                continue
            if bbox[2] - bbox[0] < 80 or bbox[3] - bbox[1] < 50:
                continue
            if self._is_whole_page_like(bbox, page_image.size):
                continue
            candidates.append(bbox)

        return self._dedupe_bboxes(sorted(candidates, key=self._bbox_area, reverse=True))

    def _detect_edge_table_bboxes(self, page_image: Any, refine_padding: int) -> List[BBox]:
        """只在工程图常见边缘表格带中补漏，避免整页扫线造成大量过检。"""
        try:
            import cv2
            import numpy as np
        except ImportError:
            return []

        crop_np = np.array(page_image.convert("RGB"))
        gray = cv2.cvtColor(crop_np, cv2.COLOR_RGB2GRAY)
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            12,
        )
        height, width = binary.shape[:2]
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(28, width // 90), 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(22, height // 100)))
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=1)
        table_lines = cv2.bitwise_or(horizontal, vertical)
        table_lines = cv2.dilate(table_lines, np.ones((5, 5), dtype=np.uint8), iterations=1)

        zones = [
            self._ratio_bbox((0.04, 0.50, 0.98, 0.98), page_image.size),  # bottom table band
            self._ratio_bbox((0.58, 0.02, 0.98, 0.98), page_image.size),  # right table/title band
            self._ratio_bbox((0.00, 0.02, 0.20, 0.98), page_image.size),  # left border/title strip
        ]

        page_area = width * height
        candidates: List[BBox] = []
        for zone in zones:
            zx1, zy1, zx2, zy2 = zone
            zone_mask = table_lines[zy1:zy2, zx1:zx2]
            contours, _ = cv2.findContours(zone_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                bbox = self._clip_absolute_bbox(
                    (
                        zx1 + x - refine_padding,
                        zy1 + y - refine_padding,
                        zx1 + x + w + refine_padding,
                        zy1 + y + h + refine_padding,
                    ),
                    page_image.size,
                )
                area_ratio = self._bbox_area(bbox) / page_area if page_area else 0
                if area_ratio < 0.0025 or area_ratio > 0.24:
                    continue
                if bbox[2] - bbox[0] < 130 or bbox[3] - bbox[1] < 70:
                    continue
                if self._is_whole_page_like(bbox, page_image.size):
                    continue
                if not self._has_table_grid_signature(horizontal, vertical, bbox):
                    continue
                candidates.append(bbox)

        return self._dedupe_bboxes(sorted(candidates, key=self._bbox_area, reverse=True))

    def _has_table_grid_signature(self, horizontal: Any, vertical: Any, bbox: BBox) -> bool:
        try:
            import cv2
            import numpy as np
        except ImportError:
            return False

        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        if width <= 0 or height <= 0:
            return False

        local_h = horizontal[y1:y2, x1:x2]
        local_v = vertical[y1:y2, x1:x2]
        row_hits = np.where(local_h.sum(axis=1) >= 255 * width * 0.16)[0]
        col_hits = np.where(local_v.sum(axis=0) >= 255 * height * 0.12)[0]
        row_spans = self._merge_indices_to_spans(row_hits)
        col_spans = self._merge_indices_to_spans(col_hits)
        if len(row_spans) < 3 or len(col_spans) < 3:
            return False

        intersection = cv2.bitwise_and(
            cv2.dilate(local_h, np.ones((3, 3), dtype=np.uint8), iterations=1),
            cv2.dilate(local_v, np.ones((3, 3), dtype=np.uint8), iterations=1),
        )
        intersection_count = int((intersection > 0).sum())
        min_intersections = max(24, len(row_spans) * len(col_spans) // 4)
        return intersection_count >= min_intersections

    def _split_container_bbox(self, page_image: Any, container_bbox: BBox, refine_padding: int) -> List[BBox]:
        """把右侧整列/大容器框按表格线间距拆成较少的主表格块。"""
        try:
            import cv2
            import numpy as np
        except ImportError:
            return []

        x1, y1, x2, y2 = container_bbox
        crop = page_image.crop(container_bbox)
        crop_np = np.array(crop.convert("RGB"))
        gray = cv2.cvtColor(crop_np, cv2.COLOR_RGB2GRAY)
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            12,
        )
        height, width = binary.shape[:2]
        if width <= 0 or height <= 0:
            return []

        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(24, width // 8), 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(18, height // 70)))
        horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
        vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=1)

        row_threshold = 255 * width * 0.22
        row_hits = np.where(horizontal.sum(axis=1) >= row_threshold)[0]
        line_spans = self._merge_indices_to_spans(row_hits)
        if len(line_spans) < 3:
            return []

        split_gap = max(120, int(height * 0.035))
        groups: List[List[Tuple[int, int]]] = []
        current = [line_spans[0]]
        for span in line_spans[1:]:
            gap = span[0] - current[-1][1]
            if gap > split_gap:
                groups.append(current)
                current = [span]
            else:
                current.append(span)
        groups.append(current)

        candidates: List[BBox] = []
        for group in groups:
            if len(group) < 3:
                continue
            local_y1 = max(0, group[0][0] - refine_padding)
            local_y2 = min(height, group[-1][1] + refine_padding)
            if local_y2 - local_y1 < 60:
                continue

            vertical_slice = vertical[local_y1:local_y2, :]
            col_threshold = 255 * max(1, local_y2 - local_y1) * 0.12
            col_hits = np.where(vertical_slice.sum(axis=0) >= col_threshold)[0]
            if len(col_hits) > 0:
                local_x1 = max(0, int(col_hits[0]) - refine_padding)
                local_x2 = min(width, int(col_hits[-1]) + refine_padding)
            else:
                local_x1, local_x2 = 0, width

            bbox = self._clip_absolute_bbox(
                (x1 + local_x1, y1 + local_y1, x1 + local_x2, y1 + local_y2),
                page_image.size,
            )
            if self._bbox_area(bbox) < self._bbox_area(container_bbox) * 0.03:
                continue
            if self._is_whole_page_like(bbox, page_image.size):
                continue
            candidates.append(bbox)

        return self._dedupe_bboxes(candidates)

    def _merge_indices_to_spans(self, indices: Any) -> List[Tuple[int, int]]:
        values = [int(value) for value in indices]
        if not values:
            return []

        spans: List[Tuple[int, int]] = []
        start = previous = values[0]
        for value in values[1:]:
            if value <= previous + 1:
                previous = value
                continue
            spans.append((start, previous + 1))
            start = previous = value
        spans.append((start, previous + 1))
        return spans

    def _largest_contour_bbox(self, mask: Any, min_area_ratio: float) -> Optional[BBox]:
        import cv2

        height, width = mask.shape[:2]
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        min_area = width * height * min_area_ratio
        best_bbox: Optional[BBox] = None
        best_area = 0
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area > best_area and area >= min_area and w >= self.MIN_TABLE_SIDE and h >= self.MIN_TABLE_SIDE:
                best_area = area
                best_bbox = (x, y, x + w, y + h)
        return best_bbox

    def _projection_bbox(self, mask: Any) -> Optional[BBox]:
        import numpy as np

        row_hits = np.where(mask.sum(axis=1) > 0)[0]
        col_hits = np.where(mask.sum(axis=0) > 0)[0]
        if len(row_hits) == 0 or len(col_hits) == 0:
            return None

        return (
            int(col_hits[0]),
            int(row_hits[0]),
            int(col_hits[-1]) + 1,
            int(row_hits[-1]) + 1,
        )

    def _merge_refined_bboxes(self, first: Optional[BBox], second: Optional[BBox]) -> Optional[BBox]:
        candidates = [bbox for bbox in (first, second) if bbox is not None]
        if not candidates:
            return None
        return (
            min(bbox[0] for bbox in candidates),
            min(bbox[1] for bbox in candidates),
            max(bbox[2] for bbox in candidates),
            max(bbox[3] for bbox in candidates),
        )

    def _is_reasonable_refined_bbox(self, refined: BBox, candidate: BBox) -> bool:
        refined_area = self._bbox_area(refined)
        candidate_area = self._bbox_area(candidate)
        if refined_area <= 0 or candidate_area <= 0:
            return False
        if refined_area < candidate_area * 0.08:
            return False
        if refined[2] - refined[0] < self.MIN_TABLE_SIDE or refined[3] - refined[1] < self.MIN_TABLE_SIDE:
            return False
        return True

    def _is_whole_page_like(self, bbox: BBox, image_size: Tuple[int, int]) -> bool:
        image_width, image_height = image_size
        if image_width <= 0 or image_height <= 0:
            return False
        width_ratio = (bbox[2] - bbox[0]) / image_width
        height_ratio = (bbox[3] - bbox[1]) / image_height
        area_ratio = self._bbox_area(bbox) / (image_width * image_height)
        return area_ratio > self.MAX_TABLE_AREA_RATIO or (
            width_ratio > self.WHOLE_PAGE_SIDE_RATIO and height_ratio > self.WHOLE_PAGE_SIDE_RATIO
        )

    def _is_container_like(self, bbox: BBox, image_size: Tuple[int, int]) -> bool:
        image_width, image_height = image_size
        if image_width <= 0 or image_height <= 0:
            return False
        bbox_width = bbox[2] - bbox[0]
        bbox_height = bbox[3] - bbox[1]
        width_ratio = bbox_width / image_width
        height_ratio = bbox_height / image_height
        area_ratio = self._bbox_area(bbox) / (image_width * image_height)
        return (
            area_ratio >= self.CONTAINER_AREA_RATIO
            and height_ratio >= self.CONTAINER_HEIGHT_RATIO
            and width_ratio <= 0.55
        )

    def _remove_duplicate_or_contained_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        keep = [True] * len(tables)
        for i, first in enumerate(tables):
            if not keep[i]:
                continue
            first_bbox = tuple(first["bbox"])
            first_area = self._bbox_area(first_bbox)
            for j in range(i + 1, len(tables)):
                if not keep[j]:
                    continue
                second = tables[j]
                second_bbox = tuple(second["bbox"])
                second_area = self._bbox_area(second_bbox)
                if first_area <= 0 or second_area <= 0:
                    continue

                overlap = self._bbox_intersection(first_bbox, second_bbox)
                if overlap <= 0:
                    continue

                smaller_area = min(first_area, second_area)
                containment = overlap / smaller_area
                iou = overlap / (first_area + second_area - overlap)
                if containment < self.CONTAINMENT_THRESHOLD and iou < self.DUPLICATE_IOU_THRESHOLD:
                    continue

                if first_area > second_area * 1.25:
                    keep[i] = False
                    break
                if second_area > first_area * 1.25:
                    keep[j] = False
                    continue

                first_score = self._to_float(first.get("score"), 0.0)
                second_score = self._to_float(second.get("score"), 0.0)
                if first_score >= second_score:
                    keep[j] = False
                else:
                    keep[i] = False
                    break

        return [table for table, should_keep in zip(tables, keep) if should_keep]

    def _dedupe_bboxes(self, bboxes: List[BBox]) -> List[BBox]:
        kept: List[BBox] = []
        for bbox in bboxes:
            if any(self._bbox_iou(bbox, existing) >= self.DUPLICATE_IOU_THRESHOLD for existing in kept):
                continue
            kept.append(bbox)
        return kept

    def _bbox_iou(self, first: BBox, second: BBox) -> float:
        intersection = self._bbox_intersection(first, second)
        union = self._bbox_area(first) + self._bbox_area(second) - intersection
        if union <= 0:
            return 0.0
        return intersection / union

    def _bbox_intersection(self, first: BBox, second: BBox) -> int:
        x1 = max(first[0], second[0])
        y1 = max(first[1], second[1])
        x2 = min(first[2], second[2])
        y2 = min(first[3], second[3])
        return self._bbox_area((x1, y1, x2, y2))

    def _clip_bbox(self, coordinate: Any, image_size: Tuple[int, int], padding: int) -> Optional[BBox]:
        rect = self._coordinate_to_rect(coordinate)
        if rect is None:
            return None
        return self._clip_absolute_bbox(
            (
                math.floor(rect[0] - padding),
                math.floor(rect[1] - padding),
                math.ceil(rect[2] + padding),
                math.ceil(rect[3] + padding),
            ),
            image_size,
        )

    def _expand_bbox(self, bbox: BBox, image_size: Tuple[int, int], padding: int) -> BBox:
        x1, y1, x2, y2 = bbox
        return self._clip_absolute_bbox((x1 - padding, y1 - padding, x2 + padding, y2 + padding), image_size)

    def _clip_absolute_bbox(self, bbox: Tuple[int, int, int, int], image_size: Tuple[int, int]) -> BBox:
        image_width, image_height = image_size
        x1 = max(0, min(image_width, int(bbox[0])))
        y1 = max(0, min(image_height, int(bbox[1])))
        x2 = max(0, min(image_width, int(bbox[2])))
        y2 = max(0, min(image_height, int(bbox[3])))
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        return left, top, right, bottom

    def _ratio_bbox(self, ratios: Tuple[float, float, float, float], image_size: Tuple[int, int]) -> BBox:
        image_width, image_height = image_size
        x1, y1, x2, y2 = ratios
        return self._clip_absolute_bbox(
            (
                int(image_width * x1),
                int(image_height * y1),
                int(image_width * x2),
                int(image_height * y2),
            ),
            image_size,
        )

    def _coordinate_to_rect(self, coordinate: Any) -> Optional[Tuple[float, float, float, float]]:
        if isinstance(coordinate, (str, bytes)):
            return None

        try:
            values = list(coordinate)
        except TypeError:
            return None

        if len(values) == 4 and all(self._is_number(value) for value in values):
            x1, y1, x2, y2 = [float(value) for value in values]
        elif values and all(self._is_point_like(point) for point in values):
            xs = [float(point[0]) for point in values if self._is_number(point[0])]
            ys = [float(point[1]) for point in values if self._is_number(point[1])]
            if not xs or not ys:
                return None
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        else:
            return None

        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        return left, top, right, bottom

    def _is_table_candidate(self, label: str, score: float, score_threshold: float) -> bool:
        normalized_label = label.lower()
        return score >= score_threshold and any(
            keyword in normalized_label for keyword in self.TABLE_LABEL_KEYWORDS
        )

    def _as_sequence(self, value: Any) -> Iterable[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return value
        if isinstance(value, IterableABC) and not isinstance(value, (dict, str, bytes)):
            return value
        return [value]

    def _to_plain_data(self, value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value

        for attr_name in ("json", "data"):
            if not hasattr(value, attr_name):
                continue
            attr = getattr(value, attr_name)
            attr_value = attr() if callable(attr) else attr
            if isinstance(attr_value, str):
                try:
                    return json.loads(attr_value)
                except json.JSONDecodeError:
                    continue
            if isinstance(attr_value, (dict, list)):
                return attr_value

        if hasattr(value, "to_dict"):
            dict_value = value.to_dict()
            if isinstance(dict_value, (dict, list)):
                return dict_value

        return value

    def _first_present(self, data: Dict[str, Any], keys: Sequence[str]) -> Any:
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        return None

    def _safe_stem(self, filename: str) -> str:
        raw_name = filename.replace("\\", "/").split("/")[-1]
        stem = Path(raw_name).stem.strip() or "upload"
        stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem)
        stem = re.sub(r"\s+", "_", stem).strip("._")
        return (stem or "upload")[:80]

    def _normalize_ratio(self, value: float, name: str) -> float:
        normalized = self._to_float(value, self.DEFAULT_DETECT_SCORE)
        if normalized < 0 or normalized > 1:
            raise ValueError(f"{name} 必须在 0 到 1 之间")
        return normalized

    def _normalize_render_scale(self, value: float) -> float:
        normalized = self._to_float(value, self.DEFAULT_RENDER_SCALE)
        if normalized <= 0 or normalized > 6:
            raise ValueError("render_scale 必须大于 0 且不超过 6")
        return normalized

    def _normalize_pixel(self, value: int, name: str, max_value: int) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} 必须是整数") from None
        if normalized < 0 or normalized > max_value:
            raise ValueError(f"{name} 必须在 0 到 {max_value} 像素之间")
        return normalized

    def _bbox_area(self, bbox: BBox) -> int:
        return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])

    def _to_float(self, value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _is_number(self, value: Any) -> bool:
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False

    def _is_point_like(self, value: Any) -> bool:
        if isinstance(value, (str, bytes)):
            return False
        try:
            return len(value) >= 2
        except TypeError:
            return False


table_layout_service = TableLayoutService()
