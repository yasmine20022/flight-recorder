"""Deterministic tests for the interception layer (no LLM, no network).

We drive the callback methods by hand exactly the way LangChain would during a ReAct run,
and assert that the resulting Step list is captured correctly.
"""
from __future__ import annotations

from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from flight_recorder.core.recorder import TraceRecorder
from flight_recorder.core.schemas import StepType


def _llm_result(text: str) -> LLMResult:
    return LLMResult(generations=[[ChatGeneration(message=AIMessage(content=text))]])


def test_records_llm_then_tool_in_order():
    rec = TraceRecorder()

    # 1) An LLM call.
    llm_run = uuid4()
    rec.on_chat_model_start(
        {}, [[SystemMessage(content="sys prompt"), HumanMessage(content="Ticket JSM-1: vpn")]],
        run_id=llm_run,
    )
    rec.on_llm_end(_llm_result("I will search the knowledge base."), run_id=llm_run)

    # 2) A tool call.
    tool_run = uuid4()
    rec.on_tool_start(
        {"name": "search_kb"}, '{"query": "vpn"}', run_id=tool_run, inputs={"query": "vpn"}
    )
    rec.on_tool_end({"found": True, "id": "KB-12"}, run_id=tool_run)

    assert [s.type for s in rec.steps] == [StepType.LLM_CALL, StepType.TOOL_CALL]
    assert [s.step_number for s in rec.steps] == [1, 2]

    llm_step = rec.steps[0]
    assert "Ticket JSM-1: vpn" in llm_step.prompt
    assert llm_step.response == "I will search the knowledge base."

    tool_step = rec.steps[1]
    assert tool_step.tool_name == "search_kb"
    assert tool_step.input == {"query": "vpn"}
    assert tool_step.output == {"found": True, "id": "KB-12"}


def test_tool_call_decision_is_summarized_when_response_empty():
    rec = TraceRecorder()
    run = uuid4()
    rec.on_chat_model_start({}, [[HumanMessage(content="hi")]], run_id=run)

    msg = AIMessage(
        content="",
        tool_calls=[{"name": "search_kb", "args": {"query": "vpn"}, "id": "call_1"}],
    )
    rec.on_llm_end(LLMResult(generations=[[ChatGeneration(message=msg)]]), run_id=run)

    assert rec.steps[0].response == "(decided to call: search_kb)"


def test_string_tool_output_is_wrapped_in_dict():
    rec = TraceRecorder()
    run = uuid4()
    rec.on_tool_start({"name": "send_notification"}, "ignored", run_id=run, inputs={"user": "a@b"})
    rec.on_tool_end("written to log", run_id=run)

    assert rec.steps[0].output == {"result": "written to log"}


def test_captures_model_and_tokens_from_llm_output():
    rec = TraceRecorder()
    run = uuid4()
    rec.on_chat_model_start({}, [[HumanMessage(content="hi")]], run_id=run)

    result = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="ok"))]],
        llm_output={"model_name": "llama-3.1-8b-instant", "token_usage": {"total_tokens": 412}},
    )
    rec.on_llm_end(result, run_id=run)

    step = rec.steps[0]
    assert step.model == "llama-3.1-8b-instant"
    assert step.tokens == 412


def test_unmatched_end_is_ignored():
    rec = TraceRecorder()
    # An end with no matching start must not raise or create a step.
    rec.on_llm_end(_llm_result("orphan"), run_id=uuid4())
    assert rec.steps == []
