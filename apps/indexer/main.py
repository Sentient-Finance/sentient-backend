from __future__ import annotations

import argparse
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from web3 import Web3

from libs.core.config import get_settings
from libs.db.models import ChainEvent, IndexerCheckpoint
from libs.db.session import get_session_factory, init_db

logger = logging.getLogger(__name__)

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
    batch_size: int


TOPIC_TO_EVENT = {Web3.keccak(text=sig).hex(): name for sig, name in EVENT_SIGNATURES.items()}


def load_config() -> IndexerConfig:
    settings = get_settings()

    rpc_url = settings.indexer_rpc_url or settings.base_rpc_url or ""
    if not rpc_url:
        raise RuntimeError("Missing INDEXER_RPC_URL (or BASE_RPC_URL)")

    contracts = [x.strip().lower() for x in settings.indexer_contracts.split(",") if x.strip()]
    if not contracts:
        raise RuntimeError("Missing INDEXER_CONTRACTS (comma-separated contract addresses)")

    return IndexerConfig(
        rpc_url=rpc_url,
        chain_id=settings.indexer_chain_id,
        contract_addresses=contracts,
        start_block=settings.indexer_start_block or 0,
        confirmations=settings.indexer_confirmations,
        poll_interval_sec=settings.indexer_poll_interval_seconds,
        batch_size=settings.indexer_batch_size,
    )


def get_checkpoint(chain_id: int, stream_key: str, default_block: int) -> int:
    with get_session_factory()() as db:
        row = db.scalar(
            select(IndexerCheckpoint).where(
                IndexerCheckpoint.chain_id == chain_id,
                IndexerCheckpoint.stream_key == stream_key,
            )
        )
        return row.last_block if row else default_block


def set_checkpoint(chain_id: int, stream_key: str, block: int) -> None:
    with get_session_factory()() as db:
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


def _to_hex(value: object, prefix: bool = True) -> str:
    raw = value.hex() if hasattr(value, "hex") else str(value)
    if prefix and not raw.startswith("0x"):
        return "0x" + raw
    return raw


def persist_logs(chain_id: int, logs: Iterable[dict], w3: Web3) -> int:
    log_list = list(logs)
    if not log_list:
        return 0

    by_block: dict[int, list[dict]] = defaultdict(list)
    for log in log_list:
        by_block[int(log["blockNumber"])].append(log)

    block_timestamps: dict[int, int] = {}
    for block_number in by_block:
        block = w3.eth.get_block(block_number)
        block_timestamps[block_number] = int(block["timestamp"])

    inserted = 0
    with get_session_factory()() as db:
        for log in log_list:
            block_number = int(log["blockNumber"])
            tx_hash = _to_hex(log["transactionHash"])
            topic_hex = [_to_hex(t) for t in log.get("topics", [])]
            data_raw = log.get("data", b"")
            data_hex = _to_hex(data_raw) if data_raw else "0x"
            event_name = decode_event_name(topic_hex)

            stmt = (
                pg_insert(ChainEvent)
                .values(
                    chain_id=chain_id,
                    contract_address=normalize_address(log["address"]),
                    event_name=event_name,
                    block_number=block_number,
                    block_timestamp=block_timestamps[block_number],
                    tx_hash=tx_hash,
                    log_index=int(log["logIndex"]),
                    payload_json=json.dumps(
                        {
                            "topics": topic_hex,
                            "data": data_hex,
                            "removed": bool(log.get("removed", False)),
                        }
                    ),
                )
                .on_conflict_do_nothing(constraint="uq_chain_tx_log")
            )
            result = db.execute(stmt)
            inserted += result.rowcount
        db.commit()
    return inserted


def run_once(cfg: IndexerConfig, w3: Web3) -> tuple[int, int, int]:
    latest = w3.eth.block_number
    confirmed_tip = latest - cfg.confirmations
    if confirmed_tip < 0:
        return (latest, 0, 0)

    stream_key = "contracts:" + ",".join(sorted(cfg.contract_addresses))
    from_block = get_checkpoint(cfg.chain_id, stream_key, cfg.start_block)

    to_block = min(from_block + cfg.batch_size - 1, confirmed_tip)
    if from_block > to_block:
        return (latest, from_block, 0)

    logs = w3.eth.get_logs(
        {
            "fromBlock": from_block,
            "toBlock": to_block,
            "address": [normalize_address(a) for a in cfg.contract_addresses],
        }
    )

    inserted = persist_logs(cfg.chain_id, logs, w3)
    set_checkpoint(cfg.chain_id, stream_key, to_block + 1)
    return (latest, to_block, inserted)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(description="Sentient backend event indexer")
    parser.add_argument("--once", action="store_true", help="Run one indexing pass and exit")
    args = parser.parse_args()

    init_db()
    cfg = load_config()
    w3 = Web3(Web3.HTTPProvider(cfg.rpc_url))

    if args.once:
        latest, processed_to, inserted = run_once(cfg, w3)
        logger.info("indexer once: latest=%d processed_to=%d inserted=%d", latest, processed_to, inserted)
        return

    while True:
        latest, processed_to, inserted = run_once(cfg, w3)
        logger.info("indexer loop: latest=%d processed_to=%d inserted=%d", latest, processed_to, inserted)
        time.sleep(cfg.poll_interval_sec)


if __name__ == "__main__":
    main()
