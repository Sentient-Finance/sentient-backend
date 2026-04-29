"""
Alert notification management.

Channel management:
  POST /alerts/channels  — register / initiate a notification channel
  GET  /alerts/channels  — list channels for a wallet

History management:
  GET  /alerts/history   — list notification history for a wallet
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from apps.api.limiter import limiter
from apps.worker.tasks import telegram_send_to_channel
from libs.core.config import get_settings
from libs.db.models import NotificationLog, UserNotificationChannel
from libs.db.session import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])

settings = get_settings()

# How long a connect token is valid (10 minutes)
_CONNECT_TOKEN_TTL_MINUTES = 10


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChannelCreateRequest(BaseModel):
    user_wallet: str = Field(..., description="User's wallet address (0x...)")
    channel_type: str = Field(
        ...,
        description="Channel type: 'telegram', 'email', 'discord'",
    )
    channel_id: str | None = Field(
        default=None,
        description="For non-telegram channels, the channel identifier directly",
    )


class ChannelCreateResponse(BaseModel):
    channel_id: int  # internal DB id
    channel_type: str
    status: str
    deep_link: str | None = Field(
        default=None,
        description="Telegram deep link to complete registration (only for telegram type)",
    )
    expires_at: datetime | None = None


class ChannelConfirmRequest(BaseModel):
    connect_token: str = Field(..., description="The connect token from /start command")
    chat_id: str = Field(..., description="Telegram chat_id to associate")


class ChannelConfirmResponse(BaseModel):
    ok: bool
    channel_id: int
    status: str


class ChannelItem(BaseModel):
    id: int
    user_wallet: str
    channel_type: str
    channel_id: str | None
    status: str
    created_at: datetime


class ChannelListResponse(BaseModel):
    items: list[ChannelItem]


class NotificationLogItem(BaseModel):
    id: int
    user_wallet: str
    channel_type: str
    channel_id: str | None
    message: str
    status: str
    error: str | None
    sent_at: datetime


class NotificationHistoryResponse(BaseModel):
    items: list[NotificationLogItem]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_connect_token() -> str:
    return secrets.token_urlsafe(32)


def _get_bot_username() -> str:
    """Resolve the bot username from TELEGRAM_BOT_USERNAME env or fall back to placeholder."""
    username = getattr(settings, "telegram_bot_username", None)
    if not username:
        # Default placeholder — set TELEGRAM_BOT_USERNAME in production
        username = "SentientFinanceBot"
    return username


# ---------------------------------------------------------------------------
# Channel Routes
# ---------------------------------------------------------------------------


@router.post(
    "/channels",
    response_model=ChannelCreateResponse,
    responses={
        422: {"description": "Validation error"},
    },
)
@limiter.limit(settings.rate_limit_public)
def create_channel(
    payload: ChannelCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new notification channel.

    For Telegram: creates a pending channel with a short-lived connect token,
    and returns a deep link to open the Telegram bot.
    """
    wallet = payload.user_wallet.strip().lower()
    if not wallet.startswith("0x") or len(wallet) != 42:
        raise HTTPException(status_code=422, detail="Invalid wallet address")

    channel_type = payload.channel_type.strip().lower()

    if channel_type not in ("telegram", "email", "discord"):
        raise HTTPException(
            status_code=422,
            detail="channel_type must be one of: telegram, email, discord",
        )

    # For Telegram we always use the token flow (no direct chat_id)
    if channel_type == "telegram":
        if payload.channel_id:
            raise HTTPException(
                status_code=422,
                detail="Telegram channels use the connect-token flow; do not send channel_id",
            )
        connect_token = _generate_connect_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=_CONNECT_TOKEN_TTL_MINUTES
        )
        channel = UserNotificationChannel(
            user_wallet=wallet,
            channel_type=channel_type,
            channel_id=None,
            connect_token=connect_token,
            token_expires_at=expires_at,
            status="pending",
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)

        bot_username = _get_bot_username()
        deep_link = f"https://t.me/{bot_username}?start={connect_token}"

        return ChannelCreateResponse(
            channel_id=channel.id,
            channel_type=channel_type,
            status=channel.status,
            deep_link=deep_link,
            expires_at=expires_at,
        )

    # Non-Telegram channels: use channel_id directly
    if not payload.channel_id:
        raise HTTPException(
            status_code=422,
            detail=f"channel_id is required for {channel_type} channels",
        )

    # Check for duplicate
    existing = db.scalar(
        select(UserNotificationChannel).where(
            and_(
                UserNotificationChannel.user_wallet == wallet,
                UserNotificationChannel.channel_type == channel_type,
                UserNotificationChannel.channel_id == payload.channel_id,
            )
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="This channel is already registered for this wallet",
        )

    channel = UserNotificationChannel(
        user_wallet=wallet,
        channel_type=channel_type,
        channel_id=payload.channel_id,
        status="active",
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    return ChannelCreateResponse(
        channel_id=channel.id,
        channel_type=channel_type,
        status=channel.status,
        deep_link=None,
        expires_at=None,
    )


@router.post(
    "/channels/confirm",
    response_model=ChannelConfirmResponse,
    responses={
        404: {"description": "Token not found or expired"},
    },
)
@limiter.limit(settings.rate_limit_public)
def confirm_channel(
    payload: ChannelConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Confirm a Telegram channel registration using the connect token.

    Called by the Telegram bot when the user clicks /start <token>.
    """
    channel = db.scalar(
        select(UserNotificationChannel).where(
            UserNotificationChannel.connect_token == payload.connect_token
        )
    )

    if not channel:
        raise HTTPException(status_code=404, detail="Token not found")

    if channel.channel_type != "telegram":
        raise HTTPException(
            status_code=422,
            detail="This endpoint is only for Telegram channel confirmation",
        )

    now = datetime.now(timezone.utc)
    if channel.token_expires_at and channel.token_expires_at < now:
        raise HTTPException(status_code=410, detail="Token has expired")

    # Idempotent — if already active, clear token and return ok
    if channel.status == "active":
        channel.connect_token = None
        channel.token_expires_at = None
        db.commit()
        return ChannelConfirmResponse(
            ok=True,
            channel_id=channel.id,
            status=channel.status,
        )

    # Activate the channel
    channel.connect_token = None
    channel.token_expires_at = None
    channel.channel_id = payload.chat_id
    channel.status = "active"
    db.commit()

    return ChannelConfirmResponse(
        ok=True,
        channel_id=channel.id,
        status="active",
    )


@router.get(
    "/channels",
    response_model=ChannelListResponse,
)
def list_channels(
    user_wallet: Annotated[
        str, Query(description="Wallet address to look up channels for")
    ],
    db: Session = Depends(get_db),
):
    """List all notification channels registered for a wallet."""
    wallet = user_wallet.strip().lower()
    rows = db.scalars(
        select(UserNotificationChannel)
        .where(UserNotificationChannel.user_wallet == wallet)
        .order_by(UserNotificationChannel.created_at.desc())
    ).all()

    return ChannelListResponse(
        items=[
            ChannelItem(
                id=row.id,
                user_wallet=row.user_wallet,
                channel_type=row.channel_type,
                channel_id=row.channel_id,
                status=row.status,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


@router.delete(
    "/channels/{channel_id:int}",
    responses={
        204: {"description": "Channel deleted"},
        404: {"description": "Channel not found"},
    },
)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
):
    """Delete a notification channel."""
    channel = db.get(UserNotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    db.delete(channel)
    db.commit()
    return None


@router.post(
    "/channels/{channel_id:int}/test",
    responses={
        202: {"description": "Test notification dispatched"},
        403: {"description": "Channel does not belong to the specified wallet"},
        404: {"description": "Channel not found"},
    },
)
def test_channel_notification(
    channel_id: int,
    user_wallet: Annotated[
        str, Query(description="Wallet address to verify ownership")
    ],
    db: Session = Depends(get_db),
):
    """Dispatch a test Telegram notification for a specific channel."""
    channel = db.get(UserNotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if channel.user_wallet.strip().lower() != user_wallet.strip().lower():
        raise HTTPException(
            status_code=403, detail="Channel does not belong to this wallet"
        )

    if channel.channel_type != "telegram" or not channel.channel_id:
        raise HTTPException(
            status_code=422,
            detail="Test notifications are only supported for confirmed Telegram channels",
        )

    # Dispatch celery task
    message = (
        "🧪 <b>Sentient Finance Test</b>\n\n"
        "Your notification channel is working correctly!\n"
        f"Wallet: <code>{channel.user_wallet}</code>\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    telegram_send_to_channel.delay(channel_id, message)

    return {"status": "ok", "detail": "Test notification dispatched"}


@router.get(
    "/channels/by-chat_id",
    response_model=ChannelItem,
    responses={
        404: {"description": "Channel not found"},
    },
)
def get_channel_by_chat_id(
    chat_id: Annotated[str, Query(description="Telegram chat_id to look up")],
    db: Session = Depends(get_db),
):
    """Look up a notification channel by Telegram chat_id."""
    channel = db.scalar(
        select(UserNotificationChannel).where(
            and_(
                UserNotificationChannel.channel_type == "telegram",
                UserNotificationChannel.channel_id == chat_id,
                UserNotificationChannel.status == "active",
            )
        )
    )
    if not channel:
        raise HTTPException(
            status_code=404, detail="No active Telegram channel found for this chat"
        )
    return ChannelItem(
        id=channel.id,
        user_wallet=channel.user_wallet,
        channel_type=channel.channel_type,
        channel_id=channel.channel_id,
        status=channel.status,
        created_at=channel.created_at,
    )


# ---------------------------------------------------------------------------
# History Routes
# ---------------------------------------------------------------------------


@router.get(
    "/history",
    response_model=NotificationHistoryResponse,
)
def list_notification_history(
    user_wallet: Annotated[str, Query(description="Wallet address")],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List notification history for a wallet (from DB)."""
    wallet = user_wallet.strip().lower()

    # Total count
    total = (
        db.scalar(
            select(func.count(NotificationLog.id)).where(
                NotificationLog.user_wallet == wallet
            )
        )
        or 0
    )

    # Page items
    rows = db.scalars(
        select(NotificationLog)
        .where(NotificationLog.user_wallet == wallet)
        .order_by(desc(NotificationLog.sent_at))
        .limit(limit)
        .offset(offset)
    ).all()

    return NotificationHistoryResponse(
        total=total,
        items=[
            NotificationLogItem(
                id=row.id,
                user_wallet=row.user_wallet,
                channel_type=row.channel_type,
                channel_id=row.channel_id,
                message=row.message,
                status=row.status,
                error=row.error,
                sent_at=row.sent_at,
            )
            for row in rows
        ],
    )
