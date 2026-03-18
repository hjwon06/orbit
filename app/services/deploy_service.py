import asyncio
import time
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Deployment


async def get_deployments(db: AsyncSession, project_id: int, limit: int = 20) -> list:
    """Get deployments for a specific project."""
    try:
        stmt = (
            select(Deployment)
            .where(Deployment.project_id == project_id)
            .order_by(Deployment.started_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    except Exception:
        return []


async def get_all_deployments(db: AsyncSession, limit: int = 50) -> list:
    """Get all deployments across projects."""
    try:
        stmt = (
            select(Deployment)
            .order_by(Deployment.started_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    except Exception:
        return []


async def trigger_deploy(db: AsyncSession, data) -> Deployment:
    """Create a deployment record and trigger background execution."""
    deploy = Deployment(
        project_id=data.project_id,
        target=data.target,
        branch=data.branch,
        status="running",
        triggered_by="manual",
    )
    db.add(deploy)
    await db.commit()
    await db.refresh(deploy)

    # Launch background task for deploy execution
    asyncio.create_task(execute_deploy(deploy.id))

    return deploy


async def execute_deploy(deploy_id: int):
    """Background task: simulate deployment execution."""
    from app.database import async_session

    await asyncio.sleep(1)  # simulate startup delay

    async with async_session() as db:
        try:
            result = await db.execute(select(Deployment).where(Deployment.id == deploy_id))
            deploy = result.scalar_one_or_none()
            if not deploy:
                return

            deploy.status = "running"
            deploy.log = "Starting deployment...\n"
            await db.commit()

            # Simulate deploy steps
            steps = [
                "Pulling latest code...",
                "Installing dependencies...",
                "Running build...",
                "Running tests...",
                "Deploying to target...",
                "Health check passed.",
            ]
            start_time = time.time()
            for step in steps:
                await asyncio.sleep(2)  # simulate work
                deploy.log += f"{step}\n"
                await db.commit()

            duration = int(time.time() - start_time)
            deploy.status = "success"
            deploy.duration_sec = duration
            deploy.finished_at = datetime.now(timezone.utc)
            deploy.log += "Deployment completed successfully.\n"
            await db.commit()

        except Exception as e:
            try:
                deploy.status = "failed"
                deploy.log += f"\nError: {str(e)}\n"
                deploy.finished_at = datetime.now(timezone.utc)
                await db.commit()
            except Exception:
                pass
