"""
Indexer: sync vault + vault_events from subgraph GraphQL API into Postgres.

Requires SUBGRAPH_URL in .env, e.g.:

Chain ID is derived from subgraph network (base-sepolia = 84532).

Run:
  python -m apps.indexer.main           # one-shot sync
  python -m apps.indexer.main --loop    # poll every INDEXER_POLL_INTERVAL_SECONDS
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func

from libs.core.config import get_settings
from libs.db.models import Vault, VaultEvent
from libs.db.session import get_session_factory

VAULTS_QUERY = """
query Vaults($first: Int!, $skip: Int!) {
  vaults(first: $first, skip: $skip) {
    id
    address
    owner
    createdAtBlock
    createdAtTimestamp
    createdTxHash
  }
}
"""

VAULT_EVENTS_QUERY = """
query VaultEvents($first: Int!, $skip: Int!) {
  vaultEvents(first: $first, skip: $skip) {
    id
    vault { id }
    eventName
    blockNumber
    blockTimestamp
    txHash
    logIndex
    token
    tokenIn
    tokenOut
    amountIn
    amountOut
  }
}
"""


def _redact_url(url: str) -> str:
    """Hide API key in URL for safe logging."""
    if "/api/" in url and "/subgraphs/" in url:
        parts = url.split("/api/", 1)
        if len(parts) == 2:
            key_part = parts[1].split("/subgraphs/", 1)[0]
            return url.replace(key_part, "***", 1)
    return url


def _graphql_request(
    url: str,
    query: str,
    variables: dict[str, Any],
    api_key: str | None = None,
) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"query": query, "variables": variables}
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            print(f"403 Forbidden. URL: {_redact_url(url)}", file=sys.stderr)
            print("Check:", file=sys.stderr)
            print("  1. API key has this subgraph assigned? (Studio → API Keys → Assign)", file=sys.stderr)
            print("  2. Domain restrictions on API key?", file=sys.stderr)
            body = e.response.text
            if body:
                print(f"  Response: {body[:200]}", file=sys.stderr)
        raise
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data.get("data", {})


def _to_hex(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, str):
        return val.lower() if val.startswith("0x") else f"0x{val.lower()}"
    return None


def _to_int(val: Any) -> int | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        return int(val, 16) if val.startswith("0x") else int(val)
    return None


def sync_vaults(
    url: str,
    session_factory,
    chain_id: int,
    batch: int = 100,
    api_key: str | None = None,
    verbose: bool = False,
) -> int:
    count = 0
    skipped = 0
    total_received = 0
    skip = 0
    while True:
        data = _graphql_request(url, VAULTS_QUERY, {"first": batch, "skip": skip}, api_key=api_key)
        vaults = data.get("vaults") or []
        if not vaults:
            if skip == 0 and count == 0:
                print("  (subgraph returned 0 vaults)", file=sys.stderr)
            break
        total_received += len(vaults)
        with session_factory() as db:
            for v in vaults:
                addr = _to_hex(v.get("address") or v.get("id"))
                if not addr:
                    continue
                owner_addr = _to_hex(v.get("owner"))
                existing = (
                    db.query(Vault)
                    .filter(
                        func.lower(Vault.address) == addr.lower(),
                        Vault.chain_id == chain_id,
                    )
                    .first()
                )
                if existing:
                    if owner_addr and (not existing.owner or existing.owner.lower() != owner_addr.lower()):
                        existing.owner = owner_addr
                        count += 1
                    else:
                        skipped += 1
                    continue
                created_block = _to_int(v.get("createdAtBlock"))
                created_ts = _to_int(v.get("createdAtTimestamp"))
                db.add(
                    Vault(
                        chain_id=chain_id,
                        address=addr,
                        owner=owner_addr,
                        created_block_number=created_block,
                        created_tx_hash=_to_hex(v.get("createdTxHash")),
                        created_timestamp=(
                            datetime.fromtimestamp(created_ts, tz=timezone.utc)
                            if created_ts
                            else None
                        ),
                    )
                )
                count += 1
            db.commit()
        skip += len(vaults)
        if len(vaults) < batch:
            break
    if verbose and total_received:
        print(f"  vaults: received={total_received}, inserted={count}, skipped={skipped}", file=sys.stderr)
    return count


def _parse_event_id(event_id: str) -> tuple[str | None, int | None]:
    """Parse id 'txHash-logIndex' into (tx_hash, log_index)."""
    if not event_id or "-" not in event_id:
        return None, None
    parts = event_id.rsplit("-", 1)
    if len(parts) != 2:
        return None, None
    tx_hash = _to_hex(parts[0])
    log_idx = _to_int(parts[1])
    return tx_hash, log_idx


def sync_vault_events(
    url: str,
    session_factory,
    chain_id: int,
    batch: int = 100,
    api_key: str | None = None,
    verbose: bool = False,
) -> int:
    count = 0
    skipped = 0
    total_received = 0
    skip = 0
    while True:
        data = _graphql_request(
            url, VAULT_EVENTS_QUERY, {"first": batch, "skip": skip}, api_key=api_key
        )
        events = data.get("vaultEvents") or []
        if not events:
            if skip == 0 and count == 0 and verbose:
                print("  (subgraph returned 0 vault_events)", file=sys.stderr)
            break
        total_received += len(events)
        with session_factory() as db:
            for e in events:
                vault_ref = e.get("vault") or {}
                vault_id = _to_hex(vault_ref.get("id"))
                if not vault_id:
                    continue
                tx_hash = _to_hex(e.get("txHash"))
                log_idx = _to_int(e.get("logIndex"))
                if not tx_hash or log_idx is None:
                    tx_hash, log_idx = _parse_event_id(e.get("id") or "")
                if not tx_hash or log_idx is None:
                    continue
                existing = (
                    db.query(VaultEvent)
                    .filter(
                        VaultEvent.chain_id == chain_id,
                        func.lower(VaultEvent.tx_hash) == tx_hash.lower(),
                        VaultEvent.log_index == log_idx,
                    )
                    .first()
                )
                if existing:
                    skipped += 1
                    continue
                block_ts = _to_int(e.get("blockTimestamp"))
                if block_ts is None:
                    block_ts = 0
                payload = {}
                if e.get("token"):
                    payload["token"] = _to_hex(e["token"])
                if e.get("tokenIn"):
                    payload["tokenIn"] = _to_hex(e["tokenIn"])
                if e.get("tokenOut"):
                    payload["tokenOut"] = _to_hex(e["tokenOut"])
                if e.get("amountIn") is not None:
                    payload["amountIn"] = str(_to_int(e["amountIn"]) or 0)
                if e.get("amountOut") is not None:
                    payload["amountOut"] = str(_to_int(e["amountOut"]) or 0)
                db.add(
                    VaultEvent(
                        chain_id=chain_id,
                        vault_address=vault_id,
                        event_type=e.get("eventName") or "Unknown",
                        block_number=_to_int(e.get("blockNumber")) or 0,
                        tx_hash=tx_hash,
                        log_index=log_idx,
                        timestamp=datetime.fromtimestamp(block_ts, tz=timezone.utc),
                        payload_json=payload,
                    )
                )
                count += 1
            db.commit()
        skip += len(events)
        if len(events) < batch:
            break
    if verbose and total_received:
        print(f"  vault_events: received={total_received}, inserted={count}, skipped={skipped}", file=sys.stderr)
    return count


def _resolve_subgraph_url(settings) -> str:
    """Use Gateway URL (with API key in path) when possible; Studio often returns 403."""
    api_key = settings.subgraph_api_key
    subgraph_id = settings.subgraph_id
    if api_key and subgraph_id:
        return f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/{subgraph_id}"
    return settings.subgraph_url or ""


def run(loop: bool = False, verbose: bool = False) -> None:
    settings = get_settings()
    url = _resolve_subgraph_url(settings)
    if not url:
        print("Subgraph URL not set. Add to .env:", file=sys.stderr)
        print("  Option A (Gateway, recommended): SUBGRAPH_API_KEY + SUBGRAPH_ID", file=sys.stderr)
        print(
            "    SUBGRAPH_ID = from Studio → Query tab → copy deployment ID",
            file=sys.stderr,
        )
        print("  Option B: SUBGRAPH_URL=https://api.studio.thegraph.com/query/...", file=sys.stderr)
        sys.exit(1)
    if not settings.subgraph_api_key and "api.studio.thegraph.com" in (settings.subgraph_url or ""):
        print(
            "Warning: Using Studio URL without API key often returns 403.",
            file=sys.stderr,
        )
        print("  Use SUBGRAPH_API_KEY + SUBGRAPH_ID for Gateway URL instead.", file=sys.stderr)
    session_factory = get_session_factory()
    batch = settings.indexer_batch_size
    interval = settings.indexer_poll_interval_seconds
    chain_id = settings.chain_base_sepolia_id
    # API key only needed when using SUBGRAPH_URL (Studio); Gateway has key in URL
    api_key = None if "gateway.thegraph.com" in url else settings.subgraph_api_key

    def _sync_once() -> None:
        v = sync_vaults(
            url, session_factory, chain_id=chain_id, batch=batch, api_key=api_key, verbose=verbose
        )
        ev = sync_vault_events(
            url, session_factory, chain_id=chain_id, batch=batch, api_key=api_key, verbose=verbose
        )
        print(f"Synced {v} vaults, {ev} vault_events from subgraph (chain_id={chain_id})")

    def do_sync() -> None:
        try:
            _sync_once()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403 and settings.subgraph_url and "gateway.thegraph.com" in url:
                print("Gateway 403. Trying Studio URL with Bearer token...", file=sys.stderr)
                url2 = settings.subgraph_url
                api_key2 = settings.subgraph_api_key
                v = sync_vaults(url2, session_factory, chain_id=chain_id, batch=batch, api_key=api_key2, verbose=verbose)
                ev = sync_vault_events(url2, session_factory, chain_id=chain_id, batch=batch, api_key=api_key2, verbose=verbose)
                print(f"Synced {v} vaults, {ev} vault_events from Studio (chain_id={chain_id})")
            else:
                raise

    if loop:
        while True:
            do_sync()
            time.sleep(interval)
    else:
        do_sync()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Poll subgraph every INDEXER_POLL_INTERVAL_SECONDS")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print received/inserted counts")
    args = parser.parse_args()
    run(loop=args.loop, verbose=args.verbose)
