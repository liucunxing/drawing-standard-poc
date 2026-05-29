from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from fastapi.responses import FileResponse
from pathlib import Path
from typing import List, Optional
from backend.app.core.response import Result
from backend.app.models.schemas import UserCreate
from backend.app.services.user_service import user_service
from backend.app.services.poc_service import poc_service

router = APIRouter()

# 配置tmp目录路径 (用于访问图片)
TMP_DIR = Path(__file__).resolve().parents[2] / "tmp"


# @router.get("/users", response_model=Result)
# def list_users():
#     """查询所有用户"""
#     data = user_service.list_users()
#     return Result.ok(data=data)
#
#
# @router.get("/users/{user_id}", response_model=Result)
# def get_user(user_id: int):
#     """根据ID查询用户"""
#     user = user_service.get_user(user_id)
#     if user:
#         return Result.ok(data=user)
#     return Result.fail(msg="用户不存在", code=404)
#
#
# @router.post("/users", response_model=Result)
# def create_user(user: UserCreate):
#     """创建用户"""
#     new_user = user_service.create_user(user.name, user.age)
#     return Result.ok(data=new_user, msg="创建成功")


@router.post("/drawing/upload-pdf", response_model=Result)
async def upload_pdf(file: UploadFile = File(...), task_name: str = None):
    """接收前端上传的PDF文件,保存到服务器并返回上传成功信息"""
    try:
        pdf_bytes = await file.read()
        data = poc_service.upload_pdf(
            pdf_bytes=pdf_bytes,
            filename=file.filename or "upload.pdf",
            task_name=task_name,
        )
        return Result.ok(data=data, msg="PDF上传成功")
    except ValueError as exc:
        return Result.fail(msg=str(exc), code=400)
    except Exception as exc:
        return Result.fail(msg=str(exc), code=500)


@router.get("/drawing/task/{task_id}", response_model=Result)
async def get_task_status(task_id: str):
    """查询任务状态和进度"""
    try:
        data = poc_service.get_task_status(task_id=task_id)
        if data:
            return Result.ok(data=data, msg="查询成功")
        else:
            return Result.fail(msg=f"任务不存在: {task_id}", code=404)
    except Exception as exc:
        return Result.fail(msg=str(exc), code=500)


@router.get("/drawing/task/{task_id}/parse-status", response_model=Result)
async def get_parse_status(task_id: str):
    """
    查询PDF解析状态(用于前端轮询)
    
    Args:
        task_id: 任务ID
    
    Returns:
        {
            "status": 2,  # 0-待处理, 1-解析中, 2-已完成, 3-失败
            "progress": 100.00,
            "current_step": "解析完成",
            "table_count": 4
        }
    """
    try:
        task_info = poc_service.get_task_status(task_id=task_id)
        if not task_info:
            return Result.fail(msg=f"任务不存在: {task_id}", code=404)
        
        # 只返回解析相关的状态信息
        parse_status = {
            "status": task_info.get('status', 0),
            "progress": task_info.get('progress', 0.0),
            "current_step": task_info.get('current_step', ''),
            "table_count": task_info.get('table_count', 0),
        }
        
        return Result.ok(data=parse_status, msg="查询成功")
    except Exception as exc:
        return Result.fail(msg=str(exc), code=500)


@router.get("/drawing/tasks", response_model=Result)
async def list_tasks(limit: int = 20):
    """查询最近的任务列表"""
    try:
        data = poc_service.list_tasks(limit=limit)
        return Result.ok(data=data, msg="查询成功")
    except Exception as exc:
        return Result.fail(msg=str(exc), code=500)


@router.post("/drawing/process-tables", response_model=Result)
async def process_pdf_tables(task_id: str):
    """解析PDF并提取表格图片"""
    try:
        data = poc_service.process_pdf_tables(task_id=task_id)
        return Result.ok(data=data, msg="PDF解析完成")
    except ValueError as exc:
        return Result.fail(msg=str(exc), code=400)
    except Exception as exc:
        return Result.fail(msg=str(exc), code=500)


@router.post("/drawing/convert-to-markdown", response_model=Result)
async def convert_to_markdown(
    task_id: str,
    tables: Optional[List[dict]] = Body(None, embed=True),
):
    """
    将表格图片转换为Markdown
    
    Args:
        task_id: 任务ID
        tables: 表格图片信息列表(从前端JSON body传入)
    """
    try:
        if not tables:
            return Result.fail(msg="缺少表格数据", code=400)
        
        print(f"[API] 接收到Markdown转换请求: task_id={task_id}, tables_count={len(tables)}")
        
        data = poc_service.convert_tables_to_markdown(
            task_id=task_id,
            tables=tables,
        )
        return Result.ok(data=data, msg="Markdown转换完成")
    except ValueError as exc:
        return Result.fail(msg=str(exc), code=400)
    except Exception as exc:
        return Result.fail(msg=str(exc), code=500)


@router.post("/drawing/detect-standards", response_model=Result)
async def detect_standards(
    task_id: str,
    markdown_files: Optional[List[str]] = Body(None, embed=True),
):
    """
    检测Markdown文件中的标准号并与标准库比对
    
    Args:
        task_id: 任务ID
        markdown_files: Markdown文件路径列表(从前端JSON body传入)
    """
    try:
        if not markdown_files:
            return Result.fail(msg="缺少Markdown文件路径", code=400)
        
        print(f"[API] 接收到标准检测请求: task_id={task_id}, files_count={len(markdown_files)}")
        
        data = poc_service.detect_standards(
            task_id=task_id,
            markdown_files=markdown_files,
        )
        return Result.ok(data=data, msg="标准检测完成")
    except ValueError as exc:
        return Result.fail(msg=str(exc), code=400)
    except Exception as exc:
        return Result.fail(msg=str(exc), code=500)


@router.get("/files/{filepath:path}", response_class=FileResponse)
async def serve_file(filepath: str):
    """
    提供文件访问服务 (图片等)
    
    Args:
        filepath: 相对于tmp目录的文件路径,例如: table_blocks/task123/page_001_table_001.png
    
    Returns:
        文件响应
    """
    file_path = TMP_DIR / filepath
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {filepath}")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail=f"不是文件: {filepath}")
    
    # 根据文件扩展名设置media_type
    media_type = "application/octet-stream"
    if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
        media_type = f"image/{file_path.suffix.lower().lstrip('.')}"
        if media_type == "image/jpg":
            media_type = "image/jpeg"
    
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name
    )


# @router.post("/drawing/extract-table-blocks", response_model=Result)
# async def extract_table_blocks_from_pdf(file: UploadFile = File(...)):
#     """第一步：上传PDF并提取所有表格区块。"""
#     try:
#         pdf_bytes = await file.read()
#         data = table_layout_service_picodet.extract_tables_from_uploaded_pdf(
#             pdf_bytes=pdf_bytes,
#             filename=file.filename or "upload.pdf",
#         )
#         return Result.ok(data=data, msg="表格区块提取完成")
#     except Exception as exc:
#         return Result.fail(msg=str(exc), code=500)