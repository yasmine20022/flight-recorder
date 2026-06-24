"""LLM-as-Judge — feature 4.

A stronger, *independent* model reviews whether the triage agent's decision was reasonably
justified **by the evidence it actually gathered** — with no predefined "correct answer".
This is what you need in production, where ground truth doesn't exist up front.
"""
from __future__ import annotations

from flight_recorder.config import settings
from flight_recorder.core.ai_common import chat_json, mistral_json, summarize_trace
from flight_recorder.core.schemas import Judgment, Session

_SYSTEM = """You are a senior IT service-desk reviewer auditing an AI triage agent.
There is NO predefined correct answer. Judge ONLY whether the agent's final decision
(team, priority, assignee) is reasonably justified by the evidence it gathered in the trace
(the knowledge-base hit, the past-ticket history, the user it looked up).

Penalise: ignoring the evidence, contradicting the knowledge base, under/over-prioritising a
clear production outage, notifying a recipient it never looked up, or skipping required steps.

Return STRICT JSON:
{"score": <int 0-10>, "verdict": "sound" | "questionable" | "flawed",
 "rationale": "<=2 sentences", "issues": ["short issue", ...]}"""


def judge_session(session: Session, *, model: str | None = None) -> Judgment:
    """Score the quality of ``session``'s final decision.

    Prefers Mistral (an independent provider) when configured, so the reviewer is genuinely
    different from the Groq agent it judges; otherwise falls back to the Groq judge model.
    """
    summary = summarize_trace(session)
    if settings.mistral_api_key:
        used = model or settings.mistral_model
        data = mistral_json(_SYSTEM, summary, model=used, max_tokens=500)
    else:
        used = model or settings.groq_judge_model
        data = chat_json(_SYSTEM, summary, model=used, max_tokens=500)
    model = used

    score = int(data.get("score", 0))
    score = max(0, min(10, score))
    verdict = str(data.get("verdict", "")).lower()
    if verdict not in {"sound", "questionable", "flawed"}:
        verdict = "sound" if score >= 7 else "questionable" if score >= 4 else "flawed"
    issues = [str(i) for i in (data.get("issues") or [])][:6]
    return Judgment(
        score=score,
        verdict=verdict,
        rationale=str(data.get("rationale", "")).strip(),
        issues=issues,
        model=model,
    )
