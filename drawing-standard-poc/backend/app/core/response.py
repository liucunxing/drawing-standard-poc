from typing import Any, Optional
from pydantic import BaseModel


class Result(BaseModel):
    code: int = 200
    msg: str = "success"
    data: Optional[Any] = None

    @classmethod
    def ok(cls, data: Any = None, msg: str = "success"):
        return cls(code=200, msg=msg, data=data)

    @classmethod
    def fail(cls, msg: str = "error", code: int = 500):
        return cls(code=code, msg=msg, data=None)