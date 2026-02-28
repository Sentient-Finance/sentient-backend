from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from web3 import Web3

from libs.db.models import ChainEvent, IndexerCheckpoint
from libs.db.session import SessionLocal, init_db


EVENT_SIGNATURES = {
    "VaultInitialized(address,address)": "VaultInitialized",
    "TokenRuleSet(address,bool,uint256,uint256,uint256)": "TokenRuleSet",
    "SwapExecuted(address,address,uint256,uint256,uint256)": "SwapExecuted",
    "CrossChainShieldTriggered(uint64,address,uint256)": "CrossChainShieldTriggered",
}


@dataclass
class IndexerConfig:
    rpc_url: str
    chain_id: int
    contract_addresses: list[str]
    start_block: int
    confirmations: int
    poll_interval_sec: int


TOPIC_TO_EVENT = {
    Web3.keccak(text=sig).hex(): name
    for sig, name in EVENT_SIGNATURES.items()
}


def load_config() -> IndexerConfig:
    rpc_url = os.getenv("INDEXER_RPC_URL", os.getenv("BASE_RPC_URL", ""))
    if not rpc_url:
        raise RuntimeError("Missing INDEXER_RPC_URL (or BASE_RPC_URL)")

    contracts = [x.strip().lower() for x in os.getenv("INDEXER_CONTRACTS", "").split(",") if x.strip()]
    if not contracts:
        raise RuntimeError("Missing INDEXER_CONTRACTS (comma-separated contract addresses)")

    return IndexerConfig(
        rpc_url=rpc_url,
        chain_id=int(os.getenv("INDEXER_CHAIN_ID", "84532")),
        contract_addresses=contracts,
        start_block=int(os.getenv("INDEXER_START_BLOCK", "0")),
        confirmations=int(os.getenv("INDEXER_CONFIRMATIONS", "2")),
        poll_interval_sec=int(os.getenv("INDEXER_POLL_INTERVAL_SEC", "12")),
    )


def get_checkpoint(chain_id: int, stream_key: str, default_block: int) -> int:
    with SessionLocal() as db:
        row = db.scalar(
            select(IndexerCheckpoint).where(
                IndexerCheckpoint.chain_id == chain_id,
                IndexerCheckpoint.stream_key == stream_key,
            )
        )
        return row.last_block if row else default_block


def set_checkpoint(chain_id: int, stream_key: str, block: int) -> None:
    with SessionLocal() as db:
        row = db.scalar(
            select(IndexerCheckpoint).where(
                IndexerCheckpoint.chain_id == chain_id,
                IndexerCheckpoint.stream_key == stream_key,
            )
        )
        if row is None:
            row = IndexerCheckpoint(chain_id=chain_id, stream_key=stream_key, last_block=block)
            db.add(row)
        else:
            row.last_block = block
        db.commit()


def normalize_address(value: str) -> str:
    return Web3.to_checksum_address(value)


def decode_event_name(topics: list[str]) -> str:
    if not topics:
        return "Unknown"
    return TOPIC_TO_EVENT.get(topics[0].lower(), "Unknown")


def persist_logs(chain_id: int, logs: Iterable[dict]) -> int:
    inserted = 0
    with SessionLocal() as db:
        for log in logs:
            tx_hash = log["transactionHash"].hex() if hasattr(log["transactionHash"], "hex") else str(log["transactionHash"])
            topic_hex = [t.hex() if hasattr(t, "hex") else str(t) for t in log.get("topics", [])]
            event_name = decode_event_name(topic_hex)

            row = ChainEvent(
                chain_id=chain_id,
                contract_address=normalize_address(log["address"]),
                event_name=event_name,
                block_number=int(log["blockNumber"]),
                tx_hash=tx_hash,
                log_index=int(log["logIndex"]),
                payload_json=json.dumps(
                    {
                        "topics": topic_hex,
                        "data": log.get("data", "0x"),
                        "removed": bool(log.get("removed", False)),
                    }
                ),
            )
            db.add(row)
            try:
                db.flush()
                inserted += 1
            except Exception:
                db.rollback()
        db.commit()
    return inserted


def run_once(cfg: IndexerConfig) -> tuple[int, int, int]:
    w3 = Web3(Web3.HTTPProvider(cfg.rpc_url))
    latest = w3.eth.block_number
    to_block = latest - cfg.confirmations
    if to_block < 0:
        return (latest, 0, 0)

    stream_key = "contracts:" + ",".join(sorted(cfg.contract_addresses))
    from_block = get_checkpoint(cfg.chain_id, stream_key, cfg.start_block)

    if from_block > to_block:
        return (latest, from_block, 0)

    logs = w3.eth.get_logs(
        {
            "fromBlock": from_block,
            "toBlock": to_block,
            "address": [normalize_address(a) for a in cfg.contract_addresses],
        }
    )

    inserted = persist_logs(cfg.chain_id, logs)
    set_checkpoint(cfg.chain_id, stream_key, to_block + 1)
    return (latest, to_block, inserted)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sentient backend event indexer")
    parser.add_argument("--once", action="store_true", help="Run one indexing pass and exit")
    args = parser.parse_args()

    init_db()
    cfg = load_config()

    if args.once:
        latest, processed_to, inserted = run_once(cfg)
        print(f"indexer once: latest={latest} processed_to={processed_to} inserted={inserted}")
        return

    while True:
        latest, processed_to, inserted = run_once(cfg)
        print(f"indexer loop: latest={latest} processed_to={processed_to} inserted={inserted}")
        time.sleep(cfg.poll_interval_sec)


if __name__ == "__main__":
    main()
