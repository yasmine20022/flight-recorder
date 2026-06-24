"""Anomaly detector — Bonus 7.

Audits a recorded session for tell-tale problems an operator would care about:
reasoning loops, suspicious tool arguments, failed/rejected tools, runaway length, and
runs that never reached a decision. Pure and deterministic — no LLM involved.
"""
from __future__ import annotations

import json

from flight_recorder.core.schemas import Anomaly, Session, StepType

MAX_REASONABLE_STEPS = 12


def detect_anomalies(session: Session) -> list[Anomaly]:
    steps = session.steps
    anomalies: list[Anomaly] = []

    # 1) Tool calls that failed or were rejected.
    for step in steps:
        if step.type == StepType.TOOL_CALL and isinstance(step.output, dict):
            status = str(step.output.get("status", "")).lower()
            if status in {"rejected", "error", "failed"}:
                anomalies.append(Anomaly(
                    type="tool_error",
                    severity="warning",
                    step_number=step.step_number,
                    message=f"Tool '{step.tool_name}' returned status '{status}'.",
                ))

    # 2) Reasoning loop: the same tool called more than once with identical input.
    occurrences: dict[tuple[str, str], list[int]] = {}
    for step in steps:
        if step.type == StepType.TOOL_CALL:
            key = (step.tool_name or "", json.dumps(step.input or {}, sort_keys=True))
            occurrences.setdefault(key, []).append(step.step_number)
    for (tool, _), nums in occurrences.items():
        if len(nums) > 1:
            anomalies.append(Anomaly(
                type="reasoning_loop",
                severity="warning",
                step_number=nums[1],
                message=(f"Tool '{tool}' was called {len(nums)} times with identical input "
                         f"(steps {nums}) — possible reasoning loop."),
            ))

    # 3) Suspicious argument: notifying an address that get_user_info never returned — a
    #    hallucinated/made-up recipient. Domain-agnostic, so it works with real Jira users.
    known_emails = {
        s.output.get("email")
        for s in steps
        if s.type == StepType.TOOL_CALL and s.tool_name == "get_user_info"
        and isinstance(s.output, dict) and s.output.get("email")
    }
    for step in steps:
        if step.type == StepType.TOOL_CALL and step.tool_name == "send_notification":
            user = str((step.input or {}).get("user", ""))
            if user and user not in known_emails:
                anomalies.append(Anomaly(
                    type="suspicious_argument",
                    severity="critical",
                    step_number=step.step_number,
                    message=(f"send_notification targeted '{user}', which get_user_info never "
                             f"returned — possible hallucinated recipient."),
                ))

    # 4) Runaway length.
    if len(steps) > MAX_REASONABLE_STEPS:
        anomalies.append(Anomaly(
            type="excessive_steps",
            severity="info",
            message=f"Run used {len(steps)} steps (> {MAX_REASONABLE_STEPS}) — unusually long.",
        ))

    # 5) No decision ever reached.
    reached_decision = any(
        s.type == StepType.LLM_CALL and "decision" in (s.response or "").lower()
        for s in steps
    )
    if steps and not reached_decision:
        anomalies.append(Anomaly(
            type="no_decision",
            severity="warning",
            message="The run never produced an explicit DECISION.",
        ))

    return anomalies
