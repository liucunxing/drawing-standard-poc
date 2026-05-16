from pydantic import BaseModel


class User(BaseModel):
    id: int
    name: str
    age: int


class UserCreate(BaseModel):
    name: str
    age: int