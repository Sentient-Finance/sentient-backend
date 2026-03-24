"""On-chain vault execution via web3.py.

The PortfolioVault implements Chainlink AutomationCompatibleInterface:
  - checkUpkeep(bytes) → (bool upkeepNeeded, bytes performData)
  - performUpkeep(bytes performData)

Flow:
  1. Call checkUpkeep(b'') to ask the contract if a swap is needed and get
     the encoded swap parameters as performData.
  2. If upkeepNeeded, sign and broadcast performUpkeep(performData).

This replaces the Chainlink CRE execution service.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Any, cast

from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.types import TxParams, Wei
from web3.exceptions import ContractLogicError

logger = logging.getLogger(__name__)

VAULT_ABI = [
    {
        "name": "checkUpkeep",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "checkData", "type": "bytes"}],
        "outputs": [
            {"name": "upkeepNeeded", "type": "bool"},
            {"name": "performData", "type": "bytes"},
        ],
    },
    {
        "name": "performUpkeep",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "performData", "type": "bytes"}],
        "outputs": [],
    },
    {
        "name": "getBalance",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "token", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

Action = Literal["buy", "sell"]


@dataclass
class ExecutionResult:
    success: bool
    vault_address: str
    action: str
    tx_hash: str | None = None
    error: str | None = None
    dry_run: bool = False
    upkeep_needed: bool = False
    performed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def execute_vault_upkeep(
    *,
    w3: Web3,
    account: LocalAccount,
    vault_address: str,
    action: str = "auto",
    gas_limit: int = 350_000,
    dry_run: bool = False,
) -> ExecutionResult:
    """Execute a vault swap via Chainlink AutomationCompatible interface.

    1. Calls checkUpkeep(b'') — contract decides if a swap is needed and
       returns the encoded swap parameters (performData).
    2. If upkeepNeeded is True, signs and broadcasts performUpkeep(performData).
       In dry_run mode, simulates the call via eth_call without broadcasting.

    Args:
        w3: Connected Web3 instance (caller is responsible for caching/reuse).
        account: Pre-loaded executor LocalAccount (raw key stays in caller scope).
        vault_address: PortfolioVault clone address.
        action: Label for logging ("buy" / "sell" / "auto").
        gas_limit: Upper gas bound; unused gas is refunded.
        dry_run: Simulate only — no real transaction is sent.
    """
    checksum_vault = Web3.to_checksum_address(vault_address)
    contract = w3.eth.contract(address=checksum_vault, abi=VAULT_ABI)

    # --- step 1: checkUpkeep ---
    try:
        upkeep_needed, perform_data = contract.functions.checkUpkeep(b"").call()
    except Exception as exc:
        logger.error("checkUpkeep failed vault=%s: %s", vault_address, exc)
        return ExecutionResult(
            success=False,
            vault_address=vault_address,
            action=action,
            error=f"checkUpkeep: {exc}",
        )

    logger.info(
        "checkUpkeep vault=%s upkeepNeeded=%s performData=%s bytes",
        vault_address,
        upkeep_needed,
        len(perform_data),
    )

    if not upkeep_needed:
        return ExecutionResult(
            success=True,
            vault_address=vault_address,
            action=action,
            upkeep_needed=False,
            error=None,
        )

    # --- step 2: performUpkeep ---
    fn = contract.functions.performUpkeep(perform_data)

    logger.info(
        "performUpkeep vault=%s action=%s executor=%s dry_run=%s",
        vault_address,
        action,
        account.address,
        dry_run,
    )

    try:
        if dry_run:
            fn.call({"from": account.address})
            logger.info(
                "dry-run performUpkeep OK vault=%s action=%s", vault_address, action
            )
            return ExecutionResult(
                success=True,
                vault_address=vault_address,
                action=action,
                upkeep_needed=True,
                dry_run=True,
            )

        nonce = w3.eth.get_transaction_count(account.address, "pending")
        latest = w3.eth.get_block("latest")
        base_fee = latest.get("baseFeePerGas", w3.to_wei(1, "gwei"))
        priority_fee = w3.to_wei(1, "gwei")
        tx_params: TxParams = {
            "from": account.address,
            "nonce": nonce,
            "gas": gas_limit,
            "maxPriorityFeePerGas": priority_fee,
            "maxFeePerGas": cast(Wei, base_fee * 2 + priority_fee),
        }
        tx = fn.build_transaction(tx_params)
        signed = account.sign_transaction(cast(Any, tx))
        raw_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        # Base Sepolia block time ~2s; 60s is more than enough
        receipt = w3.eth.wait_for_transaction_receipt(raw_hash, timeout=60)
        tx_hex = raw_hash.hex()

        if receipt["status"] == 1:
            logger.info(
                "performUpkeep OK vault=%s action=%s tx=%s",
                vault_address,
                action,
                tx_hex,
            )
            return ExecutionResult(
                success=True,
                vault_address=vault_address,
                action=action,
                tx_hash=tx_hex,
                upkeep_needed=True,
            )

        logger.warning(
            "performUpkeep REVERTED vault=%s action=%s tx=%s",
            vault_address,
            action,
            tx_hex,
        )
        return ExecutionResult(
            success=False,
            vault_address=vault_address,
            action=action,
            tx_hash=tx_hex,
            upkeep_needed=True,
            error="transaction reverted",
        )

    except ContractLogicError as exc:
        logger.error("contract revert vault=%s: %s", vault_address, exc)
        return ExecutionResult(
            success=False,
            vault_address=vault_address,
            action=action,
            upkeep_needed=True,
            error=f"revert: {exc}",
        )
    except Exception as exc:
        logger.exception("unexpected error vault=%s action=%s", vault_address, action)
        return ExecutionResult(
            success=False,
            vault_address=vault_address,
            action=action,
            upkeep_needed=True,
            error=str(exc),
        )
