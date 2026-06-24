"""The four simulated tools the triage agent can call.

None of these touch a real Atlassian/network system — they read local JSON/SQLite.
``send_notification`` is the only one with a side effect (it appends to a log file); it is
the tool that the Sprint 3 replay engine will block.

Each tool is a LangChain ``@tool`` so the LLM can choose to call it dynamically, and it has
a clear docstring because the LLM reads that docstring to decide when to use it.
"""
from __future__ import annotations

import contextvars
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.tools import tool

from flight_recorder.config import BACKEND_DIR, settings
from flight_recorder.agent.data_loader import (
    ensure_tickets_db,
    load_kb,
    load_users,
)

# The only side-effecting sink. Patchable in tests; blocked during replay (Sprint 3).
NOTIFICATIONS_LOG = BACKEND_DIR / "notifications.log"

# The Jira issue the current run is triaging — set by the runner so send_notification can
# comment on the real issue. Defaults to None so What-If/tests never write to Jira.
_current_issue: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_issue", default=None
)


def set_current_issue(issue_key: str | None) -> object:
    """Mark which Jira issue this run is about; returns a token to reset it afterwards."""
    return _current_issue.set(issue_key)


def reset_current_issue(token: object) -> None:
    _current_issue.reset(token)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


@tool
def search_kb(query: str) -> dict:
    """Search the IT knowledge base for the article most relevant to a problem.

    Use this first to understand a ticket. ``query`` should be a few keywords describing
    the issue (e.g. "vpn authentication timeout"). Returns the best-matching article with
    its id, title, category and a short summary, plus a relevance score.
    """
    # Prefer a REAL Jira ticket as the reference article; fall back to the local KB only if
    # Jira is unreachable.
    if settings.jira_enabled:
        from flight_recorder.agent import jira_client

        try:
            # Exclude the ticket currently being triaged so it never matches itself.
            hit = jira_client.search_kb_issue(query, exclude_key=_current_issue.get())
            if hit:
                return {"found": True, "source": "jira", "score": 1, **hit}
            return {"found": False, "source": "jira", "query": query,
                    "message": "No relevant past Jira ticket found."}
        except jira_client.JiraError:
            pass  # network issue → fall through to the local KB as a safety net

    query_tokens = _tokenize(query)
    best, best_score = None, 0
    for article in load_kb():
        haystack = set(article["keywords"]) | _tokenize(article["title"])
        score = len(query_tokens & haystack)
        if score > best_score:
            best, best_score = article, score

    if best is None:
        return {"found": False, "query": query, "message": "No relevant article found."}
    return {
        "found": True,
        "id": best["id"],
        "title": best["title"],
        "category": best["category"],
        "summary": best["summary"],
        "score": best_score,
    }


def _aggregate_tickets(category: str, tickets: list[dict]) -> dict:
    """Shared aggregation so the Jira and local paths return the identical shape."""
    by_priority: dict[str, int] = {}
    for t in tickets:
        by_priority[t["priority"]] = by_priority.get(t["priority"], 0) + 1

    resolved = [t for t in tickets if t.get("status") in ("Resolved", "Done", "Closed")]
    avg_hours = (
        round(sum(t.get("resolution_time_hours", 0) for t in resolved) / len(resolved), 1)
        if resolved else 0.0
    )
    return {
        "category": category,
        "count": len(tickets),
        "priority_breakdown": by_priority,
        "avg_resolution_hours": avg_hours,
        "tickets": tickets,
    }


@tool
def query_db(category: str) -> dict:
    """Look up the history of past tickets in a given category.

    Use this to see how similar issues were resolved before. ``category`` is one of:
    Network, Identity & Access, Email & Collaboration, Hardware, Software, Database,
    Security, Cloud, Telephony. Returns matching past tickets (id, summary, priority,
    status, resolution) plus aggregate stats: total count, a priority breakdown, and the
    average resolution time in hours.
    """
    # Prefer REAL Jira history when configured; fall back to the local mock on any error.
    if settings.jira_enabled:
        from flight_recorder.agent import jira_client

        try:
            tickets = jira_client.search_past_tickets(category)
            return {**_aggregate_tickets(category, tickets), "source": "jira"}
        except jira_client.JiraError:
            pass  # fall through to local mock

    db_path = ensure_tickets_db()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT ticket_id, summary, priority, status, resolution, resolution_time_hours "
            "FROM past_tickets WHERE lower(category) = lower(?) "
            "ORDER BY created_at DESC",
            (category.strip(),),
        ).fetchall()
    finally:
        conn.close()

    tickets = [dict(r) for r in rows]
    return {**_aggregate_tickets(category, tickets), "source": "local"}


@tool
def get_user_info(team_name: str) -> dict:
    """Find the responsible owner (name + email) for a given support team.

    Use this to decide who to assign a ticket to. ``team_name`` is the team that should
    own the issue, one of: Network, Identity & Access, Email & Collaboration, Hardware,
    Software, Database, Security, Cloud, Telephony, Facilities. Returns the owner's name,
    email, role, location and on-call status. Falls back to the Helpdesk dispatcher if no
    matching team is found.
    """
    # Prefer a REAL assignable Jira user when configured; fall back to the local directory.
    if settings.jira_enabled:
        from flight_recorder.agent import jira_client

        try:
            found = jira_client.find_assignable_user(team_name, issue_key=_current_issue.get())
            if found:
                return {
                    "found": True, "team": team_name, "source": "jira",
                    "name": found["name"], "email": found.get("email") or "",
                    "accountId": found.get("accountId"),
                }
        except jira_client.JiraError:
            pass  # fall through to local mock

    users = load_users()
    needle = team_name.strip().lower()

    for user in users:
        if user["team"].lower() == needle:
            return {"found": True, **user}
    # Loose contains-match before falling back to Helpdesk.
    for user in users:
        if needle and needle in user["team"].lower():
            return {"found": True, **user}
    for user in users:
        if user["team"] == "Helpdesk":
            return {"found": False, "fallback": True, **user}
    return {"found": False, "message": f"No owner for team '{team_name}'."}


@tool
def send_notification(user: str, message: str) -> dict:
    """Notify the assigned owner about the ticket. THIS HAS A SIDE EFFECT.

    Call this last, once a priority and assignee have been decided. ``user`` is the
    recipient email and ``message`` is the notification text. With a real Jira configured
    this posts a comment on the ticket; otherwise it appends to a local log. The replay
    engine blocks this tool either way.
    """
    # Real Jira: post a comment on the issue this run is triaging. This is the genuine
    # side effect — and exactly what REPLAY blocks, so it never fires during a replay.
    if settings.jira_enabled:
        issue_key = _current_issue.get()
        if issue_key:
            from flight_recorder.agent import jira_client

            try:
                res = jira_client.comment_issue(issue_key, f"[Triage] Assignee: {user}. {message}")
                return {"status": "sent", "via": "jira_comment", "issue": issue_key,
                        "to": user, "comment_id": res.get("id")}
            except jira_client.JiraError as exc:
                return {"status": "error", "via": "jira_comment", "error": str(exc)}

    # Defensive guard (local mock): never notify a fabricated address. The recipient must
    # be a real user the agent looked up via get_user_info. This makes the tool robust to
    # the LLM inventing placeholder emails — it gets rejected and must retry with the real one.
    known_emails = {u["email"] for u in load_users()}
    if user not in known_emails:
        return {
            "status": "rejected",
            "error": (
                f"Unknown recipient '{user}'. The recipient must be the exact email "
                "returned by get_user_info. Re-check that result and try again."
            ),
        }

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"[{timestamp}] to={user} :: {message}\n"
    Path(NOTIFICATIONS_LOG).parent.mkdir(parents=True, exist_ok=True)
    with open(NOTIFICATIONS_LOG, "a", encoding="utf-8") as fh:
        fh.write(line)
    return {"status": "sent", "to": user, "logged_at": timestamp}


# Exposed to the agent in this order.
ALL_TOOLS = [search_kb, query_db, get_user_info, send_notification]
