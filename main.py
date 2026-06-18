from schemas import TodoCreate
from models import Todo, Setting
from database import SessionLocal, engine
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

def init_settings():
    db = SessionLocal()
    try:
        default_settings = [
            {"key": "notify_hour", "value": "8"},
            {"key": "renotify_hour", "value": "14"},
            {"key": "notify_enabled", "value": "true"},
            {"key": "last_notified_at", "value": None},
            {"key": "line_user_id", "value": None},
        ]
        for setting in default_settings:
            # 既に存在する場合はスキップ
            exists = db.query(Setting).filter(Setting.key == setting["key"]).first()
            if not exists:
                db.add(Setting(key=setting["key"], value=setting["value"]))
        db.commit()
    finally:
        db.close()

# アプリ起動時に実行
init_settings()

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


def check_and_notify():
    db = SessionLocal()
    try:
        # DBからlast_notified_atを取得
        setting = db.query(Setting).filter(Setting.key == "last_notified_at").first()
        last_notified_at = datetime.fromisoformat(setting.value) if setting.value else None

        query = db.query(Todo).filter(Todo.is_deleted == False)
        if last_notified_at:
            query = query.filter(Todo.updated_at > last_notified_at)
        
        updated = query.first()
        if updated:
            update_priority()
            # TODO: LINE通知（後で実装）
            print("変更検知！優先度更新したよ")
            # DBにlast_notified_atを保存
            setting.value = datetime.now().isoformat()
            db.commit()
    finally:
        db.close()

# スケジューラ2本立て
if os.getenv("ENV") == "development":
    scheduler.add_job(update_priority, "interval", minutes=1)
    scheduler.add_job(check_and_notify, "interval", minutes=1)
else:
    scheduler.add_job(update_priority, "cron", hour=0, minute=0)
    scheduler.add_job(check_and_notify, "interval", minutes=5)

scheduler.start()

@app.get("/todos")
def get_todos(db: Session = Depends(get_db)):
    return db.query(Todo).filter(Todo.is_deleted == False).all()

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
    db_todo = db.query(Todo).filter(Todo.id == todo_id, Todo.is_deleted == False).first()
    if not db_todo:
        raise HTTPException(status_code=404, detail="そのIDは存在しないよ！")
    db_todo.is_deleted = True
    db.commit()
    return {"message": "削除したよ！"}

@app.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return db.query(Setting).all()

@app.put("/settings/{key}")
def update_setting(key: str, value: str, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail="そのキーは存在しないよ！")
    setting.value = value
    db.commit()
    db.refresh(setting)
    return setting