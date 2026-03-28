"""Chainlink AggregatorV3 price feed reader.

Fetches the latest USD price for a token from an on-chain Chainlink feed.
Price is returned as a plain float in USD (e.g. 1834.72).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from web3 import Web3

logger = logging.getLogger(__name__)

AGGREGATOR_V3_ABI = [
    {
        "name": "latestRoundData",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "roundId", "type": "uint80"},
            {"name": "answer", "type": "int256"},
            {"name": "startedAt", "type": "uint256"},
            {"name": "updatedAt", "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"},
        ],
    },
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
]


@dataclass
class PriceResult:
    price_usd: float
    updated_at: datetime
    feed_address: str
    stale: bool = False


def get_chainlink_price(
    w3: Web3,
    feed_address: str,
    stale_seconds: int = 3600,
) -> PriceResult | None:
    """Read latestRoundData from a Chainlink AggregatorV3 feed.

    Args:
        w3: Connected Web3 instance.
        feed_address: Chainlink price feed contract address.
        stale_seconds: Mark price as stale if updatedAt is older than this.

    Returns:
        PriceResult with price in USD, or None on error.
    """
    try:
        feed = w3.eth.contract(
            address=Web3.to_checksum_address(feed_address),
            abi=AGGREGATOR_V3_ABI,
        )
        decimals: int = feed.functions.decimals().call()
        _, answer, _, updated_at_ts, _ = feed.functions.latestRoundData().call()

        if answer <= 0:
            logger.warning(
                "feed=%s returned non-positive answer=%s", feed_address, answer
            )
            return None

        price_usd = answer / (10**decimals)
        updated_at = datetime.fromtimestamp(updated_at_ts, tz=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
        stale = age_seconds > stale_seconds

        if stale:
            logger.warning(
                "feed=%s price stale by %.0fs (threshold=%ss)",
                feed_address,
                age_seconds,
                stale_seconds,
            )

        logger.debug(
            "feed=%s price=%.4f updated_at=%s stale=%s",
            feed_address,
            price_usd,
            updated_at.isoformat(),
            stale,
        )
        return PriceResult(
            price_usd=price_usd,
            updated_at=updated_at,
            feed_address=feed_address,
            stale=stale,
        )

    except Exception as exc:
        logger.error("price feed read failed feed=%s: %s", feed_address, exc)
        return None
