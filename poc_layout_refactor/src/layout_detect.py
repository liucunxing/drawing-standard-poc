from __future__ import annotations

import traceback
from numbers import Real
from pathlib import Path
from typing import Any

from .utils import (
    bbox_pixels_to_ratio,
    clamp_bbox_ratio,
    map_local_ratio_to_page_ratio,
    normalize_label,
    round_bbox,
)


class LayoutDetectionUnavailable(RuntimeError):
    pass


class LayoutDetector:
    def __init__(
        self,
        model_name: str = "PP-DocLayout_plus-L",
        threshold: float = 0.2,
        layout_nms: bool = True,
        layout_merge_bboxes_mode: str | None = "union",
        device: str = "cpu",
        enable_mkldnn: bool = False,
        enable_cinn: bool = False,
        cpu_threads: int = 4,
        fallback_on_error: bool = True,
    ) -> None:
        self.model_name = model_name
        self.threshold = threshold
        self.layout_nms = layout_nms
        self.layout_merge_bboxes_mode = layout_merge_bboxes_mode
        self.device = device
        self.enable_mkldnn = enable_mkldnn
        self.enable_cinn = enable_cinn
        self.cpu_threads = cpu_threads
        self.fallback_on_error = fallback_on_error
        self._model: Any | None = None
        self._disabled_error: str | None = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        if self._disabled_error:
            raise LayoutDetectionUnavailable(self._disabled_error)
        try:
            from paddleocr import LayoutDetection
        except Exception as exc:  # pragma: no cover - depends on local install
            raise LayoutDetectionUnavailable(
                "PaddleOCR LayoutDetection is unavailable. Install dependencies with "
                "`pip install -r requirements.txt` inside poc_layout_refactor."
            ) from exc
        self._model = LayoutDetection(
            model_name=self.model_name,
            threshold=self.threshold,
            layout_nms=self.layout_nms,
            layout_merge_bboxes_mode=self.layout_merge_bboxes_mode,
            device=self.device,
            enable_mkldnn=self.enable_mkldnn,
            enable_cinn=self.enable_cinn,
            cpu_threads=self.cpu_threads,
        )
        return self._model

    def predict_raw(self, image_path: str | Path) -> list[Any]:
        model = self._load_model()
        kwargs: dict[str, Any] = {
            "batch_size": 1,
        }

        try:
            result = model.predict(str(image_path), **kwargs)
        except TypeError:
            result = model.predict(str(image_path))
        return list(result)

    def detect_image(
        self,
        image_path: str | Path,
        page_bbox_ratio: list[float] | None = None,
        roi_name: str | None = None,
    ) -> dict[str, Any]:
        try:
            from PIL import Image
        except Exception as exc:  # pragma: no cover - depends on local install
            raise RuntimeError(
                "Pillow is required to inspect layout input images. Install dependencies "
                "with `pip install -r requirements.txt` inside poc_layout_refactor."
            ) from exc

        source = Path(image_path)
        with Image.open(source) as image:
            image_width, image_height = image.size

        try:
            raw_results = self.predict_raw(source)
        except Exception as exc:
            if not self.fallback_on_error:
                raise
            error = f"{type(exc).__name__}: {exc}"
            self._disabled_error = error
            return {
                "image_path": str(source),
                "image_width_px": image_width,
                "image_height_px": image_height,
                "model_name": self.model_name,
                "threshold": self.threshold,
                "roi_name": roi_name,
                "page_bbox_ratio": page_bbox_ratio,
                "status": "failed",
                "error": error,
                "traceback": traceback.format_exc(),
                "boxes": [],
            }

        raw_boxes = _extract_boxes_from_results(raw_results)
        boxes = []
        for index, raw_box in enumerate(raw_boxes, start=1):
            parsed = _parse_raw_box(raw_box)
            if parsed is None:
                continue
            label = normalize_label(parsed["label"])
            score = float(parsed["score"])
            bbox_px = parsed["bbox_px"]
            local_bbox_ratio = bbox_pixels_to_ratio(bbox_px, image_width, image_height)
            if page_bbox_ratio:
                page_ratio = map_local_ratio_to_page_ratio(
                    local_bbox_ratio, page_bbox_ratio
                )
            else:
                page_ratio = local_bbox_ratio

            boxes.append(
                {
                    "box_id": f"box_{index:03d}",
                    "raw_label": parsed["label"],
                    "label": label,
                    "score": round(score, 6),
                    "bbox_px": round_bbox(bbox_px, digits=2),
                    "bbox_ratio_local": local_bbox_ratio,
                    "bbox_ratio": clamp_bbox_ratio(page_ratio),
                }
            )

        return {
            "image_path": str(source),
            "image_width_px": image_width,
            "image_height_px": image_height,
            "model_name": self.model_name,
            "threshold": self.threshold,
            "roi_name": roi_name,
            "page_bbox_ratio": page_bbox_ratio,
            "status": "ok",
            "boxes": boxes,
        }


def _extract_boxes_from_results(raw_results: list[Any]) -> list[Any]:
    boxes: list[Any] = []
    for result in raw_results:
        found = _find_boxes(result)
        if found:
            boxes.extend(found)
    return boxes


def _find_boxes(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, dict):
        for key in ("boxes", "layout_boxes", "layout_result", "layout_results"):
            item = value.get(key)
            if isinstance(item, list):
                return item
        for item in value.values():
            nested = _find_boxes(item)
            if nested:
                return nested
        return []

    try:
        boxes = value["boxes"]
        if isinstance(boxes, list):
            return boxes
    except Exception:
        pass

    if hasattr(value, "json"):
        try:
            data = value.json() if callable(value.json) else value.json
            return _find_boxes(data)
        except Exception:
            pass

    try:
        return _find_boxes(dict(value))
    except Exception:
        pass

    if hasattr(value, "__dict__"):
        return _find_boxes(vars(value))

    return []


def _parse_raw_box(raw_box: Any) -> dict[str, Any] | None:
    if isinstance(raw_box, dict):
        label = (
            raw_box.get("label")
            or raw_box.get("class_name")
            or raw_box.get("category")
            or raw_box.get("cls")
            or raw_box.get("name")
        )
        score = raw_box.get("score", raw_box.get("confidence", raw_box.get("prob", 0.0)))
        coordinate = (
            raw_box.get("coordinate")
            or raw_box.get("bbox")
            or raw_box.get("box")
            or raw_box.get("points")
            or raw_box.get("poly")
        )
    else:
        return _parse_raw_box(vars(raw_box)) if hasattr(raw_box, "__dict__") else None

    bbox_px = _coordinate_to_bbox_px(coordinate)
    if label is None or bbox_px is None:
        return None
    return {"label": label, "score": score, "bbox_px": bbox_px}


def _coordinate_to_bbox_px(coordinate: Any) -> list[float] | None:
    if coordinate is None:
        return None
    if hasattr(coordinate, "tolist"):
        coordinate = coordinate.tolist()

    if (
        isinstance(coordinate, (list, tuple))
        and len(coordinate) == 4
        and all(isinstance(item, Real) for item in coordinate)
    ):
        x1, y1, x2, y2 = [float(item) for item in coordinate]
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        return [left, top, right, bottom]

    if isinstance(coordinate, (list, tuple)):
        points: list[tuple[float, float]] = []
        for item in coordinate:
            if (
                isinstance(item, (list, tuple))
                and len(item) >= 2
                and isinstance(item[0], Real)
                and isinstance(item[1], Real)
            ):
                points.append((float(item[0]), float(item[1])))
        if points:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            return [min(xs), min(ys), max(xs), max(ys)]

    return None
