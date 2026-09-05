# -*- coding: utf-8 -*-
"""
文字区域 OCR 识别服务

功能：
- 接收文字区域切割图片（来自 table_layout_service._save_text_crops_from_boxes）
- 使用 PaddleOCR 识别图片中的文字
- 将识别结果转为简单 Markdown 格式
- 存入 text_image 和 text_markdown 表

使用方式：
    from backend.app.services.text_ocr_service import text_ocr_service

    results = text_ocr_service.process_text_images(
        task_id="xxx",
        text_items=[
            {"image_path": "/path/to/page_001_text_001.png", "page": 1, "text_index": 1, ...},
        ],
    )
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from backend.config.config import SQLManager

logger = logging.getLogger(__name__)


class TextOCRService:
    """PaddleOCR 文字识别服务（懒加载，单例）"""

    def __init__(self) -> None:
        self._ocr = None  # 延迟初始化

    # ------------------------------------------------------------------
    # PaddleOCR 初始化
    # ------------------------------------------------------------------

    def _ensure_ocr(self) -> None:
        """懒加载 PaddleOCR（首次调用时初始化，后续复用）"""
        if self._ocr is not None:
            return

        print("[TextOCR] 初始化 PaddleOCR ...")
        from paddleocr import PaddleOCR

        # 基础参数，部分旧版本 PaddleOCR 不支持 show_log / use_gpu 等参数，
        # 通过 try/except 自动移除不支持的参数，避免初始化失败。
        kwargs_list = [
            dict(use_angle_cls=True, lang="ch", show_log=False, use_gpu=True),
            dict(use_angle_cls=True, lang="ch", use_gpu=True),
            dict(use_angle_cls=True, lang="ch"),
        ]
        for kwargs in kwargs_list:
            try:
                self._ocr = PaddleOCR(**kwargs)
                print(f"[TextOCR] PaddleOCR 初始化完成, params={list(kwargs.keys())}")
                return
            except (TypeError, ValueError) as exc:
                msg = str(exc)
                if "Unknown argument" in msg or "unexpected keyword" in msg:
                    print(f"[TextOCR] PaddleOCR 参数不兼容: {msg}, 尝试下一组参数")
                    continue
                raise

        # 全部失败，使用最简参数
        self._ocr = PaddleOCR(lang="ch")
        print("[TextOCR] PaddleOCR 使用默认参数初始化")

    # ------------------------------------------------------------------
    # OCR 调用 + 结果解析（兼容 PaddleOCR v4 / v5）
    # ------------------------------------------------------------------

    def _run_ocr(self, image_path: str) -> Any:
        """调用 PaddleOCR，自动适配 v4 (ocr) / v5 (predict) API"""
        # PaddleOCR v5: predict()
        if hasattr(self._ocr, 'predict'):
            try:
                output = self._ocr.predict(image_path)
                return list(output)  # 转为 list
            except TypeError:
                pass

        # PaddleOCR v4: ocr(cls=True)
        if hasattr(self._ocr, 'ocr'):
            return self._ocr.ocr(image_path, cls=True)

        raise RuntimeError("PaddleOCR 实例没有 predict 或 ocr 方法")

    @staticmethod
    def _parse_ocr_result(result: Any, text_lines: List[str], confidences: List[float]) -> None:
        """解析 OCR 返回结果，兼容多种格式"""
        if not result:
            return

        # 如果是 generator / iterator，先转 list
        if not isinstance(result, list):
            try:
                result = list(result)
            except Exception:
                return

        for item in result:
            if not item:
                continue

            # v5 格式: dict with rec_texts / rec_scores
            if isinstance(item, dict):
                texts = item.get("rec_texts") or item.get("rec_text") or []
                scores = item.get("rec_scores") or item.get("rec_score") or []
                if isinstance(texts, str):
                    texts = [texts]
                    scores = [scores] if scores else []
                for i, text in enumerate(texts):
                    text = str(text).strip()
                    if text:
                        text_lines.append(text)
                        conf = float(scores[i]) if i < len(scores) and scores[i] is not None else 0.0
                        confidences.append(conf)
                continue

            # v4 格式: list of pages, each page is list of [bbox, (text, conf)]
            if isinstance(item, list):
                # 可能是单页结果: [[bbox, (text, conf)], ...]
                for line in item:
                    if not line or not isinstance(line, (list, tuple)) or len(line) < 2:
                        continue
                    text_info = line[1]
                    if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                        text = str(text_info[0]).strip()
                        conf = float(text_info[1]) if text_info[1] is not None else 0.0
                        if text:
                            text_lines.append(text)
                            confidences.append(conf)
                continue

            # 尝试将 item 当作嵌套的 page 列表
            if hasattr(item, '__iter__'):
                TextOCRService._parse_ocr_result(list(item), text_lines, confidences)

    # ------------------------------------------------------------------
    # 核心：OCR 识别 + 转 Markdown
    # ------------------------------------------------------------------

    def ocr_single_image(self, image_path: str) -> Dict[str, Any]:
        """
        对单张图片执行 OCR 识别，返回结构化结果。

        Returns:
            {
                "success": True/False,
                "text_lines": ["第1行文字", "第2行文字", ...],
                "markdown": "### 识别结果\\n\\n第1行文字\\n第2行文字\\n...",
                "confidence": 0.95,  # 平均置信度
                "error": None or "错误信息",
            }
        """
        self._ensure_ocr()

        image_path = str(image_path)
        if not Path(image_path).exists():
            return {"success": False, "text_lines": [], "markdown": "", "confidence": 0.0, "error": f"图片不存在: {image_path}"}

        try:
            result = self._run_ocr(image_path)
        except Exception as exc:
            logger.error(f"[TextOCR] OCR 识别失败: {image_path}, 错误: {exc}")
            return {"success": False, "text_lines": [], "markdown": "", "confidence": 0.0, "error": str(exc)}

        # 解析 OCR 结果（兼容 v4 / v5 返回格式）
        text_lines: List[str] = []
        confidences: List[float] = []

        self._parse_ocr_result(result, text_lines, confidences)

        avg_confidence = float(np.mean(confidences)) if confidences else 0.0
        markdown = self._text_lines_to_markdown(text_lines)

        return {
            "success": len(text_lines) > 0,
            "text_lines": text_lines,
            "markdown": markdown,
            "confidence": round(avg_confidence, 4),
            "error": None if text_lines else "未识别到任何文字",
        }

    # ------------------------------------------------------------------
    # 批量处理 + 存数据库
    # ------------------------------------------------------------------

    def process_text_images(
        self,
        task_id: str,
        text_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        批量处理文字区域图片：OCR 识别 → 存 text_image 表 → 存 text_markdown 表。

        Args:
            task_id: 任务ID
            text_items: 来自 _save_text_crops_from_boxes 的结果列表
                每项包含: image_path, page, text_index, display_label, bbox, labels

        Returns:
            {
                "task_id": "xxx",
                "total": 3,
                "success_count": 3,
                "fail_count": 0,
                "results": [ ... ],
                "markdown_paths": [ ... ],  # 用于后续标准检测
            }
        """
        if not text_items:
            return {"task_id": task_id, "total": 0, "success_count": 0, "fail_count": 0, "results": [], "markdown_paths": []}

        print(f"[TextOCR] 开始处理 {len(text_items)} 个文字区域图片, task_id={task_id}")

        # 1. 批量插入 text_image 表，获取 image_id 映射
        image_id_map = self._save_text_images_to_db(task_id, text_items)

        # 2. 逐个 OCR 识别 + 存 text_markdown 表
        results: List[Dict[str, Any]] = []
        markdown_paths: List[str] = []

        for item in text_items:
            image_path = str(item.get("image_path", ""))
            text_index = int(item.get("text_index", 0))

            print(f"[TextOCR] 识别: {Path(image_path).name}")
            ocr_result = self.ocr_single_image(image_path)

            result_entry = {
                "text_index": text_index,
                "image_path": image_path,
                "display_label": item.get("display_label", f"文字区域{text_index}"),
                "page": item.get("page", 0),
                **ocr_result,
            }

            # 存 text_markdown 表
            if ocr_result["success"]:
                image_id = image_id_map.get(text_index)
                if image_id:
                    # markdown 路径用于后续标准检测
                    md_path = self._save_markdown_file(task_id, text_index, ocr_result["markdown"])
                    if md_path:
                        markdown_paths.append(md_path)
                        result_entry["md_file"] = md_path

                    self._save_text_markdown_to_db(
                        task_id=task_id,
                        text_image_id=image_id,
                        markdown_content=ocr_result["markdown"],
                        confidence=ocr_result["confidence"],
                        markdown_path=md_path or "",
                    )

            results.append(result_entry)

        success_count = sum(1 for r in results if r["success"])
        print(f"[TextOCR] 完成: {success_count}/{len(text_items)} 成功")
        if markdown_paths:
            print(f"[TextOCR] markdown_paths ({len(markdown_paths)} 个): {markdown_paths}")
        else:
            print(f"[TextOCR] 警告: markdown_paths 为空！")

        return {
            "task_id": task_id,
            "total": len(text_items),
            "success_count": success_count,
            "fail_count": len(text_items) - success_count,
            "results": results,
            "markdown_paths": markdown_paths,
        }

    # ------------------------------------------------------------------
    # 文字转 Markdown（简单包装）
    # ------------------------------------------------------------------

    @staticmethod
    def _text_lines_to_markdown(lines: List[str]) -> str:
        """将 OCR 识别的文字行列表转为简单 Markdown 格式"""
        if not lines:
            return ""

        md_parts: List[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 简单判断：如果行末有句号/冒号且较短，可能是标题
            # 但 POC 阶段不做复杂结构化，直接作为正文行
            md_parts.append(line)

        return "\n\n".join(md_parts)

    # ------------------------------------------------------------------
    # 数据库操作
    # ------------------------------------------------------------------

    def _save_text_images_to_db(
        self,
        task_id: str,
        text_items: List[Dict[str, Any]],
    ) -> Dict[int, int]:
        """
        批量插入 text_image 表，返回 {text_index: db_id} 映射。
        """
        insert_sql = """
            INSERT INTO text_image (
                task_id, text_index, page_number,
                image_filename, image_path,
                image_width, image_height, file_size,
                bbox_x, bbox_y, bbox_width, bbox_height,
                ocr_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        rows = []
        for item in text_items:
            image_path = str(item.get("image_path", ""))
            text_index = int(item.get("text_index", 0))
            page = int(item.get("page", 0))
            bbox = item.get("bbox", [0, 0, 0, 0])
            filename = Path(image_path).name

            # 获取图片尺寸
            img_w, img_h, file_size = 0, 0, 0
            try:
                with Image.open(image_path) as img:
                    img_w, img_h = img.size
                file_size = Path(image_path).stat().st_size
            except Exception:
                pass

            rows.append((
                task_id, text_index, page,
                filename, image_path,
                img_w, img_h, file_size,
                bbox[0] if len(bbox) > 0 else 0,
                bbox[1] if len(bbox) > 1 else 0,
                (bbox[2] - bbox[0]) if len(bbox) > 2 else 0,
                (bbox[3] - bbox[1]) if len(bbox) > 3 else 0,
                0,  # ocr_status = 待处理
            ))

        if not rows:
            return {}

        try:
            with SQLManager() as db:
                db.multi_modify(insert_sql, rows)

            # 查询刚插入的记录，建立 text_index → id 映射
            id_map: Dict[int, int] = {}
            with SQLManager() as db:
                result = db.get_list(
                    "SELECT id, text_index FROM text_image WHERE task_id = %s",
                    [task_id]
                )
                if result:
                    for row in result:
                        id_map[int(row["text_index"])] = int(row["id"])
            return id_map

        except Exception as exc:
            logger.error(f"[TextOCR] 插入 text_image 失败: {exc}")
            return {}

    def _save_text_markdown_to_db(
        self,
        task_id: str,
        text_image_id: int,
        markdown_content: str,
        confidence: float,
        markdown_path: str = "",
    ) -> None:
        """插入 text_markdown 表"""
        sql = """
            INSERT INTO text_markdown (
                task_id, text_image_id,
                markdown_content, markdown_path, content_length,
                parser_type, confidence_score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                markdown_content = VALUES(markdown_content),
                markdown_path = VALUES(markdown_path),
                content_length = VALUES(content_length),
                parser_type = VALUES(parser_type),
                confidence_score = VALUES(confidence_score),
                updated_at = NOW()
        """
        try:
            with SQLManager() as db:
                db.modify(sql, [
                    task_id, text_image_id,
                    markdown_content, markdown_path or None, len(markdown_content),
                    "paddleocr", round(confidence, 2),
                ])
        except Exception as exc:
            logger.error(f"[TextOCR] 插入 text_markdown 失败: {exc}")

    def _save_markdown_file(self, task_id: str, text_index: int, markdown: str) -> Optional[str]:
        """将 Markdown 内容保存到文件，返回文件路径（用于后续标准检测）"""
        try:
            from backend.config.app_config import app_config
            md_dir = app_config.tmp_dir / "markdown" / task_id
            md_dir.mkdir(parents=True, exist_ok=True)
            md_path = md_dir / f"text_{text_index:03d}.md"
            md_path.write_text(markdown, encoding="utf-8")
            return str(md_path)
        except Exception as exc:
            logger.warning(f"[TextOCR] 保存 markdown 文件失败: {exc}")
            return None


# ============================================
# 全局单例
# ============================================
text_ocr_service = TextOCRService()
