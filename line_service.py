import os
import requests
from fastapi import Request
from database import SessionLocal
from models import Todo, Setting
from datetime import datetime
import hmac
import hashlib
import base64

def verify_signature(body: bytes, signature: str) -> bool:
    channel_secret = os.getenv("LINE_CHANNEL_SECRET", "")
    hash = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash).decode("utf-8")
    return hmac.compare_digest(expected, signature)

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
    print(f"LINE送信結果: {response.status_code} {response.text}")

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

async def handle_webhook(request: Request):
    body_bytes = await request.body()
    signature = request.headers.get("X-Line-Signature", "")
    
    if not verify_signature(body_bytes, signature):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="署名が不正だよ！")
    
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
                    for todo in todos[:13]
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
                    # last_notified_atを更新して変更通知を抑制する
                    notify_setting = db.query(Setting).filter(Setting.key == "last_notified_at").first()
                    if notify_setting:
                        notify_setting.value = datetime.now().isoformat()
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