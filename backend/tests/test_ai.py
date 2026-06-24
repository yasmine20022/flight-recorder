"""Tests for the AI-analysis layer (judge · auto-fix · patterns). LLM calls are mocked."""
from __future__ import annotations

from flight_recorder.core.schemas import Judgment, Session, SessionMode, Step, StepType
from flight_recorder.core.storage import Storage


def _session(store, sid, decision, team="Network"):
    store.save_session(Session(
        session_id=sid, ticket_id="JSM-1", ticket_text="VPN broken", mode=SessionMode.LIVE,
        steps=[
            Step(step_number=1, type=StepType.TOOL_CALL, tool_name="get_user_info",
                 input={"team_name": team}, output={"email": "a@b.c"}),
            Step(step_number=2, type=StepType.LLM_CALL, prompt="p", response=decision, model="m"),
        ],
    ))


# ── feature 4: LLM-as-Judge ──
def test_judge_session_returns_score(tmp_storage: Storage, monkeypatch):
    from flight_recorder.core import judge as judge_mod
    monkeypatch.setattr(judge_mod, "chat_json", lambda *a, **k: {
        "score": 9, "verdict": "sound", "rationale": "well justified", "issues": []})

    _session(tmp_storage, "s1", "DECISION: priority=High; assignee=Alice")
    j = judge_mod.judge_session(tmp_storage.get_session("s1"))
    assert j.score == 9 and j.verdict == "sound" and j.model


def test_judge_derives_verdict_when_missing(tmp_storage: Storage, monkeypatch):
    from flight_recorder.core import judge as judge_mod
    monkeypatch.setattr(judge_mod, "chat_json", lambda *a, **k: {"score": 2, "rationale": "bad"})
    _session(tmp_storage, "s1", "DECISION: x")
    j = judge_mod.judge_session(tmp_storage.get_session("s1"))
    assert j.verdict == "flawed"  # derived from the low score


def test_judge_uses_mistral_when_configured(tmp_storage: Storage, monkeypatch):
    from flight_recorder.config import settings
    from flight_recorder.core import judge as judge_mod

    monkeypatch.setattr(settings, "mistral_api_key", "test-key")  # independent provider
    monkeypatch.setattr(judge_mod, "mistral_json",
                        lambda *a, **k: {"score": 7, "verdict": "sound", "rationale": "r", "issues": []})

    _session(tmp_storage, "s1", "DECISION: x")
    j = judge_mod.judge_session(tmp_storage.get_session("s1"))
    assert j.score == 7 and j.model == settings.mistral_model  # judged by Mistral, not Groq


# ── feature 1: auto-fix closed loop ──
def test_auto_fix_reports_improvement(tmp_storage: Storage, monkeypatch):
    from flight_recorder.core import autofix as autofix_mod
    from flight_recorder.core import whatif as whatif_mod
    from flight_recorder.core.whatif import WhatIfResult

    _session(tmp_storage, "run_1", "DECISION: priority=High; assignee=Frontend")

    monkeypatch.setattr(autofix_mod, "chat_json", lambda *a, **k: {
        "root_cause": "Buggy routing rule sends API tickets to Frontend.",
        "corrected_prompt": "FIXED PROMPT: route API 500s to Backend / Critical."})

    def fake_run_whatif(session_id, system_prompt=None, store=None, **kw):
        original = store.get_session(session_id)
        fixed = Session(session_id=f"{session_id}__wf", ticket_id=original.ticket_id,
                        ticket_text=original.ticket_text, mode=SessionMode.WHATIF,
                        steps=[Step(step_number=1, type=StepType.LLM_CALL, prompt="p",
                                    response="DECISION: priority=Critical; assignee=Backend")])
        return WhatIfResult(original=original, whatif=fixed,
                            overridden_tool="system prompt", override_kind="system_prompt")
    monkeypatch.setattr(whatif_mod, "run_whatif", fake_run_whatif)

    def fake_judge(session, model=None):
        dec = next((s.response for s in reversed(session.steps)
                    if s.type == StepType.LLM_CALL and s.response), "")
        score = 9 if "critical" in dec.lower() else 4
        return Judgment(score=score, verdict="sound" if score >= 7 else "questionable",
                        rationale="r", model="judge")
    monkeypatch.setattr(autofix_mod, "judge_session", fake_judge)

    result = autofix_mod.auto_fix("run_1", store=tmp_storage)
    assert "Frontend" in result.root_cause
    assert result.corrected_prompt.startswith("FIXED PROMPT")
    assert result.original_judgment.score == 4 and result.fixed_judgment.score == 9
    assert result.improved is True


# ── feature 2: multi-run patterns ──
def test_analyze_patterns_aggregates_and_summarises(tmp_storage: Storage, monkeypatch):
    from flight_recorder.core import patterns as patterns_mod
    monkeypatch.setattr(patterns_mod, "chat_json", lambda *a, **k: {
        "summary": "API tickets are systematically misrouted.",
        "weaknesses": ["API→Frontend"], "recommendations": ["fix routing rule"]})

    _session(tmp_storage, "r1", "DECISION: priority=High; assignee=A", team="Network")
    _session(tmp_storage, "r2", "DECISION: priority=Critical; assignee=B", team="Backend")
    _session(tmp_storage, "r3", "DECISION: priority=High; assignee=C", team="Network")

    rep = patterns_mod.analyze_patterns(store=tmp_storage)
    assert rep.total_runs == 3
    assert rep.by_team == {"Network": 2, "Backend": 1}
    assert rep.by_priority.get("High") == 2 and rep.by_priority.get("Critical") == 1
    assert rep.avg_steps == 2.0
    assert "misrouted" in rep.summary and rep.recommendations


def test_analyze_patterns_empty(tmp_storage: Storage):
    from flight_recorder.core import patterns as patterns_mod
    rep = patterns_mod.analyze_patterns(store=tmp_storage)
    assert rep.total_runs == 0 and rep.summary == ""


# ── lightweight RCA (ANALYZE mode) ──
def test_rca_diagnose_quotes_faulty_rule(tmp_storage: Storage, monkeypatch):
    from flight_recorder.core import rca as rca_mod
    monkeypatch.setattr(rca_mod, "chat_json", lambda *a, **k: {
        "root_cause": "An over-broad routing rule.", "faulty_quote": "assign it to the Frontend team",
        "confidence": 88, "fix_summary": "Route API 500s to Backend."})

    _session(tmp_storage, "s1", "DECISION: priority=High; assignee=Frontend")
    r = rca_mod.diagnose(tmp_storage.get_session("s1"))
    assert r.confidence == 88 and "Frontend" in r.faulty_quote and r.root_cause


# ── multi-ticket diff (FIXED badges) ──
def test_build_diff_marks_fixed(tmp_storage: Storage, monkeypatch):
    from flight_recorder.core import autofix as autofix_mod, diff as diff_mod
    from flight_recorder.core.schemas import AutoFixResult

    _session(tmp_storage, "r1", "DECISION: priority=High; assignee=Frontend")

    def fake_autofix(session_id, *, store=None):
        orig = store.get_session(session_id)
        return AutoFixResult(
            root_cause="x", corrected_prompt="y", rca_confidence=80, original=orig, fixed=orig,
            original_decision="priority=High; assignee=Frontend",
            fixed_decision="priority=Critical; assignee=Backend",
            original_judgment=Judgment(score=4, verdict="questionable", rationale="r"),
            fixed_judgment=Judgment(score=9, verdict="sound", rationale="r"), improved=True)
    monkeypatch.setattr(autofix_mod, "auto_fix", fake_autofix)

    rep = diff_mod.build_diff(store=tmp_storage, limit=2, refresh=True)
    assert len(rep.rows) == 1 and rep.fixed_count == 1
    assert rep.rows[0].fixed is True and rep.rows[0].fixed_score == 9
