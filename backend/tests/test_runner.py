"""Tests for the record_ticket orchestration, using a fake agent (no LLM)."""
from __future__ import annotations

from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from flight_recorder.core.runner import record_ticket
from flight_recorder.core.schemas import SessionStatus, StepType
from flight_recorder.core.storage import Storage


class FakeAgent:
    """Mimics a LangGraph agent: on invoke, it drives the recorder callbacks like a real
    run would (one LLM call + one tool call), then returns a messages dict."""

    def invoke(self, inputs: dict, config: dict) -> dict:
        recorder = config["callbacks"][0]

        llm_run = uuid4()
        recorder.on_chat_model_start({}, [[HumanMessage(content="Ticket")]], run_id=llm_run)
        recorder.on_llm_end(
            LLMResult(generations=[[ChatGeneration(message=AIMessage(content="thinking"))]]),
            run_id=llm_run,
        )

        tool_run = uuid4()
        recorder.on_tool_start(
            {"name": "search_kb"}, "{}", run_id=tool_run, inputs={"query": "vpn"}
        )
        recorder.on_tool_end({"found": True}, run_id=tool_run)

        return {"messages": []}


def test_record_ticket_captures_and_persists(tmp_storage: Storage):
    session = record_ticket(
        "JSM-42", "VPN broken", store=tmp_storage, agent=FakeAgent()
    )

    assert session.status == SessionStatus.COMPLETED
    assert session.session_id.startswith("run_")
    assert [s.type for s in session.steps] == [StepType.LLM_CALL, StepType.TOOL_CALL]

    # And it is actually retrievable from storage afterwards.
    reloaded = tmp_storage.get_session(session.session_id)
    assert reloaded is not None
    assert len(reloaded.steps) == 2
    assert reloaded.steps[1].tool_name == "search_kb"


class ExplodingAgent:
    def invoke(self, inputs: dict, config: dict) -> dict:
        recorder = config["callbacks"][0]
        run = uuid4()
        recorder.on_chat_model_start({}, [[HumanMessage(content="x")]], run_id=run)
        recorder.on_llm_end(
            LLMResult(generations=[[ChatGeneration(message=AIMessage(content="partial"))]]),
            run_id=run,
        )
        raise RuntimeError("boom mid-run")


def test_record_ticket_persists_partial_trace_on_error(tmp_storage: Storage):
    try:
        record_ticket("JSM-99", "x", store=tmp_storage, agent=ExplodingAgent())
    except RuntimeError:
        pass

    sessions = tmp_storage.list_sessions()
    assert len(sessions) == 1
    reloaded = tmp_storage.get_session(sessions[0].session_id)
    assert reloaded.status == SessionStatus.ERROR
    assert len(reloaded.steps) == 1  # the partial step was still saved
