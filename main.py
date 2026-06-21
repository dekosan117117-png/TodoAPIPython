from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date, datetime
import os
from dotenv import load_dotenv
from schemas import TodoCreate, UserCreate, UserLogin, Token
from models import Todo, Setting, User
from database import SessionLocal, engine
from auth import verify_password, get_password_hash, create_access_token, decode_access_token
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
import requests
from fastapi import Request

load_dotenv()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    username = decode_access_token(token)
    if username is None:
        raise HTTPException(status_code=401, detail="トークンが無効だよ！")
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="ユーザーが存在しないよ！")
    return user

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # 開発
        "http://localhost:4173",  # プレビュー
        "https://todo-frontend-rot7.vercel.app",  # 本番URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            exists = db.query(Setting).filter(Setting.key == setting["key"]).first()
            if not exists:
                db.add(Setting(key=setting["key"], value=setting["value"]))
        db.commit()
    finally:
        db.close()

def send_line_message(text: str):
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")
    if not token or not user_id:
        print("LINE設定がないよ")
        return
    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "to": user_id,
            "messages": [{"type": "text", "text": text}]
        }
    )

def send_line_reply(reply_token: str, messages: list):
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "replyToken": reply_token,
            "messages": messages
        }
    )

init_settings()

scheduler = BackgroundScheduler()

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

scheduler.start()

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    events = body.get("events", [])
    
    for event in events:
        if event.get("type") != "message":
            continue
        if event.get("message", {}).get("type") != "text":
            continue
        
        reply_token = event.get("replyToken")
        text = event.get("message", {}).get("text", "").strip()
        
        if text == "完了":
            db = SessionLocal()
            try:
                todos = db.query(Todo).filter(
                    Todo.is_deleted == False,
                    Todo.done == False
                ).all()
                
                if not todos:
                    send_line_reply(reply_token, [{"type": "text", "text": "未完了のタスクはないよ！"}])
                    continue
                
                quick_replies = [
                    {
                        "type": "action",
                        "action": {
                            "type": "message",
                            "label": todo.title[:20],
                            "text": f"完了:{todo.id}"
                        }
                    }
                    for todo in todos[:13]  # クイックリプライは最大13個
                ]
                
                send_line_reply(reply_token, [{
                    "type": "text",
                    "text": "どのタスクを完了する？",
                    "quickReply": {"items": quick_replies}
                }])
            finally:
                db.close()
        
        elif text.startswith("完了:"):
            todo_id = int(text.split(":")[1])
            db = SessionLocal()
            try:
                todo = db.query(Todo).filter(Todo.id == todo_id).first()
                if todo:
                    todo.done = True
                    db.commit()
                    remaining = db.query(Todo).filter(Todo.is_deleted == False, Todo.done == False).all()
                    if remaining:
                        lines = [f"「{todo.title}」を完了にしたよ！✅\n\n📋 残りのタスク"]
                        for i, t in enumerate(remaining, 1):
                            expiry = f"（期限：{t.expiry_date}）" if t.expiry_date else ""
                            lines.append(f"{i}. {t.title}　優先度:{t.priority}{expiry}")
                        send_line_reply(reply_token, [{"type": "text", "text": "\n".join(lines)}])
                    else:
                        send_line_reply(reply_token, [{"type": "text", "text": f"「{todo.title}」を完了にしたよ！✅\n\n全タスク完了！🎉"}])
                else:
                    send_line_reply(reply_token, [{"type": "text", "text": "タスクが見つからなかったよ！"}])
            finally:
                db.close()
    
    return {"status": "ok"}

@app.get("/todos")
def get_todos(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Todo).filter(Todo.is_deleted == False).all()

@app.post("/todos", status_code=201)
def create_todo(todo: TodoCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
def update_todo(todo_id: int, todo: TodoCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
def delete_todo(todo_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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

@app.post("/register", status_code=201)
def register(user: UserCreate, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.username == user.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="そのユーザー名は既に使われてるよ！")
    new_user = User(username=user.username, hashed_password=get_password_hash(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "登録したよ！"}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    db_user = db.query(User).filter(User.username == form_data.username).first()
    if not db_user or not verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="ユーザー名かパスワードが違うよ！")
    token = create_access_token({"sub": db_user.username})
    return Token(access_token=token, token_type="bearer")

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "ok"}