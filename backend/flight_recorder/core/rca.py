"""Lightweight Root-Cause Analysis — auto-loaded in ANALYZE mode.

One LLM call: explain *why* the agent made the wrong/weak decision and quote the EXACT
faulty sentence from its prompt. Cheaper than the full auto-fix loop, so it can load
automatically when the user opens the ANALYZE view.
"""
from __future__ import annotations

from flight_recorder.config import settings
from flight_recorder.core.ai_common import chat_json, summarize_trace
from flight_recorder.core.schemas import RcaResult, Session

_SYSTEM = """You are debugging an AI Jira-triage agent. Given its CURRENT system prompt, a run
trace, and detected anomalies, explain WHY it made the wrong or weak decision.

You MUST quote the exact faulty sentence from the prompt, verbatim, in faulty_quote (copy it
character-for-character; empty string only if no single sentence is at fault).

Return STRICT JSON:
{"root_cause": "<=2 sentences", "faulty_quote": "<exact sentence from the prompt>",
 "confidence": <int 0-100>, "fix_summary": "<one-line fix>"}"""


def diagnose(session: Session) -> RcaResult:
    """Diagnose one run's root cause (single LLM call)."""
    from flight_recorder.agent.graph import SYSTEM_PROMPT
    from flight_recorder.core.anomalies import detect_anomalies

    anomalies = detect_anomalies(session)
    user = (
        f"CURRENT SYSTEM PROMPT:\n{SYSTEM_PROMPT}\n\n"
        f"RUN TRACE:\n{summarize_trace(session)}\n\n"
        "ANOMALIES:\n" + ("\n".join(f"- [{a.severity}] {a.message}" for a in anomalies) or "- none")
    )
    data = chat_json(_SYSTEM, user, model=settings.groq_judge_model, max_tokens=500)
    try:
        confidence = max(0, min(100, int(data.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0
    return RcaResult(
        root_cause=str(data.get("root_cause", "")).strip(),
        faulty_quote=str(data.get("faulty_quote", "")).strip(),
        confidence=confidence,
        fix_summary=str(data.get("fix_summary", "")).strip(),
        model=settings.groq_judge_model,
    )
