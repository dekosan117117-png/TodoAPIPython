from sqlalchemy import Column, Integer, String, Boolean, Date
from database import Base, engine

class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    done = Column(Boolean, default=False)
    priority = Column(Integer, default=1)
    expiry_date = Column(Date, nullable=True)

Base.metadata.create_all(bind=engine)