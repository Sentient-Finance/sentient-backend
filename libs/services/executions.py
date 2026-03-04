from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from libs.db.models import ExecutionAttempt, ExecutionRequest


@dataclass
class ExecutionState:
    execution: ExecutionRequest
    attempt_number: int


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_execution(db: Session, execution_id: int) -> ExecutionRequest | None:
    return db.scalar(
        select(ExecutionRequest).where(ExecutionRequest.id == execution_id).limit(1)
    )


def create_execution_attempt(
    db: Session,
    *,
    execution: ExecutionRequest,
    attempt_number: int,
    status: str,
    request_json: dict[str, Any] | None = None,
    response_json: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> ExecutionAttempt:
    row = ExecutionAttempt(
        execution_request_id=execution.id,
        attempt_number=attempt_number,
        status=status,
        request_json=request_json or {},
        response_json=response_json,
        error_message=error_message,
    )
    db.add(row)
    return row


def mark_execution_status(
    execution: ExecutionRequest,
    *,
    status: str,
    error_message: str | None = None,
    tx_hash: str | None = None,
    external_execution_id: str | None = None,
) -> None:
    execution.status = status
    execution.updated_at = utcnow()
    if error_message is not None:
        execution.error_message = error_message
    if tx_hash is not None:
        execution.tx_hash = tx_hash
    if external_execution_id is not None:
        execution.external_execution_id = external_execution_id


def next_attempt_number(db: Session, execution_id: int) -> int:
    row = db.scalar(
        select(ExecutionAttempt)
        .where(ExecutionAttempt.execution_request_id == execution_id)
        .order_by(ExecutionAttempt.id.desc())
        .limit(1)
    )
    return 1 if row is None else row.attempt_number + 1
