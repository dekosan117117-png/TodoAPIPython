from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends
from dotenv import load_dotenv
from database import SessionLocal
from models import Setting
from dependencies import get_db
from line_service import handle_webhook
from scheduler import create_scheduler
from routers import todos, users, settings

load_dotenv()

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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        "https://todo-frontend-rot7.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(todos.router)
app.include_router(users.router)
app.include_router(settings.router)

init_settings()
scheduler = create_scheduler()
scheduler.start()

@app.post("/webhook")
async def webhook(request: Request):
    return await handle_webhook(request)

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "ok"}