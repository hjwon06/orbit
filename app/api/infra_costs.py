from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.infra_cost import InfraCostCreate, InfraCostUpdate, InfraCostResponse
from app.services.infra_cost_service import (
    get_costs_by_project, create_cost, update_cost, delete_cost,
)

router = APIRouter(prefix="/api/infra-costs", tags=["infra-costs"])


@router.get("/project/{project_id}", response_model=list[InfraCostResponse])
async def list_costs(project_id: int, db: AsyncSession = Depends(get_db)):
    return await get_costs_by_project(db, project_id)


@router.post("", response_model=InfraCostResponse, status_code=201)
async def new_cost(data: InfraCostCreate, db: AsyncSession = Depends(get_db)):
    return await create_cost(db, data)


@router.patch("/{cost_id}", response_model=InfraCostResponse)
async def edit_cost(cost_id: int, data: InfraCostUpdate, db: AsyncSession = Depends(get_db)):
    cost = await update_cost(db, cost_id, data)
    if not cost:
        raise HTTPException(status_code=404, detail="Cost not found")
    return cost


@router.delete("/{cost_id}")
async def remove_cost(cost_id: int, db: AsyncSession = Depends(get_db)):
    if not await delete_cost(db, cost_id):
        raise HTTPException(status_code=404, detail="Cost not found")
    return {"ok": True}
