from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from apps.backend.security import require_internal_api_key
from apps.backend.services.customer_lifecycle_service import CustomerLifecycleService
from apps.backend.services.privacy_service import PrivacyService


router = APIRouter(prefix="/customer-lifecycle", tags=["customer-lifecycle"])
TaskStatus = Literal["pending", "completed", "cancelled"]


class TaskStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TaskStatus


@router.post("/profiles/generate")
def generate_profiles(_: None = Depends(require_internal_api_key)):
    profiles = CustomerLifecycleService.generate_profiles()
    return {"success": True, "generated_count": len(profiles), "profiles": profiles}


@router.get("/profiles")
def list_profiles(mask_sensitive: bool = False):
    profiles = CustomerLifecycleService.list_profiles()
    if mask_sensitive:
        profiles = PrivacyService.mask_sensitive_dict(profiles)
    return {"success": True, "count": len(profiles), "profiles": profiles}


@router.get("/high-value-customers")
def high_value_customers():
    profiles = CustomerLifecycleService.list_profiles(customer_level="high_value")
    return {"success": True, "count": len(profiles), "profiles": profiles}


@router.get("/dormant-customers")
def dormant_customers():
    profiles = CustomerLifecycleService.list_profiles(lifecycle_stage="dormant")
    return {"success": True, "count": len(profiles), "profiles": profiles}


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: int, mask_sensitive: bool = False):
    profile = CustomerLifecycleService.get_profile(profile_id)
    if mask_sensitive:
        profile = PrivacyService.mask_sensitive_dict(profile)
    return {"success": True, "profile": profile}


@router.post("/repurchase-tasks/generate")
def generate_repurchase_tasks(_: None = Depends(require_internal_api_key)):
    tasks = CustomerLifecycleService.generate_repurchase_tasks()
    return {"success": True, "generated_count": len(tasks), "tasks": tasks}


@router.get("/repurchase-tasks")
def list_repurchase_tasks(status: TaskStatus | None = None):
    tasks = CustomerLifecycleService.list_tasks(status=status)
    return {"success": True, "count": len(tasks), "tasks": tasks}


@router.patch("/repurchase-tasks/{task_id}/status")
def update_repurchase_task(
    task_id: int,
    request: TaskStatusUpdate,
    _: None = Depends(require_internal_api_key),
):
    return {"success": True, "task": CustomerLifecycleService.update_task_status(task_id, request.status)}
