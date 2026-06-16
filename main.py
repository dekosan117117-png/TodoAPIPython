
from datetime import datetime_CAPI
from schemas import TodoCreate
from models import Todo
from database import SessionLocal, engine
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

@app.get("/todos")
def get_todos(db: Session = Depends(get_db)):
    return db.query(Todo).all()

@app.post("/todos", status_code=201)
def create_todo(todo: TodoCreate, db: Session = Depends(get_db)):
    new_todo = Todo(
        title=todo.title,
        done=todo.done,
        priority=todo.priority,
        expiry_date=todo.expiry_date
    )
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    return new_todo

@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, todo: TodoCreate, db: Session = Depends(get_db)):
    db_todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if not db_todo:
        raise HTTPException(status_code=404, detail="そのIDは存在しないよ！")
    db_todo.title = todo.title
    db_todo.done = todo.done
    db_todo.priority = todo.priority
    db_todo.expiry_date = todo.expiry_date
    db.commit()
    db.refresh(db_todo)
    return db_todo

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    db_todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if not db_todo:
        raise HTTPException(status_code=404, detail="そのIDは存在しないよ！")
    db.delete(db_todo)
    db.commit()
    return {"message": "削除したよ！"} 