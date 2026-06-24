"""Tests for the M1–M6 evaluation dashboard. LLM calls are mocked; the key guarantee is that
six cards are always returned — even when the AI metrics fall back (rate limit)."""
from __future__ import annotations

from flight_recorder.core.ai_common import AIUnavailable
from flight_recorder.core.schemas import (
    AutoFixResult, Judgment, Session, SessionMode, Step, StepType,
)
from flight_recorder.core.storage import Storage


def _seed(store, sid, *, team="Network", kb="Network", decision="DECISION: priority=High; assignee=A"):
    store.save_session(Session(
        session_id=sid, ticket_id="JSM-1", ticket_text="x", mode=SessionMode.LIVE,
        steps=[
            Step(step_number=1, type=StepType.TOOL_CALL, tool_name="search_kb",
                 input={"query": "q"}, output={"found": True, "category": kb}),
            Step(step_number=2, type=StepType.TOOL_CALL, tool_name="get_user_info",
                 input={"team_name": team}, output={"email": "a@b.c"}),
            Step(step_number=3, type=StepType.LLM_CALL, prompt="p", response=decision, model="m"),
        ],
    ))


def _raise(*a, **k):
    raise AIUnavailable("rate limited")


def test_metrics_always_returns_six_cards_on_ai_fallback(tmp_storage: Storage, monkeypatch):
    from flight_recorder.core import autofix as A, judge as J, metrics as M
    monkeypatch.setattr(J, "judge_session", _raise)
    monkeypatch.setattr(A, "auto_fix", _raise)

    _seed(tmp_storage, "r1", team="Network", kb="Network")    # routed matches KB
    _seed(tmp_storage, "r2", team="Frontend", kb="Backend")   # mismatch

    rep = M.compute_metrics(store=tmp_storage, refresh=True)
    assert [m.id for m in rep.metrics] == ["M1", "M2", "M3", "M4", "M5", "M6"]
    assert rep.total_runs == 2
    m1 = next(m for m in rep.metrics if m.id == "M1")
    assert m1.value == 50.0  # 1 of 2 routed to the KB-matching team


def test_metrics_ai_success_path(tmp_storage: Storage, monkeypatch):
    from flight_recorder.core import autofix as A, judge as J, metrics as M
    monkeypatch.setattr(J, "judge_session",
                        lambda s, **k: Judgment(score=8, verdict="sound", rationale="r", model="j"))

    def fake_autofix(session_id, *, store=None):
        orig = store.get_session(session_id)
        return AutoFixResult(
            root_cause='"front-end display problem" rule misrouted it', corrected_prompt="fixed",
            rca_confidence=85, original=orig, fixed=orig,
            original_decision="d", fixed_decision="d2",
            original_judgment=Judgment(score=4, verdict="questionable", rationale="r"),
            fixed_judgment=Judgment(score=9, verdict="sound", rationale="r"), improved=True)
    monkeypatch.setattr(A, "auto_fix", fake_autofix)

    _seed(tmp_storage, "r1")
    rep = M.compute_metrics(store=tmp_storage, refresh=True)
    by = {m.id: m for m in rep.metrics}
    assert by["M3"].value == 50.0   # (9 - 4) * 10 quality points gained
    assert by["M4"].value == 80.0   # judge 8/10 -> 80%
    assert by["M6"].value == 85.0   # RCA confidence
    assert by["M6"].ai and by["M4"].ai and by["M3"].ai
