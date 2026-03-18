from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import InfraCost
from app.schemas.infra_cost import InfraCostCreate, InfraCostUpdate


async def get_costs_by_project(db: AsyncSession, project_id: int):
    stmt = (
        select(InfraCost)
        .where(InfraCost.project_id == project_id)
        .order_by(InfraCost.provider, InfraCost.service_name)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_cost(db: AsyncSession, cost_id: int):
    result = await db.execute(select(InfraCost).where(InfraCost.id == cost_id))
    return result.scalar_one_or_none()


async def create_cost(db: AsyncSession, data: InfraCostCreate) -> InfraCost:
    cost = InfraCost(**data.model_dump())
    db.add(cost)
    await db.commit()
    await db.refresh(cost)
    return cost


async def update_cost(db: AsyncSession, cost_id: int, data: InfraCostUpdate) -> InfraCost | None:
    values = data.model_dump(exclude_unset=True)
    if not values:
        return await get_cost(db, cost_id)
    await db.execute(update(InfraCost).where(InfraCost.id == cost_id).values(**values))
    await db.commit()
    return await get_cost(db, cost_id)


async def delete_cost(db: AsyncSession, cost_id: int) -> bool:
    result = await db.execute(delete(InfraCost).where(InfraCost.id == cost_id))
    await db.commit()
    return result.rowcount > 0
