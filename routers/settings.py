from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from models import Setting
from dependencies import get_db

router = APIRouter()

@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return db.query(Setting).all()

@router.put("/settings/{key}")
def update_setting(key: str, value: str, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail="そのキーは存在しないよ！")
    setting.value = value
    db.commit()
    db.refresh(setting)
    return setting