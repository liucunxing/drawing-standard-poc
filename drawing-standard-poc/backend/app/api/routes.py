from fastapi import APIRouter, File, Query, UploadFile
from backend.app.core.response import Result
from backend.app.services.table_layout_service import table_layout_service

router = APIRouter()


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


@router.post("/drawing/extract-table-blocks", response_model=Result)
async def extract_table_blocks_from_pdf(
    file: UploadFile = File(...),
    score_threshold: float = Query(0.45, ge=0, le=1, description="表格候选框最小置信度"),
    render_scale: float = Query(2.0, gt=0, le=6, description="PDF 页面渲染缩放倍数"),
    crop_padding: int = Query(16, ge=0, le=512, description="模型框外扩像素"),
    refine_padding: int = Query(8, ge=0, le=128, description="表格线精裁后保留边距"),
    enable_line_fallback: bool = Query(False, description="是否启用整页线条兜底候选，默认关闭以避免过检"),
):
    """第一步：上传 PDF 并提取所有表格区块。"""
    try:
        pdf_bytes = await file.read()
        data = table_layout_service.extract_tables_from_uploaded_pdf(
            pdf_bytes=pdf_bytes,
            filename=file.filename or "upload.pdf",
            score_threshold=score_threshold,
            render_scale=render_scale,
            crop_padding=crop_padding,
            refine_padding=refine_padding,
            enable_line_fallback=enable_line_fallback,
        )
        return Result.ok(data=data, msg="表格区块提取完成")
    except Exception as exc:
        return Result.fail(msg=str(exc), code=500)
