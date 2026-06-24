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
    overridden_tool: str          # human label of what was overridden
    override_kind: str = "tool"   # "tool" | "system_prompt"


def run_whatif(
    session_id: str,
    tool_name: Optional[str] = None,
    new_output: Optional[dict[str, Any]] = None,
    *,
    system_prompt: Optional[str] = None,
    ticket_text: Optional[str] = None,
    store: Optional[Storage] = None,
    agent: Any = None,
) -> WhatIfResult:
    """Re-run the agent for ``session_id`` with one correction injected, then compare.

    Provide exactly one correction:
      * ``tool_name`` + ``new_output`` — pin that tool's output and re-run,
      * ``system_prompt`` — re-run with corrected instructions (prompt injection), or
      * ``ticket_text`` — re-run on a *reworded* ticket (counterfactual robustness test).
    """
    from langchain_core.messages import HumanMessage

    store = store or default_storage
    original = store.get_session(session_id)
    if original is None:
        raise KeyError(session_id)

    if system_prompt:
        override_kind = "system_prompt"
    elif ticket_text:
        override_kind = "ticket"
    else:
        override_kind = "tool"

    if agent is None:
        from flight_recorder.agent.graph import build_agent

        if override_kind == "system_prompt":
            agent = build_agent(system_prompt=system_prompt)
        elif override_kind == "ticket":
            agent = build_agent()  # same agent, different input wording
        else:
            if not tool_name:
                raise ValueError(
                    "Provide a tool_name + new_output, a system_prompt, or a ticket_text."
                )
            tools = apply_overrides(ALL_TOOLS, {tool_name: new_output or {}})
            agent = build_agent(tools)

    run_text = ticket_text if override_kind == "ticket" else original.ticket_text
    recorder = TraceRecorder()
    agent.invoke(
        {"messages": [HumanMessage(content=f"Ticket {original.ticket_id}:\n{run_text}")]},
        config={"callbacks": [recorder]},
    )

    whatif_session = Session(
        session_id=f"{session_id}__whatif_{uuid4().hex[:4]}",
        ticket_id=original.ticket_id,
        ticket_text=run_text,
        status=SessionStatus.COMPLETED,
        mode=SessionMode.WHATIF,
        steps=recorder.steps,
    )
    label = {
        "tool": tool_name,
        "system_prompt": "system prompt (instructions)",
        "ticket": "ticket rephrasing",
    }[override_kind]
    return WhatIfResult(
        original=original,
        whatif=whatif_session,
        overridden_tool=label,
        override_kind=override_kind,
    )
