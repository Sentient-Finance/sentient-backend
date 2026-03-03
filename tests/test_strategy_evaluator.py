from datetime import datetime, timedelta, timezone

from libs.core.strategy import StrategyRule, evaluate_rule


def test_buy_signal_hits_threshold() -> None:
    rule = StrategyRule(
        vault_address="0xabc",
        buy_threshold=1900,
        sell_threshold=2300,
        cooldown_seconds=300,
        last_executed_at=None,
    )

    result = evaluate_rule(rule, current_price=1850)

    assert result.trigger is True
    assert result.action == "buy"


def test_sell_signal_hits_threshold() -> None:
    rule = StrategyRule(
        vault_address="0xabc",
        buy_threshold=1900,
        sell_threshold=2300,
        cooldown_seconds=300,
        last_executed_at=None,
    )

    result = evaluate_rule(rule, current_price=2350)

    assert result.trigger is True
    assert result.action == "sell"


def test_cooldown_blocks_signal() -> None:
    now = datetime.now(timezone.utc)
    rule = StrategyRule(
        vault_address="0xabc",
        buy_threshold=1900,
        sell_threshold=2300,
        cooldown_seconds=300,
        last_executed_at=now - timedelta(seconds=120),
    )

    result = evaluate_rule(rule, current_price=1800, now=now)

    assert result.trigger is False
    assert result.reason == "cooldown_not_met"
