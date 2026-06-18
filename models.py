from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime
from database import Base, engine
from datetime import datetime

class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    done = Column(Boolean, default=False)
    priority = Column(Integer, default=1)
    expiry_date = Column(Date, nullable=True)
    is_deleted = Column(Boolean, default=False)  # 論理削除用のフラグ
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)  # 更新日時を記録するカラム

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(String, nullable=True)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

Base.metadata.create_all(bind=engine)