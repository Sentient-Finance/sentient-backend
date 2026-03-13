from __future__ import annotations

import httpx
import sys
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import func
from sqlalchemy.orm import Session

from libs.db.models import Vault, VaultEvent

VAULTS_QUERY = """
query Vaults($first: Int!, $lastId: String!) {
  vaults(first: $first, where: { id_gt: $lastId }, orderBy: id, orderDirection: asc) {
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
query VaultEvents($first: Int!, $lastId: String!) {
  vaultEvents(first: $first, where: { id_gt: $lastId }, orderBy: id, orderDirection: asc) {
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
    enabled
    buyThreshold
    sellThreshold
    tradeAmount
  }
}
"""

def _graphql_request(
    url: str,
    query: str,
    variables: dict[str, Any],
    api_key: str | None = None,
) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"query": query, "variables": variables}
    resp = httpx.post(url, json=payload, headers=headers, timeout=60.0)
    resp.raise_for_status()
    data = resp.json()
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
    db: Session,
    chain_id: int,
    batch: int = 100,
    api_key: str | None = None,
) -> int:
    count = 0
    last_id = ""
    while True:
        data = _graphql_request(
            url, VAULTS_QUERY, {"first": batch, "lastId": last_id}, api_key=api_key
        )
        vaults = data.get("vaults") or []
        if not vaults:
            break
        for v in vaults:
            last_id = v["id"]
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
                updated = False
                if owner_addr and (not existing.owner or existing.owner.lower() != owner_addr.lower()):
                    existing.owner = owner_addr
                    updated = True
                if updated:
                    count += 1
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
        if len(vaults) < batch:
            break
    return count

def sync_vault_events(
    url: str,
    db: Session,
    chain_id: int,
    batch: int = 100,
    api_key: str | None = None,
) -> int:
    count = 0
    last_id = ""
    while True:
        data = _graphql_request(
            url, VAULT_EVENTS_QUERY, {"first": batch, "lastId": last_id}, api_key=api_key
        )
        events = data.get("vaultEvents") or []
        if not events:
            break
        for e in events:
            last_id = e["id"]
            vault_ref = e.get("vault") or {}
            vault_id = _to_hex(vault_ref.get("id"))
            if not vault_id:
                continue
            tx_hash = _to_hex(e.get("txHash"))
            log_idx = _to_int(e.get("logIndex"))
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
                continue
            block_ts = _to_int(e.get("blockTimestamp")) or 0
            payload = {}
            # Map GraphQL fields to payload
            for field in ["token", "tokenIn", "tokenOut"]:
                if e.get(field):
                    payload[field] = _to_hex(e[field])
            for field in ["amountIn", "amountOut", "buyThreshold", "sellThreshold", "tradeAmount"]:
                if e.get(field) is not None:
                    payload[field] = str(_to_int(e[field]) or 0)
            if e.get("enabled") is not None:
                payload["enabled"] = bool(e["enabled"])
                
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
        if len(events) < batch:
            break
    return count

def resolve_subgraph_url(settings) -> str:
    api_key = settings.subgraph_api_key
    subgraph_id = settings.subgraph_id
    if api_key and subgraph_id:
        return f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/{subgraph_id}"
    return settings.subgraph_url or ""
