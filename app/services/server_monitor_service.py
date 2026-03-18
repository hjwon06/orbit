from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings

settings = get_settings()


def get_managed_servers() -> list[dict]:
    """Return list of managed server configs."""
    return [
        {"name": "orbit-web", "type": "ec2", "instance_id": "i-placeholder-web"},
        {"name": "orbit-db", "type": "rds", "instance_id": "orbit-db-instance"},
    ]


async def get_latest_snapshots(db: AsyncSession) -> list:
    """Get the latest snapshot for each managed server."""
    from app.models import ServerSnapshot

    servers = get_managed_servers()
    results = []
    try:
        for server in servers:
            stmt = (
                select(ServerSnapshot)
                .where(ServerSnapshot.server_name == server["name"])
                .order_by(ServerSnapshot.collected_at.desc())
                .limit(1)
            )
            result = await db.execute(stmt)
            snapshot = result.scalar_one_or_none()
            if snapshot:
                results.append(snapshot)
    except Exception:
        pass
    return results


async def get_server_history(
    db: AsyncSession,
    server_name: str,
    hours: int = 24,
    limit: int = 100,
) -> list:
    """Get historical snapshots for a server."""
    from app.models import ServerSnapshot

    try:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        stmt = (
            select(ServerSnapshot)
            .where(
                ServerSnapshot.server_name == server_name,
                ServerSnapshot.collected_at >= since,
            )
            .order_by(ServerSnapshot.collected_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    except Exception:
        return []


async def collect_ec2_metrics(db: AsyncSession, server_name: str, instance_id: str) -> dict | None:
    """Collect EC2 instance metrics using boto3 CloudWatch."""
    from app.models import ServerSnapshot

    try:
        import boto3
    except ImportError:
        return {"error": "boto3 not installed"}

    try:
        cw = boto3.client(
            "cloudwatch",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)

        def _get_metric(metric_name: str, namespace: str = "AWS/EC2") -> float:
            try:
                resp = cw.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=["Average"],
                )
                datapoints = resp.get("Datapoints", [])
                if datapoints:
                    latest = sorted(datapoints, key=lambda x: x["Timestamp"])[-1]
                    return round(latest["Average"], 2)
            except Exception:
                pass
            return 0.0

        cpu_pct = _get_metric("CPUUtilization")

        raw_data = {
            "instance_id": instance_id,
            "cpu_pct": cpu_pct,
            "source": "cloudwatch",
        }

        snapshot = ServerSnapshot(
            server_name=server_name,
            cpu_pct=cpu_pct,
            memory_pct=0,
            disk_pct=0,
            raw_data=raw_data,
        )
        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)

        return {
            "server_name": server_name,
            "cpu_pct": cpu_pct,
            "collected_at": snapshot.collected_at.isoformat() if snapshot.collected_at else None,
        }
    except Exception as e:
        return {"error": str(e)}


async def collect_rds_metrics(db: AsyncSession, server_name: str, instance_id: str) -> dict | None:
    """Collect RDS instance metrics using boto3 CloudWatch."""
    from app.models import ServerSnapshot

    try:
        import boto3
    except ImportError:
        return {"error": "boto3 not installed"}

    try:
        cw = boto3.client(
            "cloudwatch",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)

        def _get_metric(metric_name: str) -> float:
            try:
                resp = cw.get_metric_statistics(
                    Namespace="AWS/RDS",
                    MetricName=metric_name,
                    Dimensions=[{"Name": "DBInstanceIdentifier", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=["Average"],
                )
                datapoints = resp.get("Datapoints", [])
                if datapoints:
                    latest = sorted(datapoints, key=lambda x: x["Timestamp"])[-1]
                    return round(latest["Average"], 2)
            except Exception:
                pass
            return 0.0

        cpu_pct = _get_metric("CPUUtilization")
        free_mem = _get_metric("FreeableMemory")
        free_storage = _get_metric("FreeStorageSpace")

        raw_data = {
            "instance_id": instance_id,
            "cpu_pct": cpu_pct,
            "freeable_memory_bytes": free_mem,
            "free_storage_bytes": free_storage,
            "source": "cloudwatch",
        }

        snapshot = ServerSnapshot(
            server_name=server_name,
            cpu_pct=cpu_pct,
            memory_pct=0,
            disk_pct=0,
            raw_data=raw_data,
        )
        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)

        return {
            "server_name": server_name,
            "cpu_pct": cpu_pct,
            "freeable_memory_bytes": free_mem,
            "free_storage_bytes": free_storage,
            "collected_at": snapshot.collected_at.isoformat() if snapshot.collected_at else None,
        }
    except Exception as e:
        return {"error": str(e)}
