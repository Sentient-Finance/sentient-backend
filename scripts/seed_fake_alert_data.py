"""
Seed fake data to trigger Telegram alerts via risk_guard_tick.

Usage:
    python scripts/seed_fake_alert_data.py [--action buy|sell|both] [--clean]

Options:
    --action buy    : price < buy_threshold  → triggers BUY alert
    --action sell   : price > sell_threshold → triggers SELL alert
    --action both   : seed both (default: buy)
    --clean         : xóa dữ liệu fake trước khi seed mới
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from libs.db.models import Vault, VaultEvent
from libs.db.session import get_session_factory

FAKE_VAULT_ADDRESS = "0xDEADBEEFdeadbeefDEADBEEFdeadbeefDEADBEEF"
CHAIN_ID = 1

BUY_THRESHOLD = 2000.0   # alert khi price <= 2000
SELL_THRESHOLD = 3000.0  # alert khi price >= 3000

# Đặt price nằm trong vùng trigger
PRICE_FOR_BUY_ALERT = 1900.0    # < BUY_THRESHOLD → trigger BUY
PRICE_FOR_SELL_ALERT = 3100.0   # > SELL_THRESHOLD → trigger SELL


def _make_vault_event(event_type: str, payload: dict, block: int) -> VaultEvent:
    return VaultEvent(
        chain_id=CHAIN_ID,
        vault_address=FAKE_VAULT_ADDRESS,
        event_type=event_type,
        block_number=block,
        tx_hash=f"0xfake{event_type.lower()}{block:08x}",
        log_index=0,
        timestamp=datetime.now(timezone.utc),
        payload_json=payload,
    )


def seed(action: str = "buy", clean: bool = False) -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        if clean:
            db.query(VaultEvent).filter_by(vault_address=FAKE_VAULT_ADDRESS).delete()
            db.query(Vault).filter_by(address=FAKE_VAULT_ADDRESS).delete()
            db.commit()
            print("Cleaned existing fake data.")

        # Upsert Vault
        vault = db.query(Vault).filter_by(address=FAKE_VAULT_ADDRESS, chain_id=CHAIN_ID).first()
        if not vault:
            vault = Vault(
                chain_id=CHAIN_ID,
                address=FAKE_VAULT_ADDRESS,
                created_block_number=1000,
                created_tx_hash="0xfakevault",
                created_timestamp=datetime.now(timezone.utc),
            )
            db.add(vault)
            db.commit()
            print(f"Created vault: {FAKE_VAULT_ADDRESS}")
        else:
            print(f"Vault already exists: {FAKE_VAULT_ADDRESS}")

        # TokenRuleSet event
        rule_payload = {
            "buy_threshold": BUY_THRESHOLD,
            "sell_threshold": SELL_THRESHOLD,
            "cooldown_seconds": 300,
        }
        rule_event = _make_vault_event("TokenRuleSet", rule_payload, block=2000)
        db.add(rule_event)

        # PriceObserved event — chọn price theo action
        if action in ("buy", "both"):
            price_event = _make_vault_event(
                "PriceObserved",
                {"price": PRICE_FOR_BUY_ALERT},
                block=3000,
            )
            db.add(price_event)
            print(f"Seeded PriceObserved price={PRICE_FOR_BUY_ALERT} (< buy_threshold={BUY_THRESHOLD}) → will trigger BUY alert")

        if action == "sell":
            price_event = _make_vault_event(
                "PriceObserved",
                {"price": PRICE_FOR_SELL_ALERT},
                block=3000,
            )
            db.add(price_event)
            print(f"Seeded PriceObserved price={PRICE_FOR_SELL_ALERT} (>= sell_threshold={SELL_THRESHOLD}) → will trigger SELL alert")

        db.commit()
        print("\nDone! Now run:")
        print("  python -c \"from apps.worker.tasks import risk_guard_tick; print(risk_guard_tick())\"")
        print("\nNếu alert đã bị dedupe trong Redis, xóa key trước:")
        print(f"  redis-cli del risk_alert:{FAKE_VAULT_ADDRESS}:price_buy_threshold")
        print(f"  redis-cli del risk_alert:{FAKE_VAULT_ADDRESS}:price_sell_threshold")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=["buy", "sell", "both"], default="buy")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    seed(action=args.action, clean=args.clean)
