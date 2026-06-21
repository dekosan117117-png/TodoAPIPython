from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from schemas import TodoCreate
from models import Todo, User
from dependencies import get_db, get_current_user

router = APIRouter()

@router.get("/todos")
def get_todos(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Todo).filter(Todo.is_deleted == False).all()

@router.post("/todos", status_code=201)
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

@router.put("/todos/{todo_id}")
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

@router.delete("/todos/{todo_id}")
def delete_todo(todo_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_todo = db.query(Todo).filter(Todo.id == todo_id, Todo.is_deleted == False).first()
    if not db_todo:
        raise HTTPException(status_code=404, detail="そのIDは存在しないよ！")
    db_todo.is_deleted = True
    db.commit()
    return {"message": "削除したよ！"}