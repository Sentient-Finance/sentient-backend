"""Celery task definitions.

Import celery_app here (not the other way around) to avoid circular imports.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from redis import Redis
from sqlalchemy import select

from apps.worker.celery_app import celery_app
from libs.core.config import get_settings
from libs.core.cre_client import submit_swap_via_cre
from libs.core.strategy import StrategyRule, evaluate_rule
from libs.db.models import ExecutionRequest, Vault, VaultEvent
from libs.db.session import get_session_factory


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"


def _latest_event(db, vault_address: str, event_type: str) -> VaultEvent | None:
    return db.scalar(
        select(VaultEvent)
        .where(VaultEvent.vault_address == vault_address, VaultEvent.event_type == event_type)
        .order_by(VaultEvent.block_number.desc(), VaultEvent.log_index.desc())
        .limit(1)
    )


@celery_app.task(name="worker.execution.enqueue")
def enqueue_execution(
    vault_address: str,
    action: str,
    reason: str | None,
    chain_id: int = 84532,
    metadata: dict | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Persist execution request row in queued state.

    Actual CRE submit happens in `worker.execution.process` / `worker.execution.drain`.
    """

    session_factory = get_session_factory()
    idem = idempotency_key or f"queue:{chain_id}:{vault_address}:{action}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    with session_factory() as db:
        existing = db.scalar(
            select(ExecutionRequest).where(ExecutionRequest.idempotency_key == idem).limit(1)
        )
        if existing is not None:
            return {
                "execution_id": existing.id,
                "status": existing.status,
                "vault": existing.vault_address,
                "action": existing.action,
                "reason": "duplicate_idempotency_key",
            }

        row = ExecutionRequest(
            chain_id=chain_id,
            vault_address=vault_address,
            action=action,
            reason=reason,
            status="queued",
            idempotency_key=idem,
            metadata_json=metadata or {},
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    return {
        "execution_id": row.id,
        "status": row.status,
        "vault": row.vault_address,
        "action": row.action,
        "queued_at": row.created_at.isoformat() if row.created_at else None,
    }


@celery_app.task(name="worker.execution.process")
def process_execution(execution_id: int) -> dict:
    """Submit one queued execution request to CRE and update lifecycle.

    status transitions:
    queued -> submitted -> confirmed | failed
    """

    session_factory = get_session_factory()

    with session_factory() as db:
        row = db.scalar(
            select(ExecutionRequest).where(ExecutionRequest.id == execution_id).limit(1)
        )
        if row is None:
            return {"execution_id": execution_id, "status": "missing"}

        if row.status not in {"queued", "submitted"}:
            return {
                "execution_id": row.id,
                "status": row.status,
                "reason": "not_processable",
            }

        # lock this row to avoid duplicate processing by concurrent workers
        row.status = "submitted"
        db.commit()
        db.refresh(row)

        result = submit_swap_via_cre(
            vault_address=row.vault_address,
            chain_id=row.chain_id,
            action=row.action,
            reason=row.reason,
            metadata=row.metadata_json or {},
        )

        if result.ok:
            row.status = "confirmed"
            row.tx_hash = result.tx_hash
            row.error_message = None
        else:
            row.status = "failed"
            row.error_message = result.error or "cre_submit_failed"

        db.commit()
        db.refresh(row)

        return {
            "execution_id": row.id,
            "status": row.status,
            "tx_hash": row.tx_hash,
            "error": row.error_message,
        }


@celery_app.task(name="worker.execution.drain")
def drain_execution_queue(limit: int = 20) -> dict:
    """Pick queued execution requests and submit them to CRE."""

    session_factory = get_session_factory()
    processed = 0
    confirmed = 0
    failed = 0

    with session_factory() as db:
        queued_ids = [
            x
            for x in db.scalars(
                select(ExecutionRequest.id)
                .where(ExecutionRequest.status == "queued")
                .order_by(ExecutionRequest.created_at.asc())
                .limit(limit)
            ).all()
        ]

    for execution_id in queued_ids:
        processed += 1
        result = process_execution(execution_id)
        status = result.get("status")
        if status == "confirmed":
            confirmed += 1
        elif status == "failed":
            failed += 1

    return {
        "processed": processed,
        "confirmed": confirmed,
        "failed": failed,
        "at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="worker.strategy.tick")
def strategy_tick() -> dict:
    """Periodic strategy scan.

    - Reads latest TokenRuleSet + PriceObserved per vault from DB
    - Evaluates threshold + cooldown
    - Enqueues execution request with Redis idempotency lock
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
                rule_payload = (
                    rule_event.payload_json
                    if isinstance(rule_event.payload_json, dict)
                    else json.loads(rule_event.payload_json)
                )
                price_payload = (
                    price_event.payload_json
                    if isinstance(price_event.payload_json, dict)
                    else json.loads(price_event.payload_json)
                )
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
                    last_executed_at = datetime.fromisoformat(
                        last_executed_iso.replace("Z", "+00:00")
                    )
                except Exception:
                    last_executed_at = None

            decision = evaluate_rule(
                StrategyRule(
                    vault_address=vault.address,
                    buy_threshold=float(buy_threshold)
                    if buy_threshold is not None
                    else None,
                    sell_threshold=float(sell_threshold)
                    if sell_threshold is not None
                    else None,
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

            enqueue_execution.delay(
                vault_address=vault.address,
                action=decision.action,
                reason=decision.reason,
                chain_id=vault.chain_id,
                metadata={"source": "strategy_tick", "price": current_price},
                idempotency_key=idem_key,
            )
            triggered += 1

    return {
        "inspected": inspected,
        "triggered": triggered,
        "skipped": skipped,
        "at": datetime.now(timezone.utc).isoformat(),
    }
