"""On-chain vault state reader.

Reads token rules and price feed addresses directly from PortfolioVault contracts,
bypassing the DB/subgraph so strategy_tick always uses the latest on-chain state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

from web3 import Web3

logger = logging.getLogger(__name__)

VAULT_READ_ABI = [
    {
        "name": "getTokenRule",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "token", "type": "address"}],
        "outputs": [
            {
                "name": "",
                "type": "tuple",
                "components": [
                    {"name": "enabled", "type": "bool"},
                    {"name": "buyThreshold", "type": "uint256"},
                    {"name": "sellThreshold", "type": "uint256"},
                    {"name": "lastExecuted", "type": "uint256"},
                    {"name": "tradeAmount", "type": "uint256"},
                    {"name": "baseToken", "type": "address"},
                ],
            }
        ],
    },
    {
        "name": "priceFeeds",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "token", "type": "address"}],
        "outputs": [{"name": "", "type": "address"}],
    },
]

# Threshold values from contract are stored with 18 decimals (USD * 1e18).
_THRESHOLD_DECIMALS = 18


@dataclass
class VaultTokenRule:
    vault_address: str
    token_address: str
    enabled: bool
    buy_threshold_usd: float | None  # normalized to plain USD float
    sell_threshold_usd: float | None
    last_executed_ts: int  # unix timestamp
    trade_amount: int  # in token's raw units (smallest denomination)
    base_token: str
    price_feed: str | None  # Chainlink feed address, or None if not set


_ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def read_vault_token_rule(
    w3: Web3,
    vault_address: str,
    token_address: str,
) -> VaultTokenRule | None:
    """Read getTokenRule + priceFeeds for one token using a single batch request.

    Batches both eth_call RPCs into one HTTP round-trip instead of two.
    Returns None on any RPC error.
    """
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(vault_address),
            abi=VAULT_READ_ABI,
        )
        token_cs = Web3.to_checksum_address(token_address)

        with w3.batch_requests() as batch:
            batch.add(contract.functions.getTokenRule(token_cs))
            batch.add(contract.functions.priceFeeds(token_cs))
            results = batch.execute()

        rule, feed = cast(list[Any], results)
        enabled, buy_raw, sell_raw, last_exec, trade_amt, base_token = rule

        divisor = 10**_THRESHOLD_DECIMALS
        buy_usd = (buy_raw / divisor) if buy_raw > 0 else None
        sell_usd = (sell_raw / divisor) if sell_raw > 0 else None
        feed_str = str(feed)
        feed_addr = feed_str if feed_str.lower() != _ZERO_ADDRESS else None

        return VaultTokenRule(
            vault_address=vault_address.lower(),
            token_address=token_address.lower(),
            enabled=enabled,
            buy_threshold_usd=buy_usd,
            sell_threshold_usd=sell_usd,
            last_executed_ts=last_exec,
            trade_amount=trade_amt,
            base_token=base_token.lower(),
            price_feed=feed_addr,
        )

    except Exception as exc:
        logger.error(
            "getTokenRule failed vault=%s token=%s: %s",
            vault_address,
            token_address,
            exc,
        )
        return None
