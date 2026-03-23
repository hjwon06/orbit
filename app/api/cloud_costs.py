"""서버 총비용 API 라우터."""
from fastapi import APIRouter

from app.services.cloud_cost_service import (
    get_aws_costs,
    get_combined_summary,
    get_vultr_costs,
    clear_cache,
)

router = APIRouter(prefix="/api/cloud-costs", tags=["cloud-costs"])


@router.get("/summary")
async def cloud_cost_summary():
    """AWS + Vultr 합산 요약."""
    return await get_combined_summary()


@router.get("/detail")
async def cloud_cost_detail():
    """AWS, Vultr 각각 서비스별 상세."""
    aws = await get_aws_costs()
    vultr = await get_vultr_costs()
    return {"aws": aws, "vultr": vultr}


@router.post("/refresh")
async def cloud_cost_refresh():
    """캐시 강제 초기화 후 재조회."""
    clear_cache()
    return await get_combined_summary()
