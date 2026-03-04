from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from libs.core.config import Settings


class CreClientError(Exception):
    pass


@dataclass
class CreSubmitResult:
    external_execution_id: str | None
    tx_hash: str | None
    status: str
    raw_response: dict[str, Any]


class ChainlinkCreClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    def _call_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._settings.chainlink_cre_api_key:
            headers["Authorization"] = f"Bearer {self._settings.chainlink_cre_api_key}"

        req = request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self._settings.chainlink_cre_timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except error.HTTPError as exc:  # pragma: no cover - depends on external API
            body = exc.read().decode("utf-8")
            raise CreClientError(f"CRE HTTP {exc.code}: {body}") from exc
        except Exception as exc:
            raise CreClientError(f"CRE request failed: {exc}") from exc

    def submit_execution(
        self,
        *,
        chain_id: int,
        vault_address: str,
        action: str,
        reason: str | None,
        metadata: dict[str, Any],
    ) -> CreSubmitResult:
        if not self._settings.chainlink_cre_execute_url:
            raise CreClientError("CHAINLINK_CRE_EXECUTE_URL is not configured")

        payload = {
            "chainId": chain_id,
            "vaultAddress": vault_address,
            "action": action,
            "reason": reason,
            "metadata": metadata,
        }
        data = self._call_json(self._settings.chainlink_cre_execute_url, payload)
        return CreSubmitResult(
            external_execution_id=data.get("executionId"),
            tx_hash=data.get("txHash"),
            status=str(data.get("status", "submitted")),
            raw_response=data,
        )
