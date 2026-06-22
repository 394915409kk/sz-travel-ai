from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from apps.backend.services.customer_lifecycle_service import CustomerLifecycleService


router = APIRouter(prefix="/customer-lifecycle", tags=["customer-lifecycle"])
TaskStatus = Literal["pending", "completed", "cancelled"]


class TaskStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TaskStatus


@router.post("/profiles/generate")
def generate_profiles():
    profiles = CustomerLifecycleService.generate_profiles()
    return {"success": True, "generated_count": len(profiles), "profiles": profiles}


@router.get("/profiles")
def list_profiles():
    profiles = CustomerLifecycleService.list_profiles()
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
def get_profile(profile_id: int):
    return {"success": True, "profile": CustomerLifecycleService.get_profile(profile_id)}


@router.post("/repurchase-tasks/generate")
def generate_repurchase_tasks():
    tasks = CustomerLifecycleService.generate_repurchase_tasks()
    return {"success": True, "generated_count": len(tasks), "tasks": tasks}


@router.get("/repurchase-tasks")
def list_repurchase_tasks(status: TaskStatus | None = None):
    tasks = CustomerLifecycleService.list_tasks(status=status)
    return {"success": True, "count": len(tasks), "tasks": tasks}


@router.patch("/repurchase-tasks/{task_id}/status")
def update_repurchase_task(task_id: int, request: TaskStatusUpdate):
    return {"success": True, "task": CustomerLifecycleService.update_task_status(task_id, request.status)}
