"""What-If divergence engine — Sprint 5.

Take a recorded session, override one tool's output to a new value, and re-run the agent
on the same ticket. Because the LLM runs at temperature 0 and the other tools are
deterministic, the run reproduces up to the overridden tool and then **diverges live** — the
LLM re-reasons with the modified value. We return both trajectories for side-by-side compare.

The agent code is never modified: divergence is injected purely by swapping the toolset.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from flight_recorder.agent.overrides import apply_overrides
from flight_recorder.agent.tools import ALL_TOOLS
from flight_recorder.core.recorder import TraceRecorder
from flight_recorder.core.schemas import (
    Session,
    SessionMode,
    SessionStatus,
)
from flight_recorder.core.storage import Storage, storage as default_storage


@dataclass
class WhatIfResult:
    original: Session
    whatif: Session
    overridden_tool: str


def run_whatif(
    session_id: str,
    tool_name: str,
    new_output: dict[str, Any],
    *,
    store: Optional[Storage] = None,
    agent: Any = None,
) -> WhatIfResult:
    """Re-run the agent for ``session_id`` with ``tool_name`` pinned to ``new_output``."""
    from langchain_core.messages import HumanMessage

    store = store or default_storage
    original = store.get_session(session_id)
    if original is None:
        raise KeyError(session_id)

    if agent is None:
        from flight_recorder.agent.graph import build_agent

        tools = apply_overrides(ALL_TOOLS, {tool_name: new_output})
        agent = build_agent(tools)

    recorder = TraceRecorder()
    agent.invoke(
        {"messages": [HumanMessage(content=f"Ticket {original.ticket_id}:\n{original.ticket_text}")]},
        config={"callbacks": [recorder]},
    )

    whatif_session = Session(
        session_id=f"{session_id}__whatif_{uuid4().hex[:4]}",
        ticket_id=original.ticket_id,
        ticket_text=original.ticket_text,
        status=SessionStatus.COMPLETED,
        mode=SessionMode.WHATIF,
        steps=recorder.steps,
    )
    return WhatIfResult(original=original, whatif=whatif_session, overridden_tool=tool_name)
