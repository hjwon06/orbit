"""AWS Cost Explorer + Vultr API 실시간 비용 조회 서비스."""
import time
from datetime import date, timedelta

from app.config import get_settings

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


# 메모리 캐시 (10분 TTL)
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 600


def _get_cache(key: str) -> dict | None:
    if key in _cache:
        expire_ts, data = _cache[key]
        if time.time() < expire_ts:
            return data
        del _cache[key]
    return None


def _set_cache(key: str, data: dict) -> None:
    _cache[key] = (time.time() + CACHE_TTL, data)


def clear_cache() -> None:
    _cache.clear()


async def get_aws_costs() -> dict:
    """AWS Cost Explorer: 이번 달 + 지난 달 서비스별 비용."""
    cached = _get_cache("aws")
    if cached is not None:
        return cached

    settings = get_settings()
    if not settings.aws_access_key_id or not HAS_BOTO3:
        return {"available": False, "reason": "AWS 키 미설정" if HAS_BOTO3 else "boto3 미설치"}

    try:
        ce = boto3.client(
            "ce",
            region_name="us-east-1",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        today = date.today()
        mtd_start = today.replace(day=1).isoformat()
        mtd_end = (today + timedelta(days=1)).isoformat()

        # 지난 달
        last_month_end = today.replace(day=1) - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1).isoformat()
        last_month_end_str = (last_month_end + timedelta(days=1)).isoformat()

        # 이번 달 서비스별
        mtd_resp = ce.get_cost_and_usage(
            TimePeriod={"Start": mtd_start, "End": mtd_end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        mtd_services = []
        mtd_total = 0.0
        for group in mtd_resp.get("ResultsByTime", [{}])[0].get("Groups", []):
            cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
            if cost > 0.001:
                mtd_services.append({
                    "service_name": group["Keys"][0],
                    "cost_usd": round(cost, 2),
                })
                mtd_total += cost

        mtd_services.sort(key=lambda x: x["cost_usd"], reverse=True)

        # 지난 달 총합
        last_resp = ce.get_cost_and_usage(
            TimePeriod={"Start": last_month_start, "End": last_month_end_str},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )
        last_total = 0.0
        for result in last_resp.get("ResultsByTime", []):
            last_total += float(result["Total"]["UnblendedCost"]["Amount"])

        result = {
            "available": True,
            "provider": "AWS",
            "mtd_total": round(mtd_total, 2),
            "last_month_total": round(last_total, 2),
            "services": mtd_services,
        }
        _set_cache("aws", result)
        return result

    except Exception as e:
        return {"available": False, "reason": f"AWS API 오류: {e}"}


async def get_vultr_costs() -> dict:
    """Vultr API v2: 현재 인스턴스 비용 + 계정 잔액."""
    cached = _get_cache("vultr")
    if cached is not None:
        return cached

    settings = get_settings()
    if not settings.vultr_api_key or not HAS_HTTPX:
        return {"available": False, "reason": "Vultr 키 미설정" if HAS_HTTPX else "httpx 미설치"}

    headers = {"Authorization": f"Bearer {settings.vultr_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # 현재 인스턴스 목록 → monthly_cost 합산
            inst_resp = await client.get(
                "https://api.vultr.com/v2/instances", headers=headers,
            )
            inst_resp.raise_for_status()
            instances = inst_resp.json().get("instances", [])
            instance_costs = []
            mtd_total = 0.0
            for inst in instances:
                cost = float(inst.get("monthly_cost", 0) or 0)
                label = inst.get("label") or inst.get("hostname") or inst.get("id", "unknown")
                region = inst.get("region", "")
                instance_costs.append({
                    "service_name": f"{label} ({region})",
                    "cost_usd": round(cost, 2),
                })
                mtd_total += cost

            instance_costs.sort(key=lambda x: float(x["cost_usd"]), reverse=True)  # type: ignore[arg-type]

            # 계정 잔액
            account_resp = await client.get(
                "https://api.vultr.com/v2/account", headers=headers,
            )
            account_resp.raise_for_status()
            account = account_resp.json().get("account", {})
            balance = float(account.get("balance", 0) or 0)
            pending = float(account.get("pending_charges", 0) or 0)

            # 최근 청구서 (지난 달 비용)
            invoices_resp = await client.get(
                "https://api.vultr.com/v2/billing/invoices", headers=headers,
            )
            invoices_resp.raise_for_status()
            invoices = invoices_resp.json().get("billing_invoices", [])
            last_month_total = 0.0
            if invoices:
                last_month_total = float(invoices[0].get("amount", 0) or 0)

        result = {
            "available": True,
            "provider": "Vultr",
            "mtd_total": round(pending if pending > 0 else mtd_total, 2),
            "last_month_total": round(last_month_total, 2),
            "monthly_estimate": round(mtd_total, 2),
            "balance": round(balance, 2),
            "services": instance_costs,
        }
        _set_cache("vultr", result)
        return result

    except Exception as e:
        return {"available": False, "reason": f"Vultr API 오류: {e}"}


async def get_combined_summary() -> dict:
    """AWS + Vultr + 수동 등록 비용 합산 요약."""
    aws = await get_aws_costs()
    vultr = await get_vultr_costs()

    aws_mtd = aws.get("mtd_total", 0) if aws.get("available") else 0
    aws_last = aws.get("last_month_total", 0) if aws.get("available") else 0
    vultr_mtd = vultr.get("mtd_total", 0) if vultr.get("available") else 0
    vultr_last = vultr.get("last_month_total", 0) if vultr.get("available") else 0

    total_mtd = round(aws_mtd + vultr_mtd, 2)
    total_last = round(aws_last + vultr_last, 2)
    change = round(total_mtd - total_last, 2)
    change_pct = round((change / total_last * 100), 1) if total_last > 0 else 0
    yearly_estimate = round(total_mtd * 12, 2)

    return {
        "total_mtd": total_mtd,
        "total_last_month": total_last,
        "change": change,
        "change_pct": change_pct,
        "yearly_estimate": yearly_estimate,
        "aws": aws,
        "vultr": vultr,
    }
