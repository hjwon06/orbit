"""AWS EC2/RDS/CloudWatch 인프라 관리 서비스.

cloud_cost_service.py 패턴을 따르며, boto3 호출은 asyncio.to_thread로 감싼다.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from app.config import get_settings

try:
    import boto3

    HAS_BOTO3 = True
except ImportError:
    boto3 = None  # type: ignore[assignment]
    HAS_BOTO3 = False

logger = logging.getLogger(__name__)

# --- 메모리 캐시 (10분 TTL) ---
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL = 600


def _get_cache(key: str) -> dict[str, Any] | None:
    if key in _cache:
        expire_ts, data = _cache[key]
        if time.time() < expire_ts:
            return data
        del _cache[key]
    return None


def _set_cache(key: str, data: dict[str, Any]) -> None:
    _cache[key] = (time.time() + CACHE_TTL, data)


def _invalidate_cache(key: str) -> None:
    _cache.pop(key, None)


def clear_aws_cache() -> None:
    """AWS 관련 캐시만 클리어."""
    keys_to_remove = [k for k in _cache if k.startswith("aws_")]
    for k in keys_to_remove:
        del _cache[k]


# --- boto3 client 싱글턴 ---

@lru_cache(maxsize=8)
def _get_boto3_client(service_name: str) -> Any:
    """boto3 client를 lru_cache로 재사용한다."""
    settings = get_settings()
    return boto3.client(  # type: ignore[union-attr]
        service_name,
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def _check_available() -> dict[str, Any] | None:
    """boto3 / 키 미설정이면 에러 dict 반환, 정상이면 None."""
    if not HAS_BOTO3:
        return {"available": False, "reason": "boto3 미설치"}
    settings = get_settings()
    if not settings.aws_access_key_id:
        return {"available": False, "reason": "AWS 키 미설정"}
    return None


# --- EC2 ---

async def get_ec2_instances() -> dict[str, Any]:
    """EC2 인스턴스 목록 조회."""
    cached = _get_cache("aws_ec2_instances")
    if cached is not None:
        return cached

    err = _check_available()
    if err is not None:
        return err

    try:
        ec2 = _get_boto3_client("ec2")
        resp = await asyncio.to_thread(ec2.describe_instances)

        instances: list[dict[str, Any]] = []
        for reservation in resp.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                name = ""
                for tag in inst.get("Tags", []):
                    if tag.get("Key") == "Name":
                        name = tag.get("Value", "")
                        break

                launch_time = inst.get("LaunchTime")
                launch_str = (
                    launch_time.isoformat()
                    if isinstance(launch_time, datetime)
                    else str(launch_time or "")
                )

                instances.append({
                    "instance_id": inst.get("InstanceId", ""),
                    "name": name,
                    "instance_type": inst.get("InstanceType", ""),
                    "state": inst.get("State", {}).get("Name", ""),
                    "az": inst.get("Placement", {}).get("AvailabilityZone", ""),
                    "public_ip": inst.get("PublicIpAddress", ""),
                    "private_ip": inst.get("PrivateIpAddress", ""),
                    "launch_time": launch_str,
                })

        result: dict[str, Any] = {"available": True, "instances": instances}
        _set_cache("aws_ec2_instances", result)
        return result

    except Exception as e:
        logger.exception("EC2 인스턴스 조회 실패")
        return {"available": False, "reason": f"EC2 API 오류: {e}"}


async def get_ec2_metrics(instance_id: str) -> dict[str, Any]:
    """CloudWatch에서 EC2 CPU/네트워크 지표 조회 (최근 1시간, 5분 간격)."""
    cache_key = f"aws_ec2_metrics_{instance_id}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    err = _check_available()
    if err is not None:
        return err

    try:
        cw = _get_boto3_client("cloudwatch")
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(hours=1)
        period = 300  # 5분

        dimensions = [{"Name": "InstanceId", "Value": instance_id}]

        def _fetch_metric(metric_name: str) -> list[dict[str, Any]]:
            resp = cw.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start,
                EndTime=now,
                Period=period,
                Statistics=["Average", "Maximum", "Sum"],
            )
            return resp.get("Datapoints", [])  # type: ignore[no-any-return]

        cpu_data, net_in_data, net_out_data = await asyncio.to_thread(
            lambda: (
                _fetch_metric("CPUUtilization"),
                _fetch_metric("NetworkIn"),
                _fetch_metric("NetworkOut"),
            ),
        )

        cpu_avg = 0.0
        cpu_max = 0.0
        if cpu_data:
            cpu_avg = round(
                sum(d["Average"] for d in cpu_data) / len(cpu_data), 2,
            )
            cpu_max = round(max(d["Maximum"] for d in cpu_data), 2)

        net_in = round(sum(d.get("Sum", 0) for d in net_in_data), 0)
        net_out = round(sum(d.get("Sum", 0) for d in net_out_data), 0)

        result: dict[str, Any] = {
            "available": True,
            "instance_id": instance_id,
            "cpu_avg": cpu_avg,
            "cpu_max": cpu_max,
            "network_in_bytes": net_in,
            "network_out_bytes": net_out,
        }
        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.exception("EC2 메트릭 조회 실패: %s", instance_id)
        return {"available": False, "reason": f"CloudWatch 오류: {e}"}


# --- RDS ---

async def get_rds_instances() -> dict[str, Any]:
    """RDS 인스턴스 목록 조회."""
    cached = _get_cache("aws_rds_instances")
    if cached is not None:
        return cached

    err = _check_available()
    if err is not None:
        return err

    try:
        rds = _get_boto3_client("rds")
        resp = await asyncio.to_thread(rds.describe_db_instances)

        instances: list[dict[str, Any]] = []
        for db in resp.get("DBInstances", []):
            endpoint = db.get("Endpoint", {})
            instances.append({
                "db_instance_id": db.get("DBInstanceIdentifier", ""),
                "engine": db.get("Engine", ""),
                "engine_version": db.get("EngineVersion", ""),
                "instance_class": db.get("DBInstanceClass", ""),
                "status": db.get("DBInstanceStatus", ""),
                "endpoint": endpoint.get("Address", ""),
                "port": endpoint.get("Port", 0),
                "az": db.get("AvailabilityZone", ""),
                "storage_gb": db.get("AllocatedStorage", 0),
                "multi_az": db.get("MultiAZ", False),
            })

        result: dict[str, Any] = {"available": True, "instances": instances}
        _set_cache("aws_rds_instances", result)
        return result

    except Exception as e:
        logger.exception("RDS 인스턴스 조회 실패")
        return {"available": False, "reason": f"RDS API 오류: {e}"}


async def get_rds_metrics(db_instance_id: str) -> dict[str, Any]:
    """CloudWatch에서 RDS CPU/메모리/커넥션 지표 조회 (최근 1시간)."""
    cache_key = f"aws_rds_metrics_{db_instance_id}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    err = _check_available()
    if err is not None:
        return err

    try:
        cw = _get_boto3_client("cloudwatch")
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(hours=1)
        period = 300

        dimensions = [{"Name": "DBInstanceIdentifier", "Value": db_instance_id}]

        def _fetch_metric(metric_name: str) -> list[dict[str, Any]]:
            resp = cw.get_metric_statistics(
                Namespace="AWS/RDS",
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start,
                EndTime=now,
                Period=period,
                Statistics=["Average", "Maximum", "Sum"],
            )
            return resp.get("Datapoints", [])  # type: ignore[no-any-return]

        cpu_data, mem_data, conn_data = await asyncio.to_thread(
            lambda: (
                _fetch_metric("CPUUtilization"),
                _fetch_metric("FreeableMemory"),
                _fetch_metric("DatabaseConnections"),
            ),
        )

        cpu_avg = 0.0
        if cpu_data:
            cpu_avg = round(
                sum(d["Average"] for d in cpu_data) / len(cpu_data), 2,
            )

        freeable_mb = 0.0
        if mem_data:
            latest = max(mem_data, key=lambda d: d.get("Timestamp", 0))
            freeable_mb = round(latest.get("Average", 0) / (1024 * 1024), 1)

        connections = 0
        if conn_data:
            latest_conn = max(conn_data, key=lambda d: d.get("Timestamp", 0))
            connections = int(latest_conn.get("Average", 0))

        result: dict[str, Any] = {
            "available": True,
            "db_instance_id": db_instance_id,
            "cpu_avg": cpu_avg,
            "freeable_memory_mb": freeable_mb,
            "connections": connections,
        }
        _set_cache(cache_key, result)
        return result

    except Exception as e:
        logger.exception("RDS 메트릭 조회 실패: %s", db_instance_id)
        return {"available": False, "reason": f"CloudWatch 오류: {e}"}


# --- CloudWatch Alarms ---

async def get_cloudwatch_alarms() -> dict[str, Any]:
    """CloudWatch 알람 전체 조회."""
    cached = _get_cache("aws_cw_alarms")
    if cached is not None:
        return cached

    err = _check_available()
    if err is not None:
        return err

    try:
        cw = _get_boto3_client("cloudwatch")
        resp = await asyncio.to_thread(cw.describe_alarms)

        alarms: list[dict[str, Any]] = []
        summary = {"ok": 0, "alarm": 0, "insufficient": 0}

        for alarm in resp.get("MetricAlarms", []):
            state = alarm.get("StateValue", "INSUFFICIENT_DATA")
            alarms.append({
                "name": alarm.get("AlarmName", ""),
                "state": state,
                "metric_name": alarm.get("MetricName", ""),
                "namespace": alarm.get("Namespace", ""),
                "description": alarm.get("AlarmDescription", ""),
            })
            if state == "OK":
                summary["ok"] += 1
            elif state == "ALARM":
                summary["alarm"] += 1
            else:
                summary["insufficient"] += 1

        result: dict[str, Any] = {
            "available": True,
            "alarms": alarms,
            "summary": summary,
        }
        _set_cache("aws_cw_alarms", result)
        return result

    except Exception as e:
        logger.exception("CloudWatch 알람 조회 실패")
        return {"available": False, "reason": f"CloudWatch 오류: {e}"}


# --- EC2 Actions ---

async def ec2_action(
    instance_id: str,
    action: str,
    reason: str = "",
    actor: str = "",
) -> dict[str, Any]:
    """EC2 인스턴스 start/stop/reboot 실행.

    실행 전 감사 로그를 남기고, 성공 후 EC2 캐시를 즉시 무효화한다.
    """
    err = _check_available()
    if err is not None:
        return {"success": False, "message": err.get("reason", "사용 불가")}

    allowed = {"start", "stop", "reboot"}
    if action not in allowed:
        return {"success": False, "message": f"허용되지 않는 액션: {action}"}

    logger.warning(
        "EC2 ACTION: %s requested %s on %s. Reason: %s",
        actor or "unknown",
        action,
        instance_id,
        reason or "none",
    )

    try:
        ec2 = _get_boto3_client("ec2")

        if action == "start":
            await asyncio.to_thread(
                ec2.start_instances, InstanceIds=[instance_id],
            )
        elif action == "stop":
            await asyncio.to_thread(
                ec2.stop_instances, InstanceIds=[instance_id],
            )
        else:  # reboot
            await asyncio.to_thread(
                ec2.reboot_instances, InstanceIds=[instance_id],
            )

        # EC2 캐시 즉시 무효화
        _invalidate_cache("aws_ec2_instances")

        return {
            "success": True,
            "message": f"{instance_id} {action} 요청 완료",
        }

    except Exception as e:
        logger.exception("EC2 액션 실패: %s %s", action, instance_id)
        return {"success": False, "message": f"EC2 액션 오류: {e}"}


# --- Cost Summary (cloud_cost_service 재활용) ---

async def get_cost_summary() -> dict[str, Any]:
    """cloud_cost_service.get_aws_costs()를 재활용한 비용 요약."""
    try:
        from app.services.cloud_cost_service import get_aws_costs

        return await get_aws_costs()
    except Exception as e:
        logger.exception("비용 요약 조회 실패")
        return {"available": False, "reason": f"비용 조회 오류: {e}"}
