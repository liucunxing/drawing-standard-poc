"""Local contract-compatible demo backend for manually testing the React MVP.

This server is intentionally in-memory and does not perform OCR or database writes.
It must never be used as evidence that the real FastAPI/MySQL/GPU chain passed.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from html import escape
from itertools import count
from typing import Annotated

import uvicorn
from fastapi import FastAPI, File, Query, UploadFile
from fastapi.responses import Response


app = FastAPI(title="Drawing Review Local Demo Backend", version="0.1.0")
task_sequence = count(20260729010)
standard_sequence = count(3)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ok(data=None, msg: str = "成功") -> dict:
    return {"code": 200, "msg": msg, "data": data}


def task_record(task_id: str, name: str, status: int, progress: int, files: list[str]) -> dict:
    completed = status == 2
    return {
        "task_id": task_id,
        "task_name": name,
        "original_filename": files[0] if files else "",
        "file_names": files,
        "pdf_count": len(files),
        "file_size": 707794 * max(1, len(files)),
        "page_count": 4 * max(1, len(files)),
        "status": status,
        "progress": progress,
        "current_step": "标准审查完成" if completed else "正在识别图纸",
        "table_count": 2 * len(files) if completed else 0,
        "standard_count": 4 * len(files) if completed else 0,
        "exact_match_count": 2 * len(files) if completed else 0,
        "year_mismatch_count": len(files) if completed else 0,
        "similar_count": len(files) if completed else 0,
        "not_found_count": 0,
        "error_message": "",
        "created_at": now(),
        "updated_at": now(),
        "started_at": now(),
        "completed_at": now() if completed else None,
    }


tasks: dict[str, dict] = {
    "DEMO-001": task_record("DEMO-001", "换热器图纸审查", 2, 100, ["换热器图纸A.pdf", "换热器图纸B.pdf"]),
    "DEMO-002": task_record("DEMO-002", "压力容器总图审查", 1, 45, ["压力容器总图.pdf"]),
    "DEMO-003": task_record("DEMO-003", "塔器设备图纸审查", 3, 30, ["塔器设备图纸.pdf"]),
}

standards: list[dict] = [
    {"id": 1, "standard_no": "GB 50016-2014", "standard_type": "国家标准", "standard_prefix": "GB", "create_time": now(), "update_time": now(), "create_user": "demo", "update_user": "demo"},
    {"id": 2, "standard_no": "GB/T 150-2024", "standard_type": "推荐性国家标准", "standard_prefix": "GB/T", "create_time": now(), "update_time": now(), "create_user": "demo", "update_user": "demo"},
]


@app.get("/")
def health() -> dict:
    return {"message": "本地演示后端运行中（Mock，不执行真实OCR）"}


@app.get("/api/drawing/tasks")
def list_tasks(limit: int = 100) -> dict:
    return ok(list(tasks.values())[:limit], "查询成功")


@app.post("/api/drawing/upload-pdf")
async def upload_pdfs(
    files: Annotated[list[UploadFile], File()],
    task_name: str | None = Query(default=None),
) -> dict:
    task_id = str(next(task_sequence))
    names = [item.filename or f"图纸-{index + 1}.pdf" for index, item in enumerate(files)]
    sizes = [len(await item.read()) for item in files]
    tasks[task_id] = task_record(task_id, task_name or names[0], 0, 0, names)
    return ok({
        "task_id": task_id,
        "filename": names[0],
        "original_filename": names[0],
        "file_path": f"uploads/{task_id}",
        "file_size": sum(sizes),
        "uploaded_at": now(),
        "pdf_count": len(names),
        "file_names": names,
        "files": [
            {"index": index + 1, "original_filename": name, "saved_filename": name, "file_path": f"uploads/{task_id}/{name}", "file_size": sizes[index]}
            for index, name in enumerate(names)
        ],
    }, "上传成功")


@app.post("/api/drawing/process-single-pdf-full")
async def process_single_pdf(task_id: str, file_index: int) -> dict:
    task = tasks.get(task_id)
    if not task:
        return {"code": 404, "msg": "任务不存在", "data": None}
    await asyncio.sleep(0.8)
    count_files = max(1, task["pdf_count"])
    task["status"] = 2 if file_index >= count_files else 1
    task["progress"] = round(file_index / count_files * 100)
    task["current_step"] = "标准审查完成" if task["status"] == 2 else f"已完成第 {file_index} 个文件"
    task["updated_at"] = now()
    if task["status"] == 2:
        task.update({"table_count": count_files * 2, "standard_count": count_files * 4, "exact_match_count": count_files * 2, "year_mismatch_count": count_files, "similar_count": count_files, "completed_at": now()})
    return ok({"task_id": task_id, "pdf_name": task["file_names"][file_index - 1], "file_index": file_index, "file_count": count_files, "processed_files": file_index, "total_pages": 4, "total_tables": 2, "tables": []}, "处理完成")


@app.get("/api/drawing/task/{task_id}")
def task_detail(task_id: str) -> dict:
    task = tasks.get(task_id)
    if not task:
        return {"code": 404, "msg": "任务不存在", "data": None}
    files = task["file_names"] or ["演示图纸.pdf"]
    tables = []
    images = []
    matches = []
    for file_index, filename in enumerate(files, start=1):
        images.append({"pdf_name": filename, "page": 1, "image_path": f"demo/layout-{file_index}.svg", "image_url": ""})
        tables.append({
            "pdf_name": filename,
            "page": 1,
            "table_index": file_index,
            "display_name": f"明细表 {file_index}",
            "image_path": f"demo/table-{file_index}.svg",
            "image_url": "",
            "raw_markdown_content": "| 标准号 | 名称 |\n|---|---|\n| GB 50016-2014 | 建筑设计防火规范 |\n| GB/T 150-2011 | 压力容器 |",
            "markdown_content": "| 标准号 | 名称 |\n|---|---|\n| GB 50016-2014 | 建筑设计防火规范 |\n| GB/T 150-2011 | 压力容器 |",
            "highlighted_markdown_content": "| 标准号 | 名称 |\n|---|---|\n| <mark class=\"review-exact\">GB 50016-2014</mark> | 建筑设计防火规范 |\n| <mark class=\"review-warning\">GB/T 150-2011</mark> | 压力容器 |",
        })
        matches.extend([
            {"pdf_name": filename, "standard_no": "GB 50016-2014", "matched_standard": "GB 50016-2014", "status": "完全符合", "result_type": "完全符合", "source_table": f"明细表 {file_index}", "confidence": 0.98, "suggestion": "标准号与标准库一致。"},
            {"pdf_name": filename, "standard_no": "GB/T 150-2011", "matched_standard": "GB/T 150-2024", "status": "年份不一致", "result_type": "年份不一致", "source_table": f"明细表 {file_index}", "confidence": 0.88, "suggestion": "建议核对并采用现行版本。"},
        ])
    detail = dict(task)
    detail.update({"description": "", "processed_count": len(files) if task["status"] == 2 else 0, "pdfs": [{"pdf_name": name, "status": "识别成功" if task["status"] == 2 else "处理中", "table_count": 1, "standard_count": 2} for name in files], "tables": tables, "standards": matches, "annotated_images": images, "overall_standard_compare": {}, "raw_json": {}})
    return ok(detail, "查询成功")


@app.get("/api/standard-data")
def list_standards(keyword: str = "", page: int = 1, page_size: int = 20) -> dict:
    query = keyword.strip().lower()
    visible = [record for record in standards if not query or query in f"{record['standard_no']} {record['standard_type']} {record['standard_prefix']}".lower()]
    start = max(0, page - 1) * page_size
    return ok({"total": len(visible), "page": page, "page_size": page_size, "items": visible[start:start + page_size]}, "查询成功")


@app.post("/api/standard-data")
def create_standard(payload: dict) -> dict:
    record = {"id": next(standard_sequence), **payload, "create_time": now(), "update_time": now(), "create_user": payload.get("operator", "demo"), "update_user": payload.get("operator", "demo")}
    standards.append(record)
    return ok(record, "新增成功")


@app.put("/api/standard-data/{standard_id}")
def update_standard(standard_id: int, payload: dict) -> dict:
    for record in standards:
        if record["id"] == standard_id:
            record.update(payload)
            record["update_time"] = now()
            return ok(record, "更新成功")
    return {"code": 404, "msg": "标准不存在", "data": None}


@app.delete("/api/standard-data/{standard_id}")
def delete_standard(standard_id: int) -> dict:
    index = next((index for index, record in enumerate(standards) if record["id"] == standard_id), None)
    if index is None:
        return {"code": 404, "msg": "标准不存在", "data": None}
    standards.pop(index)
    return ok({"id": standard_id}, "删除成功")


@app.get("/api/files/{filepath:path}")
def demo_file(filepath: str) -> Response:
    label = escape(filepath.rsplit("/", 1)[-1])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720">
      <rect width="1200" height="720" fill="#f8fafc"/><rect x="38" y="38" width="1124" height="644" fill="white" stroke="#334155" stroke-width="2"/>
      <text x="70" y="90" font-size="28" fill="#0f172a">图纸识别演示 · {label}</text>
      <g stroke="#64748b" fill="none"><rect x="90" y="140" width="760" height="400"/><circle cx="450" cy="340" r="125"/><path d="M120 590H1080M900 140V590M950 180v320M1010 180v320"/></g>
      <rect x="920" y="550" width="210" height="100" fill="#eff6ff" stroke="#2563eb"/><text x="940" y="605" font-size="22" fill="#1d4ed8">本地 Mock 图像</text>
    </svg>'''
    return Response(svg, media_type="image/svg+xml")


if __name__ == "__main__":
    port = int(os.environ.get("LOCAL_DEMO_BACKEND_PORT", "18000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
