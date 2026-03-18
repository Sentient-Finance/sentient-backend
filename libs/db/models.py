from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base


class Vault(Base):
    __tablename__ = "vaults"
    __table_args__ = (
        UniqueConstraint("chain_id", "address", name="uq_vault_chain_address"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chain_id: Mapped[int] = mapped_column(Integer, index=True)
    address: Mapped[str] = mapped_column(String(64), index=True)
    owner: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_block_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_tx_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VaultEvent(Base):
    __tablename__ = "vault_events"
    __table_args__ = (
        UniqueConstraint("chain_id", "tx_hash", "log_index", name="uq_chain_tx_log"),
        # Speeds up get_vault_history which always filters by (chain_id, vault_address)
        Index("ix_vault_events_chain_vault", "chain_id", "vault_address"),
        # Speeds up pagination ordering inside a vault's history
        Index(
            "ix_vault_events_vault_block", "vault_address", "block_number", "log_index"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chain_id: Mapped[int] = mapped_column(Integer, index=True)
    vault_address: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    block_number: Mapped[int] = mapped_column(BigInteger, index=True)
    tx_hash: Mapped[str] = mapped_column(String(80), index=True)
    log_index: Mapped[int] = mapped_column(Integer, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExecutionLog(Base):
    """Audit trail for every on-chain execution attempt."""

    __tablename__ = "execution_logs"
    __table_args__ = (
        Index("ix_execution_logs_vault_at", "vault_address", "executed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vault_address: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(16))  # "buy" | "sell"
    status: Mapped[str] = mapped_column(String(16))  # "ok" | "failed" | "skipped" | "dry_run"
    tx_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trigger_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
