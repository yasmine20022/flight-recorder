"""Closed-loop auto-correction — feature 1.

The "wow" loop that turns Flight Recorder from a *debugger* into a *self-improving* system:

    recorded run  →  LLM reads trace + anomalies  →  generates a corrected system prompt
                  →  re-runs the agent (What-If) with it  →  an independent LLM-judge
                     scores before vs after  →  reports whether the fix actually improved it.

No human writes the fix and no ground truth is needed — the judge decides if it got better.
"""
from __future__ import annotations

from typing import Optional

from flight_recorder.core.ai_common import AIUnavailable, chat_json, extract_decision, summarize_trace
from flight_recorder.core.judge import judge_session
from flight_recorder.core.schemas import AutoFixResult
from flight_recorder.core.storage import Storage, storage as default_storage

_SYSTEM = """You are an expert prompt engineer debugging an AI Jira-triage agent.
You are given the agent's CURRENT system prompt, a trace of one run, and detected anomalies.

1. Diagnose the ROOT CAUSE of the wrong or weak decision. Quote the EXACT faulty sentence from
   the current prompt that caused it (verbatim, in double quotes) inside root_cause.
2. Rewrite the FULL system prompt to fix it. You MUST keep the agent's 5-step tool process
   (search_kb -> query_db -> get_user_info -> decide -> send_notification) and the same output
   format ("DECISION: priority=...; assignee=...; reason=..."). Only fix the faulty guidance.
3. Give your confidence in the diagnosis as an integer 0-100.

Return STRICT JSON:
{"root_cause": "<=2 sentences, quoting the faulty rule verbatim>",
 "corrected_prompt": "<the full replacement system prompt>",
 "confidence": <int 0-100>}"""


def auto_fix(session_id: str, *, store: Optional[Storage] = None) -> AutoFixResult:
    """Run the full detect → diagnose → fix → re-run → judge loop for one session."""
    from flight_recorder.agent.graph import SYSTEM_PROMPT
    from flight_recorder.core.anomalies import detect_anomalies
    from flight_recorder.core.whatif import run_whatif

    store = store or default_storage
    original = store.get_session(session_id)
    if original is None:
        raise KeyError(session_id)

    anomalies = detect_anomalies(original)
    user = (
        f"CURRENT SYSTEM PROMPT:\n{SYSTEM_PROMPT}\n\n"
        f"RUN TRACE:\n{summarize_trace(original)}\n\n"
        f"ANOMALIES:\n" + ("\n".join(f"- [{a.severity}] {a.message}" for a in anomalies) or "- none")
    )
    data = chat_json(_SYSTEM, user, max_tokens=1200)
    root_cause = str(data.get("root_cause", "")).strip()
    corrected = str(data.get("corrected_prompt", "")).strip()
    try:
        confidence = max(0, min(100, int(data.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0
    if not corrected:
        raise AIUnavailable("The model did not produce a corrected prompt.")

    # Re-run the agent with the generated prompt (the closed-loop step).
    whatif = run_whatif(session_id, system_prompt=corrected, store=store)

    original_j = judge_session(whatif.original)
    fixed_j = judge_session(whatif.whatif)

    return AutoFixResult(
        root_cause=root_cause,
        corrected_prompt=corrected,
        rca_confidence=confidence,
        original=whatif.original,
        fixed=whatif.whatif,
        original_decision=extract_decision(whatif.original),
        fixed_decision=extract_decision(whatif.whatif),
        original_judgment=original_j,
        fixed_judgment=fixed_j,
        improved=fixed_j.score > original_j.score,
    )
