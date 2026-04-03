"""Price alert and notification channel management."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from libs.db.models import PriceAlert, UserNotificationChannel
from libs.db.session import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


# === Request/Response Models ===


class ChannelRegisterRequest(BaseModel):
    user_wallet: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    channel_type: Literal["telegram"] = "telegram"
    channel_id: str = Field(..., min_length=1)


class ChannelResponse(BaseModel):
    id: int
    user_wallet: str
    channel_type: str
    channel_id: str
    is_active: bool
    created_at: datetime


class PriceAlertCreateRequest(BaseModel):
    recipient_id: str = Field(..., min_length=1)
    channel_type: Literal["telegram"] = "telegram"
    vault_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    chain_id: int = Field(default=84532)
    alert_type: Literal["above", "below"]
    threshold_price: float = Field(..., gt=0)
    action_type: Literal["none", "fast_swap", "auto_swap"] = "none"
    action_config: dict | None = None


class PriceAlertResponse(BaseModel):
    id: int
    recipient_id: str
    channel_type: str
    vault_address: str
    chain_id: int
    alert_type: str
    threshold_price: float
    action_type: str
    action_config: dict | None
    is_active: bool
    triggered_at: datetime | None
    created_at: datetime


# === Channel Routes ===


@router.post("/channels", response_model=ChannelResponse)
def register_channel(body: ChannelRegisterRequest, db: Session = Depends(get_db)):
    """Register a notification channel for a user wallet."""
    # Check if channel already exists for this user+type
    existing = db.scalar(
        select(UserNotificationChannel).where(
            and_(
                UserNotificationChannel.user_wallet == body.user_wallet.lower(),
                UserNotificationChannel.channel_type == body.channel_type,
            )
        )
    )
    if existing:
        existing.channel_id = body.channel_id
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    channel = UserNotificationChannel(
        user_wallet=body.user_wallet.lower(),
        channel_type=body.channel_type,
        channel_id=body.channel_id,
    )
    db.add(channel)
    db.flush()
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/channels", response_model=list[ChannelResponse])
def list_channels(
    user_wallet: str | None = Query(default=None),
    telegram_chat_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """List notification channels."""
    stmt = select(UserNotificationChannel)
    if user_wallet:
        stmt = stmt.where(UserNotificationChannel.user_wallet == user_wallet.lower())
    if telegram_chat_id:
        stmt = stmt.where(
            and_(
                UserNotificationChannel.channel_type == "telegram",
                UserNotificationChannel.channel_id == telegram_chat_id,
            )
        )
    rows = db.scalars(stmt).all()
    return list(rows)


@router.delete("/channels/{channel_id}")
def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    """Delete a notification channel."""
    channel = db.get(UserNotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    db.delete(channel)
    db.commit()
    return {"status": "deleted"}


# === Alert Routes ===


@router.post("", response_model=PriceAlertResponse)
def create_alert(body: PriceAlertCreateRequest, db: Session = Depends(get_db)):
    """Create a new price alert."""
    alert = PriceAlert(
        recipient_id=body.recipient_id,
        channel_type=body.channel_type,
        vault_address=body.vault_address.lower(),
        chain_id=body.chain_id,
        alert_type=body.alert_type,
        threshold_price=body.threshold_price,
        action_type=body.action_type,
        action_config=body.action_config,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("", response_model=list[PriceAlertResponse])
def list_alerts(
    recipient_id: str | None = Query(default=None),
    vault_address: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """List price alerts with optional filters."""
    stmt = select(PriceAlert)
    if recipient_id:
        stmt = stmt.where(PriceAlert.recipient_id == recipient_id)
    if vault_address:
        stmt = stmt.where(PriceAlert.vault_address == vault_address.lower())
    if is_active is not None:
        stmt = stmt.where(PriceAlert.is_active == is_active)
    rows = db.scalars(stmt.order_by(PriceAlert.id.desc())).all()
    return list(rows)


@router.delete("/{alert_id}")
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    """Delete a price alert."""
    alert = db.get(PriceAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(alert)
    db.commit()
    return {"status": "deleted"}


@router.patch("/{alert_id}", response_model=PriceAlertResponse)
def update_alert(
    alert_id: int,
    body: PriceAlertCreateRequest,
    db: Session = Depends(get_db),
):
    """Update a price alert (recreates it)."""
    alert = db.get(PriceAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.recipient_id = body.recipient_id
    alert.channel_type = body.channel_type
    alert.vault_address = body.vault_address.lower()
    alert.chain_id = body.chain_id
    alert.alert_type = body.alert_type
    alert.threshold_price = body.threshold_price
    alert.action_type = body.action_type
    alert.action_config = body.action_config
    db.commit()
    db.refresh(alert)
    return alert
