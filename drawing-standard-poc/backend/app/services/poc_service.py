from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict

from backend.app.services.table_layout_service import TableLayoutService4Batch
from backend.app.services.mineru_img2md import image_to_markdown
from backend.app.services.identify_standard import StandardCodeComparator, StandardCodeExtractor
from backend.config.config import SQLManager

try:
    from PIL import Image
except Exception:
    Image = None


class PocService:
    """POC 服务层,协调PDF上传、解析等业务流程"""

    def __init__(self):
        self.table_layout_service = TableLayoutService4Batch()

    @staticmethod
    def _format_datetime_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value).replace("T", " ")[:19]

    def _serialize_task_record(self, row: Dict[str, Any] | None) -> Dict[str, Any]:
        if not row:
            return {}

        record = dict(row)
        for field in ("created_at", "updated_at", "started_at", "completed_at"):
            record[field] = self._format_datetime_value(record.get(field))
        return record

    @staticmethod
    def _parse_table_index_from_path(path: str, fallback_index: int) -> int:
        match = re.search(r"_table_(\d+)", str(path))
        if match:
            return int(match.group(1))
        return fallback_index

    @staticmethod
    def _table_display_name_from_path(path: str, fallback_index: int) -> str:
        text = str(path or "")
        match = re.search(r"_table_(\d+)(?:_part_(\d+)|_safe50_(upper|lower))?", text)
        if not match:
            return f"表格{fallback_index}"

        table_index = int(match.group(1))
        part_index = match.group(2)
        legacy_part = match.group(3)
        if part_index:
            return f"表格{table_index}-{int(part_index)}"
        if legacy_part:
            return f"表格{table_index}-{'1' if legacy_part == 'upper' else '2'}"
        return f"表格{table_index}"

    def _load_annotated_images(self, task_id: str) -> list[Dict[str, Any]]:
        debug_dir = self.table_layout_service.table_blocks_dir / task_id / "paddleocr_vl_debug"
        if not debug_dir.exists():
            return []

        images: list[Dict[str, Any]] = []
        for path in sorted(debug_dir.glob("page_*_annotated.png")):
            match = re.search(r"page_(\d+)_annotated", path.name)
            page_number = int(match.group(1)) if match else len(images) + 1
            images.append(
                {
                    "page": page_number,
                    "image_path": str(path),
                    "image_url": self._local_path_to_url(str(path)),
                }
            )
        return images

    @staticmethod
    def _highlight_markdown_by_backend_rules(markdown_content: str, detected_standards: list[str] | None = None) -> str:
        """使用后端标准提取规则生成高亮版Markdown，不改动原始内容。"""
        content = str(markdown_content or "")
        if not content:
            return ""

        extractor = StandardCodeExtractor()
        spans: list[tuple[int, int]] = []

        # 先收集合并标准号范围，确保 47018.1~47018.3.47018.5-2017 这类文本整体可高亮。
        for pattern in (extractor.MERGED_RANGE_REPEATED, extractor.MERGED_RANGE_SIMPLE):
            for match in pattern.finditer(content):
                spans.append((match.start(), match.end()))

        # 再收集普通标准号。
        for match in extractor.STANDARD_PATTERN.finditer(content):
            spans.append((match.start(), match.end()))

        # 使用已检测结果兜底高亮（仍在后端执行），处理空格变体等情况。
        for code in (detected_standards or []):
            text = str(code or "").strip()
            if not text:
                continue
            # 允许标准号中的空格在原文里可有可无。
            pattern_str = re.escape(text).replace(r"\ ", r"\s*")
            try:
                pattern = re.compile(pattern_str)
            except re.error:
                continue
            for match in pattern.finditer(content):
                spans.append((match.start(), match.end()))

        if not spans:
            return content

        # 合并重叠区间，避免重复插入标签导致 HTML 结构异常。
        spans.sort(key=lambda item: (item[0], -item[1]))
        merged_spans: list[tuple[int, int]] = []
        for start, end in spans:
            if not merged_spans or start > merged_spans[-1][1]:
                merged_spans.append((start, end))
            else:
                prev_start, prev_end = merged_spans[-1]
                merged_spans[-1] = (prev_start, max(prev_end, end))

        highlighted = content
        for start, end in reversed(merged_spans):
            fragment = highlighted[start:end]
            wrapped = (
                '<mark style="background-color:#fff3a3;padding:0 2px;">'
                f"<strong>{fragment}</strong>"
                "</mark>"
            )
            highlighted = highlighted[:start] + wrapped + highlighted[end:]

        return highlighted

    @staticmethod
    def _strip_highlight_tags(markdown_content: str) -> str:
        content = str(markdown_content or "")
        if not content:
            return ""
        content = re.sub(r"</?mark[^>]*>", "", content, flags=re.IGNORECASE)
        content = re.sub(r"</?strong>", "", content, flags=re.IGNORECASE)
        return content

    def _get_detected_standards_by_table(self, task_id: str) -> dict[int, list[str]]:
        sql = """
            SELECT
                ti.table_index,
                se.original_text
            FROM standard_extracted se
            INNER JOIN table_markdown tm ON tm.id = se.table_markdown_id
            INNER JOIN table_image ti ON ti.id = tm.table_image_id
            WHERE se.task_id = %s
            ORDER BY ti.table_index ASC, se.id ASC
        """
        result: dict[int, list[str]] = {}
        try:
            with SQLManager() as db:
                rows = db.get_list(sql, (task_id,)) or []
            for row in rows:
                table_index = int(row.get("table_index") or 0)
                original_text = str(row.get("original_text") or "").strip()
                if table_index <= 0 or not original_text:
                    continue
                result.setdefault(table_index, []).append(original_text)
        except Exception as exc:
            print(f"[POC] 查询表格标准提取结果异常: {exc}")
        return result

    def _refresh_highlighted_markdown_storage(self, task_id: str) -> None:
        sql = """
            SELECT
                tm.id,
                tm.markdown_content,
                tm.markdown_path,
                ti.table_index
            FROM table_markdown tm
            INNER JOIN table_image ti ON ti.id = tm.table_image_id
            WHERE tm.task_id = %s
            ORDER BY ti.table_index ASC
        """
        update_sql = """
            UPDATE table_markdown
            SET markdown_content = %s,
                content_length = %s,
                updated_at = NOW()
            WHERE id = %s
        """

        detected_standards_map = self._get_detected_standards_by_table(task_id)

        try:
            with SQLManager() as db:
                rows = db.get_list(sql, (task_id,)) or []
                for row in rows:
                    markdown_path = str(row.get("markdown_path") or "")
                    raw_markdown_content = ""

                    if markdown_path:
                        md_file = Path(markdown_path)
                        if md_file.exists():
                            try:
                                raw_markdown_content = md_file.read_text(encoding="utf-8")
                            except Exception:
                                raw_markdown_content = ""

                    if not raw_markdown_content:
                        raw_markdown_content = self._strip_highlight_tags(
                            str(row.get("markdown_content") or "")
                        )

                    table_index = int(row.get("table_index") or 0)
                    highlighted_markdown_content = self._highlight_markdown_by_backend_rules(
                        raw_markdown_content,
                        detected_standards_map.get(table_index, []),
                    )

                    db.modify(
                        update_sql,
                        (
                            highlighted_markdown_content,
                            len(highlighted_markdown_content),
                            int(row.get("id")),
                        ),
                    )
        except Exception as exc:
            print(f"[POC] 刷新高亮Markdown异常: {exc}")

    def _load_task_tables_from_db(self, task_id: str) -> list[Dict[str, Any]]:
        sql = """
            SELECT
                table_index,
                page_number,
                image_path,
                image_filename
            FROM table_image
            WHERE task_id = %s
            ORDER BY table_index ASC
        """
        try:
            with SQLManager() as db:
                rows = db.get_list(sql, (task_id,)) or []
            tables: list[Dict[str, Any]] = []
            for row in rows:
                image_path = row.get("image_path") or ""
                tables.append(
                    {
                        "page": row.get("page_number") or 1,
                        "table_index": row.get("table_index") or 0,
                        "image_path": image_path,
                        "image_url": self._local_path_to_url(image_path) if image_path else "",
                        "display_name": self._table_display_name_from_path(
                            image_path,
                            int(row.get("table_index") or 0),
                        ),
                        "label": "table",
                        "score": 0.0,
                    }
                )
            return tables
        except Exception as exc:
            print(f"[POC] 查询表格图片异常: {exc}")
            return []

    def _load_task_standards_from_db(self, task_id: str, original_filename: str) -> list[Dict[str, Any]]:
        sql = """
            SELECT
                se.id,
                se.original_text,
                se.row_index,
                se.col_index,
                sc.match_status,
                sc.match_score,
                sc.message,
                sc.matched_standard_no,
                ti.table_index
            FROM standard_extracted se
            LEFT JOIN standard_comparison sc ON sc.standard_extracted_id = se.id
            LEFT JOIN table_markdown tm ON tm.id = se.table_markdown_id
            LEFT JOIN table_image ti ON ti.id = tm.table_image_id
            WHERE se.task_id = %s
            ORDER BY COALESCE(ti.table_index, 999999), se.id ASC
        """
        try:
            with SQLManager() as db:
                rows = db.get_list(sql, (task_id,)) or []
            standards: list[Dict[str, Any]] = []
            for row in rows:
                match_status = row.get("match_status") or "不存在"
                standards.append(
                    {
                        "pdf_name": original_filename,
                        "standard_no": row.get("original_text") or "",
                        "matched_standard": row.get("matched_standard_no") or "未匹配",
                        "status": match_status,
                        "result_type": match_status,
                        "source_table": f"表格{row.get('table_index')}" if row.get("table_index") else "",
                        "confidence": float(row.get("match_score") or 0) / 100.0,
                        "suggestion": row.get("message") or "",
                    }
                )
            return standards
        except Exception as exc:
            print(f"[POC] 查询标准结果异常: {exc}")
            return []

    def _get_table_image_id_map(self, task_id: str) -> dict[int, int]:
        sql = """
            SELECT id, table_index
            FROM table_image
            WHERE task_id = %s
        """
        with SQLManager() as db:
            rows = db.get_list(sql, (task_id,)) or []
        return {
            int(row.get("table_index")): int(row.get("id"))
            for row in rows
            if row.get("table_index") is not None and row.get("id") is not None
        }

    def _get_table_markdown_id_map(self, task_id: str) -> dict[int, int]:
        sql = """
            SELECT tm.id, ti.table_index
            FROM table_markdown tm
            INNER JOIN table_image ti ON ti.id = tm.table_image_id
            WHERE tm.task_id = %s
        """
        with SQLManager() as db:
            rows = db.get_list(sql, (task_id,)) or []
        return {
            int(row.get("table_index")): int(row.get("id"))
            for row in rows
            if row.get("table_index") is not None and row.get("id") is not None
        }

    def _get_markdown_files_from_db(self, task_id: str) -> list[str]:
        sql = """
            SELECT markdown_path
            FROM table_markdown
            WHERE task_id = %s
            ORDER BY id ASC
        """
        with SQLManager() as db:
            rows = db.get_list(sql, (task_id,)) or []
        return [
            str(row.get("markdown_path"))
            for row in rows
            if row.get("markdown_path")
        ]

    def _clear_table_and_downstream_data(self, task_id: str) -> None:
        try:
            with SQLManager() as db:
                db.modify("DELETE FROM standard_comparison WHERE task_id = %s", (task_id,))
                db.modify("DELETE FROM standard_extracted WHERE task_id = %s", (task_id,))
                db.modify("DELETE FROM table_markdown WHERE task_id = %s", (task_id,))
                db.modify("DELETE FROM table_image WHERE task_id = %s", (task_id,))
        except Exception as exc:
            print(f"[POC] 清理历史结果异常: {exc}")

    def _clear_standard_data(self, task_id: str) -> None:
        try:
            with SQLManager() as db:
                db.modify("DELETE FROM standard_comparison WHERE task_id = %s", (task_id,))
                db.modify("DELETE FROM standard_extracted WHERE task_id = %s", (task_id,))
        except Exception as exc:
            print(f"[POC] 清理标准结果异常: {exc}")

    def _save_table_images(self, task_id: str, tables: list[Dict[str, Any]]) -> None:
        if not tables:
            return
        insert_sql = """
            INSERT INTO table_image (
                task_id,
                table_index,
                page_number,
                image_filename,
                image_path,
                image_width,
                image_height,
                file_size,
                dpi,
                ocr_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        rows = []
        for fallback_idx, table in enumerate(tables, start=1):
            table_index = int(table.get("table_index") or fallback_idx)
            image_path = str(table.get("image_path") or "")
            image_obj = Path(image_path) if image_path else None
            file_size = image_obj.stat().st_size if image_obj and image_obj.exists() else 0
            rows.append(
                (
                    task_id,
                    table_index,
                    int(table.get("page") or 1),
                    image_obj.name if image_obj else f"table_{table_index}.png",
                    image_path,
                    0,
                    0,
                    file_size,
                    300,
                    2,
                )
            )
        try:
            with SQLManager() as db:
                db.multi_modify(insert_sql, rows)
        except Exception as exc:
            print(f"[POC] 写入表格图片异常: {exc}")

    def _save_markdown_results(self, task_id: str, results: list[Dict[str, Any]]) -> None:
        if not results:
            return
        image_id_map = self._get_table_image_id_map(task_id)
        upsert_sql = """
            INSERT INTO table_markdown (
                task_id,
                table_image_id,
                markdown_content,
                markdown_path,
                content_length,
                parser_type
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                markdown_content = VALUES(markdown_content),
                markdown_path = VALUES(markdown_path),
                content_length = VALUES(content_length),
                parser_type = VALUES(parser_type),
                updated_at = NOW()
        """

        rows = []
        for fallback_idx, result in enumerate(results, start=1):
            if not result.get("success"):
                continue
            table_index = int(result.get("table_index") or fallback_idx)
            table_image_id = image_id_map.get(table_index)
            if not table_image_id:
                continue
            raw_markdown_content = str(result.get("raw_markdown_content") or result.get("md_content") or "")
            highlighted_markdown_content = self._highlight_markdown_by_backend_rules(raw_markdown_content)
            result["raw_markdown_content"] = raw_markdown_content
            result["md_content"] = highlighted_markdown_content
            result["highlighted_markdown_content"] = highlighted_markdown_content
            md_file = str(result.get("md_file") or "")
            rows.append(
                (
                    task_id,
                    table_image_id,
                    highlighted_markdown_content,
                    md_file,
                    len(highlighted_markdown_content),
                    "mineru",
                )
            )
        if not rows:
            return
        try:
            with SQLManager() as db:
                db.multi_modify(upsert_sql, rows)
        except Exception as exc:
            print(f"[POC] 写入Markdown结果异常: {exc}")

    @staticmethod
    def _build_overall_compare_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
        summary = {
            "total_standards": len(results),
            "unique_standard_count": len(results),
            "exact_match_count": 0,
            "year_mismatch_count": 0,
            "similar_count": 0,
            "not_found_count": 0,
            "results": results,
        }

        for item in results:
            status = str(item.get("status") or "")
            if status == "完全符合":
                summary["exact_match_count"] += 1
            elif status == "年份不一致":
                summary["year_mismatch_count"] += 1
            elif status == "较为相似":
                summary["similar_count"] += 1
            elif status == "不存在":
                summary["not_found_count"] += 1

        return summary

    def _build_overall_standard_compare_from_texts(self, markdown_texts: list[str]) -> dict[str, Any]:
        merged_text = "\n".join(text for text in markdown_texts if str(text or "").strip())
        if not merged_text.strip():
            return self._build_overall_compare_summary([])

        comparator = StandardCodeComparator()
        results = comparator.batch_compare(merged_text)

        overall_results: list[dict[str, Any]] = []
        for result in results:
            result_dict = result.to_dict()
            # 前端不展示分数，保持与现有接口一致。
            result_dict.pop("score", None)
            overall_results.append(result_dict)

        return self._build_overall_compare_summary(overall_results)

    def _build_overall_standard_compare(self, task_id: str, markdown_files: list[str] | None = None) -> dict[str, Any]:
        files = markdown_files or self._get_markdown_files_from_db(task_id)
        markdown_texts: list[str] = []
        for file_path in files:
            md_path = Path(str(file_path))
            if not md_path.exists():
                continue
            try:
                markdown_texts.append(md_path.read_text(encoding="utf-8"))
            except Exception:
                continue

        return self._build_overall_standard_compare_from_texts(markdown_texts)

    def upload_pdf(self, pdf_bytes: bytes, filename: str, task_name: str = None) -> Dict[str, Any]:
        """
        接收前端上传的PDF文件,保存到tmp/uploads目录,并记录到数据库
        
        Args:
            pdf_bytes: PDF文件字节流
            filename: 原始文件名
            task_name: 任务名称(可选)
            
        Returns:
            包含上传结果的字典:
            {
                "task_id": "任务ID",
                "filename": "保存的文件名",
                "file_path": "文件存储路径",
                "file_size": "文件大小(字节)",
                "uploaded_at": "上传时间"
            }
        """
        if not pdf_bytes:
            raise ValueError("上传文件内容为空")
        
        # 验证文件类型
        if not filename.lower().endswith(".pdf"):
            raise ValueError("仅支持PDF文件")
        
        # 生成任务ID: 优先使用任务名,其次使用文件名前缀 + 时间戳
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        if task_name and task_name.strip():
            # 使用任务名 + 时间戳
            task_id = f"{task_name.strip()}_{timestamp}"
            print(f"[POC] 使用任务名生成task_id: {task_id}")
        else:
            # 使用文件名前缀 + 时间戳
            file_stem = Path(filename).stem.strip() or "upload"
            task_id = f"{file_stem}_{timestamp}"
            print(f"[POC] 使用文件名生成task_id: {task_id}")
        
        # 确保uploads目录存在
        upload_dir = self.table_layout_service.base_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存PDF文件
        save_filename = f"{task_id}.pdf"
        save_path = upload_dir / save_filename
        save_path.write_bytes(pdf_bytes)
        
        file_size = len(pdf_bytes)
        uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 记录到数据库(pdf_task表)
        db_record_id = self._save_to_database(
            task_id=task_id,
            original_filename=filename,
            file_path=str(save_path),
            file_size=file_size,
            uploaded_at=uploaded_at
        )
        
        print(f"[POC] PDF上传成功: {save_path} ({file_size} bytes), DB记录ID: {db_record_id}")
        
        return {
            "task_id": task_id,
            "filename": save_filename,
            "original_filename": filename,
            "file_path": str(save_path),
            "file_size": file_size,
            "uploaded_at": uploaded_at,
        }

    def _save_to_database(
        self,
        task_id: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        uploaded_at: str,
    ) -> int:
        """
        将上传记录保存到数据库
        
        Args:
            task_id: 任务ID
            original_filename: 原始文件名
            file_path: 文件存储路径
            file_size: 文件大小
            uploaded_at: 上传时间
            
        Returns:
            插入的记录ID,失败返回0
        """
        insert_sql = """
            INSERT INTO pdf_task (
                task_id, 
                original_filename, 
                file_path, 
                file_size, 
                page_count,
                status, 
                progress,
                current_step,
                table_count,
                standard_count,
                exact_match_count,
                year_mismatch_count,
                similar_count,
                not_found_count,
                created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        args = (
            task_id,              # task_id
            original_filename,    # original_filename
            file_path,            # file_path
            file_size,            # file_size
            0,                    # page_count (待解析)
            0,                    # status (0-待处理)
            0.00,                 # progress (0%)
            "文件已上传,等待解析",  # current_step
            0,                    # table_count
            0,                    # standard_count
            0,                    # exact_match_count
            0,                    # year_mismatch_count
            0,                    # similar_count
            0,                    # not_found_count
            uploaded_at,          # created_at
            uploaded_at           # updated_at
        )
        
        try:
            with SQLManager() as db:
                last_id = db.create(insert_sql, args)
                if last_id:
                    print(f"[POC] 数据库记录成功: task_id={task_id}, db_id={last_id}")
                    return last_id
                else:
                    print(f"[POC] 数据库记录失败: task_id={task_id}")
                    return 0
        except Exception as exc:
            print(f"[POC] 数据库操作异常: {exc}")
            return 0

    def get_task_status(self, task_id: str, include_details: bool = False) -> Dict[str, Any]:
        """
        查询任务状态和进度
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息字典,未找到返回空字典
        """
        select_sql = """
            SELECT 
                id, task_id, original_filename, file_path, file_size,
                page_count, status, progress, current_step,
                table_count, standard_count,
                exact_match_count, year_mismatch_count, similar_count, not_found_count,
                error_message,
                created_at, updated_at, started_at, completed_at
            FROM pdf_task
            WHERE task_id = %s
        """
        
        try:
            with SQLManager() as db:
                result = db.get_one(select_sql, (task_id,))
                if result:
                    print(f"[POC] 查询任务成功: task_id={task_id}")
                    task = self._serialize_task_record(result)
                    if include_details:
                        task["tables"] = self._load_task_tables_from_db(task_id)
                        task["standards"] = self._load_task_standards_from_db(
                            task_id,
                            task.get("original_filename") or "",
                        )
                    return task
                else:
                    print(f"[POC] 任务不存在: task_id={task_id}")
                    return {}
        except Exception as exc:
            print(f"[POC] 查询任务异常: {exc}")
            return {}

    def list_tasks(self, limit: int = 20) -> list[Dict[str, Any]]:
        """查询最近任务列表"""
        select_sql = """
            SELECT
                id, task_id, original_filename, file_path, file_size,
                page_count, status, progress, current_step,
                table_count, standard_count,
                exact_match_count, year_mismatch_count, similar_count, not_found_count,
                error_message,
                created_at, updated_at, started_at, completed_at
            FROM pdf_task
            ORDER BY created_at DESC
            LIMIT %s
        """

        try:
            with SQLManager() as db:
                results = db.get_list(select_sql, (limit,)) or []
                print(f"[POC] 查询任务列表成功: count={len(results)}")
                return [self._serialize_task_record(row) for row in results]
        except Exception as exc:
            print(f"[POC] 查询任务列表异常: {exc}")
            return []

    def _clear_task_result_data(self, task_id: str) -> None:
        """清理任务下的历史解析结果，避免重复写入。"""
        try:
            with SQLManager() as db:
                db.modify("DELETE FROM standard_comparison WHERE task_id = %s", (task_id,))
                db.modify("DELETE FROM standard_extracted WHERE task_id = %s", (task_id,))
                db.modify("DELETE FROM table_markdown WHERE task_id = %s", (task_id,))
                db.modify("DELETE FROM table_image WHERE task_id = %s", (task_id,))
        except Exception as exc:
            print(f"[POC] 清理历史结果异常: {exc}")

    def _persist_table_images(self, task_id: str, tables: list[dict[str, Any]]) -> None:
        if not tables:
            return

        rows = []
        for fallback_index, table in enumerate(tables, start=1):
            table_index = int(table.get("table_index") or fallback_index)
            page_number = int(table.get("page") or 0)
            image_path = str(table.get("image_path") or "")
            image_filename = Path(image_path).name if image_path else ""

            image_width = 0
            image_height = 0
            file_size = 0
            if image_path and Path(image_path).exists():
                try:
                    file_size = Path(image_path).stat().st_size
                except Exception:
                    file_size = 0

                if Image is not None:
                    try:
                        with Image.open(image_path) as img:
                            image_width, image_height = img.size
                    except Exception:
                        image_width, image_height = 0, 0

            rows.append(
                (
                    task_id,
                    table_index,
                    page_number,
                    image_filename,
                    image_path,
                    image_width,
                    image_height,
                    file_size,
                    300,
                    2,
                )
            )

        insert_sql = """
            INSERT INTO table_image (
                task_id, table_index, page_number,
                image_filename, image_path, image_width, image_height,
                file_size, dpi, ocr_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        try:
            with SQLManager() as db:
                db.multi_modify(insert_sql, rows)
            print(f"[POC] 已持久化表格图片: task_id={task_id}, count={len(rows)}")
        except Exception as exc:
            print(f"[POC] 持久化表格图片异常: {exc}")

    def _get_table_image_id_map(self, task_id: str) -> dict[int, int]:
        sql = "SELECT id, table_index FROM table_image WHERE task_id = %s"
        try:
            with SQLManager() as db:
                rows = db.get_list(sql, (task_id,)) or []
            return {int(row["table_index"]): int(row["id"]) for row in rows}
        except Exception as exc:
            print(f"[POC] 查询表格图片映射异常: {exc}")
            return {}

    def _ensure_table_image_row(self, task_id: str, table_index: int, source_image: str) -> int | None:
        image_path = str(source_image or "")
        image_filename = Path(image_path).name if image_path else ""
        insert_sql = """
            INSERT INTO table_image (
                task_id, table_index, page_number,
                image_filename, image_path, image_width, image_height,
                file_size, dpi, ocr_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        args = (task_id, table_index, 0, image_filename, image_path, 0, 0, 0, 300, 2)
        try:
            with SQLManager() as db:
                return db.create(insert_sql, args)
        except Exception as exc:
            print(f"[POC] 补建table_image记录异常: {exc}")
            return None

    def _persist_markdown_results(self, task_id: str, results: list[dict[str, Any]]) -> None:
        if not results:
            return

        image_id_map = self._get_table_image_id_map(task_id)
        upsert_sql = """
            INSERT INTO table_markdown (
                task_id, table_image_id, markdown_content, markdown_path,
                content_length, parser_type, parser_version, confidence_score, table_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                markdown_content = VALUES(markdown_content),
                markdown_path = VALUES(markdown_path),
                content_length = VALUES(content_length),
                parser_type = VALUES(parser_type),
                parser_version = VALUES(parser_version),
                confidence_score = VALUES(confidence_score),
                table_type = VALUES(table_type),
                updated_at = NOW()
        """

        rows: list[tuple[Any, ...]] = []
        for fallback_index, item in enumerate(results, start=1):
            if not item.get("success"):
                continue

            table_index = int(item.get("table_index") or fallback_index)
            table_image_id = image_id_map.get(table_index)
            if not table_image_id:
                table_image_id = self._ensure_table_image_row(
                    task_id=task_id,
                    table_index=table_index,
                    source_image=item.get("source_image", ""),
                )
            if not table_image_id:
                continue

            markdown_content = str(item.get("md_content") or "")
            raw_markdown_content = str(item.get("raw_markdown_content") or markdown_content)
            highlighted_markdown_content = self._highlight_markdown_by_backend_rules(raw_markdown_content)
            markdown_path = str(item.get("md_file") or "")
            rows.append(
                (
                    task_id,
                    table_image_id,
                    highlighted_markdown_content,
                    markdown_path,
                    len(highlighted_markdown_content),
                    "mineru",
                    None,
                    None,
                    "table",
                )
            )

        if not rows:
            return

        try:
            with SQLManager() as db:
                db.multi_modify(upsert_sql, rows)
            print(f"[POC] 已持久化Markdown结果: task_id={task_id}, count={len(rows)}")
        except Exception as exc:
            print(f"[POC] 持久化Markdown结果异常: {exc}")

    def _persist_standard_results(self, task_id: str, all_results: list[dict[str, Any]]) -> None:
        if not all_results:
            return

        markdown_map_sql = """
            SELECT tm.id AS markdown_id, ti.table_index
            FROM table_markdown tm
            JOIN table_image ti ON ti.id = tm.table_image_id
            WHERE tm.task_id = %s
        """

        try:
            with SQLManager() as db:
                markdown_rows = db.get_list(markdown_map_sql, (task_id,)) or []
            markdown_id_map = {
                int(row["table_index"]): int(row["markdown_id"])
                for row in markdown_rows
            }
        except Exception as exc:
            print(f"[POC] 查询markdown映射异常: {exc}")
            markdown_id_map = {}

        insert_extracted_sql = """
            INSERT INTO standard_extracted (
                task_id, table_markdown_id,
                original_text, prefix, standard_type, number, year, has_t,
                row_index, col_index, cell_text
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        get_extracted_id_sql = """
            SELECT id FROM standard_extracted
            WHERE task_id = %s AND original_text = %s AND row_index = %s AND col_index = %s
            LIMIT 1
        """
        upsert_comparison_sql = """
            INSERT INTO standard_comparison (
                task_id, standard_extracted_id,
                match_status, match_score,
                matched_library_id, matched_standard_no, matched_prefix, matched_number, matched_year,
                prefix_match, number_match, main_number_match, year_match, number_similarity,
                message
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                match_status = VALUES(match_status),
                match_score = VALUES(match_score),
                matched_library_id = VALUES(matched_library_id),
                matched_standard_no = VALUES(matched_standard_no),
                matched_prefix = VALUES(matched_prefix),
                matched_number = VALUES(matched_number),
                matched_year = VALUES(matched_year),
                prefix_match = VALUES(prefix_match),
                number_match = VALUES(number_match),
                main_number_match = VALUES(main_number_match),
                year_match = VALUES(year_match),
                number_similarity = VALUES(number_similarity),
                message = VALUES(message)
        """

        saved = 0
        for item in all_results:
            extracted = item.get("extracted") or {}
            matched = item.get("matched_library_entry") or {}
            table_index = int(item.get("table_index") or 0)
            table_markdown_id = markdown_id_map.get(table_index)
            if not table_markdown_id:
                continue

            original_text = str(extracted.get("original") or "").strip()
            if not original_text:
                continue

            prefix = str(extracted.get("prefix") or "")
            standard_type = str(extracted.get("standard_type") or prefix)
            number = str(extracted.get("number") or "")
            year = str(extracted.get("year") or "")
            has_t = 1 if extracted.get("has_T") else 0
            row_index = table_index
            col_index = 0

            try:
                with SQLManager() as db:
                    extracted_id = db.create(
                        insert_extracted_sql,
                        (
                            task_id,
                            table_markdown_id,
                            original_text,
                            prefix,
                            standard_type,
                            number,
                            year,
                            has_t,
                            row_index,
                            col_index,
                            None,
                        ),
                    )

                    if not extracted_id:
                        existing = db.get_one(
                            get_extracted_id_sql,
                            (task_id, original_text, row_index, col_index),
                        )
                        extracted_id = (existing or {}).get("id")

                    if not extracted_id:
                        continue

                    status = str(item.get("status") or "解析错误")
                    score = int(item.get("score") or 0)

                    matched_prefix = str(matched.get("standard_type") or matched.get("prefix") or "")
                    matched_number = str(matched.get("number") or "")
                    matched_year = str(matched.get("year") or "")
                    matched_standard_no = str(matched.get("original") or "")

                    prefix_match = 1 if prefix and matched_prefix and prefix == matched_prefix else 0
                    number_match = 1 if number and matched_number and number == matched_number else 0
                    main_number_match = 1 if number and matched_number and number.split(".")[0] == matched_number.split(".")[0] else 0
                    year_match = 1 if year and matched_year and year == matched_year else 0
                    number_similarity = max(0.0, min(1.0, float(score) / 100.0))

                    db.modify(
                        upsert_comparison_sql,
                        (
                            task_id,
                            extracted_id,
                            status,
                            score,
                            None,
                            matched_standard_no or None,
                            matched_prefix or None,
                            matched_number or None,
                            matched_year or None,
                            prefix_match,
                            number_match,
                            main_number_match,
                            year_match,
                            number_similarity,
                            str(item.get("message") or "")[:500],
                        ),
                    )
                    saved += 1
            except Exception as exc:
                print(f"[POC] 持久化标准结果异常: {exc}")

        print(f"[POC] 已持久化标准比对结果: task_id={task_id}, count={saved}")

    def _load_task_tables(self, task_id: str) -> list[Dict[str, Any]]:
        sql = """
            SELECT
                ti.table_index,
                ti.page_number,
                ti.image_path,
                tm.markdown_content,
                tm.markdown_path
            FROM table_image ti
            LEFT JOIN table_markdown tm ON tm.table_image_id = ti.id
            WHERE ti.task_id = %s
            ORDER BY ti.table_index ASC
        """
        try:
            with SQLManager() as db:
                rows = db.get_list(sql, (task_id,)) or []

            detected_standards_map = self._get_detected_standards_by_table(task_id)

            tables: list[Dict[str, Any]] = []
            for row in rows:
                image_path = str(row.get("image_path") or "")
                markdown_path = str(row.get("markdown_path") or "")
                stored_markdown_content = row.get("markdown_content") or ""
                raw_markdown_content = ""
                if markdown_path:
                    md_file = Path(markdown_path)
                    if md_file.exists():
                        try:
                            raw_markdown_content = md_file.read_text(encoding="utf-8")
                        except Exception:
                            raw_markdown_content = ""
                if not raw_markdown_content:
                    raw_markdown_content = self._strip_highlight_tags(stored_markdown_content)
                table_index = int(row.get("table_index") or 0)
                highlighted_markdown_content = stored_markdown_content or self._highlight_markdown_by_backend_rules(
                    raw_markdown_content,
                    detected_standards_map.get(table_index, []),
                )
                tables.append(
                    {
                        "page": int(row.get("page_number") or 0),
                        "table_index": table_index,
                        "display_name": self._table_display_name_from_path(image_path, table_index),
                        "label": "table",
                        "score": 0.0,
                        "bbox": [],
                        "image_path": image_path,
                        "image_url": self._local_path_to_url(image_path) if image_path else "",
                        "raw_markdown_content": raw_markdown_content,
                        "markdown_content": highlighted_markdown_content,
                        "highlighted_markdown_content": highlighted_markdown_content,
                        "markdown_path": markdown_path,
                    }
                )
            return tables
        except Exception as exc:
            print(f"[POC] 查询任务表格详情异常: {exc}")
            return []

    def _load_task_standards(self, task_id: str) -> list[Dict[str, Any]]:
        sql = """
            SELECT
                se.id,
                se.original_text,
                sc.match_status,
                sc.match_score,
                sc.message,
                sc.matched_standard_no,
                ti.table_index,
                ti.image_path
            FROM standard_extracted se
            LEFT JOIN standard_comparison sc ON sc.standard_extracted_id = se.id
            LEFT JOIN table_markdown tm ON tm.id = se.table_markdown_id
            LEFT JOIN table_image ti ON ti.id = tm.table_image_id
            WHERE se.task_id = %s
            ORDER BY COALESCE(ti.table_index, 0), se.id
        """
        try:
            with SQLManager() as db:
                rows = db.get_list(sql, (task_id,)) or []

            standards: list[Dict[str, Any]] = []
            for row in rows:
                score = int(row.get("match_score") or 0)
                confidence = max(0.0, min(1.0, score / 100.0))
                table_index = int(row.get("table_index") or 0)
                source_table = self._table_display_name_from_path(row.get("image_path") or "", table_index) if table_index > 0 else ""
                standards.append(
                    {
                        "standard_no": row.get("original_text") or "",
                        "matched_standard": row.get("matched_standard_no") or "未匹配",
                        "status": row.get("match_status") or "待识别",
                        "result_type": row.get("match_status") or "待识别",
                        "source_table": source_table,
                        "confidence": confidence,
                        "suggestion": row.get("message") or "",
                    }
                )
            return standards
        except Exception as exc:
            print(f"[POC] 查询任务标准详情异常: {exc}")
            return []

    def get_task_detail(self, task_id: str) -> Dict[str, Any]:
        """查询任务完整详情（包含表格与标准结果）。"""
        task = self.get_task_status(task_id)
        if not task:
            return {}

        tables = self._load_task_tables(task_id)
        standards = self._load_task_standards(task_id)
        overall_standard_compare = self._build_overall_standard_compare(task_id)
        original_filename = task.get("original_filename") or ""

        raw_snapshot = dict(task)
        task.update(
            {
                "task_name": original_filename or task_id,
                "description": "",
                "file_names": [original_filename] if original_filename else [],
                "pdfs": [
                    {
                        "pdf_name": original_filename,
                        "status": "识别成功" if task.get("status") == 2 else "处理中",
                        "table_count": task.get("table_count", 0),
                        "standard_count": task.get("standard_count", 0),
                    }
                ]
                if original_filename
                else [],
                "tables": tables,
                "standards": standards,
                "annotated_images": self._load_annotated_images(task_id),
                "overall_standard_compare": overall_standard_compare,
                "raw_json": raw_snapshot,
            }
        )
        return task

    def process_pdf_tables(self, task_id: str) -> Dict[str, Any]:
        """
        解析PDF并提取表格图片
        
        Args:
            task_id: 任务ID
            
        Returns:
            包含表格图片信息的字典
        """
        # 1. 从数据库查询任务信息
        task_info = self.get_task_status(task_id)
        if not task_info:
            raise ValueError(f"任务不存在: {task_id}")
        
        file_path = task_info.get('file_path')
        if not file_path:
            raise ValueError(f"任务文件路径为空: {task_id}")
        
        # 2. 更新任务状态为"解析中"
        self._update_task_status(
            task_id=task_id,
            status=1,  # 1-解析中
            progress=10.00,
            current_step="解析中",
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            clear_completed_at=True,
        )
        
        try:
            # 3. 调用table_layout_service解析PDF
            print(f"[POC] 开始解析PDF: {file_path}")
            result = self.table_layout_service.export_annotated_from_pdf_path(
                pdf_path=file_path,
                task_id=task_id,
                render_zoom=None,  # 使用默认值
                max_pages=None,    # 使用默认值
            )
            
            # 4. 提取表格图片信息并转换为URL
            tables = []
            total_tables = 0
                    
            for page in result.get('pages', []):
                page_idx = page.get('page', 0)
                table_crop_items = page.get('table_crop_items') or [
                    {"image_path": table_path}
                    for table_path in page.get('table_crop_paths', [])
                ]
                total_tables += len(table_crop_items)
                        
                for table_crop in table_crop_items:
                    table_path = str(table_crop.get("image_path") or "")
                    if not table_path:
                        continue
                    table_index = len(tables) + 1
                    # 将本地路径转换为URL路径
                    url_path = self._local_path_to_url(table_path)
                    print(f"[POC] 表格图片路径转换: {table_path} -> {url_path}")
                    tables.append({
                        "page": page_idx,
                        "table_index": table_index,
                        "display_name": table_crop.get("display_label")
                        or self._table_display_name_from_path(table_path, table_index),
                        "source_table_index": table_crop.get("original_table_index"),
                        "split_part": table_crop.get("split_part"),
                        "split_total": table_crop.get("split_total", 1),
                        "image_path": table_path,  # 本地路径
                        "image_url": url_path,     # 可访问的URL
                        "label": "table",
                        "score": 0.0,
                    })

            # 重跑识别时，先清理旧结果再写入本次表格图片
            self._clear_table_and_downstream_data(task_id)
            self._save_table_images(task_id, tables)
            
            # 5. 更新数据库统计信息
            self._update_task_status(
                task_id=task_id,
                status=1,  # 1-解析中(等待Markdown阶段)
                progress=60.00,
                current_step="解析中",
                page_count=result.get('total_pages', 0),
                table_count=total_tables,
            )
            
            print(f"[POC] PDF解析成功: {total_tables} 个表格")
            
            return {
                "task_id": task_id,
                "total_pages": result.get('total_pages', 0),
                "total_tables": total_tables,
                "tables": tables,
                "annotated_images": self._load_annotated_images(task_id),
                "page_images_dir": result.get('page_images_dir', ''),
                "debug_dir": result.get('debug_dir', ''),
            }
            
        except Exception as exc:
            # 解析失败,更新状态
            self._update_task_status(
                task_id=task_id,
                status=3,  # 3-失败
                current_step=f"解析失败: {str(exc)}"
            )
            print(f"[POC] PDF解析失败: {exc}")
            raise

    def convert_tables_to_markdown(self, task_id: str, tables: list | None) -> Dict[str, Any]:
        """
        将表格图片转换为Markdown
        
        Args:
            task_id: 任务ID
            tables: 表格图片信息列表
            
        Returns:
            包含Markdown文件信息的字典
        """
        if not tables:
            tables = self._load_task_tables_from_db(task_id)
        if not tables:
            raise ValueError("没有表格图片需要转换")
        
        # 创建输出目录
        markdown_dir = self.table_layout_service.base_dir / "markdown" / task_id
        markdown_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[POC] 开始转换表格为Markdown,共 {len(tables)} 个表格")
        
        results = []
        for idx, table in enumerate(tables):
            image_path = table.get('image_path', '')
            if not image_path:
                print(f"[POC] 跳过表格 {idx}: 没有图片路径")
                continue

            original_table_index = table.get("table_index") or table.get("index") or (idx + 1)
            table_display_name = table.get("display_name") or table.get("display_label") or f"表格{original_table_index}"
            source_table_index = table.get("source_table_index") or table.get("original_table_index") or original_table_index
            split_part = table.get("split_part")
            split_total = table.get("split_total", 1)
            
            try:
                # 调用mineru_img2md转换
                print(f"[POC] 转换表格 {idx+1}/{len(tables)}: {Path(image_path).name}")
                
                # 基于原始图片文件名生成markdown文件名，保持编号一致
                image_stem = Path(image_path).stem  # e.g. page_003_table_003_part_1
                table_suffix_match = re.search(r"table_\d+(?:_part_\d+|_safe50_(?:upper|lower))?", image_stem)
                if table_suffix_match:
                    table_task_id = f"{task_id}_{table_suffix_match.group(0)}"
                else:
                    table_task_id = f"{task_id}_table_{original_table_index:03d}"
                    if split_part:
                        table_task_id = f"{table_task_id}_part_{split_part}"
                
                result = image_to_markdown(
                    image_path=Path(image_path),
                    task_id=table_task_id,
                    output_dir=str(markdown_dir),
                    dpi=300,
                    scale=1.5,
                )
                
                # 优先使用patched版本(优化后的结果),如果没有则使用raw版本
                md_file = result.get('patched_md_file')
                if not md_file or not Path(md_file).exists():
                    md_file = result.get('md_file')
                
                # 读取Markdown内容
                md_content = ""
                if md_file and Path(md_file).exists():
                    md_content = Path(md_file).read_text(encoding='utf-8')
                
                # 将本地路径转换为URL
                md_url = self._local_path_to_url(md_file) if md_file else ""
                
                # 判断是否应用了补丁
                patched = result.get('md_patched', False)
                
                # 检查是否有 Qwen 管口表修复版本
                qwen_fixed_md_file = result.get('qwen_fixed_md_file')
                qwen_fixed_applied = result.get('qwen_fixed_applied', False)
                qwen_fixed_md_content = ""
                qwen_fixed_md_url = ""
                original_md_file = md_file   # 保留原始(未Qwen修复)的md路径
                original_md_url = md_url
                original_md_content = md_content
                
                if qwen_fixed_applied and qwen_fixed_md_file and Path(qwen_fixed_md_file).exists():
                    # 有 Qwen 修复版本: 接口主字段返回修复后的md
                    qwen_fixed_md_content = Path(qwen_fixed_md_file).read_text(encoding='utf-8')
                    qwen_fixed_md_url = self._local_path_to_url(qwen_fixed_md_file)
                    # 主字段切换为 Qwen 修复版本
                    md_file = qwen_fixed_md_file
                    md_url = qwen_fixed_md_url
                    md_content = qwen_fixed_md_content
                    print(f"[POC] 表格 {idx+1} 使用 Qwen 修复版本作为主输出")
                
                results.append({
                    "table_index": original_table_index,
                    "display_name": table_display_name,
                    "source_table_index": source_table_index,
                    "split_part": split_part,
                    "split_total": split_total,
                    "source_image": image_path,
                    "md_file": md_file,
                    "md_url": md_url,
                    "raw_markdown_content": md_content,
                    "md_content": md_content,
                    "patched": patched,
                    "qwen_fixed_applied": qwen_fixed_applied,
                    "qwen_fixed_md_file": qwen_fixed_md_file,
                    "qwen_fixed_md_url": qwen_fixed_md_url,
                    "qwen_fixed_md_content": qwen_fixed_md_content,
                    "original_md_file": original_md_file,
                    "original_md_url": original_md_url,
                    "original_md_content": original_md_content,
                    "success": True,
                })
                
                print(f"[POC] 表格 {idx+1} 转换成功: {md_file} {'(已优化)' if patched else '(原始)'}{'(Qwen修复)' if qwen_fixed_applied else ''}")
                
            except Exception as exc:
                print(f"[POC] 表格 {idx+1} 转换失败: {exc}")
                results.append({
                    "table_index": original_table_index,
                    "display_name": table_display_name,
                    "source_table_index": source_table_index,
                    "split_part": split_part,
                    "split_total": split_total,
                    "source_image": image_path,
                    "error": str(exc),
                    "success": False,
                })
        
        success_count = sum(1 for r in results if r.get('success'))
        print(f"[POC] Markdown转换完成: 成功 {success_count}/{len(tables)}")

        self._save_markdown_results(task_id, results)
        self._clear_standard_data(task_id)

        self._update_task_status(
            task_id=task_id,
            status=2,
            progress=80.00,
            current_step="解析完成，等待检验",
            standard_count=0,
            exact_match_count=0,
            year_mismatch_count=0,
            similar_count=0,
            not_found_count=0,
        )
        
        return {
            "task_id": task_id,
            "total_tables": len(tables),
            "success_count": success_count,
            "fail_count": len(tables) - success_count,
            "markdown_dir": str(markdown_dir),
            "results": results,
        }

    def _local_path_to_url(self, local_path: str) -> str:
        """
        将本地文件路径转换为可访问的URL
        
        Args:
            local_path: 本地文件路径
            
        Returns:
            URL路径
        """
        # 获取base_dir (tmp目录)
        base_dir = self.table_layout_service.base_dir
        local_path_obj = Path(local_path)
        
        try:
            # 计算相对路径 (相对于tmp目录)
            relative_path = local_path_obj.relative_to(base_dir)
            # 返回URL路径 (不需要再加tmp,因为路由已经指向tmp目录)
            url_path = f"/api/files/{relative_path.as_posix()}"
            print(f"[POC] 路径转换: {local_path} -> {url_path}")
            return url_path
        except ValueError:
            # 如果不在base_dir下,返回空
            print(f"[POC] 路径转换失败: {local_path} 不在 {base_dir} 下")
            return ""

    def _update_task_status(
        self,
        task_id: str,
        status: int = None,
        progress: float = None,
        current_step: str = None,
        page_count: int = None,
        table_count: int = None,
        standard_count: int = None,
        exact_match_count: int = None,
        year_mismatch_count: int = None,
        similar_count: int = None,
        not_found_count: int = None,
        started_at: str = None,
        completed_at: str = None,
        clear_completed_at: bool = False,
    ) -> None:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 进度
            current_step: 当前步骤
            page_count: 页数
            table_count: 表格数
            standard_count: 标准号数
            started_at: 开始时间
            completed_at: 完成时间
            clear_completed_at: 清空完成时间
        """
        # 构建UPDATE语句
        updates = []
        args = []
        
        if status is not None:
            updates.append("status = %s")
            args.append(status)
        if progress is not None:
            updates.append("progress = %s")
            args.append(progress)
        if current_step is not None:
            updates.append("current_step = %s")
            args.append(current_step)
        if page_count is not None:
            updates.append("page_count = %s")
            args.append(page_count)
        if table_count is not None:
            updates.append("table_count = %s")
            args.append(table_count)
        if standard_count is not None:
            updates.append("standard_count = %s")
            args.append(standard_count)
        if exact_match_count is not None:
            updates.append("exact_match_count = %s")
            args.append(exact_match_count)
        if year_mismatch_count is not None:
            updates.append("year_mismatch_count = %s")
            args.append(year_mismatch_count)
        if similar_count is not None:
            updates.append("similar_count = %s")
            args.append(similar_count)
        if not_found_count is not None:
            updates.append("not_found_count = %s")
            args.append(not_found_count)
        if started_at is not None:
            updates.append("started_at = %s")
            args.append(started_at)
        if clear_completed_at:
            updates.append("completed_at = NULL")
        if completed_at is not None:
            updates.append("completed_at = %s")
            args.append(completed_at)
        
        # 总是更新updated_at
        updates.append("updated_at = NOW()")
        args.append(task_id)
        
        if not updates:
            return
        
        update_sql = f"UPDATE pdf_task SET {', '.join(updates)} WHERE task_id = %s"
        
        try:
            with SQLManager() as db:
                db.modify(update_sql, tuple(args))
                print(f"[POC] 任务状态更新: task_id={task_id}")
        except Exception as exc:
            print(f"[POC] 更新任务状态异常: {exc}")

    def detect_standards(self, task_id: str, markdown_files: list | None) -> Dict[str, Any]:
        """
        检测Markdown文件中的标准号并与标准库比对
        
        Args:
            task_id: 任务ID
            markdown_files: Markdown文件路径列表
            
        Returns:
            包含标准检测结果的字典
        """
        if not markdown_files:
            markdown_files = self._get_markdown_files_from_db(task_id)
        if not markdown_files:
            raise ValueError("Markdown文件列表为空")
        
        print(f"[POC] 开始标准检测: task_id={task_id}, {len(markdown_files)} 个文件")
        
        # 更新任务状态为"标准检测中"
        self._update_task_status(
            task_id=task_id,
            status=1,  # 1-解析中
            progress=90.00,
            current_step="检验中",
            clear_completed_at=True,
        )
        
        try:
            # 创建标准比对器
            comparator = StandardCodeComparator()
            self._clear_standard_data(task_id)
            markdown_id_map = self._get_table_markdown_id_map(task_id)
            
            all_results = []
            markdown_texts: list[str] = []
            total_standards = 0
            unique_standards = set()
            exact_match_count = 0
            year_mismatch_count = 0
            similar_count = 0
            not_found_count = 0
            
            # 遍历每个Markdown文件
            for idx, md_file_path in enumerate(markdown_files):
                md_path = Path(md_file_path)
                if not md_path.exists():
                    print(f"[POC] Markdown文件不存在: {md_file_path}")
                    continue

                table_index = self._parse_table_index_from_path(md_file_path, idx + 1)
                table_display_name = self._table_display_name_from_path(md_file_path, table_index)
                table_markdown_id = markdown_id_map.get(table_index)
                if not table_markdown_id:
                    print(f"[POC] 跳过标准入库，未找到table_markdown记录: task_id={task_id}, table_index={table_index}")
                    continue
                
                # 读取Markdown内容
                md_content = md_path.read_text(encoding='utf-8')
                markdown_texts.append(md_content)
                
                # 提取并去重标准号，再与标准库比对
                match_results = comparator.batch_compare(md_content)

                if not match_results:
                    print(f"[POC] 文件 {md_file_path} 未提取到标准号")
                    continue

                print(f"[POC] 文件 {md_file_path} 去重后提取到 {len(match_results)} 个标准号")

                table_results = []
                for result_idx, match_result in enumerate(match_results, start=1):
                    result_dict = match_result.to_dict()
                    raw_score = int(result_dict.get("score") or 0)
                    
                    # 添加文件信息
                    result_dict['markdown_file'] = str(md_file_path)
                    result_dict['table_index'] = table_index
                    result_dict['table_display_name'] = table_display_name
                    result_dict['source_table'] = table_display_name
                    result_dict['table_group_key'] = table_display_name.replace('表格', '').replace(' ', '')
                    
                    # 统计
                    total_standards += 1
                    extracted_original = (
                        (result_dict.get("extracted") or {}).get("original") or ""
                    )
                    unique_key = "".join(str(extracted_original).upper().split())
                    if unique_key:
                        unique_standards.add(unique_key)
                    status = match_result.status.value
                    if status == "完全符合":
                        exact_match_count += 1
                    elif status == "年份不一致":
                        year_mismatch_count += 1
                    elif status == "较为相似":
                        similar_count += 1
                    elif status == "不存在":
                        not_found_count += 1

                    extracted = result_dict.get("extracted") or {}
                    matched = result_dict.get("matched_library_entry") or {}
                    matched_original = matched.get("original") or ""
                    matched_number = matched.get("number") or ""
                    extracted_number = extracted.get("number") or ""
                    main_extracted = extracted_number.split(".")[0] if extracted_number else ""
                    main_matched = matched_number.split(".")[0] if matched_number else ""

                    insert_extracted_sql = """
                        INSERT INTO standard_extracted (
                            task_id,
                            table_markdown_id,
                            original_text,
                            prefix,
                            standard_type,
                            number,
                            year,
                            has_t,
                            row_index,
                            col_index,
                            cell_text
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    # 保证同一 task 下不同 markdown 文件的标准号不会因 row_index 重复而冲突。
                    # 之前 row_index 仅使用 result_idx，会导致表1/表2第1条同标准号触发唯一键冲突。
                    row_index = int(table_markdown_id) * 1000 + result_idx
                    extracted_args = (
                        task_id,
                        table_markdown_id,
                        extracted.get("original") or "",
                        extracted.get("prefix") or "",
                        extracted.get("standard_type") or extracted.get("prefix") or "",
                        extracted_number,
                        extracted.get("year") or "",
                        1 if extracted.get("has_T") else 0,
                        row_index,
                        0,
                        extracted.get("original") or "",
                    )

                    with SQLManager() as db:
                        standard_extracted_id = db.create(insert_extracted_sql, extracted_args)
                        if not standard_extracted_id:
                            continue

                        insert_comparison_sql = """
                            INSERT INTO standard_comparison (
                                task_id,
                                standard_extracted_id,
                                match_status,
                                match_score,
                                matched_library_id,
                                matched_standard_no,
                                matched_prefix,
                                matched_number,
                                matched_year,
                                prefix_match,
                                number_match,
                                main_number_match,
                                year_match,
                                number_similarity,
                                message
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        db.modify(
                            insert_comparison_sql,
                            (
                                task_id,
                                standard_extracted_id,
                                status,
                                raw_score,
                                None,
                                matched_original,
                                matched.get("prefix") or "",
                                matched_number,
                                matched.get("year") or "",
                                1 if (matched.get("prefix") or "") == (extracted.get("prefix") or "") and matched_original else 0,
                                1 if matched_number and matched_number == extracted_number else 0,
                                1 if main_matched and main_matched == main_extracted else 0,
                                1 if (matched.get("year") or "") == (extracted.get("year") or "") and matched_original else 0,
                                1.0 if matched_number and matched_number == extracted_number else 0.0,
                                result_dict.get("message") or "",
                            ),
                        )

                    # 前端仅需要状态结论，不返回分数。
                    result_dict.pop("score", None)
                    table_results.append(result_dict)
                
                all_results.extend(table_results)
            
            # 更新数据库统计信息
            unique_standard_count = len(unique_standards)
            self._update_task_status(
                task_id=task_id,
                status=2,  # 2-已完成
                progress=100.00,
                current_step="标准检测完成",
                standard_count=unique_standard_count,
                exact_match_count=exact_match_count,
                year_mismatch_count=year_mismatch_count,
                similar_count=similar_count,
                not_found_count=not_found_count,
                completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            print(f"[POC] 标准检测完成: 总计 {total_standards} 个标准号")

            self._refresh_highlighted_markdown_storage(task_id)

            overall_standard_compare = self._build_overall_standard_compare_from_texts(markdown_texts)
            
            return {
                "task_id": task_id,
                "total_standards": total_standards,
                "unique_standard_count": unique_standard_count,
                "exact_match_count": exact_match_count,
                "year_mismatch_count": year_mismatch_count,
                "similar_count": similar_count,
                "not_found_count": not_found_count,
                "results": all_results,
                "overall_standard_compare": overall_standard_compare,
            }
            
        except Exception as exc:
            # 检测失败,更新状态
            self._update_task_status(
                task_id=task_id,
                status=3,  # 3-失败
                current_step=f"标准检测失败: {str(exc)}"
            )
            print(f"[POC] 标准检测失败: {exc}")
            raise


# 单例实例
poc_service = PocService()
