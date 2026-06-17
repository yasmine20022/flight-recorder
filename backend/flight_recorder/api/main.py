"""FastAPI app exposing the frozen contract (see docs/CONTRACT.md).

Sprint 0 implements the read endpoints (health, list, detail). The run/replay/whatif
endpoints are stubbed with their documented shape and return 501 until later sprints.
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


@app.post("/api/runs", response_model=Session)
def run_agent(req: RunRequest) -> Session:
    """Run the triage agent live on a ticket, capture the trace, store it, return it."""
    import groq

    from flight_recorder.core.runner import record_ticket

    try:
        return record_ticket(req.ticket_id, req.ticket_text)
    except groq.RateLimitError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"LLM rate limit: {exc}")
    except RuntimeError as exc:  # e.g. missing GROQ_API_KEY
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@app.post("/api/sessions/{session_id}/replay", response_model=ReplayResponse)
def replay(session_id: str) -> ReplayResponse:
    """Deterministically replay a stored session — zero real calls, side effects blocked."""
    from flight_recorder.core.replay import ReplayEngine

    try:
        result = ReplayEngine(store=storage).replay(session_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown session: {session_id}")
    return ReplayResponse(
        session=result.session,
        real_calls=result.real_calls,
        intercepted_calls=result.intercepted_calls,
    )


@app.post("/api/sessions/{session_id}/whatif", response_model=WhatIfResponse)
def whatif(session_id: str, req: WhatIfRequest) -> WhatIfResponse:
    """Re-run the agent with one tool output overridden, then compare trajectories."""
    import groq

    from flight_recorder.core.whatif import run_whatif

    try:
        result = run_whatif(session_id, req.tool_name, req.new_output, store=storage)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown session: {session_id}")
    except groq.RateLimitError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"LLM rate limit: {exc}")
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    return WhatIfResponse(
        original=result.original,
        whatif=result.whatif,
        overridden_tool=result.overridden_tool,
    )
