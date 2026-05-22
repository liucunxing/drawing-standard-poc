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
REVIEW_STATUSES = {"待复核", "异常", "失败"}
FAILED_STATUSES = {"异常", "失败"}


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
            st.dataframe(
                [
                    {
                        "文件名": file.name,
                        "文件大小": format_file_size(file.size),
                        "上传状态": "已选择，等待开始识别",
                    }
                    for file in uploaded_files
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("尚未选择文件")
        submitted = st.form_submit_button("开始识别", type="primary")

    if submitted:
        if not task_name.strip():
            st.warning("请先填写任务名称。")
        elif not uploaded_files:
            st.warning("请至少选择一个 PDF 文件。")
        else:
            detail = build_uploaded_task(task_name.strip(), description.strip(), uploaded_files)
            st.session_state.task_details[detail["task_id"]] = detail
            upsert_task_summary(normalize_task_summary(detail))
            st.session_state.selected_task_id = detail["task_id"]
            st.session_state.created_task_id = detail["task_id"]
            st.success("任务创建成功，已进入识别队列。")

    if st.session_state.created_task_id:
        task_id = st.session_state.created_task_id
        detail = st.session_state.task_details.get(task_id)
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
        if detail and detail["status"] == "处理中":
            if cols[2].button("模拟完成识别", key="complete_created_task"):
                complete_task_for_demo(task_id)
                st.success("演示识别已完成，可查看识别结果。")


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
            for table in detail["tables"]
        ]
        if rows:
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
