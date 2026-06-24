"""Multi-run pattern analysis — feature 2.

Moves from "debug one run" to "understand the agent's structural weaknesses": aggregate the
decisions, routed teams, priorities and anomalies across every recorded run, then ask a strong
LLM to name the recurring failure patterns and recommend fixes.
"""
from __future__ import annotations

import json
from typing import Optional

from flight_recorder.core.ai_common import AIUnavailable, chat_json, extract_decision, parse_decision
from flight_recorder.core.schemas import PatternReport, SessionMode, StepType
from flight_recorder.core.storage import Storage, storage as default_storage

_SYSTEM = """You are an SRE reviewing aggregate statistics from many runs of an AI triage agent.
Identify recurring, STRUCTURAL weaknesses (not one-off mistakes): e.g. a category that is
systematically misrouted, a priority that is consistently wrong, or a frequent anomaly type.

Return STRICT JSON:
{"summary": "<=2 sentences", "weaknesses": ["short pattern", ...], "recommendations": ["short fix", ...]}"""


def _routed_team(session) -> Optional[str]:
    team = None
    for s in session.steps:
        if s.type == StepType.TOOL_CALL and s.tool_name == "get_user_info":
            team = (s.input or {}).get("team_name") or team
    return team


def analyze_patterns(*, store: Optional[Storage] = None) -> PatternReport:
    from flight_recorder.core.anomalies import detect_anomalies

    store = store or default_storage
    summaries = [s for s in store.list_sessions() if s.mode == SessionMode.LIVE]
    runs = [store.get_session(s.session_id) for s in summaries]
    runs = [r for r in runs if r and r.steps]

    report = PatternReport(total_runs=len(runs))
    if not runs:
        return report

    total_steps = 0
    for r in runs:
        total_steps += len(r.steps)
        team = _routed_team(r)
        if team:
            report.by_team[team] = report.by_team.get(team, 0) + 1
        prio = parse_decision(extract_decision(r)).get("priority")
        if prio:
            report.by_priority[prio] = report.by_priority.get(prio, 0) + 1
        for s in r.steps:
            if s.type == StepType.LLM_CALL and s.model:
                report.model_usage[s.model] = report.model_usage.get(s.model, 0) + 1
        anomalies = detect_anomalies(r)
        if anomalies:
            report.flagged_runs += 1
        for a in anomalies:
            report.anomaly_counts[a.type] = report.anomaly_counts.get(a.type, 0) + 1

    report.avg_steps = round(total_steps / len(runs), 1)

    # LLM insight layer (best-effort: aggregates still return if the LLM is unavailable).
    stats = json.dumps({
        "total_runs": report.total_runs,
        "by_team": report.by_team,
        "by_priority": report.by_priority,
        "anomaly_counts": report.anomaly_counts,
        "flagged_runs": report.flagged_runs,
        "avg_steps": report.avg_steps,
    }, ensure_ascii=False)
    try:
        data = chat_json(_SYSTEM, "AGGREGATE STATS:\n" + stats, max_tokens=600)
        report.summary = str(data.get("summary", "")).strip()
        report.weaknesses = [str(w) for w in (data.get("weaknesses") or [])][:6]
        report.recommendations = [str(w) for w in (data.get("recommendations") or [])][:6]
    except AIUnavailable:
        report.summary = ""  # aggregates alone are still useful

    return report
