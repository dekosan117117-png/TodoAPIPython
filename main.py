from schemas import TodoCreate
from models import Todo
from database import SessionLocal, engine
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

scheduler = BackgroundScheduler()
def update_priority():
    db = SessionLocal()
    try:
        # ここでDBからデータ取得してループ処理
        todos = db.query(Todo).all()
        for todo in todos:
            # 期限が近いものは優先度を上げる
            if todo.expiry_date and (todo.expiry_date - date.today()).days < 3:
                todo.priority = 5
            elif todo.expiry_date and (todo.expiry_date - date.today()).days < 5:
                todo.priority = 3
            
        db.commit()
    finally:
        db.close()

scheduler.add_job(update_priority, "interval", minutes=1)
scheduler.start()

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