"""
Seed vault + vault_events từ subgraph data vào Postgres.
Lấy timestamp thật từ RPC (eth_getBlockByNumber).

Usage:
    python scripts/seed_vault_data.py [--clean]

Options:
    --clean   : xóa vault + events của chain_id trước khi seed
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import httpx

from libs.core.config import get_settings
from libs.db.models import Vault, VaultEvent
from libs.db.session import get_session_factory

# Base Sepolia public RPC (fallback khi chưa set BASE_RPC_URL)
BASE_SEPOLIA_RPC = "https://sepolia.base.org"

# Data từ subgraph (Base Sepolia)
VAULT_ADDRESS = "0x461f11e68a000f36198f80a7bed843c1f33442b9"
VAULT_CREATED_BLOCK = 38569286  # VaultInitialized block
VAULT_CREATED_TX = "0x9c0f12a8532140ef96e23b4b3d0ff0590743fcf3012e217c51fe7f42ccf0618c"

EVENTS = [
    (
        "0x7305a6f9c104a79231545fd8fcd68d40c394eb3738a6740efcf8547e02f06bc8",
        67,
        "TokenDeposited",
        38570295,
    ),
    (
        "0x9c0f12a8532140ef96e23b4b3d0ff0590743fcf3012e217c51fe7f42ccf0618c",
        151,
        "VaultInitialized",
        38569286,
    ),
    (
        "0xb0125ac2fbba86c41c3d910d829d9f04b11ff47270d666d39c1cb66f52438a94",
        173,
        "TokenDeposited",
        38570437,
    ),
    (
        "0xb700125e525e8621849deeaee9672eb1fec33d4f84937cfc5e0cd2e78b42ad50",
        47,
        "TokenRuleSet",
        38570571,
    ),
    (
        "0xc059a78b467d94c13d51bbdcb8bcf29cab547a7b6d2b29b1890e15fc9b4dea0e",
        112,
        "TokenDeposited",
        38570446,
    ),
]


def _get_rpc_url(settings) -> str:
    return settings.base_rpc_url or BASE_SEPOLIA_RPC


def fetch_block_timestamp(block_number: int, rpc_url: str) -> int:
    """Lấy timestamp thật của block từ RPC (Unix seconds)."""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBlockByNumber",
        "params": [hex(block_number), False],
        "id": 1,
    }
    resp = httpx.post(rpc_url, json=payload, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    block = data.get("result")
    if not block:
        raise RuntimeError(f"Block {block_number} not found")
    ts_hex = block.get("timestamp")
    if not ts_hex:
        raise RuntimeError(f"Block {block_number} has no timestamp")
    return int(ts_hex, 16)


def seed(clean: bool = False) -> None:
    settings = get_settings()
    chain_id = settings.chain_base_sepolia_id
    rpc_url = _get_rpc_url(settings)

    # Lấy timestamp thật từ RPC
    block_ts_cache: dict[int, int] = {}

    def get_ts(block_num: int) -> int:
        if block_num not in block_ts_cache:
            block_ts_cache[block_num] = fetch_block_timestamp(block_num, rpc_url)
        return block_ts_cache[block_num]

    print(f"Fetching block timestamps from {rpc_url}...")
    try:
        vault_created_ts = get_ts(VAULT_CREATED_BLOCK)
        print(
            f"  Block {VAULT_CREATED_BLOCK}: {datetime.fromtimestamp(vault_created_ts, tz=timezone.utc).isoformat()}"
        )
    except Exception as e:
        print(f"Error fetching block timestamps: {e}", file=sys.stderr)
        sys.exit(1)

    session_factory = get_session_factory()

    with session_factory() as db:
        if clean:
            db.query(VaultEvent).filter_by(chain_id=chain_id).delete()
            db.query(Vault).filter_by(chain_id=chain_id).delete()
            db.commit()
            print(f"Cleaned vaults + vault_events for chain_id={chain_id}")

        # Vault
        existing = (
            db.query(Vault).filter_by(address=VAULT_ADDRESS, chain_id=chain_id).first()
        )
        if not existing:
            db.add(
                Vault(
                    chain_id=chain_id,
                    address=VAULT_ADDRESS.lower(),
                    created_block_number=VAULT_CREATED_BLOCK,
                    created_tx_hash=VAULT_CREATED_TX.lower(),
                    created_timestamp=datetime.fromtimestamp(
                        vault_created_ts, tz=timezone.utc
                    ),
                )
            )
            db.commit()
            print(f"Inserted vault: {VAULT_ADDRESS}")
        else:
            print(f"Vault already exists: {VAULT_ADDRESS}")

        # VaultEvents — lấy timestamp thật từ RPC mỗi block
        inserted = 0
        for tx_hash, log_idx, event_type, block_num in EVENTS:
            exists = (
                db.query(VaultEvent)
                .filter_by(
                    chain_id=chain_id, tx_hash=tx_hash.lower(), log_index=log_idx
                )
                .first()
            )
            if not exists:
                event_ts = get_ts(block_num)
                db.add(
                    VaultEvent(
                        chain_id=chain_id,
                        vault_address=VAULT_ADDRESS.lower(),
                        event_type=event_type,
                        block_number=block_num,
                        tx_hash=tx_hash.lower(),
                        log_index=log_idx,
                        timestamp=datetime.fromtimestamp(event_ts, tz=timezone.utc),
                        payload_json={},
                    )
                )
                inserted += 1
        db.commit()
        print(f"Inserted {inserted} vault_events (total {len(EVENTS)} in seed)")
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    seed(clean=args.clean)
