from __future__ import annotations

import inspect
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import fitz
import numpy as np
from PIL import Image, ImageDraw

# ============================================
# 禁用 oneDNN/PIR，避免 Paddle 3.x 运行时转换错误
# 必须在导入任何 Paddle 相关模块之前设置
# ============================================
os.environ.setdefault("FLAGS_use_onednn", "0")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
os.environ.setdefault("FLAGS_trt_disable_tensorrt", "1")

# Disable oneDNN/PIR paths by default to avoid Paddle 3.3.x runtime conversion issues.
os.environ.setdefault("FLAGS_use_onednn", "0")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")

CATEGORY_COLORS: Dict[str, tuple[int, int, int]] = {
    "text": (0, 255, 0),
    "title": (255, 140, 0),
    "figure": (255, 0, 255),
    "table": (30, 144, 255),
    "formula": (220, 20, 60),
    "chart": (255, 215, 0),
    "seal": (255, 105, 180),
    "paragraph_title": (128, 0, 128),
    "doc_title": (0, 0, 139),
    "page_number": (128, 128, 128),
    "header": (0, 128, 128),
    "footer": (0, 128, 128),
    "reference": (107, 142, 35),
    "content": (255, 228, 181),
    "image": (255, 0, 255),
    "ocr": (0, 255, 127),
    "other": (192, 192, 192),
}


class TableLayoutService4Batch:
    """Batch tester copied from service4 with multi-parameter experiment support."""

    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parents[2] / "tmp"
        self.page_images_dir = self.base_dir / "page_images"
        self.table_blocks_dir = self.base_dir / "table_blocks"
        self.page_images_dir.mkdir(parents=True, exist_ok=True)
        self.table_blocks_dir.mkdir(parents=True, exist_ok=True)

        default_models_root = Path(r"D:\work\Develop\conda_envs\.paddlex\official_models")
        self.local_models_root = Path(os.getenv("PADDLEOCR_LOCAL_MODELS_ROOT", str(default_models_root)))
        self.layout_model_name = os.getenv("PADDLEOCR_LAYOUT_MODEL_NAME", "PP-DocLayout_plus-L")
        self.layout_model_dir = self._resolve_layout_model_dir()

        self.default_render_zoom = float(os.getenv("PADDLEOCR_VL_RENDER_ZOOM", "4.17"))
        self.default_max_pages = int(os.getenv("PADDLEOCR_VL_MAX_PAGES", "1"))
        self.infer_max_side = int(os.getenv("PADDLEOCR_VL_INFER_MAX_SIDE", "2900"))

        self.use_doc_orientation_classify = self._read_bool_env(
            "PADDLEOCR_VL_USE_DOC_ORIENTATION_CLASSIFY",
            default=False,
        )
        self.use_doc_unwarping = self._read_bool_env(
            "PADDLEOCR_VL_USE_DOC_UNWARPING",
            default=False,
        )
        self.use_layout_detection = self._read_bool_env(
            "PADDLEOCR_VL_USE_LAYOUT_DETECTION",
            default=True,
        )
        self.use_chart_recognition = self._read_bool_env(
            "PADDLEOCR_VL_USE_CHART_RECOGNITION",
            default=False,
        )
        self.enable_vl = self._read_bool_env("PADDLEOCR_VL_ENABLE", default=False)

        # Stable table postprocess knobs.
        self.table_min_area_ratio = float(os.getenv("PADDLEOCR_TABLE_MIN_AREA_RATIO", "0.0010"))
        self.table_max_area_ratio = float(os.getenv("PADDLEOCR_TABLE_MAX_AREA_RATIO", "0.80"))
        # Debug threshold: only keep tables with score > 0.5.
        self.table_min_score = 0.5
        self.table_split_gap_ratio = float(os.getenv("PADDLEOCR_TABLE_SPLIT_GAP_RATIO", "0.10"))
        self.table_min_segment_height_ratio = float(os.getenv("PADDLEOCR_TABLE_MIN_SEGMENT_RATIO", "0.12"))

        self.pipeline: Any | None = None
        self.pipeline_name: str | None = None
        self._safe_retry_done = False

    def export_annotated_from_pdf_path(
            self,
            pdf_path: Path | str,
            render_zoom: float | None = None,
            max_pages: int | None = None,
            task_id: str | None = None,
    ) -> Dict[str, Any]:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF is supported")

        if task_id is None:
            task_id = uuid4().hex[:12]
        if render_zoom is None:
            render_zoom = self.default_render_zoom
        if max_pages is None:
            max_pages = self.default_max_pages

        self._ensure_pipeline()

        print("[testP] [1/4] converting PDF pages to images...")
        t0 = time.perf_counter()
        page_images = self._pdf_to_images(pdf_path, zoom=render_zoom)
        if max_pages > 0:
            page_images = page_images[:max_pages]
        print(f"[testP] rendered {len(page_images)} page(s) in {time.perf_counter() - t0:.2f}s")

        pages_dir = self.page_images_dir / task_id / "paddleocr_vl_pages"
        debug_dir = self.table_blocks_dir / task_id / "paddleocr_vl_debug"
        pages_dir.mkdir(parents=True, exist_ok=True)
        debug_dir.mkdir(parents=True, exist_ok=True)

        pages: List[Dict[str, Any]] = []
        for page_idx, page_img in enumerate(page_images, start=1):
            page_png_path = pages_dir / f"page_{page_idx:03d}.png"
            page_img.save(page_png_path)
            infer_img_path = self._prepare_infer_image(page_png_path)

            print(f"[testP] [2/4] page {page_idx}: image saved -> {infer_img_path}")
            t1 = time.perf_counter()
            result = self._predict_single_page(infer_img_path)
            print(f"[testP] [3/4] page {page_idx}: layout parsed in {time.perf_counter() - t1:.2f}s")

            boxes = self._extract_layout_boxes(result)
            boxes = self._postprocess_table_boxes(boxes, infer_img_path)

            annotated_path = debug_dir / f"page_{page_idx:03d}_annotated.png"
            draw_boxes = self._scale_boxes_to_output(
                boxes=boxes,
                src_image_path=infer_img_path,
                dst_image_path=page_png_path,
            )
            self._draw_annotation(page_png_path, draw_boxes, annotated_path)

            table_crops_dir = debug_dir / f"page_{page_idx:03d}_tables"
            table_crop_paths = self._save_table_crops_from_boxes(
                page_image_path=page_png_path,
                boxes=draw_boxes,
                out_dir=table_crops_dir,
                page_idx=page_idx,
            )

            print(f"[testP] [4/4] page {page_idx}: annotated image -> {annotated_path}")

            pages.append(
                {
                    "page": page_idx,
                    "saved_page_image_path": str(page_png_path),
                    "infer_image_path": str(infer_img_path),
                    "annotation_image_path": str(annotated_path),
                    "table_crops_dir": str(table_crops_dir),
                    "table_crop_paths": table_crop_paths,
                    "detected_tables": len(table_crop_paths),
                    "detected_blocks": len(boxes),
                }
            )

        return {
            "task_id": task_id,
            "pdf_path": str(pdf_path),
            "total_pages": len(page_images),
            "render_zoom": render_zoom,
            "infer_max_side": self.infer_max_side,
            "pipeline": self.pipeline_name,
            "page_images_dir": str(pages_dir),
            "debug_dir": str(debug_dir),
            "pages": pages,
        }

    def run_multi_combo_experiment(
            self,
            pdf_path: Path | str,
            zoom_values: List[float],
            infer_max_side_values: List[int],
            max_pages: int = 1,
            task_id: str | None = None,
    ) -> Dict[str, Any]:
        """Run all zoom/max_side combinations and save all outputs into one directory."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF is supported")

        if task_id is None:
            task_id = uuid4().hex[:12]

        self._ensure_pipeline()

        pages_root_dir = self.page_images_dir / task_id / "paddleocr_vl_pages"
        debug_root_dir = self.table_blocks_dir / task_id / "paddleocr_vl_debug"
        pages_root_dir.mkdir(parents=True, exist_ok=True)
        debug_root_dir.mkdir(parents=True, exist_ok=True)

        combos: List[Dict[str, Any]] = []
        for zoom in zoom_values:
            for max_side in infer_max_side_values:
                combos.append({"zoom": float(zoom), "infer_max_side": int(max_side)})

        all_results: List[Dict[str, Any]] = []
        original_max_side = self.infer_max_side

        try:
            for i, cfg in enumerate(combos, start=1):
                zoom = cfg["zoom"]
                max_side = cfg["infer_max_side"]
                self.infer_max_side = max_side

                combo_tag = self._combo_tag(zoom, max_side)
                print(f"\n[testP] [{i}/{len(combos)}] combo={combo_tag} start")
                use_combo_subdir = len(combos) > 1
                pages_dir = pages_root_dir / combo_tag if use_combo_subdir else pages_root_dir
                debug_dir = debug_root_dir / combo_tag if use_combo_subdir else debug_root_dir
                pages_dir.mkdir(parents=True, exist_ok=True)
                debug_dir.mkdir(parents=True, exist_ok=True)

                page_images = self._pdf_to_images(pdf_path, zoom=zoom)
                if max_pages > 0:
                    page_images = page_images[:max_pages]

                combo_summary: Dict[str, Any] = {
                    "combo": combo_tag,
                    "zoom": zoom,
                    "infer_max_side": max_side,
                    "pipeline": self.pipeline_name,
                    "pages": [],
                }

                for page_idx, page_img in enumerate(page_images, start=1):
                    page_png_path = pages_dir / f"page_{page_idx:03d}.png"
                    page_img.save(page_png_path)

                    infer_img_path = self._prepare_infer_image(page_png_path)
                    result = self._predict_single_page(infer_img_path)
                    boxes = self._extract_layout_boxes(result)
                    boxes = self._postprocess_table_boxes(boxes, infer_img_path)

                    annotated_path = debug_dir / f"page_{page_idx:03d}_annotated.png"
                    draw_boxes = self._scale_boxes_to_output(
                        boxes=boxes,
                        src_image_path=infer_img_path,
                        dst_image_path=page_png_path,
                    )
                    self._draw_annotation(page_png_path, draw_boxes, annotated_path)

                    table_crops_dir = debug_dir / f"page_{page_idx:03d}_tables"
                    table_crop_paths = self._save_table_crops_from_boxes(
                        page_image_path=page_png_path,
                        boxes=draw_boxes,
                        out_dir=table_crops_dir,
                        page_idx=page_idx,
                    )

                    combo_summary["pages"].append(
                        {
                            "page": page_idx,
                            "saved_page_image_path": str(page_png_path),
                            "infer_image_path": str(infer_img_path),
                            "annotation_image_path": str(annotated_path),
                            "table_crops_dir": str(table_crops_dir),
                            "table_crop_paths": table_crop_paths,
                            "detected_tables": len(table_crop_paths),
                            "detected_blocks": len(boxes),
                        }
                    )

                all_results.append(combo_summary)
                print(f"[testP] combo={combo_tag} done")
        finally:
            self.infer_max_side = original_max_side

        summary = {
            "task_id": task_id,
            "pdf_path": str(pdf_path),
            "page_images_dir": str(pages_root_dir),
            "debug_dir": str(debug_root_dir),
            "pipeline": self.pipeline_name,
            "combos": all_results,
        }

        summary_path = debug_root_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[testP] summary saved: {summary_path}")
        return summary

    def _combo_tag(self, zoom: float, max_side: int) -> str:
        return f"{zoom:g}_{max_side}"

    def _ensure_pipeline(
            self,
            force_rebuild: bool = False,
            safe_mode: bool = False,
            prefer_layout_detection: bool = False,
    ) -> None:
        if self.pipeline is not None and not force_rebuild:
            return

        if force_rebuild:
            self.pipeline = None

        if self.enable_vl and not prefer_layout_detection:
            common_kwargs: Dict[str, Any] = {
                "use_layout_detection": self.use_layout_detection,
                "use_doc_orientation_classify": self.use_doc_orientation_classify,
                "use_doc_unwarping": self.use_doc_unwarping,
                "use_chart_recognition": self.use_chart_recognition,
                "device": "cpu",
            }
            try:
                from paddleocr import PaddleOCRVL

                print("[testP] init pipeline: PaddleOCRVL")
                vl_kwargs = self._filter_supported_kwargs(PaddleOCRVL.__init__, common_kwargs, allow_var_keyword=True)
                self.pipeline = PaddleOCRVL(**vl_kwargs)
                self.pipeline_name = "PaddleOCRVL"
                return
            except Exception as exc:
                print(f"[testP] PaddleOCRVL init failed, fallback to LayoutDetection: {exc}")

        layout_kwargs: Dict[str, Any] = {"device": "cpu"}
        if safe_mode:
            layout_kwargs.update(
                {
                    "enable_mkldnn": False,
                    "ir_optim": False,
                    "cpu_threads": 1,
                }
            )

        if safe_mode:
            print("[testP] init pipeline: LayoutDetection (safe mode)")
        else:
            print("[testP] init pipeline: LayoutDetection (stable mode)")
        self.pipeline = self._create_layout_pipeline(layout_kwargs)
        self.pipeline_name = "LayoutDetection"

    def _create_layout_pipeline(self, common_kwargs: Dict[str, Any]) -> Any:
        from paddleocr import LayoutDetection

        kwargs = dict(common_kwargs)
        if self.layout_model_dir is not None:
            print(f"[testP] use local layout model: {self.layout_model_dir}")
            model_kwargs: Dict[str, Any] = {"model_dir": str(self.layout_model_dir)}
        else:
            print(
                f"[testP] local model not found under {self.local_models_root}, fallback to model_name={self.layout_model_name}"
            )
            model_kwargs = {"model_name": self.layout_model_name}

        max_retries = 6
        for _ in range(max_retries):
            try:
                return LayoutDetection(**model_kwargs, **kwargs)
            except ValueError as exc:
                message = str(exc)
                matched = re.search(r"Unknown argument:\s*([A-Za-z_][A-Za-z0-9_]*)", message)
                if not matched:
                    raise
                unknown_arg = matched.group(1)
                if unknown_arg not in kwargs:
                    raise
                print(f"[testP] LayoutDetection unknown arg {unknown_arg}, remove and retry")
                kwargs.pop(unknown_arg, None)

        return LayoutDetection(**model_kwargs, **kwargs)

    def _resolve_layout_model_dir(self) -> Path | None:
        """Resolve local layout model directory from configured root/name."""
        candidates = [
            self.local_models_root / self.layout_model_name,
            self.local_models_root,
        ]
        for candidate in candidates:
            if not candidate.exists() or not candidate.is_dir():
                continue
            if candidate == self.local_models_root:
                named_dir = candidate / self.layout_model_name
                if named_dir.exists() and named_dir.is_dir():
                    return named_dir
                continue
            return candidate
        return None

    def _filter_supported_kwargs(self, init_fn: Any, kwargs: Dict[str, Any], allow_var_keyword: bool) -> Dict[str, Any]:
        try:
            sig = inspect.signature(init_fn)
            params = sig.parameters
            supports_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
            if supports_var_kw and allow_var_keyword:
                return kwargs
            return {k: v for k, v in kwargs.items() if k in params}
        except Exception:
            return kwargs

    def _predict_single_page(self, image_path: Path) -> Any:
        if self.pipeline is None:
            self._ensure_pipeline()
        try:
            output = self.pipeline.predict(input=str(image_path), batch_size=1)
        except NotImplementedError as exc:
            if "ConvertPirAttribute2RuntimeAttribute" not in str(exc):
                raise
            if self._safe_retry_done:
                raise
            print("[testP] oneDNN/PIR issue detected, rebuild safe pipeline and retry")
            self._safe_retry_done = True
            self._ensure_pipeline(force_rebuild=True, safe_mode=True, prefer_layout_detection=True)
            output = self.pipeline.predict(input=str(image_path), batch_size=1)
        results = list(output)
        if not results:
            return {}
        return results[0]

    def _prepare_infer_image(self, page_png_path: Path) -> Path:
        if self.infer_max_side <= 0:
            return page_png_path

        img = Image.open(page_png_path).convert("RGB")
        w, h = img.size
        mx = max(w, h)
        if mx <= self.infer_max_side:
            return page_png_path

        scale = self.infer_max_side / float(mx)
        new_size = (max(32, int(w * scale)), max(32, int(h * scale)))
        resized = img.resize(new_size, Image.LANCZOS)
        infer_path = page_png_path.with_name(page_png_path.stem + "_infer.png")
        resized.save(infer_path)
        return infer_path

    def _extract_layout_boxes(self, result: Any) -> List[Dict[str, Any]]:
        if isinstance(result, dict) and isinstance(result.get("boxes"), list):
            boxes: List[Dict[str, Any]] = []
            for item in result.get("boxes", []):
                if not isinstance(item, dict):
                    continue
                bbox = self._to_bbox4(item.get("bbox") or item.get("coordinate"))
                if bbox is None:
                    continue
                boxes.append(
                    {
                        "bbox": bbox,
                        "label": str(item.get("label") or item.get("type") or "other"),
                        "score": float(item.get("score") or 1.0),
                    }
                )
            return boxes

        data = self._result_to_dict(result)
        boxes: List[Dict[str, Any]] = []

        parsing = data.get("parsing_res_list") if isinstance(data, dict) else None
        if isinstance(parsing, list):
            for item in parsing:
                if not isinstance(item, dict):
                    continue
                bbox = self._to_bbox4(item.get("block_bbox") or item.get("bbox") or item.get("coordinate"))
                if bbox is None:
                    continue
                boxes.append(
                    {
                        "bbox": bbox,
                        "label": str(item.get("block_label") or item.get("label") or "other"),
                        "score": float(item.get("score") or 1.0),
                    }
                )

        if boxes:
            return boxes

        for key in ("layout_det_res", "layout_detection_res", "layout_parsing_result"):
            node = data.get(key) if isinstance(data, dict) else None
            if isinstance(node, dict):
                for item in node.get("boxes", []):
                    if not isinstance(item, dict):
                        continue
                    bbox = self._to_bbox4(item.get("bbox") or item.get("coordinate"))
                    if bbox is None:
                        continue
                    boxes.append(
                        {
                            "bbox": bbox,
                            "label": str(item.get("label") or item.get("type") or "other"),
                            "score": float(item.get("score") or 1.0),
                        }
                    )

        return boxes

    def _postprocess_table_boxes(self, boxes: List[Dict[str, Any]], image_path: Path) -> List[Dict[str, Any]]:
        if not boxes:
            return boxes

        try:
            import numpy as np
        except Exception:
            return boxes

        img = Image.open(image_path).convert("L")
        gray = np.array(img)
        img_w, img_h = img.size
        page_area = max(1, img_w * img_h)

        processed: List[Dict[str, Any]] = []
        for item in boxes:
            bbox = self._clip_bbox4(item.get("bbox"), img_w, img_h)
            if bbox is None:
                continue

            label = str(item.get("label", "other")).lower()
            if "table" not in label:
                copied = dict(item)
                copied["bbox"] = list(bbox)
                processed.append(copied)
                continue

            area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / float(page_area)
            if area_ratio > self.table_max_area_ratio or area_ratio < self.table_min_area_ratio:
                continue

            split_bboxes = self._split_table_box_by_whitespace(gray, bbox)
            for split_bbox in split_bboxes:
                copied = dict(item)
                copied["bbox"] = [int(v) for v in split_bbox]
                processed.append(copied)

        return self._dedupe_boxes(processed)

    def _split_table_box_by_whitespace(self, gray: Any, bbox: Tuple[int, int, int, int]) -> List[
        Tuple[int, int, int, int]]:
        try:
            import numpy as np
        except Exception:
            return [bbox]

        x1, y1, x2, y2 = bbox
        w = x2 - x1
        h = y2 - y1
        if w < 120 or h < 140:
            return [bbox]

        crop = gray[y1:y2, x1:x2]
        if crop.size == 0:
            return [bbox]

        # Engineering drawings are mostly light background; dark pixels indicate lines/text.
        ink = crop < 232
        row_density = ink.mean(axis=1)
        row_has_content = row_density > 0.006
        spans = self._mask_to_spans(row_has_content)
        if len(spans) <= 1:
            return [bbox]

        merge_gap = max(16, int(h * 0.025))
        merged: List[Tuple[int, int]] = []
        for start, end in spans:
            if not merged:
                merged.append((start, end))
                continue
            prev_start, prev_end = merged[-1]
            if start - prev_end <= merge_gap:
                merged[-1] = (prev_start, end)
            else:
                merged.append((start, end))

        min_segment_h = max(80, int(h * self.table_min_segment_height_ratio))
        valid_segments = [(s, e) for s, e in merged if (e - s) >= min_segment_h]
        if len(valid_segments) <= 1:
            return [bbox]

        split_gap = max(60, int(h * self.table_split_gap_ratio))
        has_large_gap = any(
            (valid_segments[i + 1][0] - valid_segments[i][1]) >= split_gap for i in range(len(valid_segments) - 1))
        if not has_large_gap:
            return [bbox]

        pad = 3
        split_boxes: List[Tuple[int, int, int, int]] = []
        for seg_start, seg_end in valid_segments[:4]:
            sy1 = max(y1, y1 + seg_start - pad)
            sy2 = min(y2, y1 + seg_end + pad)
            if sy2 - sy1 < min_segment_h:
                continue
            split_boxes.append((x1, sy1, x2, sy2))

        return split_boxes or [bbox]

    def _mask_to_spans(self, mask: Any) -> List[Tuple[int, int]]:
        spans: List[Tuple[int, int]] = []
        start = None
        for idx, value in enumerate(mask):
            if bool(value) and start is None:
                start = idx
            elif (not bool(value)) and start is not None:
                spans.append((start, idx))
                start = None
        if start is not None:
            spans.append((start, len(mask)))
        return spans

    def _clip_bbox4(self, raw: Any, width: int, height: int) -> Tuple[int, int, int, int] | None:
        bbox = self._to_bbox4(raw)
        if bbox is None:
            return None
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(width, int(x1)))
        y1 = max(0, min(height, int(y1)))
        x2 = max(0, min(width, int(x2)))
        y2 = max(0, min(height, int(y2)))
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        if right - left < 8 or bottom - top < 8:
            return None
        return (left, top, right, bottom)

    def _dedupe_boxes(self, boxes: List[Dict[str, Any]], iou_threshold: float = 0.85) -> List[Dict[str, Any]]:
        kept: List[Dict[str, Any]] = []
        for item in boxes:
            bbox = item.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            if any(self._bbox_iou(bbox, other.get("bbox", [])) >= iou_threshold for other in kept):
                continue
            kept.append(item)
        return kept

    def _bbox_iou(self, a: Any, b: Any) -> float:
        if not (isinstance(a, list) and isinstance(b, list) and len(a) == 4 and len(b) == 4):
            return 0.0
        ax1, ay1, ax2, ay2 = [int(v) for v in a]
        bx1, by1, bx2, by2 = [int(v) for v in b]
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        a_area = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        b_area = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = a_area + b_area - inter
        if union <= 0:
            return 0.0
        return inter / float(union)

    def _draw_annotation(self, image_path: Path, boxes: List[Dict[str, Any]], out_path: Path) -> None:
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        for item in boxes:
            bbox = item.get("bbox", [])
            if len(bbox) != 4:
                continue
            x1, y1, x2, y2 = [int(v) for v in bbox]
            label = str(item.get("label", "other")).lower()
            score = float(item.get("score", 0.0) or 0.0)
            color = CATEGORY_COLORS.get(label, CATEGORY_COLORS["other"])
            draw.rectangle((x1, y1, x2, y2), outline=color, width=3)
            # Show 3 decimals to avoid visual confusion like 0.504 being displayed as 0.50.
            draw.text((x1 + 2, max(0, y1 - 16)), f"{label} {score:.3f}", fill=color)

        img.save(out_path)

    def _save_table_crops_from_boxes(
            self,
            page_image_path: Path,
            boxes: List[Dict[str, Any]],
            out_dir: Path,
            page_idx: int,
    ) -> List[str]:
        if not boxes:
            return []

        image = Image.open(page_image_path).convert("RGB")
        gray = np.array(image.convert("L"))
        width, height = image.size
        out_dir.mkdir(parents=True, exist_ok=True)
        # Remove stale crops from previous runs in the same folder.
        for stale in out_dir.glob("page_*_table_*.png"):
            try:
                stale.unlink()
            except Exception:
                pass

        table_paths: List[str] = []
        table_index = 0
        for item in boxes:
            label = str(item.get("label", "other")).lower()
            if "table" not in label:
                continue
            score = float(item.get("score", 0.0) or 0.0)
            # Output crops only when score is strictly greater than 0.51.
            if score <= self.table_min_score:
                continue
            bbox = self._clip_bbox4(item.get("bbox"), width, height)
            if bbox is None:
                continue
            x1, y1, x2, y2 = bbox
            y1 = self._expand_table_top_to_boundary(gray, x1, y1, x2, y2)
            if x2 - x1 < 20 or y2 - y1 < 20:
                continue

            table_index += 1
            crop_name = f"page_{page_idx:03d}_table_{table_index:03d}.png"
            crop_path = out_dir / crop_name
            image.crop((x1, y1, x2, y2)).save(crop_path)
            table_paths.append(str(crop_path))

            # 管口表特殊处理：检测长宽比并智能切割
            sub_table_paths = self._detect_and_split_nozzle_table(
                table_image_path=crop_path,
                out_dir=out_dir,
                page_idx=page_idx,
                table_index=table_index,
            )
            if sub_table_paths:
                table_paths.pop()
                try:
                    crop_path.unlink()
                except Exception:
                    pass
            table_paths.extend(sub_table_paths)

        return table_paths

    def _expand_table_top_to_boundary(self, gray: Any, x1: int, y1: int, x2: int, y2: int) -> int:
        if y1 <= 0 or x2 - x1 < 40 or y2 - y1 < 40:
            return y1

        box_h = y2 - y1
        max_expand = min(y1, max(36, int(box_h * 0.22)))
        search_top = max(0, y1 - max_expand)
        if search_top >= y1:
            return y1

        x_pad = max(2, int((x2 - x1) * 0.03))
        sx1 = max(0, x1 + x_pad)
        sx2 = min(gray.shape[1], x2 - x_pad)
        if sx2 - sx1 < 20:
            sx1 = max(0, x1)
            sx2 = min(gray.shape[1], x2)
        if sx2 - sx1 < 20:
            return y1

        strip = gray[search_top:y1, sx1:sx2]
        if strip.size == 0:
            return y1

        ink = strip < 232
        row_density = ink.mean(axis=1)
        if row_density.size < 6:
            return y1

        smooth_density = np.convolve(row_density, np.ones(5, dtype=float) / 5.0, mode="same")
        content_threshold = 0.006
        near_bottom_window = smooth_density[max(0, len(smooth_density) - 24):]
        if near_bottom_window.size == 0 or float(near_bottom_window.max()) < content_threshold:
            return y1

        content_spans = self._mask_to_spans(smooth_density > content_threshold)
        if not content_spans:
            return y1

        bottom_span = None
        lower_bound = len(smooth_density) - 24
        for start, end in reversed(content_spans):
            if end >= lower_bound:
                bottom_span = (start, end)
                break
        if bottom_span is None:
            return y1

        boundary_end = bottom_span[0]
        if boundary_end <= 0:
            return y1

        boundary_density = smooth_density[:boundary_end]
        if boundary_density.size == 0:
            return max(search_top, y1 - 8)

        max_density = float(boundary_density.max()) if boundary_density.size else 0.0
        line_threshold = max(0.16, min(0.72, max_density * 0.72)) if max_density > 0 else 0.16
        line_spans = [
            (start, end)
            for start, end in self._mask_to_spans(boundary_density >= line_threshold)
            if (end - start) >= 2
        ]
        if line_spans:
            line_start, _ = line_spans[-1]
            return max(0, search_top + line_start)

        blank_threshold = max(0.0, min(0.03, float(np.percentile(boundary_density, 25))))
        blank_spans = [
            (start, end)
            for start, end in self._mask_to_spans(boundary_density <= blank_threshold)
            if (end - start) >= 4
        ]
        if blank_spans:
            _, blank_end = blank_spans[-1]
            return max(0, search_top + blank_end)

        return max(0, search_top + max(0, bottom_span[0] - 4))

    def _scale_boxes_to_output(
            self,
            boxes: List[Dict[str, Any]],
            src_image_path: Path,
            dst_image_path: Path,
    ) -> List[Dict[str, Any]]:
        src_w, src_h = Image.open(src_image_path).size
        dst_w, dst_h = Image.open(dst_image_path).size
        if src_w <= 0 or src_h <= 0:
            return boxes

        sx = dst_w / float(src_w)
        sy = dst_h / float(src_h)
        if abs(sx - 1.0) < 1e-6 and abs(sy - 1.0) < 1e-6:
            return boxes

        scaled: List[Dict[str, Any]] = []
        for item in boxes:
            bbox = item.get("bbox", [])
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            x1, y1, x2, y2 = bbox
            scaled_bbox = [
                int(round(float(x1) * sx)),
                int(round(float(y1) * sy)),
                int(round(float(x2) * sx)),
                int(round(float(y2) * sy)),
            ]
            copied = dict(item)
            copied["bbox"] = scaled_bbox
            scaled.append(copied)
        return scaled

    def _result_to_dict(self, result: Any) -> Dict[str, Any]:
        if isinstance(result, dict):
            return result
        if hasattr(result, "to_dict"):
            try:
                data = result.to_dict()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        if hasattr(result, "json"):
            try:
                raw = result.json
                if callable(raw):
                    raw = raw()
                if isinstance(raw, dict):
                    return raw
            except Exception:
                pass
        return {}

    def _to_bbox4(self, raw: Any) -> List[int] | None:
        if isinstance(raw, list) and len(raw) == 4:
            try:
                x1, y1, x2, y2 = [int(float(v)) for v in raw]
                return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
            except Exception:
                return None

        if isinstance(raw, list) and len(raw) >= 8 and len(raw) % 2 == 0:
            try:
                xs = [int(float(raw[i])) for i in range(0, len(raw), 2)]
                ys = [int(float(raw[i])) for i in range(1, len(raw), 2)]
                return [min(xs), min(ys), max(xs), max(ys)]
            except Exception:
                return None

        return None

    def _detect_and_split_nozzle_table(
            self,
            table_image_path: Path,
            out_dir: Path,
            page_idx: int,
            table_index: int,
    ) -> List[str]:
        """
        管口表切割：对于超长表格（长宽比>2.0），按 50% 目标位寻找安全切点并保留上下两部分。

        Args:
            table_image_path: 一级裁剪的表格图片路径
            out_dir: 输出目录
            page_idx: 页面索引
            table_index: 一级表格索引

        Returns:
            切割后的子表格图片路径列表
        """
        try:
            # 1. 检查长宽比
            img = Image.open(table_image_path)
            width, height = img.size
            aspect_ratio = height / float(width)

            # 长宽比阈值：超过 2.0 认为是超长表格（可能是管口表）
            if aspect_ratio < 2.0:
                print(
                    f"[testP] [管口表检测] page_{page_idx:03d}_table_{table_index:03d}: "
                    f"长宽比 {aspect_ratio:.2f} < 2.0，跳过切割"
                )
                return []

            print(
                f"[testP] [管口表检测] page_{page_idx:03d}_table_{table_index:03d}: "
                f"长宽比 {aspect_ratio:.2f}，按 50% 目标位寻找安全横线切割"
            )

            # 2. 以 50% 为目标位，优先沿横线切割，避免截断首尾行文字
            split_y = self._find_safe_horizontal_split(img, target_ratio=0.5)
            if split_y is None:
                split_y = int(height * 0.5)
                print(
                    f"[testP] [管口表检测] page_{page_idx:03d}_table_{table_index:03d}: "
                    f"未找到可靠横线，回退到 50% 固定切割 (split_y={split_y})"
                )

            return self._save_split_tables(
                img=img,
                width=width,
                height=height,
                split_y=split_y,
                out_dir=out_dir,
                page_idx=page_idx,
                table_index=table_index,
                method="safe50",
            )

        except Exception as exc:
            print(f"[testP] [管口表检测] page_{page_idx:03d}_table_{table_index:03d}: 失败 - {exc}")
            import traceback
            traceback.print_exc()
            return []

    def _find_safe_horizontal_split(self, img: Image.Image, target_ratio: float = 0.5) -> int | None:
        gray = np.array(img.convert("L"))
        if gray.size == 0:
            return None

        height, width = gray.shape
        if width < 80 or height < 120:
            return None

        ink = gray < 232
        row_density = ink.mean(axis=1)
        if row_density.size == 0:
            return None

        target_y = int(height * target_ratio)
        search_margin = max(40, int(height * 0.18))
        search_start = max(0, target_y - search_margin)
        search_end = min(height, target_y + search_margin)
        if search_end - search_start < 10:
            return None

        smooth_density = np.convolve(row_density, np.ones(5, dtype=float) / 5.0, mode="same")
        search_density = smooth_density[search_start:search_end]
        if search_density.size == 0:
            return None

        max_density = float(search_density.max())
        if max_density > 0:
            line_threshold = max(0.18, min(0.72, max_density * 0.72))
            line_spans = [
                (start + search_start, end + search_start)
                for start, end in self._mask_to_spans(search_density >= line_threshold)
                if (end - start) >= 2
            ]
            if line_spans:
                best_start, best_end = min(
                    line_spans,
                    key=lambda span: abs(((span[0] + span[1]) // 2) - target_y),
                )
                return min(height - 1, max(1, best_end))

        blank_threshold = max(0.0, min(0.03, float(np.percentile(search_density, 25))))
        blank_spans = [
            (start + search_start, end + search_start)
            for start, end in self._mask_to_spans(search_density <= blank_threshold)
            if (end - start) >= 4
        ]
        if not blank_spans:
            return None

        best_start, best_end = min(
            blank_spans,
            key=lambda span: abs(((span[0] + span[1]) // 2) - target_y),
        )
        return min(height - 1, max(1, (best_start + best_end) // 2))

    def _save_split_tables(
            self,
            img: Image.Image,
            width: int,
            height: int,
            split_y: int,
            out_dir: Path,
            page_idx: int,
            table_index: int,
            method: str,
    ) -> List[str]:
        """
        保存切割后的上下两部分表格。

        Args:
            img: 原始表格图像
            width: 图像宽度
            height: 图像高度
            split_y: 切割位置（y坐标）
            out_dir: 输出目录
            page_idx: 页面索引
            table_index: 表格索引
            method: 切割方法标识（用于目录命名）

        Returns:
            子表格图片路径列表
        """
        # 校验切割位置
        if split_y < height * 0.05 or split_y > height * 0.8:
            print(f"[testP] [管口表检测] 切割位置不合理: {split_y}/{height}，跳过")
            return []

        sub_table_paths: List[str] = []

        # 上部：标题区域（不包含管口表标题）
        upper_path = out_dir / f"page_{page_idx:03d}_table_{table_index:03d}_{method}_upper.png"
        img.crop((0, 0, width, split_y)).save(upper_path)
        sub_table_paths.append(str(upper_path))

        # 下部：数据区域（包含管口表标题）
        lower_path = out_dir / f"page_{page_idx:03d}_table_{table_index:03d}_{method}_lower.png"
        img.crop((0, split_y, width, height)).save(lower_path)
        sub_table_paths.append(str(lower_path))

        print(
            f"[testP] [管口表检测] page_{page_idx:03d}_table_{table_index:03d}: "
            f"成功切割为上下两部分 (split_y={split_y}, method={method})"
        )

        return sub_table_paths

    def _read_bool_env(self, key: str, default: bool) -> bool:
        raw = os.getenv(key)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _pdf_to_images(self, pdf_path: Path, zoom: float) -> List[Image.Image]:
        doc = fitz.open(pdf_path)
        images: List[Image.Image] = []
        try:
            mat = fitz.Matrix(zoom, zoom)
            for page in doc:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                images.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
        finally:
            doc.close()
        return images


if __name__ == "__main__":
    local_pdf = Path(r"D:\work\Develop\drawing-poc\drawing-standard-poc\backend\25.918-1 A1.pdf")

    service = TableLayoutService4Batch()

    result = service.run_multi_combo_experiment(
        pdf_path=local_pdf,
        zoom_values=[3.2], #[4.17],
        infer_max_side_values=[2800],#[2900],
        max_pages=1
    )

    print("\n[testP] done")
    print("task_id:", result["task_id"])
    print("page_images_dir:", result["page_images_dir"])
    print("debug_dir:", result["debug_dir"])
    print("pipeline:", result["pipeline"])
    print("total_combos:", len(result["combos"]))
