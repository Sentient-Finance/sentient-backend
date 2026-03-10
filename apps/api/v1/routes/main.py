from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from apps.api.v1.routes.ccip import router as ccip_router
from apps.api.v1.routes.vaults import router as vaults_router
from libs.db.session import get_db

router = APIRouter()


@router.get("/ready", tags=["meta"])
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"ok": True, "service": "api", "ready": True}

router.include_router(vaults_router)
router.include_router(ccip_router)

