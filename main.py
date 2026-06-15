
from datetime import date
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class TodoCreate(BaseModel):
    title: str
    done: bool = False
    priority: int = 1
    expiry_date: date = None

todos = []
next_id = 1

@app.get("/todos")
def get_todos():
    return todos

@app.post("/todos", status_code=201)
def create_todo(todo: TodoCreate):
    global next_id
    new_todo = {"id": next_id, 
                "title": todo.title, 
                "done": todo.done, 
                "priority": todo.priority, 
                "expiry_date": todo.expiry_date
                }
    todos.append(new_todo)
    next_id += 1
    return new_todo

@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, todo: TodoCreate):
    for t in todos:
        if t["id"] == todo_id:
            t["title"] = todo.title
            t["done"] = todo.done
            t["priority"] = todo.priority
            t["expiry_date"] = todo.expiry_date
            return t
    raise HTTPException(status_code=404, detail="そのIDは存在しないよ！")

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int):
    for i, t in enumerate(todos):
        if t["id"] == todo_id:
            todos.pop(i)
            return {"message": "削除したよ！"}
    raise HTTPException(status_code=404, detail="そのIDは存在しないよ！")