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
    ticket_text: Optional[str] = None  # counterfactual: re-run on a reworded ticket


class WhatIfResponse(BaseModel):
    """Side-by-side result of a divergence run."""

    original: Session
    whatif: Session
    overridden_tool: str          # human label of what was overridden
    override_kind: str = "tool"   # "tool" | "system_prompt"


class Judgment(BaseModel):
    """LLM-as-Judge verdict on a decision's quality — no ground truth needed (feature 4)."""

    score: int = Field(..., ge=0, le=10)
    verdict: str            # sound | questionable | flawed
    rationale: str
    issues: list[str] = Field(default_factory=list)
    model: str = ""


class AutoFixResult(BaseModel):
    """Closed-loop auto-correction result (feature 1)."""

    root_cause: str
    corrected_prompt: str
    rca_confidence: int = 0  # 0–100, how sure the model is of the diagnosis (feeds M6)
    original: "Session"
    fixed: "Session"
    original_decision: str
    fixed_decision: str
    original_judgment: Judgment
    fixed_judgment: Judgment
    improved: bool


class RcaResult(BaseModel):
    """Lightweight root-cause analysis of one run (auto-loaded in ANALYZE mode)."""

    root_cause: str
    faulty_quote: str = ""   # the exact faulty sentence quoted from the agent's prompt
    confidence: int = 0      # 0–100
    fix_summary: str = ""
    model: str = ""


class DiffRow(BaseModel):
    """One ticket in the original-vs-corrected diff table."""

    ticket_id: str
    session_id: str
    original_decision: str
    fixed_decision: str
    original_score: int = 0
    fixed_score: int = 0
    fixed: bool = False


class DiffReport(BaseModel):
    rows: list[DiffRow] = Field(default_factory=list)
    fixed_count: int = 0


class MetricCard(BaseModel):
    """One dashboard metric (M1–M6)."""

    id: str            # "M1" … "M6"
    name: str
    value: float       # numeric (usually 0–100)
    display: str       # human display, e.g. "62%" or "8.1/10"
    detail: str        # the real measured value in words
    protocol: str      # how it is measured
    ai: bool = False   # True when an LLM is in the measurement loop


class MetricsReport(BaseModel):
    """The 6-metric evaluation dashboard (M1–M6)."""

    generated_at: str
    total_runs: int
    metrics: list[MetricCard] = Field(default_factory=list)


class PatternReport(BaseModel):
    """Aggregate insight across many runs (feature 2)."""

    total_runs: int = 0
    by_team: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    anomaly_counts: dict[str, int] = Field(default_factory=dict)
    model_usage: dict[str, int] = Field(default_factory=dict)
    avg_steps: float = 0.0
    flagged_runs: int = 0
    summary: str = ""
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


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
