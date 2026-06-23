import os
from datetime import date, datetime
from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal
from models import Todo, Setting
from line_service import send_line_message
from datetime import timezone, timedelta
JST = timezone(timedelta(hours=9))

def update_priority():
    print("update_priority 実行")
    db = SessionLocal()
    try:
        # 今日すでに実行済みか確認
        today = datetime.now(JST).date().isoformat()
        last_updated = db.query(Setting).filter(
            Setting.key == "last_priority_updated_date"
        ).first()

        if last_updated and last_updated.value == today:
            return

        todos = db.query(Todo).all()
        for todo in todos:
            if todo.expiry_date and (todo.expiry_date - datetime.now(JST).date()).days < 3:
                todo.priority = 5
            elif todo.expiry_date and (todo.expiry_date - datetime.now(JST).date()).days < 5:
                todo.priority = 3
        db.commit()

        # 実行済みを記録
        if last_updated:
            last_updated.value = today
        else:
            db.add(Setting(key="last_priority_updated_date", value=today))
        db.commit()
    finally:
        db.close()

def check_and_notify():
    print("check_and_notify 実行")
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
    print("notify_daily 実行")
    db = SessionLocal()
    try:
        notify_setting = db.query(Setting).filter(
            Setting.key == "notify_hour"
        ).first()
        notify_hour = int(notify_setting.value) if notify_setting else 8
        print(f"notify_hour: {notify_hour}, 現在時刻: {datetime.now(JST).hour}")

        if datetime.now(JST).hour != notify_hour:
            print("時刻不一致でスキップ")
            return

        today = date.today().isoformat()
        last_notified_daily = db.query(Setting).filter(
            Setting.key == "last_notified_daily_date"
        ).first()
        print(f"last_notified_daily: {last_notified_daily.value if last_notified_daily else None}")

        if last_notified_daily and last_notified_daily.value == today:
            print("今日分送信済みでスキップ")
            return

        todos = db.query(Todo).filter(
            Todo.is_deleted == False,
            Todo.done == False
        ).all()
        print(f"未完了タスク件数: {len(todos)}")

        if not todos:
            print("タスクなしでスキップ")
            return

        lines = ["📋 今日のタスク一覧"]
        for todo in todos:
            expiry = f"（期限：{todo.expiry_date}）" if todo.expiry_date else ""
            lines.append(f"・{todo.title}　優先度:{todo.priority}{expiry}")
        send_line_message("\n".join(lines))

        if last_notified_daily:
            last_notified_daily.value = today
        else:
            db.add(Setting(key="last_notified_daily_date", value=today))
        db.commit()
    finally:
        db.close()

def renotify_high_priority():
    print("renotify_high_priority 実行")
    db = SessionLocal()
    try:
        # renotify_hourをSettingから取得
        renotify_setting = db.query(Setting).filter(
            Setting.key == "renotify_hour"
        ).first()
        renotify_hour = int(renotify_setting.value) if renotify_setting else 14

        # 指定時刻過ぎてるか確認
        if datetime.now(JST).hour < renotify_hour:
            return

        # 今日すでに再通知送ったか確認
        today = datetime.now(JST).date().isoformat()
        last_renotified = db.query(Setting).filter(
            Setting.key == "last_renotified_date"
        ).first()

        if last_renotified and last_renotified.value == today:
            return

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

        # 今日送ったことを記録
        if last_renotified:
            last_renotified.value = today
        else:
            db.add(Setting(key="last_renotified_date", value=today))
        db.commit()
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
        scheduler.add_job(update_priority, "interval", minutes=5)
        scheduler.add_job(check_and_notify, "interval", minutes=5)
        scheduler.add_job(notify_daily, "interval", minutes=5)
        scheduler.add_job(renotify_high_priority, "interval", minutes=5)
    return scheduler