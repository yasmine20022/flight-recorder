"""Compliance PDF export — Bonus 9.

Produces an auditor-grade PDF for a session: a branded header/footer with page numbers, an
executive-summary verdict, session metadata, the cryptographic integrity block, color-coded
anomaly findings, and a clean step-by-step execution trace. Built with reportlab (pure Python).
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from flight_recorder.core.anomalies import detect_anomalies
from flight_recorder.core.schemas import Session, StepType
from flight_recorder.core.signing import signature_info

# ── palette ───────────────────────────────────────────────────────────────────
PRIMARY = colors.HexColor("#d8600a")   # brand orange
INK = colors.HexColor("#1f2430")       # near-black headings
GREY = colors.HexColor("#5b6472")
HAIR = colors.HexColor("#d8dde6")      # hairline rules
LIGHT = colors.HexColor("#f5f2ec")     # label cell background
PANEL = colors.HexColor("#faf8f4")     # step body background
GREEN = colors.HexColor("#1a7f5a")
RED = colors.HexColor("#c0392b")
AMBER = colors.HexColor("#c87f0a")
BLUE = colors.HexColor("#2f6fb0")
CORAL = colors.HexColor("#d4574a")

_SEVERITY = {"critical": RED, "warning": AMBER, "info": BLUE}
_MARGIN = 18 * mm


def _hex(c) -> str:
    """reportlab Color -> '#rrggbb' for use in Paragraph <font color=…> markup."""
    return "#" + c.hexval()[2:]


def _styles():
    ss = getSampleStyleSheet()
    add = ss.add
    add(ParagraphStyle("FRTitle", parent=ss["Title"], textColor=INK, fontSize=22, leading=25,
                       spaceAfter=2, alignment=0))
    add(ParagraphStyle("FRSubtitle", parent=ss["Normal"], textColor=PRIMARY, fontSize=10.5,
                       leading=13, spaceAfter=1, fontName="Helvetica-Bold"))
    add(ParagraphStyle("FRMeta", parent=ss["Normal"], fontSize=8, textColor=GREY, leading=11))
    add(ParagraphStyle("FRSection", parent=ss["Heading2"], textColor=INK, fontSize=12.5,
                       leading=15, spaceBefore=14, spaceAfter=2, fontName="Helvetica-Bold"))
    add(ParagraphStyle("FRCell", parent=ss["Normal"], fontSize=8.5, leading=11, textColor=INK))
    add(ParagraphStyle("FRLabel", parent=ss["Normal"], fontSize=8, leading=11, textColor=GREY,
                       fontName="Helvetica-Bold"))
    add(ParagraphStyle("FRMono", parent=ss["Code"], fontSize=7.3, leading=9.5, textColor=INK))
    add(ParagraphStyle("FRStepHead", parent=ss["Normal"], fontSize=8.5, leading=11,
                       textColor=INK, fontName="Helvetica-Bold"))
    add(ParagraphStyle("FRTag", parent=ss["Normal"], fontSize=7, leading=9, textColor=GREY,
                       fontName="Helvetica-Bold"))
    add(ParagraphStyle("FRBadge", parent=ss["Normal"], fontSize=9, leading=11, alignment=1,
                       textColor=colors.white, fontName="Helvetica-Bold"))
    return ss


def _header_footer(canvas, doc):
    """Branded header band + footer rule with page number, drawn on every page."""
    w, h = A4
    canvas.saveState()
    # header band
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, h - 15 * mm, w, 15 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10.5)
    canvas.drawString(_MARGIN, h - 9.8 * mm, "✈  FLIGHT RECORDER")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - _MARGIN, h - 9.8 * mm, "AI Agent Compliance Report")
    # footer
    canvas.setStrokeColor(HAIR)
    canvas.setLineWidth(0.5)
    canvas.line(_MARGIN, 13 * mm, w - _MARGIN, 13 * mm)
    canvas.setFillColor(GREY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(_MARGIN, 9.5 * mm,
                      "CONFIDENTIAL — tamper-evident audit record, Flight Recorder for AI Agents")
    canvas.drawRightString(w - _MARGIN, 9.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _kv_table(rows, ss, label_w=42, value_w=128):
    """Two-column label/value table. ``value`` may be a str or a ready Paragraph."""
    data = []
    for k, v in rows:
        value = v if isinstance(v, Paragraph) else Paragraph(_esc(v), ss["FRCell"])
        data.append([Paragraph(k, ss["FRLabel"]), value])
    t = Table(data, colWidths=[label_w * mm, value_w * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, HAIR),
        ("LINEBEFORE", (1, 0), (1, -1), 0.4, HAIR),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _section(number, title, ss):
    """A numbered section heading with an accent underline."""
    return KeepTogether([
        Paragraph(f'<font color="#d8600a">{number}</font>&nbsp;&nbsp;{title}', ss["FRSection"]),
        HRFlowable(width="100%", thickness=1.1, color=PRIMARY, spaceBefore=2, spaceAfter=7),
    ])


def _final_decision(session: Session) -> str:
    for s in reversed(session.steps):
        if s.type == StepType.LLM_CALL and s.response and "decision" in s.response.lower():
            return s.response.strip()
    for s in reversed(session.steps):
        if s.type == StepType.LLM_CALL and s.response:
            return s.response.strip()
    return "—"


def _step_card(step, ss, flagged: bool):
    """One execution step rendered as a badge + structured details block."""
    if step.type == StepType.LLM_CALL:
        kind, color = "LLM", BLUE
        head = f"LLM reasoning call · {step.duration_ms} ms"
        if step.model:
            head += f" · {_esc(step.model)} · {step.tokens or 0} tokens"
        fields = [("PROMPT", _esc(step.prompt, 520)), ("RESPONSE", _esc(step.response, 1100))]
    else:
        kind, color = "TOOL", CORAL
        head = f"Tool call: {_esc(step.tool_name)} · {step.duration_ms} ms"
        fields = [("INPUT", _esc(step.input, 480)), ("OUTPUT", _esc(step.output, 900))]

    if flagged:
        head += '  <font color="#c0392b"><b>⚠ ANOMALY</b></font>'

    body = [Paragraph(head, ss["FRStepHead"])]
    for label, value in fields:
        body.append(Paragraph(label, ss["FRTag"]))
        body.append(Paragraph(value or "—", ss["FRMono"]))

    badge = Paragraph(f"{step.step_number}<br/><font size='6.5'>{kind}</font>", ss["FRBadge"])
    t = Table([[badge, body]], colWidths=[14 * mm, 156 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), RED if flagged else color),
        ("BACKGROUND", (1, 0), (1, 0), PANEL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, RED if flagged else HAIR),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
        ("RIGHTPADDING", (1, 0), (1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return KeepTogether([t, Spacer(1, 5)])


def build_pdf(session: Session) -> bytes:
    """Render the compliance report for ``session`` and return PDF bytes."""
    ss = _styles()
    anomalies = detect_anomalies(session)
    sig = signature_info(session)
    flagged_steps = {a.step_number for a in anomalies if a.step_number}

    llm_steps = [s for s in session.steps if s.type == StepType.LLM_CALL]
    tool_steps = [s for s in session.steps if s.type == StepType.TOOL_CALL]
    total_tokens = sum(s.tokens or 0 for s in llm_steps)
    model = next((s.model for s in llm_steps if s.model), "—")
    crit = sum(1 for a in anomalies if a.severity == "critical")

    story = []

    # ── title block ──
    story.append(Paragraph("Compliance Report", ss["FRTitle"]))
    story.append(Paragraph(f"AI Agent Execution Audit · {_esc(session.session_id)}", ss["FRSubtitle"]))
    story.append(Paragraph(
        "Generated " + datetime.now(timezone.utc).isoformat(timespec="seconds")
        + "  ·  Deterministic black-box trace of a non-deterministic LLM agent", ss["FRMeta"]))
    story.append(HRFlowable(width="100%", thickness=0.6, color=HAIR, spaceBefore=8, spaceAfter=2))

    # ── 1. executive summary ──
    integrity = Paragraph(
        ('<font color="#1a7f5a"><b>✓ VERIFIED</b></font>' if sig.verified
         else '<font color="#c0392b"><b>✗ NOT VERIFIED</b></font>') + f" ({sig.algorithm})",
        ss["FRCell"])
    anomaly_val = Paragraph(
        (f'<font color="#c0392b"><b>{len(anomalies)} finding(s), {crit} critical</b></font>'
         if anomalies else '<font color="#1a7f5a"><b>None detected</b></font>'), ss["FRCell"])
    status_color = {"completed": GREEN, "error": RED}.get(session.status.value, AMBER)
    story.append(_section("1", "Executive Summary", ss))
    story.append(_kv_table([
        ("Status", Paragraph(f'<font color="{_hex(status_color)}"><b>'
                             f'{session.status.value.upper()}</b></font>', ss["FRCell"])),
        ("Final decision", Paragraph(_esc(_final_decision(session), 600), ss["FRCell"])),
        ("Integrity", integrity),
        ("Anomalies", anomaly_val),
        ("Model", model),
        ("Trace size", f"{len(session.steps)} steps ({len(llm_steps)} LLM, {len(tool_steps)} tool) · {total_tokens} tokens"),
    ], ss))

    # ── 2. session details ──
    story.append(_section("2", "Session Details", ss))
    story.append(_kv_table([
        ("Session ID", session.session_id),
        ("Ticket", session.ticket_id),
        ("Description", session.ticket_text or "—"),
        ("Mode", session.mode.value),
        ("Created", session.created_at),
    ], ss))

    # ── 3. cryptographic integrity ──
    story.append(_section("3", "Cryptographic Integrity", ss))
    story.append(Paragraph(
        "Each step is chained into a SHA-256 hash chain; the chain tip is signed with "
        "HMAC-SHA256. Any change to any step invalidates the signature below.", ss["FRMeta"]))
    story.append(Spacer(1, 4))
    story.append(_kv_table([
        ("Algorithm", sig.algorithm),
        ("Digest (SHA-256)", Paragraph(_esc(sig.digest), ss["FRMono"])),
        ("Signature (HMAC)", Paragraph(_esc(sig.signature), ss["FRMono"])),
        ("Verified", integrity),
    ], ss))

    # ── 4. anomaly findings ──
    story.append(_section("4", f"Anomaly Findings ({len(anomalies)})", ss))
    if anomalies:
        rows = [[Paragraph("<b>SEVERITY</b>", ss["FRTag"]), Paragraph("<b>STEP</b>", ss["FRTag"]),
                 Paragraph("<b>FINDING</b>", ss["FRTag"])]]
        for a in anomalies:
            c = _hex(_SEVERITY.get(a.severity, GREY))
            rows.append([
                Paragraph(f'<font color="{c}"><b>{a.severity.upper()}</b></font>', ss["FRCell"]),
                Paragraph(str(a.step_number or "—"), ss["FRCell"]),
                Paragraph(_esc(a.message), ss["FRCell"]),
            ])
        t = Table(rows, colWidths=[24 * mm, 14 * mm, 132 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, HAIR),
            ("BOX", (0, 0), (-1, -1), 0.5, HAIR),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
    else:
        story.append(Paragraph('<font color="#1a7f5a">✓ No anomalies detected in this run.</font>',
                               ss["FRCell"]))

    # ── 5. execution trace ──
    story.append(_section("5", "Execution Trace", ss))
    story.append(Paragraph(
        "Every LLM reasoning call and tool call, in execution order, exactly as captured.",
        ss["FRMeta"]))
    story.append(Spacer(1, 6))
    for step in session.steps:
        story.append(_step_card(step, ss, step.step_number in flagged_steps))

    buf = BytesIO()
    SimpleDocTemplate(
        buf, pagesize=A4, title=f"Compliance Report {session.session_id}",
        author="Flight Recorder for AI Agents",
        leftMargin=_MARGIN, rightMargin=_MARGIN, topMargin=22 * mm, bottomMargin=18 * mm,
    ).build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def _esc(value, limit: int = 1000) -> str:
    """Escape text for reportlab Paragraph (which parses a mini-HTML)."""
    text = "" if value is None else str(value)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text[:limit]
