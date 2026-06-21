import os
from datetime import date, datetime
from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal
from models import Todo, Setting
from line_service import send_line_message

def update_priority():
    db = SessionLocal()
    try:
        todos = db.query(Todo).all()
        for todo in todos:
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
        setting = db.query(Setting).filter(Setting.key == "last_notified_at").first()
        last_notified_at = datetime.fromisoformat(setting.value) if setting.value else None
        query = db.query(Todo).filter(Todo.is_deleted == False)
        if last_notified_at:
            query = query.filter(Todo.updated_at > last_notified_at)
        updated = query.first()
        if updated:
            update_priority()
            print("変更検知！優先度更新したよ")
            todos = db.query(Todo).filter(Todo.is_deleted == False, Todo.done == False).all()
            lines = ["📝 タスクが更新されたよ！\n\n📋 現在のタスク一覧"]
            for i, todo in enumerate(todos, 1):
                expiry = f"（期限：{todo.expiry_date}）" if todo.expiry_date else ""
                lines.append(f"{i}. {todo.title}　優先度:{todo.priority}{expiry}")
            send_line_message("\n".join(lines) if todos else "📝 タスクが更新されたよ！未完了タスクはないよ！")
            setting.value = datetime.now().isoformat()
            db.commit()
    finally:
        db.close()

def notify_daily():
    db = SessionLocal()
    try:
        todos = db.query(Todo).filter(Todo.is_deleted == False, Todo.done == False).all()
        if not todos:
            return
        lines = ["📋 今日のタスク一覧"]
        for todo in todos:
            expiry = f"（期限：{todo.expiry_date}）" if todo.expiry_date else ""
            lines.append(f"・{todo.title}　優先度:{todo.priority}{expiry}")
        send_line_message("\n".join(lines))
    finally:
        db.close()

def renotify_high_priority():
    db = SessionLocal()
    try:
        todos = db.query(Todo).filter(
            Todo.is_deleted == False,
            Todo.done == False,
            Todo.priority >= 3
        ).all()
        if not todos:
            return
        lines = ["🔥 優先度高タスク再通知"]
        for todo in todos:
            expiry = f"（期限：{todo.expiry_date}）" if todo.expiry_date else ""
            lines.append(f"・{todo.title}　優先度:{todo.priority}{expiry}")
        send_line_message("\n".join(lines))
    finally:
        db.close()

def create_scheduler():
    scheduler = BackgroundScheduler()
    if os.getenv("ENV") == "development":
        scheduler.add_job(update_priority, "interval", minutes=1)
        scheduler.add_job(check_and_notify, "interval", minutes=1)
        scheduler.add_job(notify_daily, "interval", minutes=2)
        scheduler.add_job(renotify_high_priority, "interval", minutes=3)
    else:
        scheduler.add_job(update_priority, "cron", hour=0, minute=0)
        scheduler.add_job(check_and_notify, "interval", minutes=5)
        scheduler.add_job(notify_daily, "cron", hour=8, minute=0)
        scheduler.add_job(renotify_high_priority, "cron", hour=14, minute=0)
    return scheduler