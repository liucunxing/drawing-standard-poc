from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import uuid4

import streamlit as st


STATUS_STYLE = {
    "已完成": "success",
    "处理中": "info",
    "待复核": "warning",
    "异常": "error",
    "失败": "error",
}


def load_mock_tasks() -> list[dict[str, Any]]:
    """Central mock data source, ready to be replaced by API responses later."""
    return [
        {
            "task_id": "TASK-20260521-001",
            "task_name": "压力容器图纸识别",
            "description": "南京石化压力容器施工图纸批量识别",
            "status": "已完成",
            "created_at": "2026-05-21 10:30:45",
            "pdfs": [
                {
                    "file_name": "demo_njpc_001.pdf",
                    "drawing_no": "01237-T-001",
                    "project_name": "南京石化",
                    "equipment": "常压塔",
                    "discipline": "工艺",
                    "stage": "施工图",
                    "status": "识别成功",
                },
                {
                    "file_name": "demo_njpc_002.pdf",
                    "drawing_no": "01237-P-101",
                    "project_name": "南京石化",
                    "equipment": "常压塔",
                    "discipline": "管道",
                    "stage": "施工图",
                    "status": "识别成功",
                },
                {
                    "file_name": "demo_njpc_003.pdf",
                    "drawing_no": "01237-M-201",
                    "project_name": "南京石化",
                    "equipment": "常压塔",
                    "discipline": "机械",
                    "stage": "施工图",
                    "status": "识别成功",
                },
            ],
            "tables": [
                {
                    "index": 1,
                    "source_pdf": "demo_njpc_001.pdf",
                    "table_type": "图签信息表",
                    "confidence": 0.96,
                    "bbox": "[72, 608, 540, 764]",
                    "crop_path": "backend/tmp/table_blocks/task001/page_001_table_001.png",
                },
                {
                    "index": 2,
                    "source_pdf": "demo_njpc_001.pdf",
                    "table_type": "标准引用表",
                    "confidence": 0.93,
                    "bbox": "[80, 438, 532, 590]",
                    "crop_path": "backend/tmp/table_blocks/task001/page_001_table_002.png",
                },
                {
                    "index": 3,
                    "source_pdf": "demo_njpc_002.pdf",
                    "table_type": "材料明细表",
                    "confidence": 0.91,
                    "bbox": "[64, 352, 548, 602]",
                    "crop_path": "backend/tmp/table_blocks/task001/page_001_table_003.png",
                },
                {
                    "index": 4,
                    "source_pdf": "demo_njpc_003.pdf",
                    "table_type": "标准引用表",
                    "confidence": 0.94,
                    "bbox": "[90, 410, 520, 618]",
                    "crop_path": "backend/tmp/table_blocks/task001/page_001_table_004.png",
                },
            ],
            "standards": [
                {
                    "pdf_file": "demo_njpc_001.pdf",
                    "standard_no": "GB/T 150.1-2024",
                    "library_match": "GB/T 150.1-2024 压力容器 第1部分",
                    "conclusion": "通过",
                    "source_table": "标准引用表",
                    "suggestion": "标准号匹配，版本有效。",
                },
                {
                    "pdf_file": "demo_njpc_002.pdf",
                    "standard_no": "SH/T 3059-2023",
                    "library_match": "SH/T 3059-2023 石油化工管道设计",
                    "conclusion": "通过",
                    "source_table": "标准引用表",
                    "suggestion": "可进入人工抽检。",
                },
                {
                    "pdf_file": "demo_njpc_003.pdf",
                    "standard_no": "NB/T 47013-2025",
                    "library_match": "NB/T 47013-2025 承压设备无损检测",
                    "conclusion": "通过",
                    "source_table": "标准引用表",
                    "suggestion": "无需复核。",
                },
            ],
        },
        {
            "task_id": "TASK-20260521-002",
            "task_name": "换热器图纸批量识别",
            "description": "换热器设备图纸识别与标准引用抽取",
            "status": "处理中",
            "created_at": "2026-05-21 14:15:22",
            "pdfs": [
                {
                    "file_name": "heat_exchanger_001.pdf",
                    "drawing_no": "HX-450401-A1",
                    "project_name": "南京石化",
                    "equipment": "换热器 E-450401",
                    "discipline": "设备",
                    "stage": "施工图",
                    "status": "识别成功",
                },
                {
                    "file_name": "heat_exchanger_002.pdf",
                    "drawing_no": "HX-450402-A1",
                    "project_name": "南京石化",
                    "equipment": "换热器 E-450402",
                    "discipline": "设备",
                    "stage": "施工图",
                    "status": "解析中",
                },
                {
                    "file_name": "heat_exchanger_003.pdf",
                    "drawing_no": "",
                    "project_name": "南京石化",
                    "equipment": "换热器 E-450403",
                    "discipline": "设备",
                    "stage": "施工图",
                    "status": "排队中",
                },
            ],
            "tables": [
                {
                    "index": 1,
                    "source_pdf": "heat_exchanger_001.pdf",
                    "table_type": "图签信息表",
                    "confidence": 0.92,
                    "bbox": "[74, 610, 542, 762]",
                    "crop_path": "backend/tmp/table_blocks/task002/page_001_table_001.png",
                },
                {
                    "index": 2,
                    "source_pdf": "heat_exchanger_001.pdf",
                    "table_type": "标准引用表",
                    "confidence": 0.88,
                    "bbox": "[68, 420, 538, 586]",
                    "crop_path": "backend/tmp/table_blocks/task002/page_001_table_002.png",
                },
            ],
            "standards": [
                {
                    "pdf_file": "heat_exchanger_001.pdf",
                    "standard_no": "GB/T 151-2024",
                    "library_match": "GB/T 151-2024 热交换器",
                    "conclusion": "通过",
                    "source_table": "标准引用表",
                    "suggestion": "等待其余 PDF 完成后统一复核。",
                }
            ],
        },
        {
            "task_id": "TASK-20260520-003",
            "task_name": "塔器设备图纸识别",
            "description": "塔器设备图纸识别，含低置信度标准号复核",
            "status": "待复核",
            "created_at": "2026-05-20 16:40:10",
            "pdfs": [
                {
                    "file_name": "tower_vessel_001.pdf",
                    "drawing_no": "TV-182108-A1",
                    "project_name": "南京石化",
                    "equipment": "精馏塔 V-182108",
                    "discipline": "设备",
                    "stage": "施工图",
                    "status": "识别成功",
                },
                {
                    "file_name": "tower_vessel_002.pdf",
                    "drawing_no": "TV-182108-P2",
                    "project_name": "南京石化",
                    "equipment": "精馏塔 V-182108",
                    "discipline": "管道",
                    "stage": "施工图",
                    "status": "待复核",
                },
                {
                    "file_name": "tower_vessel_003.pdf",
                    "drawing_no": "",
                    "project_name": "南京石化",
                    "equipment": "精馏塔 V-182108",
                    "discipline": "仪表",
                    "stage": "施工图",
                    "status": "异常",
                },
            ],
            "tables": [
                {
                    "index": 1,
                    "source_pdf": "tower_vessel_001.pdf",
                    "table_type": "图签信息表",
                    "confidence": 0.89,
                    "bbox": "[70, 606, 540, 760]",
                    "crop_path": "backend/tmp/table_blocks/task003/page_001_table_001.png",
                },
                {
                    "index": 2,
                    "source_pdf": "tower_vessel_002.pdf",
                    "table_type": "标准引用表",
                    "confidence": 0.68,
                    "bbox": "[86, 432, 524, 594]",
                    "crop_path": "backend/tmp/table_blocks/task003/page_001_table_002.png",
                },
                {
                    "index": 3,
                    "source_pdf": "tower_vessel_003.pdf",
                    "table_type": "图签信息表",
                    "confidence": 0.51,
                    "bbox": "[82, 616, 510, 748]",
                    "crop_path": "backend/tmp/table_blocks/task003/page_001_table_003.png",
                },
            ],
            "standards": [
                {
                    "pdf_file": "tower_vessel_001.pdf",
                    "standard_no": "HG/T 20580-2024",
                    "library_match": "HG/T 20580-2024 钢制化工容器设计基础规定",
                    "conclusion": "通过",
                    "source_table": "标准引用表",
                    "suggestion": "匹配成功。",
                },
                {
                    "pdf_file": "tower_vessel_002.pdf",
                    "standard_no": "GB 150-20?4",
                    "library_match": "候选：GB/T 150.1-2024",
                    "conclusion": "待复核",
                    "source_table": "标准引用表",
                    "suggestion": "标准号年份识别不完整，建议人工确认原图。",
                },
                {
                    "pdf_file": "tower_vessel_003.pdf",
                    "standard_no": "",
                    "library_match": "未匹配",
                    "conclusion": "异常",
                    "source_table": "图签信息表",
                    "suggestion": "图签区域置信度偏低，建议重新上传清晰版 PDF。",
                },
            ],
        },
    ]


BACKEND_RESULT_CONTRACT = """
Future OCR backend response contract:
{
  "code": 200,
  "msg": "识别完成",
  "data": {
    "task_id": "...",
    "task_name": "...",
    "description": "...",
    "total_pdfs": 3,
    "processed_count": 3,
    "total_tables": 8,
    "total_standards": 12,
    "review_count": 2,
    "status": "已完成",
    "created_at": "2026-05-21 10:30:45",
    "pdfs": [],
    "tables": [],
    "standards": []
  }
}

The normalize_backend_result(payload) adapter below converts this payload into the
front-end's stable session_state structures: task summary + task detail.
"""


def _raw_json_without_nested_raw(source: dict[str, Any]) -> dict[str, Any]:
    raw_json = deepcopy(source)
    raw_json.pop("raw_json", None)
    return raw_json


def normalize_table(table: dict[str, Any], fallback_index: int) -> dict[str, Any]:
    return {
        "pdf_name": table.get("pdf_name") or table.get("source_pdf") or table.get("pdf_file") or "",
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
        "matched_standard": standard.get("matched_standard") or standard.get("library_match") or "未匹配",
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
    standard_issues = sum(
        1 for standard in pdf_standards if standard["status"] in {"待复核", "异常", "失败"}
    )
    pdf_issue = 1 if pdf.get("status") in {"待复核", "异常", "失败"} else 0
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
    raw_tables = data.get("tables", [])
    raw_standards = data.get("standards", [])
    tables = [normalize_table(table, index) for index, table in enumerate(raw_tables, start=1)]
    standards = [normalize_standard(standard) for standard in raw_standards]

    raw_pdfs = data.get("pdfs", [])
    file_names = data.get("file_names") or [
        pdf.get("pdf_name") or pdf.get("file_name") or pdf.get("name") or ""
        for pdf in raw_pdfs
    ]
    if not raw_pdfs and file_names:
        raw_pdfs = [{"pdf_name": file_name, "status": "排队中"} for file_name in file_names]

    pdfs = [normalize_pdf(pdf, tables, standards) for pdf in raw_pdfs]
    normalized_file_names = file_names or [pdf["pdf_name"] for pdf in pdfs]
    task_id = data.get("task_id") or f"TASK-{datetime.now():%Y%m%d}-{uuid4().hex[:4].upper()}"

    return {
        "task_id": task_id,
        "task_name": data.get("task_name") or "未命名识别任务",
        "description": data.get("description") or "",
        "file_names": normalized_file_names,
        "pdfs": pdfs,
        "tables": tables,
        "standards": standards,
        "raw_json": data.get("raw_json") or _raw_json_without_nested_raw(source),
        "status": data.get("status") or "处理中",
        "created_at": data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "processed_count": data.get("processed_count"),
        "pdf_count": data.get("pdf_count", data.get("total_pdfs")),
        "table_count": data.get("table_count", data.get("total_tables")),
        "standard_count": data.get("standard_count", data.get("total_standards")),
        "review_count": data.get("review_count"),
    }


def count_detail_reviews(detail: dict[str, Any]) -> int:
    if detail.get("review_count") is not None:
        return detail["review_count"]
    pdf_reviews = sum(1 for pdf in detail["pdfs"] if pdf["issue_count"] > 0)
    standard_reviews = sum(
        1 for standard in detail["standards"] if standard["status"] in {"待复核", "异常", "失败"}
    )
    return max(pdf_reviews, standard_reviews)


def normalize_task_summary(detail: dict[str, Any]) -> dict[str, Any]:
    processed_count = detail.get("processed_count")
    if processed_count is None:
        processed_count = sum(1 for pdf in detail["pdfs"] if pdf["status"] == "识别成功")
    return {
        "task_id": detail["task_id"],
        "task_name": detail["task_name"],
        "description": detail["description"],
        "pdf_count": detail.get("pdf_count") or len(detail["pdfs"]),
        "processed_count": processed_count,
        "table_count": detail.get("table_count") if detail.get("table_count") is not None else len(detail["tables"]),
        "standard_count": detail.get("standard_count")
        if detail.get("standard_count") is not None
        else len(detail["standards"]),
        "review_count": count_detail_reviews(detail),
        "status": detail["status"],
        "created_at": detail["created_at"],
        "file_names": detail["file_names"],
    }


def normalize_backend_result(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert a future OCR backend response into Streamlit session_state data.

    Expected backend shape is documented in BACKEND_RESULT_CONTRACT. This adapter
    does not call any API in the current POC; it only keeps the future integration
    point explicit. Missing fields are filled with safe defaults so the page
    rendering code can continue to use the stable summary/detail structures.
    """
    data = payload.get("data", payload)
    detail = normalize_task_detail({"data": data, "raw_response": payload})
    summary = normalize_task_summary(detail)
    return summary, detail


def build_initial_session_data() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    details = [normalize_task_detail(task) for task in load_mock_tasks()]
    task_details = {detail["task_id"]: detail for detail in details}
    tasks = sort_task_summaries([normalize_task_summary(detail) for detail in details])
    return tasks, task_details


def parse_created_at(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.min


def sort_task_summaries(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(tasks, key=lambda task: parse_created_at(task["created_at"]), reverse=True)


def upsert_task_summary(summary: dict[str, Any]) -> None:
    tasks = [
        task for task in st.session_state.tasks if task["task_id"] != summary["task_id"]
    ]
    tasks.insert(0, summary)
    st.session_state.tasks = sort_task_summaries(tasks)


def generate_demo_completion_detail(task: dict[str, Any]) -> dict[str, Any]:
    """Create customer-demo recognition results for a queued POC task."""
    file_names = task["file_names"]
    disciplines = ["工艺", "管道", "设备", "仪表", "电气"]
    standard_candidates = [
        ("GB/T 150.1-2024", "GB/T 150.1-2024 压力容器 第1部分"),
        ("SH/T 3059-2023", "SH/T 3059-2023 石油化工管道设计"),
        ("NB/T 47013-2025", "NB/T 47013-2025 承压设备无损检测"),
        ("HG/T 20580-2024", "HG/T 20580-2024 钢制化工容器设计基础规定"),
    ]

    pdfs: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    standards: list[dict[str, Any]] = []

    for pdf_index, file_name in enumerate(file_names, start=1):
        discipline = disciplines[(pdf_index - 1) % len(disciplines)]
        drawing_no = f"NJPC-DEMO-{pdf_index:03d}"
        pdfs.append(
            {
                "pdf_name": file_name,
                "status": "识别成功",
                "project_name": "南京石化",
                "unit_name": "炼化一体化装置",
                "equipment_name": f"演示设备 {pdf_index:02d}",
                "drawing_no": drawing_no,
                "discipline": discipline,
                "design_stage": "施工图",
                "table_count": 2,
                "standard_count": 1,
                "issue_count": 0,
            }
        )

        base_table_index = (pdf_index - 1) * 2
        tables.extend(
            [
                {
                    "pdf_name": file_name,
                    "page": 1,
                    "table_index": base_table_index + 1,
                    "label": "图签信息表",
                    "score": 0.96,
                    "bbox": [72, 608, 540, 764],
                    "image_path": f"demo_outputs/{task['task_id']}/page_001_table_{base_table_index + 1:03d}.png",
                },
                {
                    "pdf_name": file_name,
                    "page": 1,
                    "table_index": base_table_index + 2,
                    "label": "标准引用表",
                    "score": 0.93,
                    "bbox": [80, 438, 532, 590],
                    "image_path": f"demo_outputs/{task['task_id']}/page_001_table_{base_table_index + 2:03d}.png",
                },
            ]
        )

        standard_no, matched_standard = standard_candidates[
            (pdf_index - 1) % len(standard_candidates)
        ]
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

    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    completed_detail = {
        **task,
        "status": "已完成",
        "processed_count": len(file_names),
        "pdf_count": len(file_names),
        "table_count": len(tables),
        "standard_count": len(standards),
        "review_count": 0,
        "pdfs": pdfs,
        "tables": tables,
        "standards": standards,
        "raw_json": {
            "source": "poc_demo_completion",
            "task_id": task["task_id"],
            "status": "已完成",
            "completed_at": completed_at,
            "total_pdfs": len(file_names),
            "processed_count": len(file_names),
            "total_tables": len(tables),
            "total_standards": len(standards),
            "review_count": 0,
            "pdfs": pdfs,
            "tables": tables,
            "standards": standards,
        },
    }
    return completed_detail


def complete_task_for_demo(task_id: str) -> None:
    detail = st.session_state.task_details.get(task_id)
    if not detail:
        return
    completed_detail = generate_demo_completion_detail(detail)
    st.session_state.task_details[task_id] = completed_detail
    upsert_task_summary(normalize_task_summary(completed_detail))
    st.session_state.selected_task_id = task_id


def go_to_page(page: str) -> None:
    st.session_state.pending_page = page
    st.rerun()


def initialize_state() -> None:
    if "tasks" not in st.session_state and "task_details" not in st.session_state:
        st.session_state.tasks, st.session_state.task_details = build_initial_session_data()
    elif "task_details" not in st.session_state:
        legacy_details = [
            normalize_task_detail(task)
            for task in st.session_state.tasks
            if isinstance(task, dict) and "pdfs" in task
        ]
        if legacy_details:
            st.session_state.task_details = {
                detail["task_id"]: detail for detail in legacy_details
            }
            st.session_state.tasks = [
                normalize_task_summary(detail) for detail in legacy_details
            ]
        else:
            st.session_state.tasks, st.session_state.task_details = build_initial_session_data()
    elif "tasks" not in st.session_state:
        st.session_state.tasks = [
            normalize_task_summary(detail)
            for detail in st.session_state.task_details.values()
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


def format_file_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    return f"{size / 1024:.1f} KB"


def get_processed_count(task: dict[str, Any]) -> int:
    if task.get("processed_count") is not None:
        return task["processed_count"]
    return sum(1 for pdf in task["pdfs"] if pdf["status"] == "识别成功")


def get_review_count(task: dict[str, Any]) -> int:
    if task.get("review_count") is not None:
        return task["review_count"]
    pdf_reviews = sum(1 for pdf in task["pdfs"] if pdf["issue_count"] > 0)
    standard_reviews = sum(
        1 for item in task["standards"] if item["status"] in {"待复核", "异常", "失败"}
    )
    return max(pdf_reviews, standard_reviews)


def get_failed_count(task: dict[str, Any]) -> int:
    if "pdfs" not in task:
        detail = st.session_state.task_details.get(task["task_id"], {})
        if not detail:
            return 0
        task = detail
    pdf_failed = sum(1 for pdf in task["pdfs"] if pdf["status"] in {"异常", "失败"})
    standard_failed = sum(1 for item in task["standards"] if item["status"] in {"异常", "失败"})
    return max(pdf_failed, standard_failed)


def calculate_metrics(
    tasks: list[dict[str, Any]],
    task_details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    total_tasks = len(tasks)
    today = datetime.now().strftime("%Y-%m-%d")
    today_uploaded_pdfs = sum(
        task["pdf_count"] for task in tasks if task["created_at"].startswith(today)
    )
    processing_tasks = sum(1 for task in tasks if task["status"] == "处理中")
    completed_tasks = sum(1 for task in tasks if task["status"] == "已完成")
    review_count = sum(get_review_count(task) for task in tasks)
    failed_count = sum(get_failed_count(task) for task in tasks)
    standards = [
        standard
        for detail in task_details.values()
        for standard in detail.get("standards", [])
    ]
    passed = sum(1 for item in standards if item["status"] == "通过")
    pass_rate = passed / len(standards) if standards else 0
    return {
        "total_tasks": total_tasks,
        "today_uploaded_pdfs": today_uploaded_pdfs,
        "processing_tasks": processing_tasks,
        "completed_tasks": completed_tasks,
        "review_count": review_count,
        "failed_count": failed_count,
        "pass_rate": pass_rate,
    }


def apply_page_style() -> None:
    st.set_page_config(
        page_title="图纸识别系统 POC",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        [data-testid="stSidebar"] {
            background: #0f1f33;
        }
        [data-testid="stSidebar"] * {
            color: #f6f8fb;
        }
        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e6eaf0;
            border-radius: 10px;
            padding: 16px 18px;
            box-shadow: 0 1px 8px rgba(15, 31, 51, 0.05);
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.65rem;
            color: #0f172a;
        }
        .section-note {
            color: #64748b;
            font-size: 0.92rem;
            margin-top: -0.3rem;
        }
        .soft-panel {
            border: 1px solid #e6eaf0;
            border-radius: 10px;
            padding: 16px 18px;
            background: #ffffff;
            box-shadow: 0 1px 8px rgba(15, 31, 51, 0.04);
        }
        .status-pill {
            display: inline-block;
            padding: 0.28rem 0.68rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
            margin-bottom: 0.35rem;
        }
        .status-success {
            color: #15803d;
            background: #dcfce7;
        }
        .status-info {
            color: #1d4ed8;
            background: #dbeafe;
        }
        .status-warning {
            color: #b45309;
            background: #fef3c7;
        }
        .status-error {
            color: #b91c1c;
            background: #fee2e2;
        }
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


def task_summary_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        for task in tasks
    ]


def render_overview(
    tasks: list[dict[str, Any]],
    task_details: dict[str, dict[str, Any]],
) -> None:
    st.title("图纸识别系统 / 总览工作台")
    st.markdown('<p class="section-note">实时掌握识别任务整体情况</p>', unsafe_allow_html=True)

    metrics = calculate_metrics(tasks, task_details)
    metric_items = [
        ("总任务数", metrics["total_tasks"]),
        ("今日上传 PDF 数", metrics["today_uploaded_pdfs"]),
        ("处理中任务数", metrics["processing_tasks"]),
        ("已完成任务数", metrics["completed_tasks"]),
        ("待复核数量", metrics["review_count"]),
        ("异常 / 失败数量", metrics["failed_count"]),
        ("标准通过率", f"{metrics['pass_rate']:.1%}"),
    ]

    columns = st.columns(4)
    for index, (label, value) in enumerate(metric_items):
        columns[index % 4].metric(label, value)

    st.divider()
    header_col, action_col = st.columns([0.75, 0.25])
    with header_col:
        st.subheader("最近任务")
    with action_col:
        st.info("入口提示：请从左侧进入“新上传任务”。")

    st.dataframe(
        task_summary_rows(tasks),
        width="stretch",
        hide_index=True,
    )


def build_uploaded_task(task_name: str, description: str, files: list[Any]) -> dict[str, Any]:
    task_id = f"TASK-{datetime.now():%Y%m%d}-{uuid4().hex[:4].upper()}"
    file_names = [file.name for file in files]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdfs = [
        {
            "pdf_name": file.name,
            "status": "排队中",
            "project_name": "",
            "unit_name": "",
            "equipment_name": "",
            "drawing_no": "",
            "discipline": "",
            "design_stage": "",
            "table_count": 0,
            "standard_count": 0,
            "issue_count": 0,
        }
        for file in files
    ]
    return {
        "task_id": task_id,
        "task_name": task_name,
        "description": description,
        "file_names": file_names,
        "status": "处理中",
        "created_at": created_at,
        "pdfs": pdfs,
        "tables": [],
        "standards": [],
        "raw_json": {
            "source": "streamlit_mock_upload",
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


def render_upload(tasks: list[dict[str, Any]]) -> None:
    st.title("图纸识别系统 / 新上传任务")
    st.markdown('<p class="section-note">上传 PDF 图纸，启动新的识别任务</p>', unsafe_allow_html=True)

    with st.form("new_task_form", clear_on_submit=False):
        task_name = st.text_input("任务名称", placeholder="请输入任务名称")
        description = st.text_area("任务说明（可选）", placeholder="请输入任务说明")
        uploaded_files = st.file_uploader(
            "PDF 文件",
            type=["pdf"],
            accept_multiple_files=True,
            help="支持一次选择多个 PDF，用于演示任务创建与识别流程。",
        )

        if uploaded_files:
            selected_rows = [
                {
                    "文件名": file.name,
                    "文件大小": format_file_size(file.size),
                    "上传状态": "已选择，等待开始识别",
                }
                for file in uploaded_files
            ]
            st.dataframe(selected_rows, width="stretch", hide_index=True)
        else:
            st.caption("尚未选择文件")

        submitted = st.form_submit_button("开始识别", type="primary")

    if submitted:
        if not task_name.strip():
            st.warning("请先填写任务名称。")
        elif not uploaded_files:
            st.warning("请至少选择一个 PDF 文件。")
        else:
            new_detail = build_uploaded_task(task_name.strip(), description.strip(), uploaded_files)
            new_summary = normalize_task_summary(new_detail)
            st.session_state.task_details[new_detail["task_id"]] = new_detail
            upsert_task_summary(new_summary)
            st.session_state.selected_task_id = new_detail["task_id"]
            st.session_state.created_task_id = new_detail["task_id"]
            st.success("任务创建成功，已进入识别队列。")

    if st.session_state.created_task_id:
        created_task_id = st.session_state.created_task_id
        created_detail = st.session_state.task_details.get(created_task_id)
        st.markdown('<div class="soft-panel">', unsafe_allow_html=True)
        st.write("新任务编号")
        st.code(created_task_id, language="text")
        st.info("可前往结果查看页面查看任务详情。")
        st.markdown("</div>", unsafe_allow_html=True)

        action_cols = st.columns([0.2, 0.2, 0.24, 0.36])
        if action_cols[0].button("查看任务详情", type="primary", key="go_created_detail"):
            st.session_state.selected_task_id = created_task_id
            go_to_page("结果查看")
        if action_cols[1].button("返回总览工作台", key="go_overview_after_create"):
            go_to_page("总览工作台")
        if (
            created_detail
            and created_detail["status"] == "处理中"
            and action_cols[2].button("模拟完成识别", key="complete_created_task")
        ):
            complete_task_for_demo(created_task_id)
            st.success("演示识别已完成，可查看识别结果。")


def render_task_header(task: dict[str, Any]) -> None:
    st.subheader(f"{task['task_id']}  {task['task_name']}")
    st.markdown(status_badge(task["status"]), unsafe_allow_html=True)
    st.caption(task.get("description") or "暂无任务说明")

    columns = st.columns(6)
    columns[0].metric("PDF 数量", len(task["pdfs"]))
    columns[1].metric("当前状态", task["status"])
    columns[2].metric("已识别表格数", len(task["tables"]))
    columns[3].metric("标准条数", len(task["standards"]))
    columns[4].metric("待复核数量", get_review_count(task))
    columns[5].metric("已处理数量", get_processed_count(task))

    progress = get_processed_count(task) / len(task["pdfs"]) if task["pdfs"] else 0
    st.progress(progress, text=f"任务处理进度 {progress:.0%}")


def render_result_tabs(task: dict[str, Any]) -> None:
    drawing_tab, table_tab, standard_tab, raw_json_tab = st.tabs(
        ["图纸识别结果", "表格解析结果", "标准提取比对结果", "技术调试信息"]
    )

    with drawing_tab:
        rows = [
            {
                "PDF 文件": pdf["pdf_name"],
                "图号": pdf["drawing_no"] or "-",
                "项目名称": pdf["project_name"] or "-",
                "装置 / 设备": pdf["equipment_name"] or pdf["unit_name"] or "-",
                "专业": pdf["discipline"] or "-",
                "阶段": pdf["design_stage"] or "-",
                "状态": pdf["status"],
            }
            for pdf in task["pdfs"]
        ]
        st.dataframe(rows, width="stretch", hide_index=True)

    with table_tab:
        rows = [
            {
                "序号": table["table_index"],
                "来源 PDF": table["pdf_name"],
                "页码": table["page"],
                "表格类型": table["label"],
                "置信度": f"{table['score']:.0%}",
                "bbox": table["bbox"],
                "裁剪文件路径": table["image_path"],
            }
            for table in task["tables"]
        ]
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("当前任务尚未生成表格解析结果。")

    with standard_tab:
        rows = [
            {
                "PDF 文件": item["pdf_name"],
                "识别标准号": item["standard_no"] or "-",
                "标准库匹配": item["matched_standard"],
                "结论": item["status"],
                "来源表格": item["source_table"],
                "置信度": f"{item['confidence']:.0%}",
                "建议": item["suggestion"],
            }
            for item in task["standards"]
        ]
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("当前任务尚未生成标准提取比对结果。")

    with raw_json_tab:
        st.json(task.get("raw_json", {}))


def render_results(
    tasks: list[dict[str, Any]],
    task_details: dict[str, dict[str, Any]],
) -> None:
    st.title("图纸识别系统 / 结果查看")
    st.markdown('<p class="section-note">查看历史任务与单个任务的识别详情</p>', unsafe_allow_html=True)

    with st.expander("历史任务列表", expanded=False):
        st.dataframe(task_summary_rows(tasks), width="stretch", hide_index=True)

    task_options = {f"{task['task_id']}｜{task['task_name']}": task["task_id"] for task in tasks}
    current_index = 0
    task_ids = list(task_options.values())
    if st.session_state.selected_task_id in task_ids:
        current_index = task_ids.index(st.session_state.selected_task_id)

    selected_label = st.selectbox(
        "选择任务",
        options=list(task_options.keys()),
        index=current_index,
    )
    st.session_state.selected_task_id = task_options[selected_label]
    task = task_details[st.session_state.selected_task_id]

    completion_message = st.session_state.pop("demo_completion_message", None)
    if completion_message:
        st.success(completion_message)

    if task["status"] == "处理中":
        if st.button("模拟完成识别", type="primary", key=f"complete_result_{task['task_id']}"):
            complete_task_for_demo(task["task_id"])
            st.session_state.demo_completion_message = "演示识别已完成，可查看识别结果。"
            st.rerun()

    render_task_header(task)
    st.divider()
    render_result_tabs(task)


def main() -> None:
    apply_page_style()
    initialize_state()

    tasks = st.session_state.tasks
    task_details = st.session_state.task_details
    page = render_sidebar()

    if page == "总览工作台":
        render_overview(tasks, task_details)
    elif page == "新上传任务":
        render_upload(tasks)
    else:
        render_results(tasks, task_details)


if __name__ == "__main__":
    main()
