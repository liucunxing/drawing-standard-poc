from fastapi import APIRouter
from backend.app.core.response import Result
from backend.app.models.schemas import UserCreate
from backend.app.services.user_service import user_service

router = APIRouter()


@router.get("/users", response_model=Result)
def list_users():
    """查询所有用户"""
    data = user_service.list_users()
    return Result.ok(data=data)


@router.get("/users/{user_id}", response_model=Result)
def get_user(user_id: int):
    """根据ID查询用户"""
    user = user_service.get_user(user_id)
    if user:
        return Result.ok(data=user)
    return Result.fail(msg="用户不存在", code=404)


@router.post("/users", response_model=Result)
def create_user(user: UserCreate):
    """创建用户"""
    new_user = user_service.create_user(user.name, user.age)
    return Result.ok(data=new_user, msg="创建成功")