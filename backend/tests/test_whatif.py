"""Tests for the What-If divergence engine (deterministic, no LLM)."""
from __future__ import annotations

from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from flight_recorder.agent.overrides import apply_overrides
from flight_recorder.agent.tools import ALL_TOOLS, get_user_info
from flight_recorder.core.schemas import Session, SessionMode, Step, StepType
from flight_recorder.core.storage import Storage
from flight_recorder.core.whatif import run_whatif


# --- apply_overrides ---

def test_override_pins_tool_output_ignoring_input():
    override = {"name": "Grace Kim", "email": "grace.kim@corp.example", "team": "Security"}
    patched = apply_overrides(ALL_TOOLS, {"get_user_info": override})

    by_name = {t.name: t for t in patched}
    # Same tools, same count, names preserved.
    assert set(by_name) == {t.name for t in ALL_TOOLS}
    # The overridden tool now returns the fixed value for ANY input.
    assert by_name["get_user_info"].invoke({"team_name": "Network"}) == override
    # Untouched tools still behave normally.
    assert by_name["search_kb"].invoke({"query": "vpn timeout"})["found"] is True


def test_override_leaves_other_tools_callable():
    patched = apply_overrides(ALL_TOOLS, {"search_kb": {"found": False}})
    by_name = {t.name: t for t in patched}
    # The real get_user_info is unchanged.
    assert by_name["get_user_info"] is get_user_info


# --- run_whatif orchestration (fake agent, no LLM) ---

class DivergingAgent:
    """Fake agent that produces a different decision than the original session."""

    def invoke(self, inputs: dict, config: dict) -> dict:
        rec = config["callbacks"][0]
        run = uuid4()
        rec.on_chat_model_start({}, [[HumanMessage(content="t")]], run_id=run)
        rec.on_llm_end(
            LLMResult(
                generations=[[ChatGeneration(message=AIMessage(content="DECISION: priority=Low; assignee=Grace Kim"))]]
            ),
            run_id=run,
        )
        return {"messages": []}


def _original(store: Storage) -> None:
    store.save_session(
        Session(
            session_id="run_1",
            ticket_id="JSM-1",
            ticket_text="VPN broken",
            steps=[
                Step(step_number=1, type=StepType.LLM_CALL, prompt="p",
                     response="DECISION: priority=High; assignee=Alice Martin"),
            ],
        )
    )


def test_run_whatif_returns_both_trajectories(tmp_storage: Storage):
    _original(tmp_storage)

    result = run_whatif(
        "run_1",
        "get_user_info",
        {"name": "Grace Kim", "email": "grace.kim@corp.example"},
        store=tmp_storage,
        agent=DivergingAgent(),
    )

    assert result.overridden_tool == "get_user_info"
    assert result.original.session_id == "run_1"
    assert result.whatif.mode == SessionMode.WHATIF
    assert result.whatif.session_id.startswith("run_1__whatif_")
    # The two trajectories reached different decisions.
    assert result.original.steps[-1].response != result.whatif.steps[-1].response


def test_run_whatif_unknown_session_raises(tmp_storage: Storage):
    import pytest

    with pytest.raises(KeyError):
        run_whatif("nope", "get_user_info", {}, store=tmp_storage, agent=DivergingAgent())


# --- prompt-injection override (Sprint B) ---

def test_run_whatif_prompt_override_sets_kind(tmp_storage: Storage):
    _original(tmp_storage)

    result = run_whatif(
        "run_1",
        system_prompt="Corrected: API 500s go to Backend / Critical.",
        store=tmp_storage,
        agent=DivergingAgent(),
    )

    assert result.override_kind == "system_prompt"
    assert "system prompt" in result.overridden_tool.lower()
    assert result.whatif.mode == SessionMode.WHATIF
    # Still a real divergence: the decision differs from the original.
    assert result.original.steps[-1].response != result.whatif.steps[-1].response


def test_run_whatif_requires_some_override(tmp_storage: Storage):
    import pytest

    _original(tmp_storage)
    # No tool override and no prompt override → can't diverge.
    with pytest.raises(ValueError):
        run_whatif("run_1", store=tmp_storage)
