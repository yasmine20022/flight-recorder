"""Shared helpers for the AI-analysis layer (LLM-judge, auto-fix, pattern insights).

These features call a *stronger, independent* model (the judge model) in strict JSON mode to
review the small triage agent's work. Kept separate from the agent so the reviewer can never
be confused with the thing being reviewed.
"""
from __future__ import annotations

import json
import re
from typing import Any

from flight_recorder.config import settings
from flight_recorder.core.schemas import Session, StepType


class AIUnavailable(RuntimeError):
    """Raised when the analysis LLM cannot be reached or returns nothing usable."""


def chat_json(system: str, user: str, *, model: str | None = None, max_tokens: int = 900) -> dict[str, Any]:
    """Call Groq in JSON mode and return the parsed object. Deterministic (temperature 0)."""
    if not settings.groq_api_key:
        raise AIUnavailable("GROQ_API_KEY is not set.")
    import groq

    client = groq.Groq(api_key=settings.groq_api_key, max_retries=settings.groq_max_retries)
    try:
        resp = client.chat.completions.create(
            model=model or settings.groq_judge_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except groq.GroqError as exc:
        raise AIUnavailable(str(exc)) from exc

    content = resp.choices[0].message.content or ""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)  # be forgiving
        if match:
            return json.loads(match.group(0))
        raise AIUnavailable("Model did not return valid JSON.")


def mistral_json(system: str, user: str, *, model: str | None = None, max_tokens: int = 900) -> dict[str, Any]:
    """Call Mistral's (OpenAI-compatible) chat API in JSON mode — the independent judge."""
    if not settings.mistral_api_key:
        raise AIUnavailable("MISTRAL_API_KEY is not set.")
    import httpx

    try:
        resp = httpx.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.mistral_api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": model or settings.mistral_model,
                "temperature": 0,
                "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
            },
            timeout=45.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise AIUnavailable(f"Mistral call failed: {exc}") from exc

    content = resp.json()["choices"][0]["message"]["content"] or ""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise AIUnavailable("Mistral did not return valid JSON.")


def extract_decision(session: Session) -> str:
    """The agent's final DECISION line (or last LLM response)."""
    for s in reversed(session.steps):
        if s.type == StepType.LLM_CALL and s.response and "decision" in s.response.lower():
            return s.response.strip()
    for s in reversed(session.steps):
        if s.type == StepType.LLM_CALL and s.response:
            return s.response.strip()
    return "(no decision reached)"


def parse_decision(text: str) -> dict[str, str]:
    """Pull priority / assignee out of a 'DECISION: priority=…; assignee=…' line."""
    out: dict[str, str] = {}
    m = re.search(r"priority\s*=\s*([A-Za-z]+)", text)
    if m:
        out["priority"] = m.group(1)
    m = re.search(r"assignee\s*=\s*([^;]+?)(?:\s*<|;|$)", text)
    if m:
        out["assignee"] = m.group(1).strip()
    return out


def summarize_trace(session: Session, *, max_steps: int = 16) -> str:
    """Compact, token-cheap rendering of a run for the analysis LLM."""
    lines = [f'Ticket {session.ticket_id}: "{session.ticket_text}"', "Steps:"]
    for s in session.steps[:max_steps]:
        if s.type == StepType.LLM_CALL:
            lines.append(f"  LLM: {(s.response or '').strip()[:160]}")
        else:
            inp = json.dumps(s.input or {}, ensure_ascii=False)[:120]
            out = json.dumps(s.output or {}, ensure_ascii=False)[:160]
            lines.append(f"  TOOL {s.tool_name}({inp}) -> {out}")
    lines.append("Final decision: " + extract_decision(session))
    return "\n".join(lines)
