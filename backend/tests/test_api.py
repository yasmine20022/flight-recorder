"""Tests for the FastAPI endpoints (Sprint 0 read endpoints + stubs)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from flight_recorder.api import main as api_main
from flight_recorder.core.schemas import Session, Step, StepType
from flight_recorder.core.storage import Storage


@pytest.fixture()
def client(tmp_storage: Storage, monkeypatch) -> TestClient:
    # Point the API at a throwaway database and seed one session.
    monkeypatch.setattr(api_main, "storage", tmp_storage)
    tmp_storage.save_session(
        Session(
            session_id="s1",
            ticket_id="JSM-1",
            ticket_text="VPN broken",
            steps=[Step(step_number=1, type=StepType.LLM_CALL, prompt="p", response="r")],
        )
    )
    return TestClient(api_main.app)


def test_health(client: TestClient):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_list_sessions(client: TestClient):
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["session_id"] == "s1"
    assert "steps" not in body[0]  # summary endpoint omits steps


def test_get_session_detail(client: TestClient):
    resp = client.get("/api/sessions/s1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticket_id"] == "JSM-1"
    assert len(body["steps"]) == 1


def test_get_unknown_session_404(client: TestClient):
    assert client.get("/api/sessions/nope").status_code == 404


def test_replay_endpoint_returns_counters(client: TestClient):
    resp = client.post("/api/sessions/s1/replay")
    assert resp.status_code == 200
    body = resp.json()
    assert body["real_calls"] == 0
    assert body["intercepted_calls"] == 1  # the seeded s1 has one step
    assert body["session"]["mode"] == "replay"


def test_replay_unknown_session_404(client: TestClient):
    assert client.post("/api/sessions/nope/replay").status_code == 404


def test_audit_endpoints(client: TestClient):
    # anomalies
    a = client.get("/api/sessions/s1/anomalies")
    assert a.status_code == 200
    assert isinstance(a.json(), list)
    # signature
    s = client.get("/api/sessions/s1/signature")
    assert s.status_code == 200
    body = s.json()
    assert body["verified"] is True and body["algorithm"] == "HMAC-SHA256"
    # pdf
    p = client.get("/api/sessions/s1/report.pdf")
    assert p.status_code == 200
    assert p.headers["content-type"] == "application/pdf"
    assert p.content.startswith(b"%PDF")


def test_audit_unknown_session_404(client: TestClient):
    assert client.get("/api/sessions/nope/anomalies").status_code == 404
    assert client.get("/api/sessions/nope/signature").status_code == 404
    assert client.get("/api/sessions/nope/report.pdf").status_code == 404


def test_whatif_endpoint_returns_both_trajectories(client: TestClient, monkeypatch):
    # Stub the divergence run so the test does not hit the LLM.
    from flight_recorder.core import whatif as whatif_mod
    from flight_recorder.core.schemas import Session, Step, StepType
    from flight_recorder.core.whatif import WhatIfResult

    def fake_run_whatif(session_id, tool_name, new_output, *, store):
        original = store.get_session(session_id)
        whatif = Session(
            session_id=f"{session_id}__whatif_abcd",
            ticket_id=original.ticket_id,
            ticket_text=original.ticket_text,
            mode="whatif",
            steps=[Step(step_number=1, type=StepType.LLM_CALL, prompt="p", response="new decision")],
        )
        return WhatIfResult(original=original, whatif=whatif, overridden_tool=tool_name)

    monkeypatch.setattr(whatif_mod, "run_whatif", fake_run_whatif)

    resp = client.post(
        "/api/sessions/s1/whatif",
        json={"tool_name": "get_user_info", "new_output": {"name": "Grace Kim"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["overridden_tool"] == "get_user_info"
    assert body["whatif"]["mode"] == "whatif"
    assert body["original"]["session_id"] == "s1"


def test_run_endpoint_records_and_returns_session(client: TestClient, monkeypatch):
    # Stub the live run so the test does not hit the LLM; just verify the wiring.
    from flight_recorder.core import runner
    from flight_recorder.core.schemas import Session, Step, StepType

    def fake_record(ticket_id, ticket_text):
        return Session(
            session_id="run_fake_1",
            ticket_id=ticket_id,
            ticket_text=ticket_text,
            steps=[Step(step_number=1, type=StepType.LLM_CALL, prompt="p", response="r")],
        )

    monkeypatch.setattr(runner, "record_ticket", fake_record)

    resp = client.post("/api/runs", json={"ticket_id": "JSM-9", "ticket_text": "VPN down"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticket_id"] == "JSM-9"
    assert len(body["steps"]) == 1
