"""Tests for the anomaly detector (Bonus 7)."""
from __future__ import annotations

from flight_recorder.core.anomalies import detect_anomalies
from flight_recorder.core.schemas import Session, Step, StepType


def _session(steps) -> Session:
    return Session(session_id="s", ticket_id="JSM-1", ticket_text="x", steps=steps)


def _types(anomalies):
    return {a.type for a in anomalies}


def test_clean_session_has_no_critical_anomalies():
    steps = [
        Step(step_number=1, type=StepType.LLM_CALL, prompt="p", response="searching"),
        Step(step_number=2, type=StepType.TOOL_CALL, tool_name="search_kb",
             input={"query": "vpn"}, output={"found": True}),
        # The agent looked the recipient up before notifying them — a clean run.
        Step(step_number=3, type=StepType.TOOL_CALL, tool_name="get_user_info",
             input={"team_name": "Network"}, output={"email": "alice.martin@corp.example"}),
        Step(step_number=4, type=StepType.TOOL_CALL, tool_name="send_notification",
             input={"user": "alice.martin@corp.example"}, output={"status": "sent"}),
        Step(step_number=5, type=StepType.LLM_CALL, prompt="p2",
             response="DECISION: priority=High; assignee=Alice"),
    ]
    assert detect_anomalies(_session(steps)) == []


def test_detects_reasoning_loop():
    steps = [
        Step(step_number=1, type=StepType.TOOL_CALL, tool_name="get_user_info",
             input={"team_name": "Network"}, output={"name": "A"}),
        Step(step_number=2, type=StepType.TOOL_CALL, tool_name="get_user_info",
             input={"team_name": "Network"}, output={"name": "A"}),
        Step(step_number=3, type=StepType.LLM_CALL, response="DECISION: x"),
    ]
    assert "reasoning_loop" in _types(detect_anomalies(_session(steps)))


def test_detects_suspicious_recipient():
    steps = [
        Step(step_number=1, type=StepType.TOOL_CALL, tool_name="send_notification",
             input={"user": "john.doe@example.com"}, output={"status": "sent"}),
        Step(step_number=2, type=StepType.LLM_CALL, response="DECISION: x"),
    ]
    anomalies = detect_anomalies(_session(steps))
    assert any(a.type == "suspicious_argument" and a.severity == "critical" for a in anomalies)


def test_detects_rejected_tool():
    steps = [
        Step(step_number=1, type=StepType.TOOL_CALL, tool_name="send_notification",
             input={"user": "x"}, output={"status": "rejected"}),
        Step(step_number=2, type=StepType.LLM_CALL, response="DECISION: x"),
    ]
    assert "tool_error" in _types(detect_anomalies(_session(steps)))


def test_detects_no_decision():
    steps = [Step(step_number=1, type=StepType.LLM_CALL, response="just thinking")]
    assert "no_decision" in _types(detect_anomalies(_session(steps)))
