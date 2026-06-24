"""FastAPI app exposing the frozen contract (see docs/CONTRACT.md).

Exposes the full surface: health/list/detail reads, the audit endpoints
(anomalies, signature, compliance PDF), plus the live run, deterministic replay,
and What-If divergence endpoints — all fully implemented.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from flight_recorder.core.schemas import (
    Anomaly,
    ReplayResponse,
    RunRequest,
    Session,
    SessionSummary,
    SignatureInfo,
    WhatIfRequest,
    WhatIfResponse,
)
from flight_recorder.core.storage import storage

app = FastAPI(title="Flight Recorder for AI Agents", version="0.1.0")

# Allow the Vite dev server on any localhost port (it picks 5173, 5174, … if busy).
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/models")
def list_models() -> dict:
    """The LLMs the user can choose from for a run (all free on Groq, tool-calling capable)."""
    from flight_recorder.agent.graph import AVAILABLE_MODELS

    return {"default": AVAILABLE_MODELS[0]["id"], "models": AVAILABLE_MODELS}


@app.get("/api/jira/status")
def jira_status() -> dict:
    """Report whether a real Jira is wired up (and reachable), for the UI to show a badge."""
    from flight_recorder.config import settings

    if not settings.jira_enabled:
        return {"enabled": False, "ok": False, "detail": "Using local mock data."}
    from flight_recorder.agent import jira_client

    try:
        me = jira_client.whoami()
        return {"enabled": True, "ok": True, "account": me.get("displayName"),
                "base_url": settings.jira_base_url}
    except jira_client.JiraError as exc:
        return {"enabled": True, "ok": False, "detail": str(exc)}


@app.get("/api/sessions", response_model=list[SessionSummary])
def list_sessions() -> list[SessionSummary]:
    return storage.list_sessions()


@app.get("/api/sessions/{session_id}", response_model=Session)
def get_session(session_id: str) -> Session:
    session = storage.get_session(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown session: {session_id}")
    return session


def _require_session(session_id: str) -> Session:
    session = storage.get_session(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown session: {session_id}")
    return session


# --- Audit & compliance (Bonus 7/8/9) ---


@app.get("/api/sessions/{session_id}/anomalies", response_model=list[Anomaly])
def session_anomalies(session_id: str) -> list[Anomaly]:
    from flight_recorder.core.anomalies import detect_anomalies

    return detect_anomalies(_require_session(session_id))


@app.get("/api/sessions/{session_id}/signature", response_model=SignatureInfo)
def session_signature(session_id: str) -> SignatureInfo:
    from flight_recorder.core.signing import signature_info

    return signature_info(_require_session(session_id))


@app.get("/api/sessions/{session_id}/report.pdf")
def session_report(session_id: str) -> Response:
    from flight_recorder.core.report import build_pdf

    pdf = build_pdf(_require_session(session_id))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{session_id}.pdf"'},
    )


# --- Live agent runs, replay, and divergence ---


def _assign_ticket_id(req: RunRequest) -> str:
    """Pick the ticket id: caller-provided, else a real Jira issue, else a generated id."""
    ticket_id = (req.ticket_id or "").strip()
    if ticket_id:
        return ticket_id

    from flight_recorder.config import settings

    if settings.jira_enabled:
        from flight_recorder.agent import jira_client

        try:
            return jira_client.create_issue(req.ticket_text)
        except jira_client.JiraError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, f"Could not create Jira ticket: {exc}"
            )
    import random

    return f"JSM-{random.randint(1000, 9999)}"


@app.post("/api/runs", response_model=Session)
def run_agent(req: RunRequest) -> Session:
    """Run the triage agent live on a ticket, capture the trace, store it, return it.

    The ticket id is assigned automatically when not provided (a real Jira issue is created
    when Jira is configured), so the user only has to describe the problem.
    """
    import groq

    from flight_recorder.agent.graph import resolve_model
    from flight_recorder.core.runner import record_ticket

    ticket_id = _assign_ticket_id(req)
    model_name = resolve_model(req.model)
    try:
        return record_ticket(ticket_id, req.ticket_text, model_name=model_name)
    except groq.RateLimitError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"LLM rate limit: {exc}")
    except RuntimeError as exc:  # e.g. missing GROQ_API_KEY
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@app.post("/api/sessions/{session_id}/replay", response_model=ReplayResponse)
def replay(session_id: str, engine: str = "reemit") -> ReplayResponse:
    """Replay a stored session.

    ``engine=reemit`` (default) re-emits the stored steps — zero real calls, side effects
    blocked. ``engine=proxy`` re-runs the agent with the LLM served from cache by the proxy.
    ``engine=live`` re-runs the agent while **actually re-calling the LLM** (side effects
    still blocked, so notifications are never sent).
    """
    import groq

    try:
        if engine == "live":
            from flight_recorder.core.proxy_replay import replay_live

            result = replay_live(session_id, store=storage)
        elif engine == "proxy":
            from flight_recorder.core.proxy_replay import replay_through_proxy

            result = replay_through_proxy(session_id, store=storage)
        else:
            from flight_recorder.core.replay import ReplayEngine

            result = ReplayEngine(store=storage).replay(session_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown session: {session_id}")
    except ValueError as exc:  # proxy replay needs a session recorded with ai_message
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except groq.RateLimitError as exc:  # engine=live exhausted the Groq daily/TPM quota
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"LLM rate limit: {exc}")
    except RuntimeError as exc:  # e.g. missing GROQ_API_KEY for engine=live
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    return ReplayResponse(
        session=result.session,
        real_calls=result.real_calls,
        intercepted_calls=result.intercepted_calls,
    )


@app.get("/api/agent/prompt")
def agent_prompt() -> dict[str, str]:
    """Expose the agent's current (buggy) prompt + the corrected one, for the What-If UI."""
    from flight_recorder.agent.graph import CORRECTED_SYSTEM_PROMPT, SYSTEM_PROMPT

    return {"system_prompt": SYSTEM_PROMPT, "corrected_system_prompt": CORRECTED_SYSTEM_PROMPT}


@app.post("/api/sessions/{session_id}/whatif", response_model=WhatIfResponse)
def whatif(session_id: str, req: WhatIfRequest) -> WhatIfResponse:
    """Re-run the agent with one correction injected (tool output OR system prompt)."""
    import groq

    from flight_recorder.core.whatif import run_whatif

    try:
        result = run_whatif(
            session_id,
            req.tool_name,
            req.new_output,
            system_prompt=req.system_prompt,
            ticket_text=req.ticket_text,
            store=storage,
        )
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown session: {session_id}")
    except ValueError as exc:  # no override of any kind was provided
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    except groq.RateLimitError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"LLM rate limit: {exc}")
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    return WhatIfResponse(
        original=result.original,
        whatif=result.whatif,
        overridden_tool=result.overridden_tool,
        override_kind=result.override_kind,
    )


# --- AI analysis layer (LLM-judge · auto-fix · multi-run patterns) ---


@app.get("/api/sessions/{session_id}/judge")
def judge(session_id: str):
    """LLM-as-Judge: score this run's decision quality (no ground truth)."""
    from flight_recorder.core.ai_common import AIUnavailable
    from flight_recorder.core.judge import judge_session

    session = _require_session(session_id)
    try:
        return judge_session(session)
    except AIUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@app.post("/api/sessions/{session_id}/autofix")
def autofix(session_id: str):
    """Closed loop: diagnose → generate corrected prompt → re-run → judge before/after."""
    import groq

    from flight_recorder.core.ai_common import AIUnavailable
    from flight_recorder.core.autofix import auto_fix

    try:
        return auto_fix(session_id, store=storage)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown session: {session_id}")
    except groq.RateLimitError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"LLM rate limit: {exc}")
    except (AIUnavailable, RuntimeError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@app.get("/api/patterns")
def patterns():
    """Aggregate insight across every recorded run + LLM structural-weakness summary."""
    from flight_recorder.core.patterns import analyze_patterns

    return analyze_patterns(store=storage)


@app.get("/api/metrics")
def metrics(refresh: bool = False):
    """The 6-metric evaluation dashboard (M1–M6). Always returns six cards (graceful fallbacks)."""
    from flight_recorder.core.metrics import compute_metrics

    return compute_metrics(store=storage, refresh=refresh)


@app.get("/api/sessions/{session_id}/rca")
def rca(session_id: str):
    """ANALYZE mode: auto-load the root cause + the exact faulty prompt sentence (1 LLM call)."""
    from flight_recorder.core.ai_common import AIUnavailable
    from flight_recorder.core.rca import diagnose

    session = _require_session(session_id)
    try:
        return diagnose(session)
    except AIUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@app.get("/api/diff")
def diff(limit: int = 2, refresh: bool = False):
    """Original-vs-corrected decision diff across the most-flawed runs (FIXED badges)."""
    from flight_recorder.core.diff import build_diff

    return build_diff(store=storage, limit=max(1, min(limit, 6)), refresh=refresh)
