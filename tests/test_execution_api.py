from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.app.main import create_app
from apps.api.v1.routes.vaults import get_db
from libs.db.base import Base
from libs.db.models import ExecutionRequest, Vault


class DummyTask:
    def __init__(self):
        self.calls: list[int] = []

    def delay(self, execution_id: int):
        self.calls.append(execution_id)


def build_client():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    app = create_app()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app, TestingSessionLocal


def test_execute_and_fetch_status(monkeypatch):
    app, SessionLocal = build_client()

    dummy = DummyTask()
    monkeypatch.setattr("apps.api.v1.routes.vaults.process_execution", dummy)

    with SessionLocal() as db:
        db.add(Vault(chain_id=84532, address="0x1111111111111111111111111111111111111111"))
        db.commit()

    client = TestClient(app)
    res = client.post(
        "/api/v1/vaults/0x1111111111111111111111111111111111111111/action/execute",
        json={"action": "buy", "metadata": {"foo": "bar"}},
    )
    assert res.status_code == 200
    execution_id = res.json()["execution_id"]
    assert dummy.calls == [execution_id]

    status_res = client.get(f"/api/v1/executions/{execution_id}")
    assert status_res.status_code == 200
    payload = status_res.json()
    assert payload["status"] == "queued"
    assert payload["attempts"] == []


def test_swap_requires_swap_payload(monkeypatch):
    app, SessionLocal = build_client()
    monkeypatch.setattr("apps.api.v1.routes.vaults.process_execution", DummyTask())

    with SessionLocal() as db:
        db.add(Vault(chain_id=84532, address="0x3333333333333333333333333333333333333333"))
        db.commit()

    client = TestClient(app)
    res = client.post(
        "/api/v1/vaults/0x3333333333333333333333333333333333333333/action/execute",
        json={"action": "swap"},
    )
    assert res.status_code == 422


def test_shield_requires_shield_payload(monkeypatch):
    app, SessionLocal = build_client()
    monkeypatch.setattr("apps.api.v1.routes.vaults.process_execution", DummyTask())

    with SessionLocal() as db:
        db.add(Vault(chain_id=84532, address="0x4444444444444444444444444444444444444444"))
        db.commit()

    client = TestClient(app)
    res = client.post(
        "/api/v1/vaults/0x4444444444444444444444444444444444444444/action/execute",
        json={"action": "shield"},
    )
    assert res.status_code == 422


def test_duplicate_idempotency_key_returns_409(monkeypatch):
    app, SessionLocal = build_client()
    monkeypatch.setattr("apps.api.v1.routes.vaults.process_execution", DummyTask())

    with SessionLocal() as db:
        db.add(Vault(chain_id=84532, address="0x2222222222222222222222222222222222222222"))
        db.commit()

    client = TestClient(app)
    headers = {"Idempotency-Key": "same-key"}
    url = "/api/v1/vaults/0x2222222222222222222222222222222222222222/action/execute"

    first = client.post(url, json={"action": "sell"}, headers=headers)
    second = client.post(url, json={"action": "sell"}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 409

    with SessionLocal() as db:
        total = db.query(ExecutionRequest).count()
        assert total == 1
