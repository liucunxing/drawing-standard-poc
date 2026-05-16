from app.models.schemas import User


class UserService:
    def __init__(self):
        # 模拟数据库，写死数据
        self._users = [
            User(id=1, name="张三", age=25),
            User(id=2, name="李四", age=30),
        ]

    def list_users(self):
        return self._users

    def get_user(self, user_id: int):
        for u in self._users:
            if u.id == user_id:
                return u
        return None

    def create_user(self, name: str, age: int):
        new_id = max(u.id for u in self._users) + 1
        user = User(id=new_id, name=name, age=age)
        self._users.append(user)
        return user


user_service = UserService()