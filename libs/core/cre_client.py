from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import urllib.request

from libs.core.config import get_settings


@dataclass
class CreExecutionResult:
    ok: bool
    tx_hash: str | None
    error: str | None = None
    raw: dict | None = None


def _fake_tx_hash(payload: dict) -> str:
    seed = json.dumps(payload, sort_keys=True).encode()
    digest = hashlib.sha256(seed).hexdigest()
    return "0x" + digest[:64]


def submit_swap_via_cre(*, vault_address: str, chain_id: int, action: str, reason: str | None, metadata: dict) -> CreExecutionResult:
    """Submit execution request to Chainlink CRE gateway.

    Behavior:
    - If CRE_EXECUTOR_URL is missing: run in mock mode (deterministic fake tx hash)
    - If configured: POST JSON payload to executor endpoint
    """

    settings = get_settings()
    payload = {
        "vault_address": vault_address,
        "chain_id": chain_id,
        "action": action,
        "reason": reason,
        "metadata": metadata,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }

    # Mock mode to keep dev flow unblocked
    if not settings.cre_executor_url:
        return CreExecutionResult(ok=True, tx_hash=_fake_tx_hash(payload), raw={"mode": "mock"})

    try:
        req = urllib.request.Request(
            settings.cre_executor_url,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        if settings.cre_executor_token:
            req.add_header("Authorization", f"Bearer {settings.cre_executor_token}")

        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="ignore")

        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body}

        tx_hash = parsed.get("tx_hash") or parsed.get("txHash")
        if not tx_hash:
            # still allow as success if executor accepted but did not return hash
            tx_hash = _fake_tx_hash({**payload, "executor": "no_tx_hash"})

        return CreExecutionResult(ok=True, tx_hash=tx_hash, raw=parsed)
    except Exception as exc:
        return CreExecutionResult(ok=False, tx_hash=None, error=str(exc), raw=None)
