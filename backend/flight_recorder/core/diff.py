"""Original-vs-corrected decision diff across the most-flawed runs — the FIXED-badge page.

Runs the closed-loop auto-fix on the top ``limit`` flagged runs and returns a per-ticket
table of original vs corrected decision. Bounded + cached because each row is a full auto-fix
(several LLM calls); rows that fail (e.g. rate limit) are skipped so the page still renders.
"""
from __future__ import annotations

from typing import Optional

from flight_recorder.core.schemas import DiffReport, DiffRow, SessionMode
from flight_recorder.core.storage import Storage, storage as default_storage

_CACHE: dict[tuple[int, int], DiffReport] = {}


def build_diff(*, store: Optional[Storage] = None, limit: int = 2, refresh: bool = False) -> DiffReport:
    from flight_recorder.core.anomalies import detect_anomalies
    from flight_recorder.core.autofix import auto_fix

    store = store or default_storage
    runs = []
    for s in store.list_sessions():
        if s.mode == SessionMode.LIVE:
            full = store.get_session(s.session_id)
            if full and full.steps:
                runs.append(full)

    key = (limit, len(runs))
    if not refresh and key in _CACHE:
        return _CACHE[key]

    ranked = sorted(runs, key=lambda r: len(detect_anomalies(r)), reverse=True)[:limit]
    rows: list[DiffRow] = []
    fixed_count = 0
    for r in ranked:
        try:
            res = auto_fix(r.session_id, store=store)
        except Exception:
            continue  # skip on failure so the page still renders
        is_fixed = res.improved or res.original_decision.strip() != res.fixed_decision.strip()
        fixed_count += 1 if is_fixed else 0
        rows.append(DiffRow(
            ticket_id=r.ticket_id, session_id=r.session_id,
            original_decision=res.original_decision, fixed_decision=res.fixed_decision,
            original_score=res.original_judgment.score, fixed_score=res.fixed_judgment.score,
            fixed=is_fixed,
        ))

    report = DiffReport(rows=rows, fixed_count=fixed_count)
    _CACHE[key] = report
    return report
