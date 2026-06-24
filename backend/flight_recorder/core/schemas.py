"""Pydantic models that ARE the contract (see docs/CONTRACT.md).

These models are the single source of truth for the trace shape shared between the
backend and the frontend. Changing them changes the contract — coordinate with the team.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    """ISO-8601 UTC timestamp, e.g. 2026-06-17T09:00:00Z."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class StepType(str, Enum):
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"


class SessionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class SessionMode(str, Enum):
    LIVE = "live"
    REPLAY = "replay"
    WHATIF = "whatif"


class Step(BaseModel):
    """One fine-grained step: either an LLM call or a tool call.

    Fields irrelevant to the step's ``type`` are left as ``None`` (see CONTRACT.md).
    """

    step_number: int = Field(..., ge=1, description="1-based order within the session")
    type: StepType
    timestamp: str = Field(default_factory=_utcnow_iso)
    duration_ms: int = Field(default=0, ge=0)

    # llm_call fields
    prompt: Optional[str] = None
    response: Optional[str] = None
    # Provenance of a real LLM call — proves the step hit Groq, not a mock.
    model: Optional[str] = None
    tokens: Optional[int] = None

    # tool_call fields
    tool_name: Optional[str] = None
    input: Optional[dict[str, Any]] = None
    output: Optional[dict[str, Any]] = None

    # Serialized AIMessage for an llm_call (langchain message dict). Internal: lets the
    # proxy replay the exact tool-call decisions without hitting the LLM. Not shown in UI.
    ai_message: Optional[dict[str, Any]] = None


class SessionSummary(BaseModel):
    """Lightweight session row returned by ``GET /api/sessions`` (no steps)."""

    session_id: str
    ticket_id: str
    status: SessionStatus = SessionStatus.COMPLETED
    mode: SessionMode = SessionMode.LIVE
    created_at: str = Field(default_factory=_utcnow_iso)
    # True for hand-written demo data that never hit a real LLM.
    synthetic: bool = False


class Session(SessionSummary):
    """Full session returned by ``GET /api/sessions/{id}`` (with steps)."""

    ticket_text: str = ""
    steps: list[Step] = Field(default_factory=list)


# --- API request/response payloads ---


class RunRequest(BaseModel):
    """Body of ``POST /api/runs``.

    ``ticket_id`` is optional: leave it blank and the server assigns one automatically —
    a real Jira issue when Jira is configured, otherwise a generated ``JSM-####`` id.
    """

    ticket_id: str = ""
    ticket_text: str
    model: str = ""  # which LLM to run (id from /api/models); blank = configured default


class ReplayResponse(BaseModel):
    """Body of ``POST /api/sessions/{id}/replay`` (Sprint 3)."""

    session: Session
    real_calls: int = 0
    intercepted_calls: int = 0


class WhatIfRequest(BaseModel):
    """Body of ``POST /api/sessions/{id}/whatif``.

    Two kinds of correction can be injected (exactly one is required):
      * a **tool** override — pin ``tool_name`` to ``new_output`` and re-run, or
      * a **prompt** override — re-run the agent with a corrected ``system_prompt``
        (this is the "inject a corrected prompt at step 1" correction).
    """

    tool_name: Optional[str] = None
    new_output: Optional[dict[str, Any]] = None
    system_prompt: Optional[str] = None


class WhatIfResponse(BaseModel):
    """Side-by-side result of a divergence run."""

    original: Session
    whatif: Session
    overridden_tool: str          # human label of what was overridden
    override_kind: str = "tool"   # "tool" | "system_prompt"


class Anomaly(BaseModel):
    """A flagged issue found while auditing a session (Bonus 7)."""

    type: str
    severity: str  # info | warning | critical
    step_number: Optional[int] = None
    message: str


class SignatureInfo(BaseModel):
    """Tamper-evident signature of a trace (Bonus 8)."""

    algorithm: str = "HMAC-SHA256"
    digest: str
    signature: str
    verified: bool
    step_hashes: list[str] = Field(default_factory=list)
