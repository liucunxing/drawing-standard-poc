from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import getpass
from html import escape
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import requests
import streamlit as st


STATUS_STYLE = {
    "已完成": "success",
    "处理中": "info",
    "待复核": "warning",
    "异常": "error",
    "失败": "error",
}
REVIEW_STATUSES = {"待复核", "异常", "失败"}
FAILED_STATUSES = {"异常", "失败"}

# 后端API配置
BACKEND_BASE_URL = "http://localhost:8000"  # FastAPI后端地址
BACKEND_TMP_DIR = Path(__file__).resolve().parent / "drawing-standard-poc" / "backend" / "tmp"
STANDARD_LIBRARY_OPERATOR = "ADMIN"


# Future OCR backend responses should follow this shape. The Streamlit page does
# not call the backend in the POC; normalize_backend_result(payload) is the
# integration adapter reserved for the next wiring step.
BACKEND_RESULT_CONTRACT = """
{
  "code": 200,
  "msg": "识别完成",
  "data": {
    "task_id": "...",
    "task_name": "...",
    "description": "...",
    "created_at": "2026-05-22 09:30:00",
    "total_pdfs": 3,
    "processed_count": 3,
    "total_tables": 8,
    "total_standards": 12,
    "review_count": 2,
    "status": "已完成",
    "pdfs": [],
    "tables": [],
    "standards": []
  }
}
"""


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def truncate_display_text(value: Any, max_chars: int = 26) -> tuple[str, str]:
    text = str(value or "-")
    if len(text) <= max_chars:
        return text, text
    if max_chars <= 3:
        return text[:max_chars], text
    return f"{text[: max_chars - 3]}...", text


def upload_pdf_to_backend(pdf_file, task_name: str = None) -> dict[str, Any]:
    """
    将PDF文件上传到后端API
    
    Args:
        pdf_file: Streamlit上传的文件对象
        task_name: 任务名称(可选)
        
    Returns:
        后端返回的结果字典
        {
            "success": True/False,
            "data": {...},  # 上传成功时的数据
            "message": "错误信息"  # 失败时的信息
        }
    """
    try:
        # 准备文件数据
        files = {
            "file": (pdf_file.name, pdf_file.getvalue(), "application/pdf")
        }
        
        # 如果有任务名,添加到请求参数
        params = {}
        if task_name:
            params["task_name"] = task_name
        
        # 发送POST请求到后端
        response = requests.post(
            f"{BACKEND_BASE_URL}/api/drawing/upload-pdf",
            files=files,
            params=params,
            timeout=30,
        )
        
        # 解析响应
        result = response.json()
        
        if result.get("code") == 200:
            return {
                "success": True,
                "data": result.get("data", {}),
                "message": result.get("msg", "上传成功"),
            }
        else:
            return {
                "success": False,
                "data": None,
                "message": result.get("msg", "上传失败"),
            }
            
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "data": None,
            "message": f"无法连接到后端服务器 ({BACKEND_BASE_URL})，请确保后端已启动",
        }
    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "message": f"上传异常: {str(exc)}",
        }


def process_tables_from_backend(task_id: str) -> dict[str, Any]:
    """
    调用后端解析PDF并提取表格图片
    
    Args:
        task_id: 任务ID
        
    Returns:
        后端返回的结果字典
    """
    try:
        # 发送POST请求到后端
        response = requests.post(
            f"{BACKEND_BASE_URL}/api/drawing/process-tables",
            params={"task_id": task_id},
            timeout=120,  # 解析可能需要较长时间
        )
        
        # 解析响应
        result = response.json()
        
        if result.get("code") == 200:
            return {
                "success": True,
                "data": result.get("data", {}),
                "message": result.get("msg", "解析成功"),
            }
        else:
            return {
                "success": False,
                "data": None,
                "message": result.get("msg", "解析失败"),
            }
            
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "data": None,
            "message": f"无法连接到后端服务器 ({BACKEND_BASE_URL})",
        }
    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "message": f"解析异常: {str(exc)}",
        }


def check_parse_status(task_id: str) -> dict[str, Any]:
    """
    查询PDF解析状态(用于轮询)
    
    Args:
        task_id: 任务ID
        
    Returns:
        {
            "success": True,
            "data": {
                "status": 2,  # 0-待处理, 1-解析中, 2-已完成, 3-失败
                "progress": 100.00,
                "current_step": "解析完成",
                "table_count": 4
            }
        }
    """
    try:
        response = requests.get(
            f"{BACKEND_BASE_URL}/api/drawing/task/{task_id}/parse-status",
            timeout=10,
        )
        
        result = response.json()
        
        if result.get("code") == 200:
            return {
                "success": True,
                "data": result.get("data", {}),
            }
        else:
            return {
                "success": False,
                "data": None,
                "message": result.get("msg", "查询失败"),
            }
            
    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "message": f"查询异常: {str(exc)}",
        }


def convert_to_markdown_from_backend(task_id: str, tables: list) -> dict[str, Any]:
    """
    调用后端将表格图片转换为Markdown
    
    Args:
        task_id: 任务ID
        tables: 表格图片信息列表
        
    Returns:
        后端返回的结果字典
    """
    try:
        # 发送POST请求到后端
        response = requests.post(
            f"{BACKEND_BASE_URL}/api/drawing/convert-to-markdown",
            params={"task_id": task_id},
            json={"tables": tables},
            timeout=300,  # 转换可能需要很长时间
        )
        
        # 解析响应
        result = response.json()
        
        if result.get("code") == 200:
            return {
                "success": True,
                "data": result.get("data", {}),
                "message": result.get("msg", "转换成功"),
            }
        else:
            return {
                "success": False,
                "data": None,
                "message": result.get("msg", "转换失败"),
            }
            
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "data": None,
            "message": f"无法连接到后端服务器 ({BACKEND_BASE_URL})",
        }
    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "message": f"转换异常: {str(exc)}",
        }


def detect_standards_from_backend(task_id: str, markdown_files: list) -> dict[str, Any]:
    """
    调用后端检测Markdown文件中的标准号
    
    Args:
        task_id: 任务ID
        markdown_files: Markdown文件路径列表
        
    Returns:
        后端返回的结果字典
    """
    try:
        # 发送POST请求到后端
        response = requests.post(
            f"{BACKEND_BASE_URL}/api/drawing/detect-standards",
            params={"task_id": task_id},
            json={"markdown_files": markdown_files},
            timeout=300,  # 标准检测可能需要较长时间
        )
        
        # 解析响应
        result = response.json()
        
        if result.get("code") == 200:
            return {
                "success": True,
                "data": result.get("data", {}),
                "message": result.get("msg", "检测成功"),
            }
        else:
            return {
                "success": False,
                "data": None,
                "message": result.get("msg", "检测失败"),
            }
            
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "data": None,
            "message": f"无法连接到后端服务器 ({BACKEND_BASE_URL})",
        }
    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "message": f"检测异常: {str(exc)}",
        }


def get_task_status_from_backend(task_id: str) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{BACKEND_BASE_URL}/api/drawing/task/{task_id}",
            timeout=5,
        )

        result = response.json()
        if result.get("code") == 200:
            return {
                "success": True,
                "data": result.get("data", {}),
            }
        return {
            "success": False,
            "data": None,
            "message": result.get("msg", "查询失败"),
        }
    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "message": f"查询异常: {str(exc)}",
        }


def list_tasks_from_backend(limit: int = 50) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{BACKEND_BASE_URL}/api/drawing/tasks",
            params={"limit": limit},
            timeout=5,
        )

        result = response.json()
        if result.get("code") == 200:
            return {
                "success": True,
                "data": result.get("data", []),
            }
        return {
            "success": False,
            "data": None,
            "message": result.get("msg", "查询失败"),
        }
    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "message": f"查询异常: {str(exc)}",
        }


def list_standard_data_from_backend(keyword: str = "", page: int = 1, page_size: int = 20) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{BACKEND_BASE_URL}/api/standard-data",
            params={
                "keyword": keyword,
                "page": page,
                "page_size": page_size,
            },
            timeout=8,
        )
        result = response.json()
        if result.get("code") == 200:
            return {"success": True, "data": result.get("data", {})}
        return {"success": False, "data": None, "message": result.get("msg", "查询失败")}
    except Exception as exc:
        return {"success": False, "data": None, "message": f"查询异常: {str(exc)}"}


def create_standard_data_from_backend(
    standard_no: str,
    standard_type: str,
    standard_prefix: str,
    operator: str = STANDARD_LIBRARY_OPERATOR,
) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{BACKEND_BASE_URL}/api/standard-data",
            json={
                "standard_no": standard_no,
                "standard_type": standard_type,
                "standard_prefix": standard_prefix,
                "operator": operator,
            },
            timeout=8,
        )
        result = response.json()
        if result.get("code") == 200:
            return {"success": True, "data": result.get("data", {})}
        return {"success": False, "data": None, "message": result.get("msg", "新增失败")}
    except Exception as exc:
        return {"success": False, "data": None, "message": f"新增异常: {str(exc)}"}


def update_standard_data_from_backend(
    standard_id: int,
    standard_no: str,
    standard_type: str,
    standard_prefix: str,
    operator: str = STANDARD_LIBRARY_OPERATOR,
) -> dict[str, Any]:
    try:
        response = requests.put(
            f"{BACKEND_BASE_URL}/api/standard-data/{standard_id}",
            json={
                "standard_no": standard_no,
                "standard_type": standard_type,
                "standard_prefix": standard_prefix,
                "operator": operator,
            },
            timeout=8,
        )
        result = response.json()
        if result.get("code") == 200:
            return {"success": True, "data": result.get("data", {})}
        return {"success": False, "data": None, "message": result.get("msg", "更新失败")}
    except Exception as exc:
        return {"success": False, "data": None, "message": f"更新异常: {str(exc)}"}


def delete_standard_data_from_backend(standard_id: int) -> dict[str, Any]:
    try:
        response = requests.delete(
            f"{BACKEND_BASE_URL}/api/standard-data/{standard_id}",
            timeout=8,
        )
        result = response.json()
        if result.get("code") == 200:
            return {"success": True}
        return {"success": False, "message": result.get("msg", "删除失败")}
    except Exception as exc:
        return {"success": False, "message": f"删除异常: {str(exc)}"}


def detect_default_operator() -> str:
    try:
        value = (getpass.getuser() or "").strip()
        return value or "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def format_datetime_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    text = str(value).replace("T", " ")
    return text[:19] if len(text) >= 19 else text


def format_date_only_text(value: Any) -> str:
    text = format_datetime_text(value)
    if not text:
        return "无"
    return text[:10] if len(text) >= 10 else text


def normalize_task_status(status: Any, current_step: str = "") -> str:
    if isinstance(status, str):
        return status or "处理中"
    if status in (3, 4):
        return "失败"
    if status == 2 and current_step == "标准检测完成":
        return "已完成"
    return "处理中"


def normalize_pdf_status(status: Any, current_step: str = "") -> str:
    if status in (3, 4):
        return "失败"
    if current_step in {"解析完成", "解析完成，等待检验", "标准检测完成"} or status == 2:
        return "识别成功"
    if status == 1:
        return "处理中"
    return "排队中"


def parse_created_at(value: str) -> datetime:
    normalized = format_datetime_text(value)
    try:
        return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.min


def format_file_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    return f"{size / 1024:.1f} KB"


def stable_raw_json(source: dict[str, Any]) -> dict[str, Any]:
    raw_json = deepcopy(source)
    raw_json.pop("raw_json", None)
    return raw_json


def normalize_table(table: dict[str, Any], fallback_index: int) -> dict[str, Any]:
    return {
        "pdf_name": table.get("pdf_name")
        or table.get("source_pdf")
        or table.get("pdf_file")
        or "",
        "page": table.get("page", 1),
        "table_index": table.get("table_index") or table.get("index") or fallback_index,
        "label": table.get("label") or table.get("table_type") or "未分类表格",
        "score": table.get("score", table.get("confidence", 0.0)),
        "bbox": table.get("bbox", []),
        "image_path": table.get("image_path") or table.get("crop_path") or "",
        "image_url": table.get("image_url") or "",
        "display_name": table.get("display_name") or table.get("display_label") or "",
        "source_table_index": table.get("source_table_index") or table.get("original_table_index"),
        "split_part": table.get("split_part"),
        "split_total": table.get("split_total", 1),
        "raw_markdown_content": table.get("raw_markdown_content") or "",
        "markdown_content": table.get("markdown_content") or "",
        "highlighted_markdown_content": table.get("highlighted_markdown_content") or "",
        "markdown_path": table.get("markdown_path") or "",
    }


def normalize_standard(standard: dict[str, Any]) -> dict[str, Any]:
    status = standard.get("status") or standard.get("conclusion") or "待识别"
    return {
        "pdf_name": standard.get("pdf_name") or standard.get("pdf_file") or "",
        "standard_no": standard.get("standard_no") or "",
        "matched_standard": standard.get("matched_standard")
        or standard.get("library_match")
        or "未匹配",
        "status": status,
        "result_type": standard.get("result_type") or status,
        "source_table": standard.get("source_table") or "",
        "confidence": standard.get("confidence", 1.0 if status == "通过" else 0.0),
        "suggestion": standard.get("suggestion") or "",
    }


def normalize_pdf(
    pdf: dict[str, Any],
    tables: list[dict[str, Any]],
    standards: list[dict[str, Any]],
) -> dict[str, Any]:
    pdf_name = pdf.get("pdf_name") or pdf.get("file_name") or pdf.get("name") or ""
    pdf_tables = [table for table in tables if table["pdf_name"] == pdf_name]
    pdf_standards = [standard for standard in standards if standard["pdf_name"] == pdf_name]
    standard_issues = sum(1 for standard in pdf_standards if standard["status"] in REVIEW_STATUSES)
    pdf_issue = 1 if pdf.get("status") in REVIEW_STATUSES else 0
    return {
        "pdf_name": pdf_name,
        "status": pdf.get("status") or "排队中",
        "project_name": pdf.get("project_name") or "",
        "unit_name": pdf.get("unit_name") or "",
        "equipment_name": pdf.get("equipment_name") or pdf.get("equipment") or "",
        "drawing_no": pdf.get("drawing_no") or "",
        "discipline": pdf.get("discipline") or "",
        "design_stage": pdf.get("design_stage") or pdf.get("stage") or "",
        "table_count": pdf.get("table_count", len(pdf_tables)),
        "standard_count": pdf.get("standard_count", len(pdf_standards)),
        "issue_count": pdf.get("issue_count", pdf_issue + standard_issues),
    }


def normalize_task_detail(source: dict[str, Any]) -> dict[str, Any]:
    data = source.get("data", source)
    current_step = data.get("current_step") or ""
    status_text = normalize_task_status(data.get("status"), current_step)
    tables = [
        normalize_table(table, index)
        for index, table in enumerate(data.get("tables", []), start=1)
    ]
    standards = [normalize_standard(standard) for standard in data.get("standards", [])]

    source_pdfs = data.get("pdfs", [])
    file_names = data.get("file_names") or [
        pdf.get("pdf_name") or pdf.get("file_name") or pdf.get("name") or ""
        for pdf in source_pdfs
    ]
    if not file_names and data.get("original_filename"):
        file_names = [data.get("original_filename")]
    if not source_pdfs and file_names:
        pdf_status = normalize_pdf_status(data.get("status"), current_step)
        source_pdfs = [{"pdf_name": file_name, "status": pdf_status} for file_name in file_names]

    pdfs = [normalize_pdf(pdf, tables, standards) for pdf in source_pdfs]
    return {
        "task_id": data.get("task_id") or f"TASK-{datetime.now():%Y%m%d}-{uuid4().hex[:4].upper()}",
        "task_name": data.get("task_name") or data.get("original_filename") or data.get("task_id") or "未命名识别任务",
        "description": data.get("description") or "",
        "file_names": file_names or [pdf["pdf_name"] for pdf in pdfs],
        "original_filename": data.get("original_filename") or (file_names[0] if file_names else ""),
        "pdfs": pdfs,
        "tables": tables,
        "standards": standards,
        "annotated_images": data.get("annotated_images") or [],
        "overall_standard_compare": data.get("overall_standard_compare") or {},
        "raw_json": data.get("raw_json") or stable_raw_json(source),
        "status": status_text,
        "current_step": current_step or "文件已上传,等待解析",
        "created_at": format_datetime_text(data.get("created_at")) or now_text(),
        "started_at": format_datetime_text(data.get("started_at")),
        "completed_at": format_datetime_text(data.get("completed_at")),
        "backend_status": data.get("status"),
        "processed_count": data.get("processed_count"),
        "pdf_count": data.get("pdf_count", data.get("total_pdfs")) or len(pdfs),
        "table_count": data.get("table_count", data.get("total_tables")),
        "standard_count": data.get("standard_count", data.get("total_standards")),
        "review_count": data.get("review_count"),
    }


def processed_count(detail: dict[str, Any]) -> int:
    if detail.get("processed_count") is not None:
        return detail["processed_count"]
    return sum(1 for pdf in detail["pdfs"] if pdf["status"] == "识别成功")


def review_count(detail: dict[str, Any]) -> int:
    if detail.get("review_count") is not None:
        return detail["review_count"]
    pdf_reviews = sum(1 for pdf in detail["pdfs"] if pdf["issue_count"] > 0)
    standard_reviews = sum(1 for standard in detail["standards"] if standard["status"] in REVIEW_STATUSES)
    return max(pdf_reviews, standard_reviews)


def failed_count(detail: dict[str, Any]) -> int:
    pdf_failed = sum(1 for pdf in detail["pdfs"] if pdf["status"] in FAILED_STATUSES)
    standard_failed = sum(
        1 for standard in detail["standards"] if standard["status"] in FAILED_STATUSES
    )
    return max(pdf_failed, standard_failed)


def normalize_task_summary(detail: dict[str, Any]) -> dict[str, Any]:
    table_total = detail.get("table_count")
    standard_total = detail.get("standard_count")
    return {
        "task_id": detail["task_id"],
        "task_name": detail["task_name"],
        "description": detail["description"],
        "original_filename": detail.get("original_filename") or (detail.get("file_names") or [""])[0],
        "pdf_count": detail.get("pdf_count") or len(detail["pdfs"]),
        "processed_count": processed_count(detail),
        "table_count": table_total if table_total is not None else len(detail["tables"]),
        "standard_count": standard_total if standard_total is not None else len(detail["standards"]),
        "review_count": review_count(detail),
        "status": detail["status"],
        "current_step": detail.get("current_step", ""),
        "created_at": detail["created_at"],
        "started_at": detail.get("started_at", ""),
        "completed_at": detail.get("completed_at", ""),
        "file_names": detail["file_names"],
    }


def merge_backend_task_detail(
    existing_detail: dict[str, Any] | None,
    backend_task: dict[str, Any],
) -> dict[str, Any]:
    backend_detail = normalize_task_detail(backend_task)
    if not existing_detail:
        return backend_detail

    merged = deepcopy(backend_detail)
    merged["task_name"] = existing_detail.get("task_name") or backend_detail["task_name"]
    merged["description"] = existing_detail.get("description") or backend_detail["description"]
    merged["file_names"] = existing_detail.get("file_names") or backend_detail["file_names"]
    merged["pdfs"] = backend_detail["pdfs"] or existing_detail.get("pdfs", [])
    merged["tables"] = backend_detail["tables"] or existing_detail.get("tables", [])
    merged["standards"] = backend_detail["standards"] or existing_detail.get("standards", [])
    merged["annotated_images"] = (
        backend_detail.get("annotated_images")
        or existing_detail.get("annotated_images", [])
    )
    merged["overall_standard_compare"] = (
        backend_detail.get("overall_standard_compare")
        or existing_detail.get("overall_standard_compare", {})
    )
    merged["raw_json"] = existing_detail.get("raw_json") or backend_detail["raw_json"]
    if existing_detail.get("backend_file_path"):
        merged["backend_file_path"] = existing_detail["backend_file_path"]
    return merged


def refresh_single_task_detail_from_backend(task_id: str, force: bool = False, ttl_seconds: float = 3.0) -> bool:
    detail_sync_ts = st.session_state.setdefault("task_detail_sync_ts", {})
    now_ts = time.time()
    if (
        not force
        and st.session_state.get("task_details", {}).get(task_id)
        and (now_ts - float(detail_sync_ts.get(task_id, 0.0))) < ttl_seconds
    ):
        return True

    result = get_task_status_from_backend(task_id)
    if not result.get("success"):
        return False

    backend_data = result.get("data") or {}
    existing_detail = st.session_state.get("task_details", {}).get(task_id)
    merged = merge_backend_task_detail(existing_detail, backend_data)
    st.session_state.task_details[task_id] = merged
    detail_sync_ts[task_id] = now_ts
    upsert_task_summary(normalize_task_summary(merged))
    return True


def sync_tasks_from_backend(limit: int = 50) -> bool:
    tasks_result = list_tasks_from_backend(limit=limit)
    backend_rows = tasks_result.get("data") if tasks_result.get("success") else None
    if not backend_rows:
        return False

    existing_details = st.session_state.get("task_details", {})
    merged_details: dict[str, dict[str, Any]] = {}
    for row in backend_rows:
        task_id = row.get("task_id")
        if not task_id:
            continue
        merged_details[task_id] = merge_backend_task_detail(existing_details.get(task_id), row)

    if not merged_details:
        return False

    st.session_state.task_details = merged_details
    st.session_state.tasks = sort_task_summaries(
        [normalize_task_summary(detail) for detail in merged_details.values()]
    )

    if st.session_state.get("selected_task_id") not in st.session_state.task_details:
        st.session_state.selected_task_id = st.session_state.tasks[0]["task_id"]
    if (
        st.session_state.get("current_task_id") is not None
        and st.session_state.get("current_task_id") not in st.session_state.task_details
    ):
        st.session_state.current_task_id = st.session_state.tasks[0]["task_id"]

    return True


def maybe_sync_tasks_from_backend(force: bool = False, limit: int = 50) -> bool:
    now_ts = time.time()
    last_sync_ts = st.session_state.get("last_backend_sync_ts", 0.0)
    if not force and (now_ts - last_sync_ts) < 3.0:
        return False

    synced = sync_tasks_from_backend(limit=limit)
    if synced:
        st.session_state.last_backend_sync_ts = now_ts
    return synced


def normalize_backend_result(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert a future OCR payload to the POC task summary and task detail.

    Missing fields are filled with front-end defaults. This function is the next
    backend integration point; this POC does not call any real endpoint.
    """
    detail = normalize_task_detail({"data": payload.get("data", payload), "raw_response": payload})
    return normalize_task_summary(detail), detail


def load_mock_tasks() -> list[dict[str, Any]]:
    """Return the centralized demo data source for task details."""
    return [
        {
            "task_id": "TASK-20260521-001",
            "task_name": "压力容器图纸识别",
            "description": "压力容器施工图纸识别与标准引用抽取",
            "status": "已完成",
            "created_at": "2026-05-21 09:30:45",
            "processed_count": 3,
            "pdfs": [
                {
                    "pdf_name": "demo_njpc_001.pdf",
                    "status": "识别成功",
                    "project_name": "南京石化",
                    "unit_name": "常减压装置",
                    "equipment_name": "常压塔",
                    "drawing_no": "01237-T-001",
                    "discipline": "工艺",
                    "design_stage": "施工图",
                },
                {
                    "pdf_name": "demo_njpc_002.pdf",
                    "status": "识别成功",
                    "project_name": "南京石化",
                    "unit_name": "常减压装置",
                    "equipment_name": "常压塔",
                    "drawing_no": "01237-P-101",
                    "discipline": "管道",
                    "design_stage": "施工图",
                },
                {
                    "pdf_name": "demo_njpc_003.pdf",
                    "status": "识别成功",
                    "project_name": "南京石化",
                    "unit_name": "常减压装置",
                    "equipment_name": "常压塔",
                    "drawing_no": "01237-M-201",
                    "discipline": "设备",
                    "design_stage": "施工图",
                },
            ],
            "tables": [
                {
                    "pdf_name": "demo_njpc_001.pdf",
                    "page": 1,
                    "table_index": 1,
                    "label": "图签信息表",
                    "score": 0.96,
                    "bbox": [72, 608, 540, 764],
                    "image_path": "demo_outputs/task001/page_001_table_001.png",
                },
                {
                    "pdf_name": "demo_njpc_001.pdf",
                    "page": 1,
                    "table_index": 2,
                    "label": "标准引用表",
                    "score": 0.93,
                    "bbox": [80, 438, 532, 590],
                    "image_path": "demo_outputs/task001/page_001_table_002.png",
                },
                {
                    "pdf_name": "demo_njpc_002.pdf",
                    "page": 1,
                    "table_index": 3,
                    "label": "材料明细表",
                    "score": 0.91,
                    "bbox": [64, 352, 548, 602],
                    "image_path": "demo_outputs/task001/page_001_table_003.png",
                },
            ],
            "standards": [
                {
                    "pdf_name": "demo_njpc_001.pdf",
                    "standard_no": "GB/T 150.1-2024",
                    "matched_standard": "GB/T 150.1-2024 压力容器 第1部分",
                    "status": "通过",
                    "result_type": "标准匹配",
                    "source_table": "标准引用表",
                    "confidence": 0.97,
                    "suggestion": "标准号匹配，版本有效。",
                },
                {
                    "pdf_name": "demo_njpc_002.pdf",
                    "standard_no": "SH/T 3059-2023",
                    "matched_standard": "SH/T 3059-2023 石油化工管道设计",
                    "status": "通过",
                    "result_type": "标准匹配",
                    "source_table": "标准引用表",
                    "confidence": 0.95,
                    "suggestion": "可进入人工抽检。",
                },
            ],
        },
        {
            "task_id": "TASK-20260521-002",
            "task_name": "换热器图纸批量识别",
            "description": "换热器设备图纸批量识别",
            "status": "处理中",
            "created_at": "2026-05-21 10:12:22",
            "pdfs": [
                {
                    "pdf_name": "heat_exchanger_001.pdf",
                    "status": "识别成功",
                    "project_name": "南京石化",
                    "unit_name": "加氢装置",
                    "equipment_name": "换热器 E-450401",
                    "drawing_no": "HX-450401-A1",
                    "discipline": "设备",
                    "design_stage": "施工图",
                },
                {
                    "pdf_name": "heat_exchanger_002.pdf",
                    "status": "解析中",
                    "project_name": "南京石化",
                    "unit_name": "加氢装置",
                    "equipment_name": "换热器 E-450402",
                    "drawing_no": "HX-450402-A1",
                    "discipline": "设备",
                    "design_stage": "施工图",
                },
                {
                    "pdf_name": "heat_exchanger_003.pdf",
                    "status": "排队中",
                    "project_name": "南京石化",
                    "unit_name": "加氢装置",
                    "equipment_name": "换热器 E-450403",
                    "drawing_no": "",
                    "discipline": "设备",
                    "design_stage": "施工图",
                },
            ],
            "tables": [
                {
                    "pdf_name": "heat_exchanger_001.pdf",
                    "page": 1,
                    "table_index": 1,
                    "label": "图签信息表",
                    "score": 0.92,
                    "bbox": [74, 610, 542, 762],
                    "image_path": "demo_outputs/task002/page_001_table_001.png",
                }
            ],
            "standards": [
                {
                    "pdf_name": "heat_exchanger_001.pdf",
                    "standard_no": "GB/T 151-2024",
                    "matched_standard": "GB/T 151-2024 热交换器",
                    "status": "通过",
                    "result_type": "标准匹配",
                    "source_table": "标准引用表",
                    "confidence": 0.91,
                    "suggestion": "等待其余 PDF 完成后统一复核。",
                }
            ],
        },
        {
            "task_id": "TASK-20260520-003",
            "task_name": "塔器设备图纸识别",
            "description": "含低置信度标准引用的复核样例",
            "status": "待复核",
            "created_at": "2026-05-20 16:40:10",
            "processed_count": 3,
            "pdfs": [
                {
                    "pdf_name": "tower_vessel_001.pdf",
                    "status": "识别成功",
                    "project_name": "南京石化",
                    "unit_name": "芳烃装置",
                    "equipment_name": "精馏塔 V-182108",
                    "drawing_no": "TV-182108-A1",
                    "discipline": "设备",
                    "design_stage": "施工图",
                },
                {
                    "pdf_name": "tower_vessel_002.pdf",
                    "status": "待复核",
                    "project_name": "南京石化",
                    "unit_name": "芳烃装置",
                    "equipment_name": "精馏塔 V-182108",
                    "drawing_no": "TV-182108-P2",
                    "discipline": "管道",
                    "design_stage": "施工图",
                },
                {
                    "pdf_name": "tower_vessel_003.pdf",
                    "status": "异常",
                    "project_name": "南京石化",
                    "unit_name": "芳烃装置",
                    "equipment_name": "精馏塔 V-182108",
                    "drawing_no": "",
                    "discipline": "仪表",
                    "design_stage": "施工图",
                },
            ],
            "tables": [
                {
                    "pdf_name": "tower_vessel_002.pdf",
                    "page": 1,
                    "table_index": 1,
                    "label": "标准引用表",
                    "score": 0.68,
                    "bbox": [86, 432, 524, 594],
                    "image_path": "demo_outputs/task003/page_001_table_001.png",
                },
                {
                    "pdf_name": "tower_vessel_003.pdf",
                    "page": 1,
                    "table_index": 2,
                    "label": "图签信息表",
                    "score": 0.51,
                    "bbox": [82, 616, 510, 748],
                    "image_path": "demo_outputs/task003/page_001_table_002.png",
                },
            ],
            "standards": [
                {
                    "pdf_name": "tower_vessel_001.pdf",
                    "standard_no": "HG/T 20580-2024",
                    "matched_standard": "HG/T 20580-2024 钢制化工容器设计基础规定",
                    "status": "通过",
                    "result_type": "标准匹配",
                    "source_table": "标准引用表",
                    "confidence": 0.92,
                    "suggestion": "匹配成功。",
                },
                {
                    "pdf_name": "tower_vessel_002.pdf",
                    "standard_no": "GB 150-20?4",
                    "matched_standard": "候选：GB/T 150.1-2024",
                    "status": "待复核",
                    "result_type": "低置信度候选",
                    "source_table": "标准引用表",
                    "confidence": 0.63,
                    "suggestion": "标准号年份识别不完整，建议人工确认原图。",
                },
                {
                    "pdf_name": "tower_vessel_003.pdf",
                    "standard_no": "",
                    "matched_standard": "未匹配",
                    "status": "异常",
                    "result_type": "解析异常",
                    "source_table": "图签信息表",
                    "confidence": 0.0,
                    "suggestion": "图签区域置信度偏低，建议上传清晰版 PDF。",
                },
            ],
        },
    ]


def sort_task_summaries(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(tasks, key=lambda task: parse_created_at(task["created_at"]), reverse=True)


def build_initial_session_data() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    return [], {}


def initialize_state() -> None:
    if "tasks" not in st.session_state and "task_details" not in st.session_state:
        st.session_state.tasks, st.session_state.task_details = build_initial_session_data()
    elif "task_details" not in st.session_state:
        details = [
            normalize_task_detail(task)
            for task in st.session_state.tasks
            if isinstance(task, dict) and "pdfs" in task
        ]
        if details:
            st.session_state.task_details = {detail["task_id"]: detail for detail in details}
            st.session_state.tasks = [normalize_task_summary(detail) for detail in details]
        else:
            st.session_state.tasks, st.session_state.task_details = build_initial_session_data()
    elif "tasks" not in st.session_state:
        st.session_state.tasks = [
            normalize_task_summary(detail) for detail in st.session_state.task_details.values()
        ]

    st.session_state.tasks = sort_task_summaries(st.session_state.tasks)
    if "selected_task_id" not in st.session_state:
        st.session_state.selected_task_id = st.session_state.tasks[0]["task_id"] if st.session_state.tasks else None
    if "created_task_id" not in st.session_state:
        st.session_state.created_task_id = None
    if "upload_action_busy" not in st.session_state:
        st.session_state.upload_action_busy = False
    if "upload_action_name" not in st.session_state:
        st.session_state.upload_action_name = None
    if "upload_action_started_at" not in st.session_state:
        st.session_state.upload_action_started_at = 0.0
    if "last_backend_sync_ts" not in st.session_state:
        st.session_state.last_backend_sync_ts = 0.0
    if "task_detail_sync_ts" not in st.session_state:
        st.session_state.task_detail_sync_ts = {}
    if "current_page" not in st.session_state:
        st.session_state.current_page = "总览工作台"
    if "pending_page" in st.session_state:
        st.session_state.current_page = st.session_state.pending_page
        del st.session_state.pending_page
    if "standard_library_query" not in st.session_state:
        st.session_state.standard_library_query = ""
    if "standard_library_page" not in st.session_state:
        st.session_state.standard_library_page = 1
    if "standard_library_page_size" not in st.session_state:
        st.session_state.standard_library_page_size = 20
    if "standard_library_operator" not in st.session_state:
        st.session_state.standard_library_operator = STANDARD_LIBRARY_OPERATOR
    if "standard_library_query_input" not in st.session_state:
        st.session_state.standard_library_query_input = st.session_state.standard_library_query
    if "standard_library_editing_id" not in st.session_state:
        st.session_state.standard_library_editing_id = None
    if "standard_library_toast" not in st.session_state:
        st.session_state.standard_library_toast = None
    if "standard_library_pending_delete_id" not in st.session_state:
        st.session_state.standard_library_pending_delete_id = None
    if "pending_pdf_compare_notice" not in st.session_state:
        st.session_state.pending_pdf_compare_notice = ""
    if "last_synced_page" not in st.session_state:
        st.session_state.last_synced_page = ""

    # Failsafe: avoid getting stuck in busy mode after unexpected interruption.
    if st.session_state.upload_action_busy and st.session_state.upload_action_started_at:
        if time.time() - st.session_state.upload_action_started_at > 900:
            st.session_state.upload_action_busy = False
            st.session_state.upload_action_name = None
            st.session_state.upload_action_started_at = 0.0


def upsert_task_summary(summary: dict[str, Any]) -> None:
    tasks = [task for task in st.session_state.tasks if task["task_id"] != summary["task_id"]]
    st.session_state.tasks = sort_task_summaries([summary, *tasks])


def apply_page_style() -> None:
    st.set_page_config(
        page_title="图纸识别系统 POC",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.45rem; padding-bottom: 2rem; }
        [data-testid="stSidebar"] { background: #0f1f33; }
        [data-testid="stSidebar"] * { color: #f6f8fb; }
        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e6eaf0;
            border-radius: 8px;
            padding: 16px 18px;
            box-shadow: 0 1px 8px rgba(15, 31, 51, 0.05);
        }
        div[data-testid="stMetricValue"] { color: #0f172a; font-size: 1.62rem; }
        .section-note { color: #64748b; font-size: 0.92rem; margin-top: -0.3rem; }
        .collapsible-section-title {
            color: #0f172a;
            font-size: 1.72rem;
            font-weight: 700;
            line-height: 1.2;
            margin: 0.08rem 0 0.65rem 0;
        }
        .jump-anchor {
            display: block;
            height: 0;
            margin: 0;
            padding: 0;
            visibility: hidden;
        }
        .jump-link-caption {
            color: #6b7280;
            font-size: 0.88rem;
            margin: 0 0 0.35rem 0;
        }
        .jump-link-caption__anchor,
        .jump-link-caption__disabled {
            color: #6b7280;
            text-decoration: none;
        }
        .jump-link-caption__anchor:hover {
            color: #1d4ed8;
            text-decoration: underline;
        }
        .jump-link-caption__disabled {
            border-bottom: 1px dashed #cbd5e1;
            cursor: default;
        }
        .jump-back-link {
            color: #1d4ed8;
            display: inline-block;
            font-size: 0.92rem;
            margin-bottom: 0.85rem;
            text-decoration: none;
        }
        .jump-back-link:hover {
            text-decoration: underline;
        }
        .soft-panel {
            background: #ffffff;
            border: 1px solid #e6eaf0;
            border-radius: 8px;
            padding: 16px 18px;
            box-shadow: 0 1px 8px rgba(15, 31, 51, 0.04);
        }
        .status-pill {
            display: inline-block;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
            margin-bottom: 0.35rem;
            padding: 0.28rem 0.68rem;
        }
        .status-success { color: #15803d; background: #dcfce7; }
        .status-info { color: #1d4ed8; background: #dbeafe; }
        .status-warning { color: #b45309; background: #fef3c7; }
        .status-error { color: #b91c1c; background: #fee2e2; }
        div[data-testid="stFormSubmitButton"] button[kind="primary"],
        .stButton button[kind="primary"],
        button[data-testid="stBaseButton-primary"] {
            background: #1d4ed8;
            border-color: #1d4ed8;
            color: #ffffff;
        }
        div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
        .stButton button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            background: #1e40af;
            border-color: #1e40af;
            color: #ffffff;
        }
        [class*="st-key-collapse_toggle_"] button[kind="secondary"],
        [class*="st-key-collapse_toggle_"] button[data-testid="stBaseButton-secondary"] {
            background: transparent;
            border: none;
            box-shadow: none;
            color: #334155;
            line-height: 1;
            min-height: 2.6rem;
            padding: 0;
            justify-content: flex-start;
        }
        [class*="st-key-collapse_toggle_"] button[kind="secondary"] p,
        [class*="st-key-collapse_toggle_"] button[data-testid="stBaseButton-secondary"] p {
            color: inherit;
            font-size: 3.45rem;
            line-height: 1;
            margin: 0;
        }
        [class*="st-key-collapse_toggle_"] button[kind="secondary"]:hover,
        [class*="st-key-collapse_toggle_"] button[data-testid="stBaseButton-secondary"]:hover,
        [class*="st-key-collapse_toggle_"] button[kind="secondary"]:focus,
        [class*="st-key-collapse_toggle_"] button[data-testid="stBaseButton-secondary"]:focus {
            background: transparent;
            border: none;
            box-shadow: none;
            color: #1d4ed8;
        }
        [class*="st-key-toggle_overall_compare_"] button[kind="secondary"],
        [class*="st-key-toggle_overall_compare_"] button[data-testid="stBaseButton-secondary"],
        [class*="st-key-toggle_overall_image_"] button[kind="secondary"],
        [class*="st-key-toggle_overall_image_"] button[data-testid="stBaseButton-secondary"] {
            min-height: 1.95rem;
            padding: 0.08rem 0.6rem;
            border-radius: 0.46rem;
        }
        [class*="st-key-toggle_overall_compare_"] button[kind="secondary"] p,
        [class*="st-key-toggle_overall_compare_"] button[data-testid="stBaseButton-secondary"] p,
        [class*="st-key-toggle_overall_image_"] button[kind="secondary"] p,
        [class*="st-key-toggle_overall_image_"] button[data-testid="stBaseButton-secondary"] p {
            font-size: 0.92rem;
            line-height: 1.2;
            margin: 0;
        }
        [class*="st-key-edit_standard_"] button,
        [class*="st-key-delete_standard_"] button {
            min-width: 68px;
            padding-left: 10px;
            padding-right: 10px;
        }
        [class*="st-key-edit_standard_"] button p,
        [class*="st-key-delete_standard_"] button p {
            white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    style = STATUS_STYLE.get(status, "info")
    return f'<span class="status-pill status-{style}">{status}</span>'


def render_sidebar() -> str:
    st.sidebar.title("图纸识别系统")
    st.sidebar.caption("图纸识别 POC 原型")
    busy = st.session_state.get("upload_action_busy", False)

    requested_page = st.sidebar.radio(
        "导航",
        ["总览工作台", "新上传任务", "结果查看", "标准信息库"],
        label_visibility="collapsed",
        key="current_page",
        disabled=busy,
    )

    if busy:
        st.sidebar.info("当前操作执行中，导航暂不可点击，请等待完成。")

    page = requested_page

    st.sidebar.divider()
    return page


def summary_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "任务编号": task["task_id"],
            "任务名称": task["task_name"],
            "PDF 数量": task["pdf_count"],
            "状态": task["status"],
            "创建时间": task["created_at"],
            "操作提示": "进入结果查看页查看详情",
        }
        for task in sort_task_summaries(tasks)
    ]


def calculate_metrics(
    tasks: list[dict[str, Any]],
    task_details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "total_tasks": len(tasks),
        "today_pdfs": sum(task["pdf_count"] for task in tasks if task["created_at"].startswith(today)),
        "processing_tasks": sum(1 for task in tasks if task["status"] == "处理中"),
        "completed_tasks": sum(1 for task in tasks if task["status"] == "已完成"),
        "review_count": sum(task["review_count"] for task in tasks),
    }


def render_overview(
    tasks: list[dict[str, Any]],
    task_details: dict[str, dict[str, Any]],
) -> None:
    page_name = "总览工作台"
    should_sync = st.session_state.get("last_synced_page") != page_name
    if should_sync:
        maybe_sync_tasks_from_backend(limit=100)
    st.session_state.last_synced_page = page_name

    tasks = st.session_state.tasks
    task_details = st.session_state.task_details

    st.title("图纸识别系统 / 总览工作台")
    st.markdown('<p class="section-note">掌握识别任务整体进度与复核情况</p>', unsafe_allow_html=True)
    metrics = calculate_metrics(tasks, task_details)
    metric_items = [
        ("总任务数", metrics["total_tasks"]),
        ("今日上传 PDF 数", metrics["today_pdfs"]),
        ("处理中任务数", metrics["processing_tasks"]),
        ("已完成任务数", metrics["completed_tasks"]),
    ]
    metric_cols = st.columns(4)
    for index, (label, value) in enumerate(metric_items):
        metric_cols[index % 4].metric(label, value)

    st.divider()
    title_col, hint_col = st.columns([0.72, 0.28])
    title_col.subheader("最近任务")
    hint_col.info("从左侧“新上传任务”创建识别任务。")
    st.dataframe(summary_rows(tasks), width="stretch", hide_index=True)


def build_uploaded_task(task_name: str, description: str, files: list[Any]) -> dict[str, Any]:
    task_id = f"TASK-{datetime.now():%Y%m%d}-{uuid4().hex[:4].upper()}"
    file_names = [file.name for file in files]
    created_at = now_text()
    return normalize_task_detail(
        {
            "task_id": task_id,
            "task_name": task_name,
            "description": description,
            "file_names": file_names,
            "status": "处理中",
            "created_at": created_at,
            "pdfs": [
                {
                    "pdf_name": file.name,
                    "status": "排队中",
                    "table_count": 0,
                    "standard_count": 0,
                    "issue_count": 0,
                }
                for file in files
            ],
            "tables": [],
            "standards": [],
            "raw_json": {
                "source": "streamlit_demo_upload",
                "task_id": task_id,
                "task_name": task_name,
                "description": description,
                "created_at": created_at,
                "file_names": file_names,
                "files": [
                    {
                        "file_name": file.name,
                        "size": file.size,
                        "upload_status": "已选择，等待识别",
                    }
                    for file in files
                ],
            },
        }
    )


def generate_demo_completion_detail(task: dict[str, Any]) -> dict[str, Any]:
    """Create finished demo results for a queued upload without backend calls."""
    standards_pool = [
        ("GB/T 150.1-2024", "GB/T 150.1-2024 压力容器 第1部分"),
        ("SH/T 3059-2023", "SH/T 3059-2023 石油化工管道设计"),
        ("NB/T 47013-2025", "NB/T 47013-2025 承压设备无损检测"),
        ("HG/T 20580-2024", "HG/T 20580-2024 钢制化工容器设计基础规定"),
    ]
    disciplines = ["工艺", "管道", "设备", "仪表", "电气"]
    pdfs: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    standards: list[dict[str, Any]] = []

    for index, file_name in enumerate(task["file_names"], start=1):
        pdfs.append(
            {
                "pdf_name": file_name,
                "status": "识别成功",
                "project_name": "南京石化",
                "unit_name": "炼化一体化装置",
                "equipment_name": f"演示设备 {index:02d}",
                "drawing_no": f"NJPC-DEMO-{index:03d}",
                "discipline": disciplines[(index - 1) % len(disciplines)],
                "design_stage": "施工图",
                "table_count": 2,
                "standard_count": 1,
                "issue_count": 0,
            }
        )
        first_table = (index - 1) * 2 + 1
        tables.extend(
            [
                {
                    "pdf_name": file_name,
                    "page": 1,
                    "table_index": first_table,
                    "label": "图签信息表",
                    "score": 0.96,
                    "bbox": [72, 608, 540, 764],
                    "image_path": f"demo_outputs/{task['task_id']}/page_001_table_{first_table:03d}.png",
                },
                {
                    "pdf_name": file_name,
                    "page": 1,
                    "table_index": first_table + 1,
                    "label": "标准引用表",
                    "score": 0.93,
                    "bbox": [80, 438, 532, 590],
                    "image_path": f"demo_outputs/{task['task_id']}/page_001_table_{first_table + 1:03d}.png",
                },
            ]
        )
        standard_no, matched_standard = standards_pool[(index - 1) % len(standards_pool)]
        standards.append(
            {
                "pdf_name": file_name,
                "standard_no": standard_no,
                "matched_standard": matched_standard,
                "status": "通过",
                "result_type": "标准匹配",
                "source_table": "标准引用表",
                "confidence": 0.94,
                "suggestion": "标准号匹配，建议进入人工抽检。",
            }
        )

    result = {
        **task,
        "status": "已完成",
        "processed_count": len(pdfs),
        "pdf_count": len(pdfs),
        "table_count": len(tables),
        "standard_count": len(standards),
        "review_count": 0,
        "pdfs": pdfs,
        "tables": tables,
        "standards": standards,
    }
    result["raw_json"] = {
        "source": "poc_demo_completion",
        "task_id": task["task_id"],
        "status": "已完成",
        "completed_at": now_text(),
        "total_pdfs": len(pdfs),
        "processed_count": len(pdfs),
        "total_tables": len(tables),
        "total_standards": len(standards),
        "review_count": 0,
        "pdfs": pdfs,
        "tables": tables,
        "standards": standards,
    }
    return normalize_task_detail(result)


def complete_task_for_demo(task_id: str) -> None:
    detail = st.session_state.task_details.get(task_id)
    if not detail:
        return
    completed = generate_demo_completion_detail(detail)
    st.session_state.task_details[task_id] = completed
    st.session_state.selected_task_id = task_id
    upsert_task_summary(normalize_task_summary(completed))


def go_to_page(page: str) -> None:
    # Radio state can only be swapped safely before the next script rerun.
    st.session_state.pending_page = page
    st.rerun()


UPLOAD_ACTION_LABELS = {
    "upload": "开始上传",
    "process": "开始识别",
    "markdown": "转为Markdown",
    "detect": "标准检测",
}


def ensure_upload_state() -> None:
    state_defaults = {
        "upload_completed": False,
        "current_task_id": None,
        "tables_parsed": False,
        "current_tables": [],
        "markdown_conversion_completed": False,
        "markdown_file_paths": [],
        "markdown_results": [],
        "standard_detection_results": None,
        "upload_action_busy": False,
        "upload_action_name": None,
        "upload_action_started_at": 0.0,
        "upload_action_feedback": None,
    }
    for key, default in state_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = deepcopy(default) if isinstance(default, (list, dict)) else default


def start_upload_action(action: str) -> None:
    st.session_state.upload_action_busy = True
    st.session_state.upload_action_name = action
    st.session_state.upload_action_started_at = time.time()
    st.session_state.upload_action_feedback = None


def finish_upload_action(
    feedback_type: str | None = None,
    message: str | None = None,
) -> None:
    st.session_state.upload_action_busy = False
    st.session_state.upload_action_name = None
    st.session_state.upload_action_started_at = 0.0
    st.session_state.upload_action_feedback = (
        {"type": feedback_type, "message": message}
        if feedback_type and message
        else None
    )


def finish_upload_action_and_rerun(
    feedback_type: str | None = None,
    message: str | None = None,
) -> None:
    finish_upload_action(feedback_type, message)
    st.rerun()


def reset_markdown_outputs() -> None:
    st.session_state.markdown_conversion_completed = False
    st.session_state.markdown_file_paths = []
    st.session_state.markdown_results = []
    st.session_state.standard_detection_results = None


def reset_table_outputs() -> None:
    st.session_state.tables_parsed = False
    st.session_state.current_tables = []
    reset_markdown_outputs()


def render_upload_feedback() -> None:
    feedback = st.session_state.upload_action_feedback
    if not feedback:
        return

    renderer = getattr(st, feedback.get("type", "info"), st.info)
    renderer(feedback.get("message", ""))
    st.session_state.upload_action_feedback = None


def toggle_section_expanded(session_key: str) -> None:
    st.session_state[session_key] = not st.session_state[session_key]


def render_collapsible_section_header(title: str, state_key: str) -> bool:
    session_key = f"section_expanded_{state_key}"
    if session_key not in st.session_state:
        st.session_state[session_key] = True

    toggle_col, title_col = st.columns([0.032, 0.968])
    with toggle_col:
        with st.container(key=f"collapse_toggle_{state_key}"):
            icon = "▾" if st.session_state[session_key] else "▸"
            st.button(
                icon,
                key=f"{session_key}_toggle",
                help="展开或收起此部分",
                use_container_width=True,
                on_click=toggle_section_expanded,
                args=(session_key,),
            )

    with title_col:
        st.markdown(
            f"<div class='collapsible-section-title'>{title}</div>",
            unsafe_allow_html=True,
        )

    return st.session_state[session_key]


def resolve_table_index(item: dict[str, Any], fallback_index: int) -> int:
    raw_index = item.get("table_index") or item.get("index") or fallback_index
    try:
        return int(raw_index)
    except (TypeError, ValueError):
        return fallback_index


def table_display_name(table: dict[str, Any], fallback_index: int) -> str:
    display_name = str(table.get("display_name") or "").strip()
    if display_name:
        return display_name
    return f"表格{resolve_table_index(table, fallback_index)}"


def preview_anchor_id(table_index: int) -> str:
    return f"table-preview-{table_index}"


def markdown_anchor_id(table_index: int) -> str:
    return f"markdown-result-{table_index}"


def render_preview_title_link(page: int, table_index: int, has_markdown: bool, display_name: str = "") -> None:
    title_text = f"第{page}页 - {display_name or f'表格{table_index}'}"
    if has_markdown:
        st.markdown(
            (
                f'<div class="jump-link-caption">'
                f'<a class="jump-link-caption__anchor" href="#{markdown_anchor_id(table_index)}" '
                f'title="点击跳转到对应Markdown">{title_text}</a>'
                f"</div>"
            ),
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        (
            f'<div class="jump-link-caption">'
            f'<span class="jump-link-caption__disabled" title="请先点击转为Markdown">{title_text}</span>'
            f"</div>"
        ),
        unsafe_allow_html=True,
    )


def render_table_previews(tables: list[dict[str, Any]]) -> None:
    if not tables:
        return

    previews_expanded = render_collapsible_section_header("📸 表格图片预览", "table_previews")
    markdown_results = st.session_state.get("markdown_results", [])
    markdown_table_indexes = {
        resolve_table_index(result, fallback_index)
        for fallback_index, result in enumerate(markdown_results, start=1)
        if result.get("success") and result.get("md_content")
    }

    for fallback_index, table in enumerate(tables, start=1):
        table_index = resolve_table_index(table, fallback_index)
        display_name = table_display_name(table, fallback_index)
        image_url = table.get("image_url", "")
        page = table.get("page", 0)

        st.markdown(
            f'<div id="{preview_anchor_id(table_index)}" class="jump-anchor"></div>',
            unsafe_allow_html=True,
        )

        if not previews_expanded:
            continue

        render_preview_title_link(page, table_index, table_index in markdown_table_indexes, display_name)
        if image_url:
            full_url = f"{BACKEND_BASE_URL}{image_url}"
            st.image(full_url, use_container_width=True)
            st.caption(f"URL: {full_url}")
        else:
            st.warning("图片路径无效")


def render_markdown_results(results: list[dict[str, Any]]) -> None:
    if not results:
        return

    markdown_expanded = render_collapsible_section_header("📄 Markdown 转换结果", "markdown_results")

    current_task_id = st.session_state.current_task_id or "current"

    for fallback_index, result in enumerate(results, start=1):
        table_index = resolve_table_index(result, fallback_index)
        if result.get("success"):
            md_content = result.get("md_content", "")
            patched = result.get("patched", False)
            display_name = table_display_name(result, fallback_index)

            st.markdown(
                f'<div id="{markdown_anchor_id(table_index)}" class="jump-anchor"></div>',
                unsafe_allow_html=True,
            )

            if not markdown_expanded:
                continue

            with st.expander(display_name, expanded=False):
                st.markdown(
                    f'<a class="jump-back-link" href="#{preview_anchor_id(table_index)}" title="点击跳转到对应表格">查看对应表格</a>',
                    unsafe_allow_html=True,
                )
                if md_content:
                    if "<table>" in md_content or "<tr>" in md_content:
                        st.markdown(md_content, unsafe_allow_html=True)
                    else:
                        st.markdown(md_content)

                    st.download_button(
                        label=f"📥 下载 {display_name} 的 Markdown",
                        data=md_content,
                        file_name=f"{display_name}.md",
                        mime="text/markdown",
                        key=f"download_table_{current_task_id}_{table_index}",
                    )
                else:
                    st.info("Markdown 内容为空")
        else:
            if not markdown_expanded:
                continue
            error = result.get("error", "未知错误")
            st.error(f"❌ 表格 {table_index} 转换失败: {error}")


def render_standard_detection_results(detection_data: dict[str, Any]) -> None:
    if not detection_data:
        return

    total_standards = detection_data.get("total_standards", 0)
    exact_match = detection_data.get("exact_match_count", 0)
    year_mismatch = detection_data.get("year_mismatch_count", 0)
    similar = detection_data.get("similar_count", 0)
    not_found = detection_data.get("not_found_count", 0)

    stats_expanded = render_collapsible_section_header("📊 标准检测统计", "standard_stats")

    if stats_expanded:
        stat_cols = st.columns(5)
        stat_cols[0].metric("总计", total_standards)
        stat_cols[1].metric("完全符合", exact_match)
        stat_cols[2].metric("年份不一致", year_mismatch)
        stat_cols[3].metric("较为相似", similar)
        stat_cols[4].metric("不存在", not_found)

    results = detection_data.get("results", [])
    details_expanded = render_collapsible_section_header("📋 详细检测结果", "standard_details")

    if not results:
        if details_expanded:
            st.info("ℹ️ 未在Markdown文件中检测到标准号。")
        return

    if not details_expanded:
        return

    table_groups: dict[str, list[dict[str, Any]]] = {}
    table_labels: dict[str, str] = {}
    for result in results:
        table_key = (
            parse_table_group_key(result.get("table_group_key"))
            or parse_table_group_key(result.get("source_table"))
            or parse_table_group_key(result.get("table_display_name"))
            or parse_table_group_key(result.get("markdown_file"))
            or parse_table_group_key(result.get("table_index"))
            or "0"
        )
        table_groups.setdefault(table_key, []).append(result)
        table_label = (
            str(result.get("source_table") or "").strip()
            or str(result.get("table_display_name") or "").strip()
            or f"表{table_key}"
        )
        table_labels.setdefault(table_key, table_label)

    for table_key in sorted(table_groups.keys(), key=parse_table_group_sort_key):
        table_results = table_groups[table_key]
        display_name = table_labels.get(table_key, f"表{table_key}")

        with st.expander(f"📄 {display_name} ({len(table_results)} 个标准号)", expanded=False):
            for index, result in enumerate(table_results, 1):
                extracted = result.get("extracted", {})
                matched = result.get("matched_library_entry")
                status = result.get("status", "")
                message = result.get("message", "")

                status_color = {
                    "完全符合": "green",
                    "年份不一致": "orange",
                    "较为相似": "blue",
                    "不存在": "red",
                    "解析错误": "red",
                }.get(status, "gray")

                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 12px; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid {status_color};">
                    <strong>标准号 {index}:</strong> <code style="background-color: #e9ecef; padding: 2px 6px; border-radius: 3px;">{extracted.get('original', 'N/A')}</code><br>
                    <strong>比对结果:</strong> <span style="color: {status_color}; font-weight: bold;">{status}</span><br>
                    <strong>标准库匹配:</strong> {matched.get('original', '无') if matched else '无'}<br>
                    <strong>说明:</strong> {message}
                </div>
                """, unsafe_allow_html=True)


def render_upload(tasks: list[dict[str, Any]]) -> None:
    st.title("图纸识别系统 / 新上传任务")
    st.markdown('<p class="section-note">上传 PDF 图纸，启动新的识别任务</p>', unsafe_allow_html=True)

    ensure_upload_state()

    with st.form("new_task_form", clear_on_submit=False):
        task_name = st.text_input("任务名称", placeholder="请输入任务名称(可选,不填则使用文件名)")
        description = st.text_area("任务说明（可选）", placeholder="请输入任务说明")
        uploaded_files = st.file_uploader(
            "PDF 文件",
            type=["pdf"],
            accept_multiple_files=True,
            help="支持一次选择多个 PDF，用于演示任务创建与识别流程。",
        )
        if uploaded_files:
            st.dataframe(
                [
                    {
                        "文件名": file.name,
                        "文件大小": format_file_size(file.size),
                        "上传状态": "已选择，等待上传",
                    }
                    for file in uploaded_files
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("尚未选择文件")

        buttons_disabled = st.session_state.upload_action_busy

        col1, col2, col3, col4 = st.columns([0.2, 0.2, 0.25, 0.25])

        upload_submitted = col1.form_submit_button(
            "开始上传",
            type="primary",
            disabled=buttons_disabled,
            on_click=start_upload_action,
            args=("upload",),
        )
        process_submitted = col2.form_submit_button(
            "开始识别",
            type="primary",
            disabled=buttons_disabled,
            on_click=start_upload_action,
            args=("process",),
        )
        markdown_submitted = col3.form_submit_button(
            "转为Markdown",
            type="primary",
            disabled=buttons_disabled,
            on_click=start_upload_action,
            args=("markdown",),
        )
        detect_standards_submitted = col4.form_submit_button(
            "标准检测",
            type="primary",
            disabled=buttons_disabled,
            on_click=start_upload_action,
            args=("detect",),
        )

    if st.session_state.upload_action_busy and st.session_state.upload_action_name:
        action_label = UPLOAD_ACTION_LABELS.get(
            st.session_state.upload_action_name,
            st.session_state.upload_action_name,
        )
        st.info(f"正在执行“{action_label}”，其他按钮已暂时禁用，请等待后端返回。")

    if upload_submitted:
        if not uploaded_files:
            finish_upload_action_and_rerun("warning", "请至少选择一个 PDF 文件。")

        normalized_task_name = task_name.strip()
        with st.spinner(f"正在上传 {uploaded_files[0].name} 到后端..."):
            upload_result = upload_pdf_to_backend(
                uploaded_files[0],
                task_name=normalized_task_name or None,
            )

        if upload_result["success"]:
            backend_data = upload_result["data"]
            task_id = backend_data.get("task_id")

            detail = build_uploaded_task(
                normalized_task_name or uploaded_files[0].name,
                description.strip(),
                uploaded_files,
            )
            detail["task_id"] = task_id
            detail["backend_file_path"] = backend_data.get("file_path", "")

            st.session_state.task_details[detail["task_id"]] = detail
            upsert_task_summary(normalize_task_summary(detail))

            maybe_sync_tasks_from_backend(force=True)
            task_status_result = get_task_status_from_backend(task_id)
            if task_status_result["success"]:
                detail = merge_backend_task_detail(detail, task_status_result["data"])
            else:
                detail = st.session_state.task_details.get(task_id, detail)

            detail["task_name"] = normalized_task_name or detail.get("task_name") or uploaded_files[0].name
            detail["description"] = description.strip()
            detail["backend_file_path"] = backend_data.get("file_path", "")
            st.session_state.task_details[task_id] = detail
            upsert_task_summary(normalize_task_summary(detail))

            st.session_state.selected_task_id = detail["task_id"]
            st.session_state.current_task_id = task_id
            st.session_state.upload_completed = True
            reset_table_outputs()

            finish_upload_action_and_rerun(
                "success",
                f"✅ {upload_result['message']}\n\n任务ID: {task_id}\n文件已保存到: {backend_data.get('file_path', '未知')}",
            )

        finish_upload_action_and_rerun("error", f"❌ 上传失败: {upload_result['message']}")

    if process_submitted:
        task_id = st.session_state.current_task_id
        if not task_id:
            finish_upload_action_and_rerun("warning", "请先上传PDF文件。")

        with st.spinner("🔍 正在查询任务状态..."):
            status_result = check_parse_status(task_id)

        if not status_result["success"]:
            finish_upload_action_and_rerun("error", f"❌ 查询失败: {status_result.get('message')}")

        status_data = status_result["data"]
        status = status_data.get("status", 0)
        current_step = status_data.get("current_step", "")
        table_count = status_data.get("table_count", 0)

        if status == 0 or current_step == "文件已上传,等待解析":
            with st.spinner("🔍 正在解析PDF并提取表格图片，这可能需要几分钟..."):
                process_result = process_tables_from_backend(task_id)

            if process_result["success"]:
                process_data = process_result["data"]
                total_tables = process_data.get("total_tables", 0)
                tables = process_data.get("tables", [])

                print(f"[前端调试] 解析结果: {process_data}")
                if tables:
                    print(f"[前端调试] 第一个表格的image_url: {tables[0].get('image_url')}")
                    print(f"[前端调试] 完整URL: {BACKEND_BASE_URL}{tables[0].get('image_url')}")

                if task_id in st.session_state.task_details:
                    detail = st.session_state.task_details[task_id]
                    detail["tables"] = tables
                    detail["total_pages"] = process_data.get("total_pages", 0)
                    detail["total_tables"] = total_tables
                    st.session_state.task_details[task_id] = detail

                st.session_state.current_tables = tables
                st.session_state.tables_parsed = bool(tables)
                reset_markdown_outputs()
                maybe_sync_tasks_from_backend(force=True)

                print(f"[前端调试] 已保存 {len(tables)} 个表格到 session_state")

                finish_upload_action_and_rerun(
                    "success",
                    f"✅ {process_result['message']}\n\n共识别到 {total_tables} 个表格",
                )

            finish_upload_action_and_rerun("error", f"❌ 解析失败: {process_result['message']}")

        if table_count > 0:
            finish_upload_action_and_rerun(
                "info",
                "✅ 表格已提取完成，请点击'转为Markdown'按钮。",
            )

        if status == 2 or current_step == "解析完成":
            finish_upload_action_and_rerun("info", "✅ 表格已经解析完成，请点击'转为Markdown'按钮。")
        if status == 1:
            finish_upload_action_and_rerun("warning", f"任务正在解析中，请稍后重试。\n\n当前状态: {current_step}")
        if status == 3:
            finish_upload_action_and_rerun(
                "error",
                f"❌ 上次解析失败: {current_step}\n\n请重新点击'开始识别'重试。",
            )

        finish_upload_action_and_rerun("warning", f"未知状态: status={status}, step={current_step}")

    if markdown_submitted:
        task_id = st.session_state.current_task_id

        if not task_id:
            finish_upload_action_and_rerun("warning", "请先上传PDF文件。")

        with st.spinner("🔍 正在查询任务状态..."):
            status_result = check_parse_status(task_id)

        if not status_result["success"]:
            finish_upload_action_and_rerun("error", f"❌ 查询失败: {status_result.get('message')}")

        status_data = status_result["data"]
        status = status_data.get("status", 0)
        current_step = status_data.get("current_step", "")
        table_count = status_data.get("table_count", 0)

        if table_count > 0:
            tables = st.session_state.current_tables

            print(f"[前端调试] Markdown按钮: status={status}, tables数量={len(tables) if tables else 0}")

            if not tables:
                print("[前端调试] session_state 中没有 tables，重新调用识别接口获取")
                with st.spinner("正在获取表格数据..."):
                    process_result = process_tables_from_backend(task_id)

                if process_result["success"]:
                    tables = process_result["data"].get("tables", [])
                    st.session_state.current_tables = tables
                    st.session_state.tables_parsed = bool(tables)
                    print(f"[前端调试] 重新获取到 {len(tables)} 个表格")
                else:
                    finish_upload_action_and_rerun("error", f"❌ 获取表格数据失败: {process_result['message']}")

            if not tables:
                finish_upload_action_and_rerun("warning", "⚠️ 未找到表格数据，请重新点击'开始识别'。")

            with st.spinner("📝 正在将表格图片转换为Markdown，这可能需要较长时间..."):
                markdown_result = convert_to_markdown_from_backend(task_id, tables)

            if markdown_result["success"]:
                markdown_data = markdown_result["data"]
                results = markdown_data.get("results", [])
                success_count = markdown_data.get("success_count", 0)
                total_tables = markdown_data.get("total_tables", 0)

                md_file_paths = []
                for result in results:
                    if result.get("success"):
                        md_file = result.get("md_file", "")
                        if md_file:
                            md_file_paths.append(md_file)

                st.session_state.markdown_file_paths = md_file_paths
                st.session_state.markdown_results = results
                st.session_state.markdown_conversion_completed = True
                st.session_state.standard_detection_results = None
                maybe_sync_tasks_from_backend(force=True)
                print(f"[前端调试] 已保存 {len(md_file_paths)} 个Markdown文件路径")

                finish_upload_action_and_rerun(
                    "success",
                    f"✅ {markdown_result['message']}\n\n成功转换 {success_count}/{total_tables} 个表格",
                )

            finish_upload_action_and_rerun("error", f"❌ 转换失败: {markdown_result['message']}")

        if status == 0 and table_count == 0:
            finish_upload_action_and_rerun(
                "warning",
                f"️ 表格还未提取完成，请先点击'开始识别'并等待解析完成。\n\n当前状态: {current_step}",
            )
        if status == 3:
            finish_upload_action_and_rerun(
                "error",
                f"❌ 上次解析失败: {current_step}\n\n请先重新点击'开始识别'进行解析。",
            )

        finish_upload_action_and_rerun("warning", f"未知状态: status={status}, step={current_step}")

    if detect_standards_submitted:
        task_id = st.session_state.current_task_id

        if not task_id:
            finish_upload_action_and_rerun("warning", "请先上传PDF文件。")
        if not st.session_state.markdown_conversion_completed:
            finish_upload_action_and_rerun("warning", "请先将表格转为Markdown格式。")

        markdown_files = st.session_state.markdown_file_paths
        if not markdown_files:
            finish_upload_action_and_rerun("warning", "⚠️ 未找到Markdown文件，请重新点击'转为Markdown'。")

        with st.spinner(f"🔍 正在检测 {len(markdown_files)} 个Markdown文件中的标准号..."):
            detection_result = detect_standards_from_backend(task_id, markdown_files)

        if detection_result["success"]:
            detection_data = detection_result["data"]
            total_standards = detection_data.get("total_standards", 0)
            st.session_state.standard_detection_results = detection_data
            maybe_sync_tasks_from_backend(force=True)

            finish_upload_action_and_rerun(
                "success",
                f"✅ {detection_result['message']}\n\n共检测到 {total_standards} 个标准号",
            )

        finish_upload_action_and_rerun("error", f"❌ 检测失败: {detection_result['message']}")

    render_upload_feedback()
    render_table_previews(st.session_state.current_tables)
    render_markdown_results(st.session_state.markdown_results)
    render_standard_detection_results(st.session_state.standard_detection_results)

    if st.session_state.current_task_id:
        task_id = st.session_state.current_task_id
        detail = st.session_state.task_details.get(task_id)
        if detail:
            st.markdown('<div class="soft-panel">', unsafe_allow_html=True)
            st.write("新任务编号")
            st.code(task_id, language="text")
            st.info("可前往结果查看页面查看任务详情。")
            st.markdown("</div>", unsafe_allow_html=True)

            cols = st.columns([0.2, 0.2, 0.24, 0.36])
            if cols[0].button("查看任务详情", type="primary", key="go_created_detail"):
                st.session_state.selected_task_id = task_id
                go_to_page("结果查看")
            if cols[1].button("返回总览工作台", key="go_created_overview"):
                go_to_page("总览工作台")


def render_task_header(detail: dict[str, Any]) -> None:
    st.subheader(f"{detail['task_id']}  {detail['task_name']}")
    st.markdown(status_badge(detail["status"]), unsafe_allow_html=True)
    st.caption(detail["description"] or "暂无任务说明")
    cols = st.columns(4)
    cols[0].metric("PDF 数量", len(detail["pdfs"]))
    cols[1].metric("当前状态", detail["status"])
    cols[2].metric("已识别表格数", len(detail["tables"]))
    standard_count = detail.get("standard_count")
    cols[3].metric("标准条数", standard_count if standard_count is not None else len(detail["standards"]))
    if detail.get("current_step") == "标准检测完成":
        progress = 1.0
    else:
        progress = processed_count(detail) / len(detail["pdfs"]) if detail["pdfs"] else 0
    st.progress(progress, text=f"任务处理进度 {progress:.0%}")


def get_query_param(name: str) -> str:
    value = st.query_params.get(name)
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value) if value is not None else ""


def clear_resource_view_query() -> None:
    params = dict(st.query_params)
    for key in ("view", "task_id", "table_index", "standalone"):
        params.pop(key, None)
    st.query_params.clear()
    for key, value in params.items():
        st.query_params[key] = value


def is_standalone_resource_view() -> bool:
    return (
        get_query_param("standalone") == "1"
        and get_query_param("view") in {"table_image", "table_markdown", "table_result", "standard_compare", "overall_compare", "annotated_image"}
    )


def build_resource_view_link(
    view: str,
    task_id: str,
    table_index: int,
    standalone: bool = True,
    pdf_name: str = "",
) -> str:
    link = f"?view={view}&task_id={task_id}&table_index={table_index}"
    if pdf_name:
        link += f"&pdf_name={quote(str(pdf_name))}"
    if standalone:
        link += "&standalone=1"
    return link


def can_open_overall_compare_for_pdf(detail: dict[str, Any], pdf_name: str) -> bool:
    if not str(pdf_name or "").strip():
        return False
    completed_at = str(detail.get("completed_at") or "").strip()
    current_step = str(detail.get("current_step") or "").strip()
    if not completed_at:
        return False
    if current_step != "标准检测完成":
        return False
    return True


def render_pdf_compare_not_ready_dialog(pdf_name: str) -> None:
    dialog_api = getattr(st, "dialog", None)
    if callable(dialog_api):
        @dialog_api("提示")
        def _modal() -> None:
            st.warning(f"请等待标准检测完成。\n\n当前文件: {pdf_name or '-'}")
            if st.button("确定", key=f"confirm_pdf_notice_{pdf_name}"):
                st.session_state.pending_pdf_compare_notice = ""
                st.rerun()

        _modal()
        return

    st.warning(f"请等待标准检测完成。当前文件: {pdf_name or '-'}")


def apply_standalone_resource_style() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="collapsedControl"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def resolve_table_image_url(table: dict[str, Any]) -> str:
    image_url = table.get("image_url", "")
    if image_url:
        return f"{BACKEND_BASE_URL}{image_url}" if image_url.startswith("/") else image_url

    image_path = table.get("image_path", "")
    if not image_path:
        return ""

    try:
        relative_path = Path(image_path).resolve().relative_to(BACKEND_TMP_DIR.resolve())
        return f"{BACKEND_BASE_URL}/api/files/{relative_path.as_posix()}"
    except Exception:
        return ""


def resolve_file_url(resource: dict[str, Any]) -> str:
    image_url = resource.get("image_url", "")
    if image_url:
        return f"{BACKEND_BASE_URL}{image_url}" if image_url.startswith("/") else image_url

    image_path = resource.get("image_path", "")
    if not image_path:
        return ""

    try:
        relative_path = Path(image_path).resolve().relative_to(BACKEND_TMP_DIR.resolve())
        return f"{BACKEND_BASE_URL}/api/files/{relative_path.as_posix()}"
    except Exception:
        return ""


def first_annotated_image(detail: dict[str, Any], page: int = 1) -> dict[str, Any]:
    images = detail.get("annotated_images") or []
    if images:
        return next((item for item in images if int(item.get("page") or 0) == page), images[0])

    task_id = detail.get("task_id", "")
    if not task_id:
        return {}
    fallback_path = BACKEND_TMP_DIR / "table_blocks" / task_id / "paddleocr_vl_debug" / f"page_{page:03d}_annotated.png"
    if fallback_path.exists():
        return {"page": page, "image_path": str(fallback_path)}
    return {}


def build_markdown_lookup(task_id: str) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    detail = st.session_state.get("task_details", {}).get(task_id, {})
    for fallback_index, table in enumerate(detail.get("tables", []), start=1):
        idx = resolve_table_index(table, fallback_index)
        if idx <= 0:
            continue
        md_content = table.get("markdown_content") or ""
        highlighted_md_content = table.get("highlighted_markdown_content") or ""
        md_file = table.get("markdown_path") or ""
        if md_content or highlighted_md_content or md_file:
            lookup[idx] = {
                "md_content": md_content,
                "highlighted_md_content": highlighted_md_content,
                "md_file": md_file,
            }

    markdown_dir = BACKEND_TMP_DIR / "markdown" / task_id
    if markdown_dir.exists():
        for md_file in sorted(markdown_dir.glob("*.md")):
            match = re.search(r"_table_(\d+)", md_file.stem)
            if not match:
                continue
            table_index = int(match.group(1))
            if table_index in lookup and (
                lookup[table_index].get("md_content")
                or lookup[table_index].get("highlighted_md_content")
            ):
                continue
            try:
                md_content = md_file.read_text(encoding="utf-8")
            except Exception:
                md_content = ""
            if table_index not in lookup:
                lookup[table_index] = {
                    "md_content": md_content,
                    "highlighted_md_content": "",
                    "md_file": str(md_file),
                }

    return lookup


def parse_table_index_from_text(value: Any) -> int:
    text = str(value or "")
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def parse_table_group_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    md_match = re.search(r"_table_(\d+)(?:_part_(\d+)|_safe50_(upper|lower))?", text)
    if md_match:
        base = md_match.group(1)
        part = md_match.group(2)
        legacy = md_match.group(3)
        if part:
            return f"{int(base)}-{int(part)}"
        if legacy:
            return f"{int(base)}-{'1' if legacy == 'upper' else '2'}"
        return str(int(base))

    match = re.search(r"(\d+)(?:\s*[-_]\s*(\d+))?", text)
    if not match:
        return ""
    if match.group(2):
        return f"{int(match.group(1))}-{int(match.group(2))}"
    return str(int(match.group(1)))


def parse_table_group_sort_key(group_key: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", str(group_key or ""))
    if not match:
        return (10**9, 10**9)
    base = int(match.group(1))
    part = int(match.group(2)) if match.group(2) else 0
    return (base, part)


def build_standard_compare_groups(detail: dict[str, Any]) -> list[dict[str, Any]]:
    task_id = detail.get("task_id", "")
    tables = detail.get("tables", [])
    table_lookup = {
        resolve_table_index(table, idx): table
        for idx, table in enumerate(tables, start=1)
    }

    groups: dict[str, dict[str, Any]] = {}

    detection_data = st.session_state.get("standard_detection_results")
    use_detection_data = bool(
        detection_data
        and st.session_state.get("current_task_id") == task_id
        and detection_data.get("results")
    )

    if use_detection_data:
        for result in detection_data.get("results", []):
            table_key = (
                parse_table_group_key(result.get("table_group_key"))
                or parse_table_group_key(result.get("source_table"))
                or parse_table_group_key(result.get("table_display_name"))
                or parse_table_group_key(result.get("markdown_file"))
                or parse_table_group_key(result.get("table_index"))
            )
            table_index = parse_table_index_from_text(table_key)
            if table_index <= 0:
                continue

            group = groups.setdefault(
                table_key,
                {
                    "table_index": table_index,
                    "table_key": table_key,
                    "display_name": (
                        str(result.get("source_table") or "").strip()
                        or str(result.get("table_display_name") or "").strip()
                        or table_display_name(table_lookup.get(table_index, {}), table_index)
                        or f"表格{table_key}"
                    ),
                    "source_pdf": "-",
                    "page": "-",
                    "total": 0,
                    "exact_match": 0,
                    "year_mismatch": 0,
                    "similar": 0,
                    "not_found": 0,
                    "results": [],
                },
            )

            status = result.get("status", "")
            group["total"] += 1
            if status == "完全符合":
                group["exact_match"] += 1
            elif status == "年份不一致":
                group["year_mismatch"] += 1
            elif status == "较为相似":
                group["similar"] += 1
            elif status == "不存在":
                group["not_found"] += 1

            group["results"].append(result)
    else:
        for idx, item in enumerate(detail.get("standards", []), start=1):
            table_key = parse_table_group_key(item.get("source_table")) or str(idx)
            table_index = parse_table_index_from_text(table_key) or idx
            group = groups.setdefault(
                table_key,
                {
                    "table_index": table_index,
                    "table_key": table_key,
                    "display_name": (
                        str(item.get("source_table") or "").strip()
                        or table_display_name(table_lookup.get(table_index, {}), table_index)
                        or f"表格{table_key}"
                    ),
                    "source_pdf": "-",
                    "page": "-",
                    "total": 0,
                    "exact_match": 0,
                    "year_mismatch": 0,
                    "similar": 0,
                    "not_found": 0,
                    "results": [],
                },
            )

            status = item.get("status", "")
            group["total"] += 1
            if status in {"通过", "完全符合"}:
                group["exact_match"] += 1
            elif status == "年份不一致":
                group["year_mismatch"] += 1
            elif status in {"待复核", "较为相似"}:
                group["similar"] += 1
            elif status in {"异常", "失败", "不存在"}:
                group["not_found"] += 1

            group["results"].append(
                {
                    "status": "完全符合" if status == "通过" else status,
                    "message": item.get("suggestion", ""),
                    "extracted": {"original": item.get("standard_no", "-")},
                    "matched_library_entry": {"original": item.get("matched_standard", "-")},
                }
            )

    for _, group in groups.items():
        table_index = group.get("table_index", 0)
        table = table_lookup.get(table_index)
        if table:
            group["source_pdf"] = table.get("pdf_name") or detail.get("original_filename") or "-"
            group["page"] = table.get("page", "-")
            if not str(group.get("display_name") or "").strip():
                group["display_name"] = table_display_name(table, table_index)
        else:
            group["source_pdf"] = detail.get("original_filename") or "-"

    return [groups[key] for key in sorted(groups.keys(), key=parse_table_group_sort_key)]


def render_table_resource_detail_view(task_details: dict[str, dict[str, Any]]) -> bool:
    view = get_query_param("view")
    if view not in {"table_image", "table_markdown", "table_result", "standard_compare", "overall_compare", "annotated_image"}:
        return False

    task_id = get_query_param("task_id")
    table_index_text = get_query_param("table_index")
    try:
        table_index = int(table_index_text)
    except ValueError:
        table_index = 0

    detail = task_details.get(task_id)
    if not detail:
        st.error("未找到对应的表格资源。")
        if st.button("返回结果列表", key="back_result_list_invalid"):
            clear_resource_view_query()
            st.rerun()
        return True

    if view == "annotated_image":
        if st.button("返回结果列表", key=f"back_result_list_{view}_{task_id}"):
            clear_resource_view_query()
            st.rerun()

        annotated_image = first_annotated_image(detail)
        image_url = resolve_file_url(annotated_image)
        st.subheader(f"任务 {task_id} / 总识别图")
        if image_url:
            st.image(image_url, use_container_width=True)
            st.caption(f"图片链接: {image_url}")
        else:
            st.warning("未找到可访问的总识别图。")
        return True

    if view == "overall_compare":
        if st.button("返回结果列表", key=f"back_result_list_{view}_{task_id}"):
            clear_resource_view_query()
            st.rerun()

        pdf_name = get_query_param("pdf_name")
        title_pdf = pdf_name or detail.get("original_filename") or "-"
        st.subheader(f"任务 {task_id} / PDF {title_pdf} / 总标准结果对比")

        # 强校验: 必须任务已完成标准检测，且链接包含有效pdf_name。
        if not can_open_overall_compare_for_pdf(detail, title_pdf):
            st.warning("请等待标准检测完成")
            return True

        valid_pdf_names = {
            str((pdf or {}).get("pdf_name") or "").strip()
            for pdf in (detail.get("pdfs") or [])
            if str((pdf or {}).get("pdf_name") or "").strip()
        }
        if valid_pdf_names and title_pdf not in valid_pdf_names:
            st.error("当前PDF不属于该任务，无法查看总标准结果对比。")
            return True

        overall = detail.get("overall_standard_compare") or {}
        rows = overall.get("results") or []

        if rows:
            table_rows = []
            for item in rows:
                extracted = item.get("extracted") or {}
                matched = item.get("matched_library_entry") or {}
                table_rows.append(
                    {
                        "提取标准信息": extracted.get("original") or "-",
                        "标准库信息": matched.get("original") or "-",
                        "比对结果": item.get("status") or "-",
                    }
                )
            st.dataframe(table_rows, width="stretch", hide_index=True)
        else:
            st.info("当前任务暂无总标准对比结果。")

        return True

    if table_index <= 0:
        st.error("未找到对应的表格资源。")
        if st.button("返回结果列表", key="back_result_list_invalid_table"):
            clear_resource_view_query()
            st.rerun()
        return True

    tables = detail.get("tables", [])
    table = next(
        (item for idx, item in enumerate(tables, start=1) if resolve_table_index(item, idx) == table_index),
        None,
    )
    if not table:
        st.error("未找到对应的表格记录。")
        if st.button("返回结果列表", key="back_result_list_missing"):
            clear_resource_view_query()
            st.rerun()
        return True

    if st.button("返回结果列表", key=f"back_result_list_{view}_{task_id}_{table_index}"):
        clear_resource_view_query()
        st.rerun()

    display_name = table_display_name(table, table_index)
    st.subheader(f"任务 {task_id} / {display_name}")
    source_pdf = table.get("pdf_name") or detail.get("original_filename") or "-"
    st.caption(f"来源PDF: {source_pdf} | 页码: {table.get('page', '-')}")

    if view == "table_image":
        image_url = resolve_table_image_url(table)
        if image_url:
            st.image(image_url, use_container_width=True)
            st.caption(f"图片链接: {image_url}")
            try:
                image_resp = requests.get(image_url, timeout=15)
                if image_resp.ok:
                    st.download_button(
                        label="下载裁剪表格图片",
                        data=image_resp.content,
                        file_name=f"{task_id}_table_{table_index}.png",
                        mime="image/png",
                        key=f"download_image_{task_id}_{table_index}",
                    )
            except Exception:
                pass
        else:
            st.warning("未找到可访问的裁剪表格图片链接。")
        return True

    if view == "table_result":
        image_col, md_col = st.columns(2)

        with image_col:
            st.markdown("#### 裁剪表格图片")
            image_url = resolve_table_image_url(table)
            if image_url:
                st.image(image_url, use_container_width=True)
                try:
                    image_resp = requests.get(image_url, timeout=15)
                    if image_resp.ok:
                        st.download_button(
                            label="下载裁剪表格图片",
                            data=image_resp.content,
                            file_name=f"{task_id}_table_{table_index}.png",
                            mime="image/png",
                            key=f"download_image_combined_{task_id}_{table_index}",
                        )
                except Exception:
                    pass
            else:
                st.warning("未找到可访问的裁剪表格图片链接。")

        with md_col:
            st.markdown("#### 表格识别Markdown")
            markdown_lookup = build_markdown_lookup(task_id)
            markdown_item = markdown_lookup.get(table_index)
            md_content = (markdown_item or {}).get("md_content", "")
            if md_content:
                if "<table>" in md_content or "<tr>" in md_content:
                    st.markdown(md_content, unsafe_allow_html=True)
                else:
                    st.markdown(md_content)
                st.download_button(
                    label="下载Markdown",
                    data=md_content,
                    file_name=f"{task_id}_table_{table_index}.md",
                    mime="text/markdown",
                    key=f"download_markdown_combined_{task_id}_{table_index}",
                )
            else:
                st.info("等待markdown生成")

        return True

    if view == "standard_compare":
        compare_groups = build_standard_compare_groups(detail)
        group = next((item for item in compare_groups if item.get("table_index") == table_index), None)
        if not group:
            st.warning("未找到该表格的标准对比结果。")
            return True

        st.markdown("### 标准对比结果预览")
        stat_cols = st.columns(5)
        stat_cols[0].metric("总计标准号", group["total"])
        stat_cols[1].metric("完全符合", group["exact_match"])
        stat_cols[2].metric("年份不一致", group["year_mismatch"])
        stat_cols[3].metric("较为相似", group["similar"])
        stat_cols[4].metric("不存在", group["not_found"])

        st.markdown("#### 对应Markdown（命中标准号已高亮）")
        markdown_lookup = build_markdown_lookup(task_id)
        markdown_item = markdown_lookup.get(table_index)
        md_content = (markdown_item or {}).get("md_content", "")
        highlighted_md_content = (markdown_item or {}).get("highlighted_md_content", "")
        if highlighted_md_content:
            st.markdown(highlighted_md_content, unsafe_allow_html=True)
        elif md_content:
            st.markdown(md_content, unsafe_allow_html=True)
        else:
            st.info("等待markdown生成")

        st.markdown("#### 比对明细")
        detail_rows = []
        for result in group.get("results", []):
            extracted = result.get("extracted", {})
            matched = result.get("matched_library_entry") or {}
            detail_rows.append(
                {
                    "提取标准信息": extracted.get("original", "-"),
                    "标准库信息": matched.get("original", "-"),
                    "比对结果": result.get("status", ""),
                    "说明": result.get("message", "") or "-",
                }
            )

        if detail_rows:
            st.dataframe(detail_rows, width="stretch", hide_index=True)
        else:
            st.info("当前表格暂无比对明细。")

        return True

    markdown_lookup = build_markdown_lookup(task_id)
    markdown_item = markdown_lookup.get(table_index)
    md_content = (markdown_item or {}).get("md_content", "")
    if md_content:
        if "<table>" in md_content or "<tr>" in md_content:
            st.markdown(md_content, unsafe_allow_html=True)
        else:
            st.markdown(md_content)
        st.download_button(
            label="下载Markdown",
            data=md_content,
            file_name=f"{task_id}_table_{table_index}.md",
            mime="text/markdown",
            key=f"download_markdown_{task_id}_{table_index}",
        )
    else:
        st.warning("该表格尚未生成Markdown内容，请先执行转为Markdown。")

    return True


def render_result_tabs(detail: dict[str, Any]) -> None:
    drawing_tab, table_tab, standard_tab, debug_tab = st.tabs(
        ["图纸识别结果", "表格解析结果", "标准提取比对结果", "技术调试信息"]
    )
    with drawing_tab:
        pdf_file = detail.get("original_filename") or "，".join(
            [file_name for file_name in detail.get("file_names", []) if file_name]
        )
        overall_image_state_key = f"overall_image_inline_open_pdf_{detail['task_id']}"
        open_overall_image_pdf = st.session_state.get(overall_image_state_key)
        overall_compare_state_key = f"overall_compare_inline_open_pdf_{detail['task_id']}"
        open_overall_compare_pdf = st.session_state.get(overall_compare_state_key)
        pdf_rows = detail.get("pdfs") or []
        if not pdf_rows:
            pdf_rows = [{"pdf_name": pdf_file or "-", "status": detail.get("current_step") or "-"}]

        header_style = "font-size:0.96rem;font-weight:700;line-height:1.25;margin-bottom:0.1rem;white-space:nowrap;"
        value_style = "font-size:0.92rem;line-height:1.35;white-space:nowrap;"
        col_spec = [0.22, 0.15, 0.16, 0.15, 0.10, 0.12, 0.1]
        header_cols = st.columns(col_spec, gap="small")
        header_cols[0].markdown(f'<div style="{header_style}">任务号</div>', unsafe_allow_html=True)
        header_cols[1].markdown(f'<div style="{header_style}">PDF 文件</div>', unsafe_allow_html=True)
        header_cols[2].markdown(f'<div style="{header_style}">任务开始时间</div>', unsafe_allow_html=True)
        header_cols[3].markdown(f'<div style="{header_style}">任务结束时间</div>', unsafe_allow_html=True)
        header_cols[4].markdown(f'<div style="{header_style}">状态</div>', unsafe_allow_html=True)
        header_cols[5].markdown(f'<div style="{header_style}">总识别图</div>', unsafe_allow_html=True)
        header_cols[6].markdown(f'<div style="{header_style}">总标准结果对比</div>', unsafe_allow_html=True)

        for idx, pdf in enumerate(pdf_rows, start=1):
            current_pdf_name = pdf.get("pdf_name") or pdf_file or "-"
            status_text = detail.get("current_step") or "-"
            can_open = can_open_overall_compare_for_pdf(detail, current_pdf_name)
            annotated_image = first_annotated_image(detail, int(pdf.get("page") or 1))
            can_open_annotated_image = bool(resolve_file_url(annotated_image))
            is_image_open = open_overall_image_pdf == current_pdf_name
            is_overall_open = open_overall_compare_pdf == current_pdf_name
            task_id_display, task_id_full = truncate_display_text(detail.get("task_id") or "-")
            pdf_name_display, pdf_name_full = truncate_display_text(current_pdf_name)

            row_cols = st.columns(col_spec, gap="small")
            row_cols[0].markdown(
                f'<div style="{value_style}" title="{escape(task_id_full)}">{escape(task_id_display)}</div>',
                unsafe_allow_html=True,
            )
            row_cols[1].markdown(
                f'<div style="{value_style}" title="{escape(pdf_name_full)}">{escape(pdf_name_display)}</div>',
                unsafe_allow_html=True,
            )
            row_cols[2].markdown(f'<div style="{value_style}">{detail.get("started_at") or "-"}</div>', unsafe_allow_html=True)
            row_cols[3].markdown(f'<div style="{value_style}">{detail.get("completed_at") or "-"}</div>', unsafe_allow_html=True)
            row_cols[4].markdown(f'<div style="{value_style}">{status_text}</div>', unsafe_allow_html=True)
            if can_open_annotated_image:
                image_button_label = "关闭图片" if is_image_open else "查看图片"
                if row_cols[5].button(image_button_label, key=f"toggle_overall_image_{detail['task_id']}_{idx}"):
                    st.session_state[overall_image_state_key] = None if is_image_open else current_pdf_name
                    st.rerun()
            else:
                row_cols[5].markdown(f'<div style="{value_style}">-</div>', unsafe_allow_html=True)
            if can_open:
                button_label = "关闭结果" if is_overall_open else "查看结果"
                if row_cols[6].button(button_label, key=f"toggle_overall_compare_{detail['task_id']}_{idx}"):
                    st.session_state[overall_compare_state_key] = None if is_overall_open else current_pdf_name
                    st.rerun()
            else:
                row_cols[6].markdown(f'<div style="{value_style}">-</div>', unsafe_allow_html=True)

        if open_overall_image_pdf:
            selected_pdf_row = next(
                (item for item in pdf_rows if (item.get("pdf_name") or pdf_file or "-") == open_overall_image_pdf),
                {},
            )
            selected_page = int(selected_pdf_row.get("page") or 1)
            annotated_image = first_annotated_image(detail, selected_page)
            image_url = resolve_file_url(annotated_image)

            st.divider()
            st.markdown(f"#### 总识别图（{open_overall_image_pdf}）")
            if image_url:
                st.image(image_url, use_container_width=True)
                st.caption(f"图片链接: {image_url}")
            else:
                st.info("当前任务暂无可展示的总识别图。")

        if open_overall_compare_pdf:
            st.divider()
            st.markdown(f"#### 总标准结果对比（{open_overall_compare_pdf}）")
            overall = detail.get("overall_standard_compare") or {}
            rows = overall.get("results") or []

            if rows:
                table_rows = []
                for item in rows:
                    extracted = item.get("extracted") or {}
                    matched = item.get("matched_library_entry") or {}
                    table_rows.append(
                        {
                            "提取标准信息": extracted.get("original") or "-",
                            "标准库信息": matched.get("original") or "-",
                            "比对结果": item.get("status") or "-",
                        }
                    )
                st.dataframe(table_rows, width="stretch", hide_index=True)
            else:
                st.info("当前任务暂无总标准对比结果。")
    with table_tab:
        tables = detail.get("tables", [])
        if tables:
            header_cols = st.columns([0.28, 0.22, 0.1, 0.4])
            header_cols[0].markdown("**任务号**")
            header_cols[1].markdown("**来源 PDF**")
            header_cols[2].markdown("**页码**")
            header_cols[3].markdown("**表格识别结果**")

            for idx, table in enumerate(tables, start=1):
                table_index = resolve_table_index(table, idx)
                display_name = table_display_name(table, idx)
                source_pdf = table.get("pdf_name") or detail.get("original_filename") or "-"
                result_link = build_resource_view_link("table_result", detail["task_id"], table_index)

                row_cols = st.columns([0.28, 0.22, 0.1, 0.4])
                row_cols[0].write(detail["task_id"])
                row_cols[1].write(source_pdf)
                row_cols[2].write(table.get("page", "-"))
                row_cols[3].markdown(
                    f'<a href="{result_link}" target="_blank">{display_name}</a>',
                    unsafe_allow_html=True,
                )

                st.divider()
        else:
            st.info("当前任务尚未生成表格解析结果。")
    with standard_tab:
        groups = build_standard_compare_groups(detail)
        if groups:
            header_cols = st.columns([0.2, 0.13, 0.1, 0.1, 0.09, 0.09, 0.09, 0.08, 0.12])
            header_cols[0].markdown("**任务id**")
            header_cols[1].markdown("**来源pdf**")
            header_cols[2].markdown("**来源表格**")
            header_cols[3].markdown("**总计标准号**")
            header_cols[4].markdown("**完全符合**")
            header_cols[5].markdown("**年份不一致**")
            header_cols[6].markdown("**较为相似**")
            header_cols[7].markdown("**不存在**")
            header_cols[8].markdown("**标准对比详情**")

            for group in groups:
                table_index = group["table_index"]
                display_name = group.get("display_name") or f"表格{table_index}"
                table_image_link = build_resource_view_link("table_image", detail["task_id"], table_index)
                standard_compare_link = build_resource_view_link("standard_compare", detail["task_id"], table_index)
                row_cols = st.columns([0.2, 0.13, 0.1, 0.1, 0.09, 0.09, 0.09, 0.08, 0.12])
                row_cols[0].write(detail["task_id"])
                row_cols[1].write(group.get("source_pdf", "-"))
                row_cols[2].markdown(
                    f'<a href="{table_image_link}" target="_blank">{display_name}</a>',
                    unsafe_allow_html=True,
                )
                row_cols[3].write(group.get("total", 0))
                row_cols[4].write(group.get("exact_match", 0))
                row_cols[5].write(group.get("year_mismatch", 0))
                row_cols[6].write(group.get("similar", 0))
                row_cols[7].write(group.get("not_found", 0))
                row_cols[8].markdown(
                    f'<a href="{standard_compare_link}" target="_blank">查看详情</a>',
                    unsafe_allow_html=True,
                )
                st.divider()
        else:
            st.info("当前任务尚未生成标准提取比对结果。")
    with debug_tab:
        st.json(detail.get("raw_json", {}))


def render_results(
    tasks: list[dict[str, Any]],
    task_details: dict[str, dict[str, Any]],
) -> None:
    st.title("图纸识别系统 / 结果查看")
    st.markdown('<p class="section-note">查看历史任务与单个任务的识别详情</p>', unsafe_allow_html=True)

    page_name = "结果查看"
    should_sync = st.session_state.get("last_synced_page") != page_name
    if should_sync:
        maybe_sync_tasks_from_backend(limit=100)
    st.session_state.last_synced_page = page_name

    tasks = st.session_state.tasks
    task_details = st.session_state.task_details

    if not tasks:
        st.info("暂无任务数据，请先在“新上传任务”页面创建任务。")
        return

    deep_link_task_id = get_query_param("task_id")
    if deep_link_task_id:
        refresh_single_task_detail_from_backend(deep_link_task_id)
        task_details = st.session_state.task_details

    if render_table_resource_detail_view(task_details):
        return

    with st.expander("历史任务列表", expanded=False):
        st.dataframe(summary_rows(tasks), width="stretch", hide_index=True)

    labels = {f"{task['task_id']}｜{task['task_name']}": task["task_id"] for task in tasks}
    task_ids = list(labels.values())
    previous_selected_task_id = st.session_state.selected_task_id
    selected_index = task_ids.index(st.session_state.selected_task_id) if st.session_state.selected_task_id in task_ids else 0
    selected_label = st.selectbox("选择任务", options=list(labels.keys()), index=selected_index)
    task_id = labels[selected_label]
    st.session_state.selected_task_id = task_id
    cached_detail = st.session_state.task_details.get(task_id, {})
    need_backend_highlight = (
        str(cached_detail.get("current_step") or "") == "标准检测完成"
        and bool(cached_detail.get("tables"))
        and not any(
            str((table or {}).get("highlighted_markdown_content") or "").strip()
            for table in (cached_detail.get("tables") or [])
        )
    )
    detail_incomplete = (
        not cached_detail
        or (
            not cached_detail.get("tables")
            and (
                int(cached_detail.get("table_count") or 0) > 0
                or str(cached_detail.get("current_step") or "") == "标准检测完成"
            )
        )
        or (
            not cached_detail.get("standards")
            and int(cached_detail.get("standard_count") or 0) > 0
        )
        or need_backend_highlight
    )

    # 在进入结果页、切换任务、或缓存明细不完整时，主动拉取任务完整详情。
    if should_sync or task_id != previous_selected_task_id or detail_incomplete:
        refresh_single_task_detail_from_backend(task_id, force=detail_incomplete)
    task_details = st.session_state.task_details
    detail = task_details[task_id]

    message = st.session_state.pop("demo_completion_message", None)
    if message:
        st.success(message)

    render_task_header(detail)
    st.divider()
    render_result_tabs(detail)


def _run_delete_standard(standard_id: int) -> None:
    delete_result = delete_standard_data_from_backend(int(standard_id))
    if delete_result.get("success"):
        st.session_state.standard_library_toast = {
            "level": "success",
            "message": "删除成功",
        }
        st.session_state.standard_library_pending_delete_id = None
        if st.session_state.standard_library_editing_id == int(standard_id):
            st.session_state.standard_library_editing_id = None
        st.rerun()
    else:
        st.error(delete_result.get("message", "删除失败"))


def render_standard_delete_confirm_dialog(standard_id: int, standard_no: str) -> None:
    dialog_api = getattr(st, "dialog", None)
    if callable(dialog_api):
        @dialog_api("删除确认")
        def _modal() -> None:
            st.write(f"是否确认删除标准：{standard_no or '-'}")
            confirm_cols = st.columns([0.3, 0.3, 0.4])
            if confirm_cols[0].button("是", key=f"confirm_delete_standard_{standard_id}", type="primary"):
                _run_delete_standard(standard_id)
            if confirm_cols[1].button("否", key=f"cancel_delete_standard_{standard_id}"):
                st.session_state.standard_library_pending_delete_id = None
                st.rerun()

        _modal()
        return

    # Fallback for older Streamlit versions without st.dialog.
    st.warning(f"是否确认删除标准：{standard_no or '-'}")
    confirm_cols = st.columns([0.12, 0.12, 0.76])
    if confirm_cols[0].button("是", key=f"confirm_delete_standard_{standard_id}", type="primary"):
        _run_delete_standard(standard_id)
    if confirm_cols[1].button("否", key=f"cancel_delete_standard_{standard_id}"):
        st.session_state.standard_library_pending_delete_id = None
        st.rerun()


def render_standard_library() -> None:
    st.title("图纸识别系统 / 标准信息库")
    st.markdown('<p class="section-note">标准库数据独立管理（增删改查与模糊查询）</p>', unsafe_allow_html=True)
    st.session_state.last_synced_page = "标准信息库"

    pending_toast = st.session_state.pop("standard_library_toast", None)
    if isinstance(pending_toast, dict) and pending_toast.get("message"):
        level = pending_toast.get("level", "success")
        icon = "✅" if level == "success" else "⚠️"
        st.toast(pending_toast.get("message"), icon=icon)

    with st.form("standard_library_search_form", clear_on_submit=False):
        query_col, size_col, user_col, action_col = st.columns([0.42, 0.16, 0.2, 0.22])
        query_col.text_input(
            "模糊查询",
            key="standard_library_query_input",
            placeholder="按标准号/标准类型/标准前缀查询",
        )
        page_size = size_col.selectbox(
            "每页条数",
            options=[10, 20, 50, 100],
            index=[10, 20, 50, 100].index(st.session_state.standard_library_page_size),
            key="standard_library_page_size_input",
        )
        user_col.text_input(
            "操作人",
            value=STANDARD_LIBRARY_OPERATOR,
            disabled=True,
        )
        action_col.markdown('<div style="height: 1.7rem;"></div>', unsafe_allow_html=True)
        search_submitted = action_col.form_submit_button("查询", type="primary")

    if search_submitted:
        st.session_state.standard_library_query = (
            st.session_state.get("standard_library_query_input", "") or ""
        ).strip()
        st.session_state.standard_library_page_size = int(page_size)
        st.session_state.standard_library_page = 1
        st.session_state.standard_library_editing_id = None
        st.rerun()

    st.divider()

    with st.expander("新增标准信息", expanded=False):
        with st.form("standard_library_create_form", clear_on_submit=True):
            new_no = st.text_input("标准号")
            new_type = st.text_input("标准类型")
            new_prefix = st.text_input("标准前缀")
            submitted = st.form_submit_button("新增", type="primary")

        if submitted:
            create_result = create_standard_data_from_backend(
                standard_no=new_no,
                standard_type=new_type,
                standard_prefix=new_prefix,
                operator=STANDARD_LIBRARY_OPERATOR,
            )
            if create_result.get("success"):
                st.session_state.standard_library_toast = {
                    "level": "success",
                    "message": "新增成功",
                }
                st.rerun()
            else:
                st.error(create_result.get("message", "新增失败"))

    list_result = list_standard_data_from_backend(
        keyword=st.session_state.standard_library_query,
        page=st.session_state.standard_library_page,
        page_size=st.session_state.standard_library_page_size,
    )

    if not list_result.get("success"):
        st.error(list_result.get("message", "查询失败"))
        return

    payload = list_result.get("data") or {}
    items = payload.get("items") or []
    total = int(payload.get("total") or 0)
    page = int(payload.get("page") or 1)
    page_size = int(payload.get("page_size") or st.session_state.standard_library_page_size)

    st.caption(f"共 {total} 条，当前第 {page} 页")

    if not items:
        st.info("暂无标准信息数据")
        return

    pending_delete_id = st.session_state.get("standard_library_pending_delete_id")
    if pending_delete_id is not None:
        pending_row = next(
            (row for row in items if int(row.get("id") or 0) == int(pending_delete_id)),
            None,
        )
        if pending_row:
            render_standard_delete_confirm_dialog(
                int(pending_delete_id),
                str(pending_row.get("standard_no") or ""),
            )
        else:
            st.session_state.standard_library_pending_delete_id = None

    # 在“标准类型”和“标准前缀”之间增加留白，避免两列过于拥挤。
    column_spec = [0.17, 0.085, 0.03, 0.11, 0.13, 0.13, 0.09, 0.09, 0.145]
    header_cols = st.columns(column_spec, gap="small")
    header_cols[0].markdown("**标准号**")
    header_cols[1].markdown("**标准类型**")
    header_cols[2].markdown("")
    header_cols[3].markdown("**标准前缀**")
    header_cols[4].markdown("**创建时间**")
    header_cols[5].markdown("**更新时间**")
    header_cols[6].markdown("**创建人**")
    header_cols[7].markdown("**更新人**")
    header_cols[8].markdown("**操作**")

    for row in items:
        standard_id = row.get("id")
        if not standard_id:
            continue

        with st.container(border=True):
            row_cols = st.columns(column_spec, gap="small")
            row_cols[0].write(row.get("standard_no") or "无")
            row_cols[1].write(row.get("standard_type") or "无")
            row_cols[2].write("")
            row_cols[3].write(row.get("standard_prefix") or "无")
            row_cols[4].write(format_date_only_text(row.get("create_time")))
            row_cols[5].write(format_date_only_text(row.get("update_time")))
            row_cols[6].write(row.get("create_user") or "无")
            row_cols[7].write(row.get("update_user") or "无")

            action_cols = row_cols[8].columns(2)
            if action_cols[0].button("编辑", key=f"edit_standard_{standard_id}"):
                st.session_state.standard_library_editing_id = int(standard_id)
            if action_cols[1].button("删除", key=f"delete_standard_{standard_id}"):
                st.session_state.standard_library_pending_delete_id = int(standard_id)
                st.rerun()

            if st.session_state.standard_library_editing_id == int(standard_id):
                st.markdown(f"编辑记录（ID: {standard_id}）")
                edit_no = st.text_input(
                    "标准号",
                    value=row.get("standard_no") or "",
                    key=f"edit_standard_no_{standard_id}",
                )
                edit_type = st.text_input(
                    "标准类型",
                    value=row.get("standard_type") or "",
                    key=f"edit_standard_type_{standard_id}",
                )
                edit_prefix = st.text_input(
                    "标准前缀",
                    value=row.get("standard_prefix") or "",
                    key=f"edit_standard_prefix_{standard_id}",
                )

                op_cols = st.columns([0.2, 0.2, 0.6])
                if op_cols[0].button("保存", key=f"save_standard_{standard_id}", type="primary"):
                    update_result = update_standard_data_from_backend(
                        standard_id=int(standard_id),
                        standard_no=edit_no,
                        standard_type=edit_type,
                        standard_prefix=edit_prefix,
                        operator=STANDARD_LIBRARY_OPERATOR,
                    )
                    if update_result.get("success"):
                        st.session_state.standard_library_toast = {
                            "level": "success",
                            "message": "编辑成功",
                        }
                        st.session_state.standard_library_editing_id = None
                        st.rerun()
                    else:
                        st.error(update_result.get("message", "更新失败"))

                if op_cols[1].button("取消", key=f"cancel_edit_standard_{standard_id}"):
                    st.session_state.standard_library_editing_id = None
                    st.rerun()

    page_count = max(1, (total + page_size - 1) // page_size)
    pager_cols = st.columns([0.2, 0.2, 0.6])
    if pager_cols[0].button("上一页", disabled=page <= 1, key="standard_library_prev"):
        st.session_state.standard_library_page = max(1, page - 1)
        st.rerun()
    if pager_cols[1].button("下一页", disabled=page >= page_count, key="standard_library_next"):
        st.session_state.standard_library_page = min(page_count, page + 1)
        st.rerun()


def main() -> None:
    apply_page_style()
    initialize_state()

    if is_standalone_resource_view():
        apply_standalone_resource_style()
        render_results(st.session_state.tasks, st.session_state.task_details)
        return

    # Ensure deep-links from table result rows always render in the results page.
    if get_query_param("view") in {"table_image", "table_markdown", "table_result", "standard_compare", "overall_compare", "annotated_image"}:
        st.session_state.current_page = "结果查看"

    page = render_sidebar()
    if page == "总览工作台":
        render_overview(st.session_state.tasks, st.session_state.task_details)
    elif page == "新上传任务":
        render_upload(st.session_state.tasks)
    elif page == "结果查看":
        render_results(st.session_state.tasks, st.session_state.task_details)
    else:
        render_standard_library()


if __name__ == "__main__":
    main()