from fastapi import APIRouter

from apps.backend.services.dashboard_service import DashboardService


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
def dashboard_overview():
    return {"success": True, **DashboardService.overview()}


@router.get("/today")
def dashboard_today():
    return {"success": True, **DashboardService.today()}


@router.get("/sales")
def dashboard_sales():
    return {"success": True, **DashboardService.sales()}


@router.get("/profit")
def dashboard_profit():
    return {"success": True, **DashboardService.profit()}


@router.get("/risks")
def dashboard_risks():
    return {"success": True, **DashboardService.risks()}


@router.get("/actions")
def dashboard_actions():
    return {"success": True, **DashboardService.actions()}
