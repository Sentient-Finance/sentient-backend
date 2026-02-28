from fastapi import APIRouter, Depends, Request

from apps.api.v1.routes.vaults import router as vault_router
from libs.core.config import Settings

router = APIRouter(tags=["meta"])


def get_settings_from_request(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/health")
def health(settings: Settings = Depends(get_settings_from_request)):
    return {"ok": True, "service": "api", "env": settings.app_env}


@router.get("/ready")
def ready(settings: Settings = Depends(get_settings_from_request)):
    return {"ok": True, "service": "api", "ready": True}


router.include_router(vault_router)

