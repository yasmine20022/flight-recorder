"""Tests for the contract models (schemas.py)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from flight_recorder.core.schemas import (
    Session,
    SessionStatus,
    Step,
    StepType,
)


def test_llm_step_roundtrips_through_json():
    step = Step(step_number=1, type=StepType.LLM_CALL, prompt="hi", response="hello")
    restored = Step(**step.model_dump())
    assert restored == step
    assert restored.tool_name is None  # irrelevant fields stay None


def test_tool_step_keeps_structured_io():
    step = Step(
        step_number=2,
        type=StepType.TOOL_CALL,
        tool_name="search_kb",
        input={"query": "vpn"},
        output={"article_id": "KB-12"},
    )
    assert step.input["query"] == "vpn"
    assert step.output["article_id"] == "KB-12"


def test_step_number_must_be_positive():
    with pytest.raises(ValidationError):
        Step(step_number=0, type=StepType.LLM_CALL)


def test_session_defaults_and_timestamp_format():
    session = Session(session_id="s1", ticket_id="JSM-1")
    assert session.status == SessionStatus.COMPLETED
    assert session.steps == []
    assert session.created_at.endswith("Z")  # ISO-8601 UTC marker


def test_invalid_step_type_rejected():
    with pytest.raises(ValidationError):
        Step(step_number=1, type="not_a_real_type")
