from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

Action = Literal["buy", "sell"]


@dataclass
class StrategyRule:
    vault_address: str
    buy_threshold: float | None
    sell_threshold: float | None
    cooldown_seconds: int
    last_executed_at: datetime | None


@dataclass
class StrategyDecision:
    trigger: bool
    action: Action | None
    reason: str


def evaluate_rule(
    rule: StrategyRule, current_price: float, now: datetime | None = None
) -> StrategyDecision:
    ts = now or datetime.now(timezone.utc)

    if current_price <= 0:
        return StrategyDecision(False, None, "invalid_price")

    if rule.last_executed_at is not None:
        elapsed = (ts - rule.last_executed_at).total_seconds()
        if elapsed < rule.cooldown_seconds:
            return StrategyDecision(False, None, "cooldown_not_met")

    if rule.buy_threshold is not None and current_price <= rule.buy_threshold:
        return StrategyDecision(True, "buy", "buy_threshold_hit")

    if rule.sell_threshold is not None and current_price >= rule.sell_threshold:
        return StrategyDecision(True, "sell", "sell_threshold_hit")

    return StrategyDecision(False, None, "no_signal")
