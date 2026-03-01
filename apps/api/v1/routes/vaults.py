from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from web3 import Web3

from libs.db.models import ChainEvent
from libs.db.session import get_db

router = APIRouter(prefix="/vaults", tags=["vaults"])


class EventOut(BaseModel):
    id: int
    event_name: str
    block_number: int
    block_timestamp: int
    tx_hash: str
    log_index: int
    payload_json: str

    model_config = {"from_attributes": True}


@router.get("/{address}/events", response_model=list[EventOut])
def get_vault_events(
    address: str,
    limit: int = Query(default=20, ge=1, le=100),
    before_block: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ChainEvent]:
    try:
        checksum = Web3.to_checksum_address(address)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid contract address")

    stmt = (
        select(ChainEvent)
        .where(ChainEvent.contract_address == checksum)
        .order_by(ChainEvent.block_number.desc(), ChainEvent.log_index.desc())
    )
    if before_block is not None:
        stmt = stmt.where(ChainEvent.block_number < before_block)
    stmt = stmt.limit(limit)

    return list(db.scalars(stmt).all())
