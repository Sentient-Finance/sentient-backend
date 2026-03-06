"""Celery task definitions.

Import celery_app here (not the other way around) to avoid circular imports.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from redis import Redis
from sqlalchemy import and_, select

from apps.worker.celery_app import celery_app
from libs.core.config import get_settings
from libs.core.strategy import StrategyRule, evaluate_rule
from libs.db.models import Vault, VaultEvent
from libs.db.session import get_session_factory


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="worker.execution.enqueue")
def enqueue_execution(vault_address: str, action: str, reason: str) -> dict:
    """Placeholder execution enqueue task.

    In Issue #6 this should call the CRE execution service.
    """

    return {
        "vault": vault_address,
        "action": action,
        "reason": reason,
        "status": "queued",
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="worker.notify.telegram")
def notify_telegram(message: str) -> dict:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"status": "skipped", "reason": "telegram_not_configured"}

    base = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": settings.telegram_chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode()

    req = urllib.request.Request(base, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8", errors="ignore")
        return {"status": "sent", "response": body[:200]}
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}


def _latest_event(db, vault_address: str, event_type: str) -> VaultEvent | None:
    return db.scalar(
        select(VaultEvent)
        .where(VaultEvent.vault_address == vault_address, VaultEvent.event_type == event_type)
        .order_by(VaultEvent.block_number.desc(), VaultEvent.log_index.desc())
        .limit(1)
    )


@celery_app.task(name="worker.strategy.tick")
def strategy_tick() -> dict:
    """Periodic strategy scan.

    - Reads latest TokenRuleSet + PriceObserved per vault from DB
    - Evaluates threshold + cooldown
    - Enqueues execution task with Redis idempotency lock
    """

    session_factory = get_session_factory()
    redis_client = Redis.from_url(get_settings().redis_url)
    inspected = 0
    triggered = 0
    skipped = 0

    with session_factory() as db:
        vaults = db.scalars(select(Vault)).all()

        for vault in vaults:
            inspected += 1

            rule_event = _latest_event(db, vault.address, "TokenRuleSet")
            price_event = _latest_event(db, vault.address, "PriceObserved")

            if rule_event is None or price_event is None:
                skipped += 1
                continue

            try:
                rule_payload = rule_event.payload_json if isinstance(rule_event.payload_json, dict) else json.loads(rule_event.payload_json)
                price_payload = price_event.payload_json if isinstance(price_event.payload_json, dict) else json.loads(price_event.payload_json)
            except Exception:
                skipped += 1
                continue

            buy_threshold = rule_payload.get("buy_threshold")
            sell_threshold = rule_payload.get("sell_threshold")
            cooldown_seconds = int(rule_payload.get("cooldown_seconds", 300))
            last_executed_iso = rule_payload.get("last_executed_at")
            current_price = float(price_payload.get("price", 0))

            last_executed_at = None
            if last_executed_iso:
                try:
                    last_executed_at = datetime.fromisoformat(last_executed_iso.replace("Z", "+00:00"))
                except Exception:
                    last_executed_at = None

            decision = evaluate_rule(
                StrategyRule(
                    vault_address=vault.address,
                    buy_threshold=float(buy_threshold) if buy_threshold is not None else None,
                    sell_threshold=float(sell_threshold) if sell_threshold is not None else None,
                    cooldown_seconds=cooldown_seconds,
                    last_executed_at=last_executed_at,
                ),
                current_price=current_price,
            )

            if not decision.trigger or decision.action is None:
                skipped += 1
                continue

            minute_key = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
            idem_key = f"strategy:{vault.address}:{decision.action}:{minute_key}"
            lock = redis_client.set(idem_key, "1", ex=90, nx=True)

            if not lock:
                skipped += 1
                continue

            enqueue_execution.delay(vault.address, decision.action, decision.reason)
            triggered += 1

    return {
        "inspected": inspected,
        "triggered": triggered,
        "skipped": skipped,
        "at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="worker.risk_guard.tick")
def risk_guard_tick() -> dict:
    """Sends Telegram alert when price hits buy/sell threshold."""

    settings = get_settings()
    session_factory = get_session_factory()
    redis_client = Redis.from_url(settings.redis_url)

    inspected = 0
    alerts_sent = 0
    alerts_skipped = 0

    now = datetime.now(timezone.utc)

    with session_factory() as db:
        vaults = db.scalars(select(Vault)).all()

        for vault in vaults:
            inspected += 1

            rule_event = _latest_event(db, vault.address, "TokenRuleSet")
            price_event = _latest_event(db, vault.address, "PriceObserved")

            if rule_event is None or price_event is None:
                continue

            try:
                rule_payload = rule_event.payload_json if isinstance(rule_event.payload_json, dict) else json.loads(rule_event.payload_json)
                price_payload = price_event.payload_json if isinstance(price_event.payload_json, dict) else json.loads(price_event.payload_json)
                buy_threshold = rule_payload.get("buy_threshold")
                sell_threshold = rule_payload.get("sell_threshold")
                current_price = float(price_payload.get("price", 0))
            except Exception:
                continue

            if current_price <= 0:
                continue

            if buy_threshold is not None and current_price <= float(buy_threshold):
                key = f"risk_alert:{vault.address}:price_buy_threshold"
                if redis_client.set(key, "1", ex=settings.alert_dedupe_seconds, nx=True):
                    notify_telegram.delay(
                        f"📉 Price hit BUY threshold\nVault: {vault.address}\nPrice: {current_price}\nThreshold: {buy_threshold}"
                    )
                    alerts_sent += 1
                else:
                    alerts_skipped += 1
            elif sell_threshold is not None and current_price >= float(sell_threshold):
                key = f"risk_alert:{vault.address}:price_sell_threshold"
                if redis_client.set(key, "1", ex=settings.alert_dedupe_seconds, nx=True):
                    notify_telegram.delay(
                        f"📈 Price hit SELL threshold\nVault: {vault.address}\nPrice: {current_price}\nThreshold: {sell_threshold}"
                    )
                    alerts_sent += 1
                else:
                    alerts_skipped += 1

    return {
        "inspected": inspected,
        "alerts_sent": alerts_sent,
        "alerts_skipped": alerts_skipped,
        "at": now.isoformat(),
    }
