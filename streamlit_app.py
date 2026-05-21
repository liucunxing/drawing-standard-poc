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


def initialize_state() -> None:
    if "tasks" not in st.session_state:
        st.session_state.tasks = deepcopy(load_mock_tasks())
    if "selected_task_id" not in st.session_state:
        st.session_state.selected_task_id = st.session_state.tasks[0]["task_id"]
    if "created_task_id" not in st.session_state:
        st.session_state.created_task_id = None


def format_file_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    return f"{size / 1024:.1f} KB"


def get_processed_count(task: dict[str, Any]) -> int:
    return sum(1 for pdf in task["pdfs"] if pdf["status"] == "识别成功")


def get_review_count(task: dict[str, Any]) -> int:
    pdf_reviews = sum(1 for pdf in task["pdfs"] if pdf["status"] in {"待复核", "异常", "失败"})
    standard_reviews = sum(
        1 for item in task["standards"] if item["conclusion"] in {"待复核", "异常", "失败"}
    )
    return max(pdf_reviews, standard_reviews)


def get_failed_count(task: dict[str, Any]) -> int:
    pdf_failed = sum(1 for pdf in task["pdfs"] if pdf["status"] in {"异常", "失败"})
    standard_failed = sum(1 for item in task["standards"] if item["conclusion"] in {"异常", "失败"})
    return max(pdf_failed, standard_failed)


def calculate_metrics(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    total_tasks = len(tasks)
    today = datetime.now().strftime("%Y-%m-%d")
    today_uploaded_pdfs = sum(
        len(task["pdfs"]) for task in tasks if task["created_at"].startswith(today)
    )
    processing_tasks = sum(1 for task in tasks if task["status"] == "处理中")
    completed_tasks = sum(1 for task in tasks if task["status"] == "已完成")
    review_count = sum(get_review_count(task) for task in tasks)
    failed_count = sum(get_failed_count(task) for task in tasks)
    standards = [item for task in tasks for item in task["standards"]]
    passed = sum(1 for item in standards if item["conclusion"] == "通过")
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
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    style = STATUS_STYLE.get(status, "info")
    return f'<span class="status-pill status-{style}">{status}</span>'


def render_sidebar() -> str:
    st.sidebar.title("图纸识别系统")
    st.sidebar.caption("POC 演示前端")
    page = st.sidebar.radio(
        "导航",
        ["总览工作台", "新上传任务", "结果查看"],
        label_visibility="collapsed",
    )
    st.sidebar.divider()
    st.sidebar.caption("当前版本仅展示 mock 数据")
    st.sidebar.caption("未连接后端接口 / 未写入数据库")
    return page


def task_summary_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "任务编号": task["task_id"],
            "任务名称": task["task_name"],
            "PDF 数量": len(task["pdfs"]),
            "已处理数量": get_processed_count(task),
            "待复核数量": get_review_count(task),
            "状态": task["status"],
            "创建时间": task["created_at"],
            "操作提示": "进入结果查看页查看详情",
        }
        for task in tasks
    ]


def render_overview(tasks: list[dict[str, Any]]) -> None:
    st.title("图纸识别系统 / 总览工作台")
    st.markdown('<p class="section-note">实时掌握识别任务整体情况</p>', unsafe_allow_html=True)

    metrics = calculate_metrics(tasks)
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
    pdfs = [
        {
            "file_name": file.name,
            "drawing_no": "",
            "project_name": "",
            "equipment": "",
            "discipline": "",
            "stage": "",
            "status": "排队中",
        }
        for file in files
    ]
    return {
        "task_id": task_id,
        "task_name": task_name,
        "description": description,
        "status": "处理中",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pdfs": pdfs,
        "tables": [],
        "standards": [],
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
            help="支持一次选择多个 PDF。本页面仅做 mock 演示，不会上传到后端。",
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
            new_task = build_uploaded_task(task_name.strip(), description.strip(), uploaded_files)
            tasks.insert(0, new_task)
            st.session_state.selected_task_id = new_task["task_id"]
            st.session_state.created_task_id = new_task["task_id"]
            st.success("任务创建成功，本轮已在 session_state 中模拟新增任务。")

    if st.session_state.created_task_id:
        st.markdown('<div class="soft-panel">', unsafe_allow_html=True)
        st.write("新任务编号")
        st.code(st.session_state.created_task_id, language="text")
        st.info("可进入左侧“结果查看”页面查看任务详情。")
        st.markdown("</div>", unsafe_allow_html=True)


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
    drawing_tab, table_tab, standard_tab = st.tabs(
        ["图纸识别结果", "表格解析结果", "标准提取比对结果"]
    )

    with drawing_tab:
        rows = [
            {
                "PDF 文件": pdf["file_name"],
                "图号": pdf["drawing_no"] or "-",
                "项目名称": pdf["project_name"] or "-",
                "装置 / 设备": pdf["equipment"] or "-",
                "专业": pdf["discipline"] or "-",
                "阶段": pdf["stage"] or "-",
                "状态": pdf["status"],
            }
            for pdf in task["pdfs"]
        ]
        st.dataframe(rows, width="stretch", hide_index=True)

    with table_tab:
        rows = [
            {
                "序号": table["index"],
                "来源 PDF": table["source_pdf"],
                "表格类型": table["table_type"],
                "置信度": f"{table['confidence']:.0%}",
                "bbox": table["bbox"],
                "裁剪文件路径": table["crop_path"],
            }
            for table in task["tables"]
        ]
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("当前 mock 任务尚未生成表格解析结果。")

    with standard_tab:
        rows = [
            {
                "PDF 文件": item["pdf_file"],
                "识别标准号": item["standard_no"] or "-",
                "标准库匹配": item["library_match"],
                "结论": item["conclusion"],
                "来源表格": item["source_table"],
                "建议": item["suggestion"],
            }
            for item in task["standards"]
        ]
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("当前 mock 任务尚未生成标准提取比对结果。")


def render_results(tasks: list[dict[str, Any]]) -> None:
    st.title("图纸识别系统 / 结果查看")
    st.markdown('<p class="section-note">查看历史任务与单个任务的识别详情</p>', unsafe_allow_html=True)

    with st.expander("历史任务列表", expanded=True):
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
    task = next(item for item in tasks if item["task_id"] == st.session_state.selected_task_id)

    render_task_header(task)
    st.divider()
    render_result_tabs(task)


def main() -> None:
    apply_page_style()
    initialize_state()

    tasks = st.session_state.tasks
    page = render_sidebar()

    if page == "总览工作台":
        render_overview(tasks)
    elif page == "新上传任务":
        render_upload(tasks)
    else:
        render_results(tasks)


if __name__ == "__main__":
    main()
