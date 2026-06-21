from datetime import date

from fastapi import APIRouter

from apps.backend.db import get_connection
from apps.backend.services.ceo_agent_service import CeoAgentService


router = APIRouter(prefix="/ceo-agent", tags=["ceo-agent"])


@router.get("/daily-report")
def get_daily_report(report_date: date | None = None):
    conn = get_connection()
    try:
        report = CeoAgentService(conn).daily_report(report_date)
    finally:
        conn.close()
    return {"success": True, **report}


@router.get("/risk-alerts")
def get_risk_alerts(report_date: date | None = None):
    conn = get_connection()
    try:
        alerts = CeoAgentService(conn).risk_alerts(report_date)
    finally:
        conn.close()
    return {"success": True, **alerts}


@router.get("/recommendations")
def get_recommendations(report_date: date | None = None):
    conn = get_connection()
    try:
        recommendations = CeoAgentService(conn).recommendations(report_date)
    finally:
        conn.close()
    return {"success": True, **recommendations}
