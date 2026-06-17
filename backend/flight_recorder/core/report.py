"""Compliance PDF export — Bonus 9.

Produces an auditor-friendly PDF for a session: metadata, cryptographic integrity block,
anomaly findings, and the full step-by-step trace. Built with reportlab (pure Python).
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from flight_recorder.core.anomalies import detect_anomalies
from flight_recorder.core.schemas import Session, StepType
from flight_recorder.core.signing import signature_info

ORANGE = colors.HexColor("#d8600a")
GREY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#f0ece2")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("FRTitle", parent=ss["Title"], textColor=ORANGE, fontSize=20))
    ss.add(ParagraphStyle("FRH2", parent=ss["Heading2"], textColor=ORANGE, fontSize=12,
                          spaceBefore=12, spaceAfter=4))
    ss.add(ParagraphStyle("FRSmall", parent=ss["Normal"], fontSize=8, textColor=GREY))
    ss.add(ParagraphStyle("FRMono", parent=ss["Code"], fontSize=7, leading=9))
    ss.add(ParagraphStyle("FRCell", parent=ss["Normal"], fontSize=8, leading=10))
    return ss


def _kv_table(rows: list[tuple[str, str]], ss) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", ss["FRCell"]), Paragraph(_esc(v), ss["FRCell"])] for k, v in rows]
    t = Table(data, colWidths=[40 * mm, 130 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def build_pdf(session: Session) -> bytes:
    """Render the compliance report for ``session`` and return PDF bytes."""
    ss = _styles()
    anomalies = detect_anomalies(session)
    sig = signature_info(session)

    story = []
    story.append(Paragraph("Flight Recorder — Compliance Report", ss["FRTitle"]))
    story.append(Paragraph(
        f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ·  "
        "AI agent black-box audit", ss["FRSmall"]))
    story.append(Spacer(1, 8))

    # Session metadata
    story.append(Paragraph("Session", ss["FRH2"]))
    story.append(_kv_table([
        ("Session ID", session.session_id),
        ("Ticket", session.ticket_id),
        ("Description", session.ticket_text or "—"),
        ("Mode", session.mode.value),
        ("Status", session.status.value),
        ("Created", session.created_at),
        ("Steps", str(len(session.steps))),
    ], ss))

    # Integrity
    story.append(Paragraph("Cryptographic integrity", ss["FRH2"]))
    story.append(_kv_table([
        ("Algorithm", sig.algorithm),
        ("Digest (SHA-256)", sig.digest),
        ("Signature (HMAC)", sig.signature),
        ("Verified", "YES" if sig.verified else "NO"),
    ], ss))

    # Anomalies
    story.append(Paragraph(f"Anomaly findings ({len(anomalies)})", ss["FRH2"]))
    if anomalies:
        rows = [[Paragraph("<b>Severity</b>", ss["FRCell"]),
                 Paragraph("<b>Step</b>", ss["FRCell"]),
                 Paragraph("<b>Finding</b>", ss["FRCell"])]]
        for a in anomalies:
            rows.append([
                Paragraph(a.severity.upper(), ss["FRCell"]),
                Paragraph(str(a.step_number or "—"), ss["FRCell"]),
                Paragraph(_esc(a.message), ss["FRCell"]),
            ])
        t = Table(rows, colWidths=[22 * mm, 14 * mm, 134 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No anomalies detected.", ss["FRCell"]))

    # Steps
    story.append(Paragraph("Recorded steps", ss["FRH2"]))
    for step in session.steps:
        if step.type == StepType.LLM_CALL:
            head = f"#{step.step_number} · LLM · {step.duration_ms} ms"
            body = f"<b>Prompt:</b> {_esc(step.prompt)}<br/><b>Response:</b> {_esc(step.response)}"
        else:
            head = f"#{step.step_number} · TOOL {step.tool_name} · {step.duration_ms} ms"
            body = f"<b>Input:</b> {_esc(step.input)}<br/><b>Output:</b> {_esc(step.output)}"
        story.append(Paragraph(head, ss["FRCell"]))
        story.append(Paragraph(body, ss["FRMono"]))
        story.append(Spacer(1, 4))

    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, title=f"Compliance Report {session.session_id}",
                      leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=16 * mm, bottomMargin=16 * mm).build(story)
    return buf.getvalue()


def _esc(value) -> str:
    """Escape text for reportlab Paragraph (which parses a mini-HTML)."""
    text = "" if value is None else str(value)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text[:1200]  # keep cells reasonable
