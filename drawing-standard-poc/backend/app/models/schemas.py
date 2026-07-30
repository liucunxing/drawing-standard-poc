from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str
    age: int


class UserCreate(BaseModel):
    name: str
    age: int


class StandardDataCreate(BaseModel):
    standard_no: str
    standard_type: str
    standard_prefix: str
    operator: str | None = "system"


class StandardDataUpdate(BaseModel):
    standard_no: str
    standard_type: str
    standard_prefix: str
    operator: str | None = "system"