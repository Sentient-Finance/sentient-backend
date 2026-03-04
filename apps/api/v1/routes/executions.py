from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from libs.db.models import ExecutionAttempt, ExecutionRequest
from libs.db.session import get_db

router = APIRouter(prefix="/executions", tags=["executions"])


class ExecutionAttemptResponse(BaseModel):
    attempt_number: int
    status: str
    error_message: str | None
    created_at: datetime


class ExecutionStatusResponse(BaseModel):
    execution_id: int
    chain_id: int
    vault_address: str
    action: str
    status: str
    reason: str | None
    tx_hash: str | None
    external_execution_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    attempts: list[ExecutionAttemptResponse] = Field(default_factory=list)


@router.get("/{execution_id}", response_model=ExecutionStatusResponse)
def get_execution_status(execution_id: int, db: Session = Depends(get_db)):
    row = db.scalar(
        select(ExecutionRequest).where(ExecutionRequest.id == execution_id).limit(1)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="execution not found")

    attempts = db.scalars(
        select(ExecutionAttempt)
        .where(ExecutionAttempt.execution_request_id == row.id)
        .order_by(ExecutionAttempt.attempt_number.asc(), ExecutionAttempt.id.asc())
    ).all()

    return ExecutionStatusResponse(
        execution_id=row.id,
        chain_id=row.chain_id,
        vault_address=row.vault_address,
        action=row.action,
        status=row.status,
        reason=row.reason,
        tx_hash=row.tx_hash,
        external_execution_id=row.external_execution_id,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
        attempts=[
            ExecutionAttemptResponse(
                attempt_number=a.attempt_number,
                status=a.status,
                error_message=a.error_message,
                created_at=a.created_at,
            )
            for a in attempts
        ],
    )
