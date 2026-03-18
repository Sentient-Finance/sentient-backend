from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select  # func kept for count() aggregates
from sqlalchemy.orm import Session

from libs.db.models import Vault, VaultEvent
from libs.db.session import get_db

router = APIRouter(prefix="/vaults", tags=["vaults"])

T = TypeVar("T")

# Keep aligned with sentient-vault-solidity contract event names.
VaultEventType = Literal[
    "VaultInitialized",
    "TokenRuleSet",
    "TokenDeposited",
    "TokenWithdrawn",
    "SwapExecuted",
    "RouterUpdated",
    "AuthorizedExecutorUpdated",
    "ExecutorUpdated",
    "MaxTradeAmountUpdated",
    "CooldownPeriodUpdated",
    "PriceFeedUpdated",
    "OwnershipTransferred",
    "MaxSlippageUpdated",
    "CrossChainShieldTriggered",
    "CCIPRouterUpdated",
    "AutomationConfigUpdated",
]

AddressParam = Annotated[
    str,
    Path(pattern=r"^0x[a-fA-F0-9]{40}$", description="Vault address"),
]


class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    limit: int
    offset: int
    items: list[T]


class VaultListItem(BaseModel):
    chain_id: int
    address: str
    owner: str | None = None
    created_block_number: int | None
    created_tx_hash: str | None
    created_timestamp: datetime | None


class VaultDetail(BaseModel):
    chain_id: int
    address: str
    owner: str | None = None
    created_block_number: int | None
    created_tx_hash: str | None
    created_timestamp: datetime | None
    event_count: int = Field(default=0)
    latest_event_block: int | None = None
    latest_event_timestamp: datetime | None = None


class HistoryItem(BaseModel):
    chain_id: int
    vault_address: str
    event_type: str
    block_number: int
    tx_hash: str
    log_index: int
    timestamp: datetime
    payload_json: dict[str, Any]


def _normalize_address(address: str) -> str:
    return address.lower()


def _vault_to_list_item(row: Vault) -> VaultListItem:
    return VaultListItem(
        chain_id=row.chain_id,
        address=row.address,
        owner=row.owner,
        created_block_number=row.created_block_number,
        created_tx_hash=row.created_tx_hash,
        created_timestamp=row.created_timestamp,
    )


def _event_to_history_item(row: VaultEvent) -> HistoryItem:
    return HistoryItem(
        chain_id=row.chain_id,
        vault_address=row.vault_address,
        event_type=row.event_type,
        block_number=row.block_number,
        tx_hash=row.tx_hash,
        log_index=row.log_index,
        timestamp=row.timestamp,
        payload_json=row.payload_json or {},
    )


@router.get("", response_model=PaginatedResponse[VaultListItem])
def list_vaults(
    chain_id: int | None = Query(default=84532, alias="chain"),
    owner: str | None = Query(
        default=None, description="Filter by vault owner (wallet address)"
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    filters = []
    if chain_id is not None:
        filters.append(Vault.chain_id == chain_id)
    if owner is not None and owner.strip():
        # Addresses are stored lowercase — direct equality uses the index
        filters.append(Vault.owner == _normalize_address(owner.strip()))

    count_stmt = select(func.count()).select_from(Vault)
    data_stmt = select(Vault).order_by(Vault.id.desc()).offset(offset).limit(limit)

    if filters:
        count_stmt = count_stmt.where(and_(*filters))
        data_stmt = data_stmt.where(and_(*filters))

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(data_stmt).all()

    return PaginatedResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_vault_to_list_item(row) for row in rows],
    )


@router.get(
    "/{address}/history",
    response_model=PaginatedResponse[HistoryItem],
    responses={
        404: {"description": "Vault not found"},
        422: {"description": "Invalid request params (including date range)"},
    },
)
def get_vault_history(
    address: AddressParam,
    chain_id: int | None = Query(default=None, alias="chain"),
    event_type: VaultEventType | None = Query(default=None, alias="type"),
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    if from_time and to_time and from_time > to_time:
        raise HTTPException(status_code=422, detail="from must be <= to")

    normalized = _normalize_address(address)

    vault_exists_stmt = select(Vault.id).where(Vault.address == normalized)
    if chain_id is not None:
        vault_exists_stmt = vault_exists_stmt.where(Vault.chain_id == chain_id)
    if db.scalar(vault_exists_stmt.limit(1)) is None:
        raise HTTPException(status_code=404, detail="vault not found")

    filters = [VaultEvent.vault_address == normalized]
    if chain_id is not None:
        filters.append(VaultEvent.chain_id == chain_id)
    if event_type:
        filters.append(VaultEvent.event_type == event_type)
    if from_time:
        filters.append(VaultEvent.timestamp >= from_time)
    if to_time:
        filters.append(VaultEvent.timestamp <= to_time)

    count_stmt = select(func.count()).select_from(VaultEvent).where(and_(*filters))
    data_stmt = (
        select(VaultEvent)
        .where(and_(*filters))
        .order_by(VaultEvent.block_number.desc(), VaultEvent.log_index.desc())
        .offset(offset)
        .limit(limit)
    )

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(data_stmt).all()

    return PaginatedResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_event_to_history_item(row) for row in rows],
    )


@router.get(
    "/{address}",
    response_model=VaultDetail,
    responses={
        404: {"description": "Vault not found"},
        409: {"description": "Multiple chains match; provide `chain` query param"},
        422: {"description": "Invalid address or query params"},
    },
)
def get_vault(
    address: AddressParam,
    chain_id: int | None = Query(default=None, alias="chain"),
    db: Session = Depends(get_db),
):
    normalized = _normalize_address(address)

    stmt = select(Vault).where(Vault.address == normalized)
    if chain_id is not None:
        stmt = stmt.where(Vault.chain_id == chain_id)

    rows = db.scalars(stmt.order_by(Vault.id.desc())).all()
    if not rows:
        raise HTTPException(status_code=404, detail="vault not found")
    if len(rows) > 1 and chain_id is None:
        raise HTTPException(
            status_code=409,
            detail="multiple vaults for this address; specify `chain` query param",
        )
    vault = rows[0]

    event_filters = [
        VaultEvent.vault_address == normalized,
        VaultEvent.chain_id == vault.chain_id,
    ]

    event_count = (
        db.scalar(
            select(func.count()).select_from(VaultEvent).where(and_(*event_filters))
        )
        or 0
    )

    latest_event = db.scalar(
        select(VaultEvent)
        .where(and_(*event_filters))
        .order_by(VaultEvent.block_number.desc(), VaultEvent.log_index.desc())
        .limit(1)
    )

    return VaultDetail(
        chain_id=vault.chain_id,
        address=vault.address,
        owner=vault.owner,
        created_block_number=vault.created_block_number,
        created_tx_hash=vault.created_tx_hash,
        created_timestamp=vault.created_timestamp,
        event_count=event_count,
        latest_event_block=latest_event.block_number if latest_event else None,
        latest_event_timestamp=latest_event.timestamp if latest_event else None,
    )
