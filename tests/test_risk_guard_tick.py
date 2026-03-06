from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.worker import tasks
from libs.db.base import Base
from libs.db.models import Vault, VaultEvent


class FakeRedis:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.keys:
            return False
        self.keys.add(key)
        return True


class DelayRecorder:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def __call__(self, message: str) -> None:
        self.messages.append(message)


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _seed_vault_and_events(*, session_factory, stale_price: bool = False, fail_event: bool = False):
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        vault = Vault(chain_id=84532, address="0xabc", created_block_number=1)
        db.add(vault)
        db.flush()

        price_ts = now - timedelta(minutes=10) if stale_price else now
        db.add(
            VaultEvent(
                chain_id=84532,
                vault_address=vault.address,
                event_type="PriceObserved",
                block_number=10,
                tx_hash="0xprice",
                log_index=0,
                timestamp=price_ts,
                payload_json={"price": 123.45},
            )
        )

        if fail_event:
            db.add(
                VaultEvent(
                    chain_id=84532,
                    vault_address=vault.address,
                    event_type="ExecutionFailed",
                    block_number=11,
                    tx_hash="0xfail",
                    log_index=1,
                    timestamp=now,
                    payload_json={"reason": "slippage"},
                )
            )

        db.commit()


def test_risk_guard_tick_sends_alert_for_stale_price(monkeypatch) -> None:
    session_factory = _session_factory()
    _seed_vault_and_events(session_factory=session_factory, stale_price=True, fail_event=False)

    fake_redis = FakeRedis()
    recorder = DelayRecorder()

    monkeypatch.setattr(tasks, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(tasks.Redis, "from_url", lambda _url: fake_redis)
    monkeypatch.setattr(tasks.notify_telegram, "delay", recorder)

    result = tasks.risk_guard_tick()

    assert result["inspected"] == 1
    assert result["alerts_sent"] == 1
    assert result["alerts_skipped"] == 0
    assert len(recorder.messages) == 1
    assert "Stale price detected" in recorder.messages[0]


def test_risk_guard_tick_dedupes_repeated_alerts(monkeypatch) -> None:
    session_factory = _session_factory()
    _seed_vault_and_events(session_factory=session_factory, stale_price=True, fail_event=False)

    fake_redis = FakeRedis()
    recorder = DelayRecorder()

    monkeypatch.setattr(tasks, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(tasks.Redis, "from_url", lambda _url: fake_redis)
    monkeypatch.setattr(tasks.notify_telegram, "delay", recorder)

    first = tasks.risk_guard_tick()
    second = tasks.risk_guard_tick()

    assert first["alerts_sent"] == 1
    assert second["alerts_sent"] == 0
    assert second["alerts_skipped"] == 1
    assert len(recorder.messages) == 1


def test_risk_guard_tick_sends_alert_for_failure_event(monkeypatch) -> None:
    session_factory = _session_factory()
    _seed_vault_and_events(session_factory=session_factory, stale_price=False, fail_event=True)

    fake_redis = FakeRedis()
    recorder = DelayRecorder()

    monkeypatch.setattr(tasks, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(tasks.Redis, "from_url", lambda _url: fake_redis)
    monkeypatch.setattr(tasks.notify_telegram, "delay", recorder)

    result = tasks.risk_guard_tick()

    assert result["inspected"] == 1
    assert result["alerts_sent"] == 1
    assert len(recorder.messages) == 1
    assert "Execution risk alert" in recorder.messages[0]
