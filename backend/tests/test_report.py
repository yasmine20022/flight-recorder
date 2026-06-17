"""Tests for the compliance PDF export (Bonus 9)."""
from __future__ import annotations

from flight_recorder.core.report import build_pdf
from flight_recorder.core.schemas import Session, Step, StepType


def test_build_pdf_returns_valid_pdf_bytes():
    session = Session(
        session_id="s1", ticket_id="JSM-1", ticket_text="VPN down",
        steps=[
            Step(step_number=1, type=StepType.LLM_CALL, prompt="p", response="DECISION: x"),
            Step(step_number=2, type=StepType.TOOL_CALL, tool_name="search_kb",
                 input={"query": "vpn"}, output={"found": True}),
        ],
    )
    pdf = build_pdf(session)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")     # valid PDF header
    assert len(pdf) > 1000             # non-trivial document


def test_build_pdf_handles_html_special_chars():
    session = Session(
        session_id="s2", ticket_id="JSM-2", ticket_text="a <b> & c",
        steps=[Step(step_number=1, type=StepType.LLM_CALL, prompt="<tag>", response="x & y")],
    )
    pdf = build_pdf(session)  # must not raise on angle brackets / ampersands
    assert pdf.startswith(b"%PDF")
