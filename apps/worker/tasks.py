"""Celery task definitions.

Import celery_app here (not the other way around) to avoid circular imports.
"""

from __future__ import annotations

import logging
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import httpx
from redis import Redis
from sqlalchemy import select
from web3 import Web3

from apps.worker.celery_app import celery_app
from libs.chain.executor import execute_vault_upkeep
from libs.chain.price_feed import get_chainlink_price
from libs.chain.vault_reader import read_vault_token_rule
from libs.core.config import get_settings
from libs.core.strategy import StrategyRule, evaluate_rule
from libs.db.models import ExecutionLog, Vault
from libs.db.session import get_session_factory

logging.getLogger("httpx").setLevel(logging.WARNING)

# WETH address on Base Sepolia
_WETH_BASE_SEPOLIA = "0x4200000000000000000000000000000000000006"
# Chainlink ETH/USD feed on Base Sepolia
_ETH_USD_FEED_BASE_SEPOLIA = "0x4aDC67696bA383F43DD60A9e78F2C97Fbbfc7cb1"

# Module-level singletons — created once per worker process, reused every tick
_w3: Web3 | None = None
_redis: Redis | None = None

logger = logging.getLogger(__name__)


def _get_w3() -> Web3 | None:
    global _w3
    if _w3 is not None:
        return _w3
    settings = get_settings()
    rpc = settings.base_rpc_url or settings.eth_rpc_url
    if not rpc:
        return None
    candidate = Web3(Web3.HTTPProvider(rpc))
    if not candidate.is_connected():
        return None
    _w3 = candidate
    return _w3


def _get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url)
    return _redis


# Shared helpers


def _build_price_cache(
    w3: Web3, feed_addrs: set[str], stale_seconds: int
) -> dict[str, float | None]:
    """Fetch Chainlink prices for a set of feed addresses (deduped).

    Stale prices (result.stale is True) are stored as None so callers that
    check ``if current_price is None`` will automatically skip stale feeds.
    """
    cache: dict[str, float | None] = {}
    for addr in feed_addrs:
        result = get_chainlink_price(w3, addr, stale_seconds=stale_seconds)
        cache[addr] = result.price_usd if (result and not result.stale) else None
    return cache


def _iter_active_rules(w3: Web3, vaults: list) -> list[tuple]:
    """Return (vault, rule) pairs where the rule is enabled with a threshold."""
    active = []
    for vault in vaults:
        rule = read_vault_token_rule(w3, vault.address, _WETH_BASE_SEPOLIA)
        if rule is None or not rule.enabled or rule.trade_amount == 0:
            continue
        if rule.buy_threshold_usd is None and rule.sell_threshold_usd is None:
            continue
        active.append((vault, rule))
    return active


# Helpers
def _persist_execution_log(
    vault_address: str,
    action: str,
    status: str,
    *,
    tx_hash: str | None = None,
    error: str | None = None,
    dry_run: bool = False,
    reason: str | None = None,
    executed_at: datetime,
) -> None:
    try:
        with get_session_factory()() as db:
            db.add(
                ExecutionLog(
                    vault_address=vault_address,
                    action=action,
                    status=status,
                    tx_hash=tx_hash,
                    dry_run=dry_run,
                    error=error[:500] if error else None,
                    trigger_reason=reason[:200] if reason else None,
                    executed_at=executed_at,
                )
            )
            db.commit()
    except Exception as exc:
        # Never let DB failure block the task result
        logging.getLogger(__name__).warning("Failed to persist ExecutionLog: %s", exc)


# Tasks
@celery_app.task(name="worker.execution.enqueue", bind=True, max_retries=2)
def enqueue_execution(self, vault_address: str, action: str, reason: str) -> dict:
    """Execute a vault swap on-chain via Chainlink AutomationCompatible interface.

    Calls checkUpkeep(b'') on the vault to obtain performData, then broadcasts
    performUpkeep(performData). Set EXECUTOR_DRY_RUN=false in .env for real txs.
    """
    settings = get_settings()
    w3 = _get_w3()

    now = datetime.now(timezone.utc)

    if not settings.executor_private_key or w3 is None:
        missing = []
        if not settings.executor_private_key:
            missing.append("EXECUTOR_PRIVATE_KEY")
        if w3 is None:
            missing.append("BASE_RPC_URL / ETH_RPC_URL")
        detail = f"executor not configured — missing: {', '.join(missing)}"
        _persist_execution_log(
            vault_address,
            action,
            "skipped",
            reason=reason,
            error=detail,
            executed_at=now,
        )
        return {
            "vault": vault_address,
            "action": action,
            "status": "skipped",
            "detail": detail,
            "at": now.isoformat(),
        }

    # Load Account here so the raw key never travels through function call chains
    account = w3.eth.account.from_key(settings.executor_private_key)
    result = execute_vault_upkeep(
        w3=w3,
        account=account,
        vault_address=vault_address,
        action=action,
        gas_limit=settings.executor_gas_limit,
        dry_run=settings.executor_dry_run,
    )

    executed_at = (
        datetime.fromisoformat(result.performed_at) if result.performed_at else now
    )

    if not result.upkeep_needed:
        _persist_execution_log(
            vault_address, action, "skipped", reason=reason, executed_at=executed_at
        )
        return {
            "vault": vault_address,
            "action": action,
            "status": "skipped",
            "detail": "checkUpkeep returned false — no swap needed",
            "at": result.performed_at,
        }

    if not result.success and not result.dry_run:
        _persist_execution_log(
            vault_address,
            action,
            "failed",
            tx_hash=result.tx_hash,
            error=result.error,
            dry_run=result.dry_run,
            reason=reason,
            executed_at=executed_at,
        )
        try:
            self.retry(countdown=30, exc=RuntimeError(result.error))
        except self.MaxRetriesExceededError:
            raise RuntimeError(f"max retries exceeded: {result.error}") from None

    status = "dry_run" if result.dry_run else ("ok" if result.success else "failed")
    _persist_execution_log(
        vault_address,
        action,
        status,
        tx_hash=result.tx_hash,
        error=result.error,
        dry_run=result.dry_run,
        reason=reason,
        executed_at=executed_at,
    )
    return {
        "vault": vault_address,
        "action": action,
        "status": status,
        "tx_hash": result.tx_hash,
        "dry_run": result.dry_run,
        "error": result.error,
        "at": result.performed_at,
    }


@celery_app.task(name="worker.notify.telegram")
def notify_telegram(message: str) -> dict:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"status": "skipped", "reason": "telegram_not_configured"}

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": settings.telegram_chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8", errors="ignore")
        return {"status": "sent", "response": body[:200]}
    except Exception as exc:
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(name="worker.strategy.tick")
def strategy_tick() -> dict:
    """Periodic strategy scan — evaluate rules and enqueue executions."""
    settings = get_settings()
    redis_client = _get_redis()

    tick_lock_key = "strategy:tick:running"
    if not redis_client.set(tick_lock_key, "1", ex=120, nx=True):
        return {
            "inspected": 0,
            "triggered": 0,
            "skipped": 0,
            "reason": "already_running",
            "at": datetime.now(timezone.utc).isoformat(),
        }

    inspected = triggered = skipped = 0

    try:
        w3 = _get_w3()
        if w3 is None:
            logger.error("strategy_tick RPC not configured or unreachable")
            return {
                "inspected": 0,
                "triggered": 0,
                "skipped": 0,
                "error": "RPC not configured or unreachable",
                "at": datetime.now(timezone.utc).isoformat(),
            }

        with get_session_factory()() as db:
            vaults = db.scalars(select(Vault)).all()
            active = _iter_active_rules(w3, list(vaults))
            inspected = len(vaults)
            skipped = inspected - len(active)

            # Fetch prices only for feeds actually in use
            feed_addrs = {r.price_feed or _ETH_USD_FEED_BASE_SEPOLIA for _, r in active}
            price_cache = _build_price_cache(
                w3, feed_addrs, settings.stale_price_seconds
            )

            for vault, rule in active:
                feed_addr = rule.price_feed or _ETH_USD_FEED_BASE_SEPOLIA
                current_price = price_cache.get(feed_addr)
                if current_price is None:
                    skipped += 1
                    continue

                last_executed_at = (
                    datetime.fromtimestamp(rule.last_executed_ts, tz=timezone.utc)
                    if rule.last_executed_ts > 0
                    else None
                )

                decision = evaluate_rule(
                    StrategyRule(
                        vault_address=vault.address,
                        buy_threshold=rule.buy_threshold_usd,
                        sell_threshold=rule.sell_threshold_usd,
                        cooldown_seconds=settings.execution_cooldown_seconds,
                        last_executed_at=last_executed_at,
                    ),
                    current_price=current_price,
                )

                if not decision.trigger or decision.action is None:
                    skipped += 1
                    continue

                idem_key = f"strategy:exec:{vault.address}:{decision.action}"
                if not redis_client.set(
                    idem_key, "1", ex=settings.execution_cooldown_seconds, nx=True
                ):
                    skipped += 1
                    continue

                enqueue_execution.delay(vault.address, decision.action, decision.reason)
                triggered += 1

    finally:
        redis_client.delete(tick_lock_key)

    logger.info(
        "strategy_tick done inspected=%d triggered=%d skipped=%d",
        inspected,
        triggered,
        skipped,
    )

    return {
        "inspected": inspected,
        "triggered": triggered,
        "skipped": skipped,
        "at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="worker.risk_guard.tick")
def risk_guard_tick() -> dict:
    """Sends Telegram alert when live Chainlink price hits a vault threshold."""
    settings = get_settings()
    redis_client = _get_redis()
    now = datetime.now(timezone.utc)

    w3 = _get_w3()
    if w3 is None:
        logger.error("risk_guard_tick RPC not configured or unreachable")
        return {
            "inspected": 0,
            "alerts_sent": 0,
            "alerts_skipped": 0,
            "error": "RPC not configured or unreachable",
            "at": now.isoformat(),
        }

    inspected = alerts_sent = alerts_skipped = 0

    with get_session_factory()() as db:
        vaults = db.scalars(select(Vault)).all()
        active = _iter_active_rules(w3, list(vaults))
        inspected = len(vaults)

        feed_addrs = {r.price_feed or _ETH_USD_FEED_BASE_SEPOLIA for _, r in active}
        price_cache = _build_price_cache(w3, feed_addrs, settings.stale_price_seconds)

        for vault, rule in active:
            feed_addr = rule.price_feed or _ETH_USD_FEED_BASE_SEPOLIA
            current_price = price_cache.get(feed_addr)
            if not current_price or current_price <= 0:
                continue

            if (
                rule.buy_threshold_usd is not None
                and current_price <= rule.buy_threshold_usd
            ):
                key = f"risk_alert:{vault.address}:buy"
                if redis_client.set(
                    key, "1", ex=settings.alert_dedupe_seconds, nx=True
                ):
                    notify_telegram.delay(
                        f"📉 BUY threshold hit\n"
                        f"Vault: {vault.address}\n"
                        f"Price: ${current_price:,.2f}\n"
                        f"Threshold: ${rule.buy_threshold_usd:,.2f}"
                    )
                    alerts_sent += 1
                else:
                    alerts_skipped += 1

            elif (
                rule.sell_threshold_usd is not None
                and current_price >= rule.sell_threshold_usd
            ):
                key = f"risk_alert:{vault.address}:sell"
                if redis_client.set(
                    key, "1", ex=settings.alert_dedupe_seconds, nx=True
                ):
                    notify_telegram.delay(
                        f"📈 SELL threshold hit\n"
                        f"Vault: {vault.address}\n"
                        f"Price: ${current_price:,.2f}\n"
                        f"Threshold: ${rule.sell_threshold_usd:,.2f}"
                    )
                    alerts_sent += 1
                else:
                    alerts_skipped += 1

    logger.info(
        "risk_guard_tick done inspected=%d alerts_sent=%d alerts_skipped=%d",
        inspected,
        alerts_sent,
        alerts_skipped,
    )

    return {
        "inspected": inspected,
        "alerts_sent": alerts_sent,
        "alerts_skipped": alerts_skipped,
        "at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Indexer task
# ---------------------------------------------------------------------------

from apps.indexer.main import sync_vault_events, sync_vaults  # noqa: E402


def _resolve_subgraph_url(settings) -> str:
    """Use Gateway URL (with API key in path) when possible; Studio often returns 403."""
    api_key = settings.subgraph_api_key
    subgraph_id = settings.subgraph_id
    if api_key and subgraph_id:
        return f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/{subgraph_id}"
    return settings.subgraph_url or ""


@celery_app.task(name="worker.indexer.tick", bind=True)
def indexer_tick(self) -> dict:
    """Periodic indexer sync — fetches vaults + vault_events from subgraph."""
    settings = get_settings()
    url = _resolve_subgraph_url(settings)

    if not url:
        logger.warning("indexer_tick skipped: SUBGRAPH_URL not configured")
        return {
            "synced_vaults": 0,
            "synced_events": 0,
            "error": "SUBGRAPH_URL not configured",
            "at": datetime.now(timezone.utc).isoformat(),
        }

    session_factory = get_session_factory()
    batch = settings.indexer_batch_size
    chain_id = settings.chain_base_sepolia_id
    api_key = None if "gateway.thegraph.com" in url else settings.subgraph_api_key

    synced_vaults = synced_events = 0
    error: str | None = None

    try:
        synced_vaults = sync_vaults(
            url,
            session_factory,
            chain_id=chain_id,
            batch=batch,
            api_key=api_key,
            verbose=False,
        )
        synced_events = sync_vault_events(
            url,
            session_factory,
            chain_id=chain_id,
            batch=batch,
            api_key=api_key,
            verbose=False,
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403 and settings.subgraph_url:
            # Fallback to Studio URL on Gateway 403
            url2 = settings.subgraph_url
            api_key2 = settings.subgraph_api_key
            synced_vaults = sync_vaults(
                url2,
                session_factory,
                chain_id=chain_id,
                batch=batch,
                api_key=api_key2,
                verbose=False,
            )
            synced_events = sync_vault_events(
                url2,
                session_factory,
                chain_id=chain_id,
                batch=batch,
                api_key=api_key2,
                verbose=False,
            )
        else:
            error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as exc:
        error = str(exc)[:200]

    if error:
        logger.error("indexer_tick error=%s", error)
    else:
        logger.info(
            "indexer_tick done synced_vaults=%d synced_events=%d",
            synced_vaults,
            synced_events,
        )

    return {
        "synced_vaults": synced_vaults,
        "synced_events": synced_events,
        "error": error,
        "at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="worker.notify.send")
def notify_send(recipient_id: str, channel_type: str, message: str) -> dict:
    """Gửi notification qua đúng channel."""
    settings = get_settings()
    if channel_type == "telegram":
        if not settings.telegram_bot_token:
            return {"status": "skipped", "reason": "telegram_bot_token_not_configured"}

        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": recipient_id, "text": message, "parse_mode": "HTML"}
        try:
            resp = httpx.post(url, json=payload, timeout=10)
            return resp.json()
        except Exception as exc:
            logging.getLogger(__name__).warning("Telegram send failed: %s", exc)
            return {"status": "error", "detail": str(exc)}
    return {"status": "unsupported_channel"}


def _fetch_vault_token_price(vault_address: str, chain_id: int) -> float | None:
    """Fetch current token price from Chainlink price feed for a vault's active token.

    Uses the same pattern as _iter_active_rules: reads the vault's token rule
    for WETH to get the price feed address, then fetches the USD price.
    """
    from libs.chain.price_feed import get_chainlink_price
    from libs.chain.vault_reader import read_vault_token_rule

    w3 = _get_w3()
    if w3 is None:
        return None

    try:
        # Use WETH as the base token (same as _iter_active_rules)
        rule = read_vault_token_rule(w3, vault_address, _WETH_BASE_SEPOLIA)
        if rule is None or not rule.price_feed:
            return None
        result = get_chainlink_price(
            w3, rule.price_feed, stale_seconds=get_settings().stale_price_seconds
        )
        if result and not result.stale:
            return result.price_usd
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Price fetch failed for %s: %s", vault_address, exc
        )
    return None


@celery_app.task(name="worker.alerts.check", bind=True, max_retries=2)
def check_price_alerts(self) -> dict:
    """Check all active price alerts and trigger notifications/actions."""
    from libs.db.models import PriceAlert

    settings = get_settings()
    redis_client = _get_redis()

    tick_lock_key = "alerts:check:running"
    if not redis_client.set(tick_lock_key, "1", ex=120, nx=True):
        return {
            "triggered": 0,
            "checked": 0,
            "errors": [],
            "reason": "already_running",
            "at": datetime.now(timezone.utc).isoformat(),
        }

    triggered_count = 0
    errors = []

    try:
        with get_session_factory()() as db:
            alerts = db.scalars(select(PriceAlert).where(PriceAlert.is_active)).all()

            # Build price cache keyed by (vault_address, chain_id) to avoid
            # redundant on-chain reads for the same vault across multiple alerts
            price_cache: dict[tuple[str, int], float | None] = {}
            for alert in alerts:
                key = (alert.vault_address, alert.chain_id)
                if key not in price_cache:
                    price_cache[key] = _fetch_vault_token_price(
                        alert.vault_address, alert.chain_id
                    )

            for alert in alerts:
                try:
                    price = price_cache.get((alert.vault_address, alert.chain_id))
                    if price is None:
                        continue

                    should_trigger = (
                        alert.alert_type == "below" and price <= alert.threshold_price
                    ) or (
                        alert.alert_type == "above" and price >= alert.threshold_price
                    )
                    if not should_trigger:
                        continue

                    # Idempotency: skip if already triggered while this task was running
                    idem_key = f"alert:triggered:{alert.id}"
                    if not redis_client.set(
                        idem_key, "1", ex=settings.execution_cooldown_seconds, nx=True
                    ):
                        continue

                    # Execute action
                    if alert.action_type == "none":
                        msg = (
                            f"🔔 <b>Price Alert!</b>\n"
                            f"Vault: <code>{alert.vault_address}</code>\n"
                            f"Type: {alert.alert_type.upper()} ${alert.threshold_price}\n"
                            f"Current: ${price}"
                        )
                        notify_send.delay(alert.recipient_id, alert.channel_type, msg)

                    elif alert.action_type == "fast_swap":
                        msg = (
                            f"🚀 <b>Fast Swap Alert!</b>\n"
                            f"Vault: <code>{alert.vault_address}</code>\n"
                            f"Type: {alert.alert_type.upper()} ${alert.threshold_price}\n"
                            f"Current: ${price}\n\n"
                            f"Swap triggered manually — tap to execute."
                        )
                        notify_send.delay(alert.recipient_id, alert.channel_type, msg)

                    elif alert.action_type == "auto_swap":
                        enqueue_execution.delay(
                            alert.vault_address, "buy", f"auto_swap_alert_{alert.id}"
                        )
                        msg = (
                            f"⚡ <b>Auto-swap Triggered!</b>\n"
                            f"Vault: <code>{alert.vault_address}</code>\n"
                            f"Price: ${price}\n"
                            f"Action: buy"
                        )
                        notify_send.delay(alert.recipient_id, alert.channel_type, msg)

                    # One-shot deactivate
                    alert.is_active = False
                    alert.triggered_at = datetime.now(timezone.utc)
                    triggered_count += 1

                except Exception as exc:
                    errors.append({"alert_id": alert.id, "error": str(exc)})
                    logging.getLogger(__name__).warning(
                        "Alert check failed for %s: %s", alert.id, exc
                    )

            db.commit()
    except Exception as exc:
        logging.getLogger(__name__).error("check_price_alerts failed: %s", exc)
        raise self.retry(countdown=30, exc=exc)
    finally:
        redis_client.delete(tick_lock_key)

    return {"triggered": triggered_count, "checked": len(alerts), "errors": errors}
