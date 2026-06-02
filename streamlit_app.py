from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import time
from typing import Any
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


def parse_created_at(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
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
    if not source_pdfs and file_names:
        source_pdfs = [{"pdf_name": file_name, "status": "排队中"} for file_name in file_names]

    pdfs = [normalize_pdf(pdf, tables, standards) for pdf in source_pdfs]
    return {
        "task_id": data.get("task_id") or f"TASK-{datetime.now():%Y%m%d}-{uuid4().hex[:4].upper()}",
        "task_name": data.get("task_name") or "未命名识别任务",
        "description": data.get("description") or "",
        "file_names": file_names or [pdf["pdf_name"] for pdf in pdfs],
        "pdfs": pdfs,
        "tables": tables,
        "standards": standards,
        "raw_json": data.get("raw_json") or stable_raw_json(source),
        "status": data.get("status") or "处理中",
        "created_at": data.get("created_at") or now_text(),
        "processed_count": data.get("processed_count"),
        "pdf_count": data.get("pdf_count", data.get("total_pdfs")),
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
        "pdf_count": detail.get("pdf_count") or len(detail["pdfs"]),
        "processed_count": processed_count(detail),
        "table_count": table_total if table_total is not None else len(detail["tables"]),
        "standard_count": standard_total if standard_total is not None else len(detail["standards"]),
        "review_count": review_count(detail),
        "status": detail["status"],
        "created_at": detail["created_at"],
        "file_names": detail["file_names"],
    }


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
    details = [normalize_task_detail(task) for task in load_mock_tasks()]
    task_details = {detail["task_id"]: detail for detail in details}
    tasks = sort_task_summaries([normalize_task_summary(detail) for detail in details])
    return tasks, task_details


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
        st.session_state.selected_task_id = st.session_state.tasks[0]["task_id"]
    if "created_task_id" not in st.session_state:
        st.session_state.created_task_id = None
    if "current_page" not in st.session_state:
        st.session_state.current_page = "总览工作台"
    if "pending_page" in st.session_state:
        st.session_state.current_page = st.session_state.pending_page
        del st.session_state.pending_page


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
    page = st.sidebar.radio(
        "导航",
        ["总览工作台", "新上传任务", "结果查看"],
        label_visibility="collapsed",
        key="current_page",
    )
    st.sidebar.divider()
    st.sidebar.caption("演示环境")
    return page


def summary_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "任务编号": task["task_id"],
            "任务名称": task["task_name"],
            "PDF 数量": task["pdf_count"],
            "已处理数量": task["processed_count"],
            "待复核数量": task["review_count"],
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
    standards = [
        standard
        for detail in task_details.values()
        for standard in detail.get("standards", [])
    ]
    standard_passes = sum(1 for standard in standards if standard["status"] == "通过")
    return {
        "total_tasks": len(tasks),
        "today_pdfs": sum(task["pdf_count"] for task in tasks if task["created_at"].startswith(today)),
        "processing_tasks": sum(1 for task in tasks if task["status"] == "处理中"),
        "completed_tasks": sum(1 for task in tasks if task["status"] == "已完成"),
        "review_count": sum(task["review_count"] for task in tasks),
        "failed_count": sum(failed_count(detail) for detail in task_details.values()),
        "standard_pass_rate": standard_passes / len(standards) if standards else 0,
    }


def render_overview(
    tasks: list[dict[str, Any]],
    task_details: dict[str, dict[str, Any]],
) -> None:
    st.title("图纸识别系统 / 总览工作台")
    st.markdown('<p class="section-note">掌握识别任务整体进度与复核情况</p>', unsafe_allow_html=True)
    metrics = calculate_metrics(tasks, task_details)
    metric_items = [
        ("总任务数", metrics["total_tasks"]),
        ("今日上传 PDF 数", metrics["today_pdfs"]),
        ("处理中任务数", metrics["processing_tasks"]),
        ("已完成任务数", metrics["completed_tasks"]),
        ("待复核数量", metrics["review_count"]),
        ("异常 / 失败数量", metrics["failed_count"]),
        ("标准通过率", f"{metrics['standard_pass_rate']:.1%}"),
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
        "upload_action_feedback": None,
    }
    for key, default in state_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = deepcopy(default) if isinstance(default, (list, dict)) else default


def start_upload_action(action: str) -> None:
    st.session_state.upload_action_busy = True
    st.session_state.upload_action_name = action
    st.session_state.upload_action_feedback = None


def finish_upload_action(
    feedback_type: str | None = None,
    message: str | None = None,
) -> None:
    st.session_state.upload_action_busy = False
    st.session_state.upload_action_name = None
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


def render_table_previews(tables: list[dict[str, Any]]) -> None:
    if not tables:
        return

    st.markdown("### 📸 表格图片预览")

    cols_per_row = 2
    for index in range(0, len(tables), cols_per_row):
        cols = st.columns(cols_per_row)
        for offset in range(cols_per_row):
            table_index = index + offset
            if table_index >= len(tables):
                continue

            table = tables[table_index]
            image_url = table.get("image_url", "")
            page = table.get("page", 0)

            with cols[offset]:
                st.caption(f"第{page}页 - 表格 {table_index + 1}")
                if image_url:
                    full_url = f"{BACKEND_BASE_URL}{image_url}"
                    st.image(full_url, use_container_width=True)
                    st.caption(f"URL: {full_url}")
                else:
                    st.warning("图片路径无效")


def render_markdown_results(results: list[dict[str, Any]]) -> None:
    if not results:
        return

    st.markdown("### 📄 Markdown 转换结果")
    current_task_id = st.session_state.current_task_id or "current"

    for result in results:
        if result.get("success"):
            table_index = result.get("table_index", 0)
            md_content = result.get("md_content", "")
            patched = result.get("patched", False)

            with st.expander(f"表格 {table_index} {'(已优化)' if patched else ''}", expanded=False):
                if md_content:
                    if "<table>" in md_content or "<tr>" in md_content:
                        st.markdown(md_content, unsafe_allow_html=True)
                    else:
                        st.markdown(md_content)

                    st.download_button(
                        label=f"📥 下载表格 {table_index} 的 Markdown",
                        data=md_content,
                        file_name=f"table_{table_index}.md",
                        mime="text/markdown",
                        key=f"download_table_{current_task_id}_{table_index}",
                    )
                else:
                    st.info("Markdown 内容为空")
        else:
            table_index = result.get("table_index", 0)
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

    st.markdown("### 📊 标准检测统计")

    stat_cols = st.columns(5)
    stat_cols[0].metric("总计", total_standards)
    stat_cols[1].metric("完全符合", exact_match)
    stat_cols[2].metric("年份不一致", year_mismatch)
    stat_cols[3].metric("较为相似", similar)
    stat_cols[4].metric("不存在", not_found)

    results = detection_data.get("results", [])
    if not results:
        st.info("ℹ️ 未在Markdown文件中检测到标准号。")
        return

    st.markdown("### 📋 详细检测结果")

    table_groups: dict[int, list[dict[str, Any]]] = {}
    for result in results:
        table_idx = result.get("table_index", 0)
        table_groups.setdefault(table_idx, []).append(result)

    for table_idx in sorted(table_groups.keys()):
        table_results = table_groups[table_idx]
        md_file = table_results[0].get("markdown_file", "")
        md_filename = Path(md_file).name if md_file else f"表格 {table_idx}"

        with st.expander(f"📄 {md_filename} ({len(table_results)} 个标准号)", expanded=False):
            for index, result in enumerate(table_results, 1):
                extracted = result.get("extracted", {})
                matched = result.get("matched_library_entry")
                status = result.get("status", "")
                score = result.get("score", 0)
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
                    <strong>比对结果:</strong> <span style="color: {status_color}; font-weight: bold;">{status}</span> (分数: {score})<br>
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

                print(f"[前端调试] 已保存 {len(tables)} 个表格到 session_state")

                finish_upload_action_and_rerun(
                    "success",
                    f"✅ {process_result['message']}\n\n共识别到 {total_tables} 个表格",
                )

            finish_upload_action_and_rerun("error", f"❌ 解析失败: {process_result['message']}")

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

        if status == 2 or current_step == "解析完成":
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
                print(f"[前端调试] 已保存 {len(md_file_paths)} 个Markdown文件路径")

                finish_upload_action_and_rerun(
                    "success",
                    f"✅ {markdown_result['message']}\n\n成功转换 {success_count}/{total_tables} 个表格",
                )

            finish_upload_action_and_rerun("error", f"❌ 转换失败: {markdown_result['message']}")

        if status == 0 or status == 1:
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
    cols = st.columns(6)
    cols[0].metric("PDF 数量", len(detail["pdfs"]))
    cols[1].metric("当前状态", detail["status"])
    cols[2].metric("已识别表格数", len(detail["tables"]))
    cols[3].metric("标准条数", len(detail["standards"]))
    cols[4].metric("待复核数量", review_count(detail))
    cols[5].metric("已处理数量", processed_count(detail))
    progress = processed_count(detail) / len(detail["pdfs"]) if detail["pdfs"] else 0
    st.progress(progress, text=f"任务处理进度 {progress:.0%}")


def render_result_tabs(detail: dict[str, Any]) -> None:
    drawing_tab, table_tab, standard_tab, debug_tab = st.tabs(
        ["图纸识别结果", "表格解析结果", "标准提取比对结果", "技术调试信息"]
    )
    with drawing_tab:
        st.dataframe(
            [
                {
                    "PDF 文件": pdf["pdf_name"],
                    "图号": pdf["drawing_no"] or "-",
                    "项目名称": pdf["project_name"] or "-",
                    "装置 / 设备": pdf["equipment_name"] or pdf["unit_name"] or "-",
                    "专业": pdf["discipline"] or "-",
                    "阶段": pdf["design_stage"] or "-",
                    "状态": pdf["status"],
                }
                for pdf in detail["pdfs"]
            ],
            width="stretch",
            hide_index=True,
        )
    with table_tab:
        tables = detail.get("tables", [])
        if tables:
            rows = [
                {
                    "序号": table.get("table_index", "-"),
                    "来源 PDF": table.get("pdf_name", "-"),
                    "页码": table.get("page", "-"),
                    "表格类型": table.get("label", "-"),
                    "置信度": f"{table.get('score', 0):.0%}",
                    "bbox": table.get("bbox", []),
                    "裁剪文件路径": table.get("image_path", "-"),
                }
                for table in tables
            ]
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("当前任务尚未生成表格解析结果。")
    with standard_tab:
        rows = [
            {
                "PDF 文件": standard["pdf_name"],
                "识别标准号": standard["standard_no"] or "-",
                "标准库匹配": standard["matched_standard"],
                "结论": standard["status"],
                "来源表格": standard["source_table"],
                "置信度": f"{standard['confidence']:.0%}",
                "建议": standard["suggestion"],
            }
            for standard in detail["standards"]
        ]
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
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
    with st.expander("历史任务列表", expanded=False):
        st.dataframe(summary_rows(tasks), width="stretch", hide_index=True)

    labels = {f"{task['task_id']}｜{task['task_name']}": task["task_id"] for task in tasks}
    task_ids = list(labels.values())
    selected_index = task_ids.index(st.session_state.selected_task_id) if st.session_state.selected_task_id in task_ids else 0
    selected_label = st.selectbox("选择任务", options=list(labels.keys()), index=selected_index)
    task_id = labels[selected_label]
    st.session_state.selected_task_id = task_id
    detail = task_details[task_id]

    message = st.session_state.pop("demo_completion_message", None)
    if message:
        st.success(message)
    if detail["status"] == "处理中":
        if st.button("模拟完成识别", type="primary", key=f"complete_result_{task_id}"):
            complete_task_for_demo(task_id)
            st.session_state.demo_completion_message = "演示识别已完成，可查看识别结果。"
            st.rerun()

    render_task_header(detail)
    st.divider()
    render_result_tabs(detail)


def main() -> None:
    apply_page_style()
    initialize_state()
    page = render_sidebar()
    if page == "总览工作台":
        render_overview(st.session_state.tasks, st.session_state.task_details)
    elif page == "新上传任务":
        render_upload(st.session_state.tasks)
    else:
        render_results(st.session_state.tasks, st.session_state.task_details)


if __name__ == "__main__":
    main()