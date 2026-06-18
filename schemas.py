from datetime import date
from pydantic import BaseModel

class TodoCreate(BaseModel):
    title: str
    done: bool = False
    priority: int = 1
    expiry_date: date = None

# ユーザー登録用
class UserCreate(BaseModel):
    username: str
    password: str

# ログイン用（UserCreateと同じだけど役割を明示的に分ける）
class UserLogin(BaseModel):
    username: str
    password: str

# トークンレスポンス用
class Token(BaseModel):
    access_token: str
    token_type: str