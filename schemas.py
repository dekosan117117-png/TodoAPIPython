from datetime import date
from pydantic import BaseModel

class TodoCreate(BaseModel):
    title: str
    done: bool = False
    priority: int = 1
    expiry_date: date = None