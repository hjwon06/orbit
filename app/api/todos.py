from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.todo import TodoCreate, TodoUpdate, TodoResponse
from app.services.todo_service import (
    get_todos_by_project, create_todo, update_todo, delete_todo,
    ai_recommend_todos, reprioritize_todos,
)

router = APIRouter(prefix="/api/todos", tags=["todos"])


@router.get("/project/{project_id}", response_model=list[TodoResponse])
async def list_todos(project_id: int, db: AsyncSession = Depends(get_db)):
    return await get_todos_by_project(db, project_id)


@router.post("", response_model=TodoResponse, status_code=201)
async def new_todo(data: TodoCreate, db: AsyncSession = Depends(get_db)):
    return await create_todo(db, data)


@router.patch("/{todo_id}", response_model=TodoResponse)
async def edit_todo(todo_id: int, data: TodoUpdate, db: AsyncSession = Depends(get_db)):
    todo = await update_todo(db, todo_id, data)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo


@router.delete("/{todo_id}")
async def remove_todo(todo_id: int, db: AsyncSession = Depends(get_db)):
    if not await delete_todo(db, todo_id):
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"ok": True}


@router.post("/project/{project_id}/recommend", response_model=list[TodoResponse])
async def recommend_todos(project_id: int, db: AsyncSession = Depends(get_db)):
    return await ai_recommend_todos(db, project_id)


@router.post("/project/{project_id}/reprioritize")
async def reprioritize(project_id: int, db: AsyncSession = Depends(get_db)):
    return await reprioritize_todos(db, project_id)
