"""Quick E2E smoke for Issue #5 strategy tick.

Usage:
  python scripts/test_issue5_e2e.py

Prerequisites:
  - Postgres + Redis running
  - .env configured (DATABASE_URL, REDIS_URL)
  - alembic upgrade head
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select

from apps.worker.tasks import strategy_tick
from libs.db.models import Vault, VaultEvent
from libs.db.session import get_session_factory

TEST_VAULT = "0x0000000000000000000000000000000000000A55"
CHAIN_ID = 84532


def seed_data() -> None:
    session_factory = get_session_factory()

    with session_factory() as db:
        # cleanup old test records
        db.execute(delete(VaultEvent).where(VaultEvent.vault_address == TEST_VAULT))
        db.execute(delete(Vault).where(Vault.address == TEST_VAULT))

        vault = Vault(
            chain_id=CHAIN_ID,
            address=TEST_VAULT,
            created_block_number=1,
            created_tx_hash="0xseed",
            created_timestamp=datetime.now(timezone.utc),
        )
        db.add(vault)

        rule_event = VaultEvent(
            chain_id=CHAIN_ID,
            vault_address=TEST_VAULT,
            event_type="TokenRuleSet",
            block_number=100,
            tx_hash="0xrule",
            log_index=0,
            timestamp=datetime.now(timezone.utc),
            payload_json={
                "buy_threshold": 1900,
                "sell_threshold": 2300,
                "cooldown_seconds": 300,
                "last_executed_at": None,
            },
        )

        # price below buy threshold -> should trigger BUY
        price_event = VaultEvent(
            chain_id=CHAIN_ID,
            vault_address=TEST_VAULT,
            event_type="PriceObserved",
            block_number=101,
            tx_hash="0xprice",
            log_index=0,
            timestamp=datetime.now(timezone.utc),
            payload_json={"price": 1850},
        )

        db.add(rule_event)
        db.add(price_event)
        db.commit()


def assert_seed() -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        row = db.scalar(select(Vault).where(Vault.address == TEST_VAULT))
        if row is None:
            raise RuntimeError("Seed failed: test vault missing")


def main() -> None:
    print("[issue5] seeding test data...")
    seed_data()
    assert_seed()

    print("[issue5] first tick (expect triggered >= 1)")
    first = strategy_tick()
    print(first)
    if first["triggered"] < 1:
        raise RuntimeError(f"Expected first tick to trigger >=1, got: {first}")

    print("[issue5] second tick in same minute (expect triggered = 0 due to idempotency)")
    second = strategy_tick()
    print(second)
    if second["triggered"] != 0:
        raise RuntimeError(f"Expected second tick triggered=0, got: {second}")

    print("[issue5] ✅ PASS")


if __name__ == "__main__":
    main()
