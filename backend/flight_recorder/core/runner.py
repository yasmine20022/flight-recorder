"""Orchestrates a *recorded* agent run: attach the recorder, run, persist the trace.

This is the bridge between the agent (Sprint 1) and the storage (Sprint 0). Note that the
agent itself is untouched — interception happens purely through the callback handler passed
in ``config``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from flight_recorder.core.recorder import TraceRecorder
from flight_recorder.core.schemas import Session, SessionMode, SessionStatus
from flight_recorder.core.storage import Storage, storage as default_storage


def new_session_id() -> str:
    """Human-readable, collision-resistant session id, e.g. run_2026-06-17_4f9c2a."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"run_{day}_{uuid4().hex[:6]}"


def record_ticket(
    ticket_id: str,
    ticket_text: str,
    *,
    store: Optional[Storage] = None,
    agent: Any = None,
) -> Session:
    """Run the agent on a ticket while capturing every step, then save the trace.

    ``agent`` and ``store`` are injectable for testing; by default the real triage agent
    and the default SQLite storage are used.
    """
    from langchain_core.messages import HumanMessage

    store = store or default_storage
    if agent is None:
        from flight_recorder.agent.graph import build_agent

        agent = build_agent()

    recorder = TraceRecorder()
    session = Session(
        session_id=new_session_id(),
        ticket_id=ticket_id,
        ticket_text=ticket_text,
        status=SessionStatus.RUNNING,
        mode=SessionMode.LIVE,
    )

    try:
        agent.invoke(
            {"messages": [HumanMessage(content=f"Ticket {ticket_id}:\n{ticket_text}")]},
            config={"callbacks": [recorder]},
        )
        session.status = SessionStatus.COMPLETED
    except Exception:
        session.status = SessionStatus.ERROR
        session.steps = recorder.steps
        store.save_session(session)
        raise

    session.steps = recorder.steps
    store.save_session(session)
    return session
