from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from apps.backend.security import require_internal_api_key
from apps.backend.services.content_marketing_service import ContentMarketingService


router = APIRouter(prefix="/content-marketing", tags=["content-marketing"])
Platform = Literal["xiaohongshu", "douyin", "video_account", "wechat", "website"]
ContentType = Literal["note", "short_video_script", "poster_copy", "itinerary_post", "promotion_post"]
ContentStatus = Literal["draft", "ready", "published", "archived"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContentGenerate(StrictModel):
    campaign_name: str | None = None
    destination: str = Field(min_length=1)
    product_theme: str | None = None
    target_audience: str | None = None
    platform: Platform
    content_type: ContentType
    related_product_id: int | None = Field(default=None, gt=0)
    related_resource_ids: list[int] = Field(default_factory=list)


class ContentStatusUpdate(StrictModel):
    status: ContentStatus


@router.post("/generate")
def generate_content(
    request: ContentGenerate,
    _: None = Depends(require_internal_api_key),
):
    return {"success": True, "campaign": ContentMarketingService.generate(request.model_dump())}


@router.get("")
def list_content(status: ContentStatus | None = None, platform: Platform | None = None):
    campaigns = ContentMarketingService.list_campaigns(status=status, platform=platform)
    return {"success": True, "count": len(campaigns), "campaigns": campaigns}


@router.get("/high-margin-topics")
def high_margin_topics():
    topics = ContentMarketingService.high_margin_topics()
    return {"success": True, "count": len(topics), "topics": topics}


@router.get("/calendar")
def content_calendar(date_from: date | None = None, date_to: date | None = None, status: ContentStatus | None = None):
    campaigns = ContentMarketingService.list_campaigns(status=status, date_from=date_from, date_to=date_to)
    return {"success": True, "count": len(campaigns), "calendar": campaigns}


@router.get("/{campaign_id}")
def get_content(campaign_id: int):
    return {"success": True, "campaign": ContentMarketingService.get(campaign_id)}


@router.patch("/{campaign_id}/status")
def update_content_status(
    campaign_id: int,
    request: ContentStatusUpdate,
    _: None = Depends(require_internal_api_key),
):
    return {"success": True, "campaign": ContentMarketingService.update_status(campaign_id, request.status)}
