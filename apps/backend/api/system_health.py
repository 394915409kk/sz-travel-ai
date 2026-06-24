from fastapi import APIRouter, Request

from apps.backend.services.system_health_service import SystemHealthService


router = APIRouter(prefix="/system-health", tags=["system-health"])


def _route_paths(request):
    return [getattr(route, "path", "") for route in request.app.routes]


@router.get("")
def system_health(request: Request):
    return {"success": True, **SystemHealthService.full_health(_route_paths(request))}


@router.get("/database")
def database_health():
    return {"success": True, **SystemHealthService.database()}


@router.get("/modules")
def module_health(request: Request):
    return {"success": True, **SystemHealthService.modules(_route_paths(request))}


@router.get("/risks")
def system_risks():
    return {"success": True, **SystemHealthService.risks()}


@router.get("/readiness")
def system_readiness(request: Request):
    return {"success": True, **SystemHealthService.readiness(_route_paths(request))}
