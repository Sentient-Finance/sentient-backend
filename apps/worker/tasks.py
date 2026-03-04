"""Celery task definitions.

Import celery_app here (not the other way around) to avoid circular imports.
"""

from __future__ import annotations

from apps.worker.celery_app import celery_app
from libs.chain.cre_client import ChainlinkCreClient, CreClientError
from libs.core.config import get_settings
from libs.db.session import get_session_factory
from libs.services.executions import (
    create_execution_attempt,
    get_execution,
    mark_execution_status,
    next_attempt_number,
)


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"


@celery_app.task(bind=True, name="worker.process_execution", max_retries=4)
def process_execution(self, execution_id: int) -> str:
    settings = get_settings()
    session_factory = get_session_factory()

    db = session_factory()
    try:
        execution = get_execution(db, execution_id)
        if execution is None:
            return "missing"

        attempt_no = next_attempt_number(db, execution_id)
        payload = {
            "chainId": execution.chain_id,
            "vaultAddress": execution.vault_address,
            "action": execution.action,
            "reason": execution.reason,
            "metadata": execution.metadata_json or {},
        }

        mark_execution_status(execution, status="submitted")
        create_execution_attempt(
            db,
            execution=execution,
            attempt_number=attempt_no,
            status="submitted",
            request_json=payload,
        )
        db.commit()

        try:
            client = ChainlinkCreClient(settings)
            result = client.submit_execution(
                chain_id=execution.chain_id,
                vault_address=execution.vault_address,
                action=execution.action,
                reason=execution.reason,
                metadata=execution.metadata_json or {},
            )

            final_status = "confirmed" if result.tx_hash else "submitted"
            mark_execution_status(
                execution,
                status=final_status,
                tx_hash=result.tx_hash,
                external_execution_id=result.external_execution_id,
                error_message=None,
            )
            create_execution_attempt(
                db,
                execution=execution,
                attempt_number=attempt_no,
                status=final_status,
                request_json=payload,
                response_json=result.raw_response,
            )
            db.commit()
            return final_status
        except CreClientError as exc:
            retries = int(getattr(self.request, "retries", 0))
            final_failure = retries >= self.max_retries
            status = "dead_letter" if final_failure else "queued"

            mark_execution_status(execution, status=status, error_message=str(exc))
            create_execution_attempt(
                db,
                execution=execution,
                attempt_number=attempt_no,
                status="failed",
                request_json=payload,
                error_message=str(exc),
            )
            db.commit()

            if final_failure:
                return "dead_letter"

            countdown = min(15 * (2**retries), 5 * 60)
            raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
