"""Tests for the LLM proxy and proxy-based deterministic replay (Sprint A).

All offline — no Groq key, no network. The replay test even drives the full ReAct agent
loop with the LLM served entirely from cache, proving zero real calls.
"""
from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, message_to_dict

from flight_recorder.core.proxy import CallCounter, ProxiedChatModel, ReplayState
from flight_recorder.core.proxy_replay import replay_through_proxy
from flight_recorder.core.recorder import TraceRecorder
from flight_recorder.core.schemas import Session, Step, StepType
from flight_recorder.core.storage import Storage


# --- ProxiedChatModel: record mode ---

def test_record_mode_forwards_to_provider_and_counts():
    inner = FakeMessagesListChatModel(responses=[AIMessage(content="hello world")])
    counter = CallCounter()
    proxy = ProxiedChatModel(inner=inner, mode="record", call_counter=counter)

    rec = TraceRecorder()
    out = proxy.invoke([HumanMessage(content="hi")], config={"callbacks": [rec]})

    assert out.content == "hello world"
    assert counter.count == 1
    # The trace recorder captured exactly one LLM step (no double-capture).
    assert len(rec.steps) == 1
    assert rec.steps[0].type == StepType.LLM_CALL


# --- ProxiedChatModel: replay mode ---

def test_replay_mode_serves_cached_messages_in_order():
    cached = [AIMessage(content="first"), AIMessage(content="second")]
    proxy = ProxiedChatModel(inner=None, mode="replay", replay_state=ReplayState(cached))

    assert proxy.invoke([HumanMessage(content="x")]).content == "first"
    assert proxy.invoke([HumanMessage(content="y")]).content == "second"


def test_replay_mode_raises_when_cache_exhausted():
    proxy = ProxiedChatModel(inner=None, mode="replay", replay_state=ReplayState([]))
    with pytest.raises(RuntimeError):
        proxy.invoke([HumanMessage(content="x")])


def test_bind_tools_shares_the_replay_cursor():
    # The agent binds tools before the first call; the bound copy must share the cursor.
    state = ReplayState([AIMessage(content="a"), AIMessage(content="b")])
    proxy = ProxiedChatModel(inner=None, mode="replay", replay_state=state)

    bound = proxy.bind_tools([])
    assert bound.mode == "replay"
    bound.invoke([HumanMessage(content="x")])  # consumes "a" via the shared state
    assert state.index == 1


# --- proxy_replay: full agent loop, no LLM ---

def _llm_step(n: int, msg: AIMessage) -> Step:
    text = msg.content or (
        "(decided to call: " + ", ".join(tc["name"] for tc in msg.tool_calls) + ")"
    )
    return Step(step_number=n, type=StepType.LLM_CALL, response=text, ai_message=message_to_dict(msg))


def test_replay_through_proxy_reruns_agent_with_zero_real_calls(tmp_storage: Storage):
    # A recorded trajectory: search_kb -> final decision. Tools run for real on replay;
    # the LLM decisions are served from the recorded ai_message payloads.
    search = AIMessage(
        content="",
        tool_calls=[{"name": "search_kb", "args": {"query": "vpn authentication timeout"},
                     "id": "c1", "type": "tool_call"}],
    )
    final = AIMessage(content="DECISION: priority=High; assignee=Alice Martin alice.martin@corp.example; reason=vpn")
    tmp_storage.save_session(Session(
        session_id="rec_1",
        ticket_id="JSM-9",
        ticket_text="Cannot connect to the VPN, authentication timeout.",
        steps=[
            _llm_step(1, search),
            Step(step_number=2, type=StepType.TOOL_CALL, tool_name="search_kb",
                 input={"query": "vpn authentication timeout"}, output={"found": True}),
            _llm_step(3, final),
        ],
    ))

    result = replay_through_proxy("rec_1", store=tmp_storage)

    assert result.real_calls == 0
    assert result.intercepted_calls == 2          # two recorded LLM decisions served
    assert result.session.mode.value == "replay"
    # The re-executed run reached the same decision, and really ran the search_kb tool.
    assert "DECISION" in result.session.steps[-1].response
    assert any(s.type == StepType.TOOL_CALL and s.tool_name == "search_kb"
               for s in result.session.steps)


def test_replay_through_proxy_needs_recorded_messages(tmp_storage: Storage):
    # A pre-Sprint-A session (no ai_message) cannot be proxy-replayed.
    tmp_storage.save_session(Session(
        session_id="old_1", ticket_id="JSM-1", ticket_text="x",
        steps=[Step(step_number=1, type=StepType.LLM_CALL, response="hi")],
    ))
    with pytest.raises(ValueError):
        replay_through_proxy("old_1", store=tmp_storage)


def test_replay_through_proxy_unknown_session_raises(tmp_storage: Storage):
    with pytest.raises(KeyError):
        replay_through_proxy("nope", store=tmp_storage)
