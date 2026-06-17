"""Tests for the SQLite storage layer."""
from __future__ import annotations

from flight_recorder.core.schemas import (
    Session,
    SessionMode,
    SessionStatus,
    Step,
    StepType,
)
from flight_recorder.core.storage import Storage


def _make_session(session_id: str = "s1") -> Session:
    return Session(
        session_id=session_id,
        ticket_id="JSM-1",
        ticket_text="VPN broken",
        status=SessionStatus.COMPLETED,
        mode=SessionMode.LIVE,
        steps=[
            Step(step_number=1, type=StepType.LLM_CALL, prompt="p", response="r"),
            Step(
                step_number=2,
                type=StepType.TOOL_CALL,
                tool_name="search_kb",
                input={"query": "vpn"},
                output={"article_id": "KB-12"},
            ),
        ],
    )


def test_save_and_get_roundtrip(tmp_storage: Storage):
    original = _make_session()
    tmp_storage.save_session(original)

    loaded = tmp_storage.get_session("s1")
    assert loaded is not None
    assert loaded.ticket_id == "JSM-1"
    assert len(loaded.steps) == 2
    assert loaded.steps[1].tool_name == "search_kb"
    assert loaded.steps[1].output == {"article_id": "KB-12"}


def test_get_unknown_session_returns_none(tmp_storage: Storage):
    assert tmp_storage.get_session("does-not-exist") is None


def test_synthetic_flag_persists(tmp_storage: Storage):
    s = _make_session("syn")
    s.synthetic = True
    tmp_storage.save_session(s)

    assert tmp_storage.get_session("syn").synthetic is True
    assert tmp_storage.list_sessions()[0].synthetic is True


def test_list_sessions(tmp_storage: Storage):
    tmp_storage.save_session(_make_session("s1"))
    tmp_storage.save_session(_make_session("s2"))

    summaries = tmp_storage.list_sessions()
    ids = {s.session_id for s in summaries}
    assert ids == {"s1", "s2"}
    # Summaries are lightweight and carry no steps attribute.
    assert not hasattr(summaries[0], "steps")


def test_save_is_idempotent_and_replaces_steps(tmp_storage: Storage):
    tmp_storage.save_session(_make_session("s1"))

    smaller = _make_session("s1")
    smaller.steps = smaller.steps[:1]  # drop to a single step
    tmp_storage.save_session(smaller)

    loaded = tmp_storage.get_session("s1")
    assert loaded is not None
    assert len(loaded.steps) == 1  # old steps were cleared, not duplicated


def test_append_step(tmp_storage: Storage):
    tmp_storage.save_session(_make_session("s1"))
    tmp_storage.append_step(
        "s1", Step(step_number=3, type=StepType.LLM_CALL, prompt="p3", response="r3")
    )
    loaded = tmp_storage.get_session("s1")
    assert loaded is not None
    assert len(loaded.steps) == 3
    assert loaded.steps[2].prompt == "p3"
