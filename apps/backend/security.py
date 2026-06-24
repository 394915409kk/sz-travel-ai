import hmac
import os

from fastapi import Header, HTTPException


PROTECTED_ENVS = {"staging", "production"}


def get_app_env():
    return (os.getenv("APP_ENV") or "development").strip().lower() or "development"


def get_internal_api_key():
    return (os.getenv("INTERNAL_API_KEY") or "").strip()


def is_internal_auth_required():
    app_env = get_app_env()
    configured_key = get_internal_api_key()
    return app_env in PROTECTED_ENVS or bool(configured_key)


def security_config_status():
    app_env = get_app_env()
    configured_key = get_internal_api_key()
    auth_required = is_internal_auth_required()
    key_configured = bool(configured_key)
    security_config_ok = key_configured if app_env in PROTECTED_ENVS else True
    recommendations = []

    if app_env in PROTECTED_ENVS and not key_configured:
        recommendations.append("staging/production 环境必须配置 INTERNAL_API_KEY。")
    if app_env == "development" and not key_configured:
        recommendations.append("development 可免鉴权；内测联调建议配置 INTERNAL_API_KEY。")

    return {
        "app_env": app_env,
        "auth_required": auth_required,
        "internal_api_key_configured": key_configured,
        "security_config_ok": security_config_ok,
        "recommendations": recommendations,
        "healthy": security_config_ok,
    }


def require_internal_api_key(
    x_internal_api_key: str | None = Header(
        default=None,
        alias="X-Internal-API-Key",
        description="Internal beta API key for protected write operations.",
    ),
):
    expected_key = get_internal_api_key()

    if not is_internal_auth_required():
        return None

    if not expected_key:
        raise HTTPException(status_code=403, detail="内部 API Key 未配置")

    if not x_internal_api_key:
        raise HTTPException(status_code=401, detail="缺少内部 API Key")

    if not hmac.compare_digest(x_internal_api_key, expected_key):
        raise HTTPException(status_code=403, detail="内部 API Key 无效")

    return None
