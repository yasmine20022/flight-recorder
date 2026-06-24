"""A thin, real client for the Atlassian Jira Cloud REST API (v3).

This is what makes the data *real*: when Jira credentials are configured, the agent reads
genuine past tickets and posts genuine comments instead of using the local mock. Auth is
HTTP Basic with your account email + an API token
(https://id.atlassian.com/manage-profile/security/api-tokens).

Everything is best-effort: any network/auth error raises ``JiraError`` so the calling tool
can fall back to the local mock and the demo never hard-fails.
"""
from __future__ import annotations

import re
import time
from typing import Any, Optional

import httpx

from flight_recorder.config import settings


class JiraError(RuntimeError):
    """Raised when a real Jira call fails (network, auth, or API error)."""


def label_for(category: str) -> str:
    """Turn a category into a valid Jira label (no spaces/punctuation allowed).

    e.g. "Identity & Access" -> "IdentityAccess". Used by BOTH the seeder and the search
    so a category reliably matches the tickets seeded under it.
    """
    return re.sub(r"[^A-Za-z0-9]+", "", category) or "general"


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.jira_base_url.rstrip("/"),
        auth=(settings.jira_email, settings.jira_api_token),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30.0,
    )


# Network blips and Jira 429/5xx are transient — retry them with a short backoff.
_TRANSIENT = (
    httpx.RemoteProtocolError, httpx.ConnectError, httpx.ConnectTimeout,
    httpx.ReadError, httpx.ReadTimeout, httpx.WriteError, httpx.PoolTimeout,
)


def _request(method: str, path: str, *, params: dict | None = None,
             json: dict | None = None, retries: int = 4) -> Any:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with _client() as c:
                r = c.request(method, path, params=params, json=json)
                r.raise_for_status()
                return r.json() if r.content else {}
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 429 or code >= 500:  # transient server side — retry
                last = exc
                time.sleep(0.7 * (attempt + 1))
                continue
            raise JiraError(f"{method} {path} -> {code}: {exc.response.text[:200]}") from exc
        except _TRANSIENT as exc:
            last = exc
            time.sleep(0.7 * (attempt + 1))
            continue
        except httpx.HTTPError as exc:
            raise JiraError(f"{method} {path} failed: {exc}") from exc
    raise JiraError(f"{method} {path} failed after {retries} attempts: {last}")


def _get(path: str, params: dict | None = None) -> Any:
    return _request("GET", path, params=params)


def _post(path: str, json: dict) -> Any:
    return _request("POST", path, json=json)


def whoami() -> dict[str, Any]:
    """Return the authenticated account — used to verify the token works."""
    return _get("/rest/api/3/myself")


def _text_of(adf: Any) -> str:
    """Flatten Jira's Atlassian Document Format (or plain string) into readable text."""
    if isinstance(adf, str):
        return adf
    if not isinstance(adf, dict):
        return ""
    out: list[str] = []
    if adf.get("text"):
        out.append(adf["text"])
    for child in adf.get("content", []) or []:
        out.append(_text_of(child))
    return " ".join(p for p in out if p).strip()


def search_past_tickets(category: str, *, limit: int = 10) -> list[dict[str, Any]]:
    """JQL-search resolved issues related to ``category`` (real past-ticket history)."""
    safe = category.replace('"', " ").strip()
    token = label_for(category)
    clauses = [f'(labels = "{token}" OR text ~ "{safe}")', "statusCategory = Done"]
    if settings.jira_project_key:
        clauses.insert(0, f"project = {settings.jira_project_key}")
    jql = " AND ".join(clauses) + " ORDER BY created DESC"

    # Atlassian removed the old /rest/api/3/search (410 Gone) in 2025; the current endpoint
    # is the enhanced JQL search at /rest/api/3/search/jql (token-paginated, fields required).
    data = _post(
        "/rest/api/3/search/jql",
        {
            "jql": jql,
            "maxResults": limit,
            "fields": ["summary", "priority", "status", "resolution", "resolutiondate", "created"],
        },
    )
    tickets: list[dict[str, Any]] = []
    for issue in data.get("issues", []):
        f = issue.get("fields", {})
        tickets.append({
            "ticket_id": issue.get("key"),
            "summary": f.get("summary", ""),
            "priority": (f.get("priority") or {}).get("name", "Unknown"),
            "status": (f.get("status") or {}).get("name", "Unknown"),
            "resolution": (f.get("resolution") or {}).get("name", "Unresolved"),
        })
    return tickets


# Short/common words to ignore when turning a ticket into search keywords (FR + EN).
_STOPWORDS = {
    "les", "des", "une", "sur", "pas", "plus", "mon", "est", "que", "qui", "dans", "vers",
    "the", "and", "not", "for", "with", "can", "cannot", "peux", "peut", "peuvent", "avec",
    "mes", "ses", "nos", "vos", "leur", "this", "that", "have", "has",
}


def _keywords(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) > 2 and w not in _STOPWORDS][:10]


def search_kb_issue(query: str, *, exclude_key: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Find the most relevant RESOLVED Jira ticket for ``query`` (the 'knowledge base').

    Only past/resolved tickets are searched (so the brand-new ticket never matches itself).
    We OR the query keywords (robust across FR/EN), fetch candidates, then rank them by how
    many keywords overlap the summary — and return the best match's first label as category.
    """
    keywords = _keywords(query)
    if not keywords:
        return None

    or_clause = " OR ".join(f'text ~ "{kw}"' for kw in keywords)
    clauses = [f"({or_clause})", "statusCategory = Done"]
    if settings.jira_project_key:
        clauses.insert(0, f"project = {settings.jira_project_key}")
    if exclude_key:
        clauses.append(f"key != {exclude_key}")
    jql = " AND ".join(clauses)

    data = _post("/rest/api/3/search/jql",
                 {"jql": jql, "maxResults": 20, "fields": ["summary", "labels"]})
    issues = data.get("issues", [])
    if not issues:
        return None

    qtokens = set(keywords)

    def overlap(issue: dict) -> int:
        summary = (issue.get("fields", {}).get("summary") or "").lower()
        return len(qtokens & set(re.findall(r"[a-z0-9]+", summary)))

    best = max(issues, key=overlap)
    f = best.get("fields", {})
    labels = f.get("labels") or []
    return {
        "id": best.get("key"),
        "title": f.get("summary", ""),
        "category": labels[0] if labels else "General",
        "summary": f.get("summary", ""),
    }


def find_assignable_user(query: str, *, issue_key: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Find a REAL assignable Jira user. Tries to match ``query``; otherwise returns any
    assignable user on the issue/project (so a single-user Jira always yields that user)."""
    base: dict[str, Any] = {}
    if issue_key:
        base["issueKey"] = issue_key
    elif settings.jira_project_key:
        base["project"] = settings.jira_project_key

    users: list = []
    for params in ({**base, "query": query, "maxResults": 1}, {**base, "maxResults": 1}):
        users = _get("/rest/api/3/user/assignable/search", params=params)
        if users:
            break
    if not users:
        return None

    u = users[0]
    email = u.get("emailAddress")
    if not email:  # Jira hides emails; if it's our own account we know it from /myself.
        try:
            me = whoami()
            if me.get("accountId") == u.get("accountId"):
                email = me.get("emailAddress")
        except JiraError:
            pass
    return {"accountId": u.get("accountId"), "name": u.get("displayName"), "email": email or ""}


# Cached project/type/reporter so auto-creating a ticket needs no extra round-trips.
_project_cache: Optional[str] = None
_issuetype_cache: Optional[str] = None
_reporter_cache: Optional[str] = None


def _resolve_project() -> str:
    global _project_cache
    if _project_cache:
        return _project_cache
    key = settings.jira_project_key
    if key:
        try:
            _get(f"/rest/api/3/project/{key}")
            _project_cache = key
            return key
        except JiraError:
            pass
    projects = _get("/rest/api/3/project/search", params={"maxResults": 1})
    values = projects.get("values", [])
    if not values:
        raise JiraError("No Jira project found to create the ticket in.")
    _project_cache = values[0]["key"]
    return _project_cache


def _issue_type(project: str) -> str:
    global _issuetype_cache
    if _issuetype_cache:
        return _issuetype_cache
    proj = _get(f"/rest/api/3/project/{project}")
    types = [t for t in proj.get("issueTypes", []) if not t.get("subtask")]
    for t in types:
        if t["name"] not in ("Epic", "Feature"):
            _issuetype_cache = t["name"]
            return _issuetype_cache
    _issuetype_cache = types[0]["name"]
    return _issuetype_cache


def _reporter_id() -> str:
    global _reporter_cache
    if _reporter_cache:
        return _reporter_cache
    _reporter_cache = whoami().get("accountId")
    return _reporter_cache


def create_issue(summary: str, *, labels: Optional[list[str]] = None) -> str:
    """Create a real Jira issue and return its key (e.g. ``KAN-63``)."""
    project = _resolve_project()
    fields: dict[str, Any] = {
        "project": {"key": project},
        "summary": (summary or "New ticket")[:240],
        "issuetype": {"name": _issue_type(project)},
        "reporter": {"id": _reporter_id()},
    }
    if labels:
        fields["labels"] = labels
    return _post("/rest/api/3/issue", {"fields": fields})["key"]


def add_labels(issue_key: str, labels: list[str]) -> dict[str, Any]:
    """Add labels to a real Jira issue (a genuine write performed after each run)."""
    clean = [re.sub(r"\s+", "_", str(l).strip()) for l in labels if l]
    if not clean:
        return {}
    _request("PUT", f"/rest/api/3/issue/{issue_key}",
             json={"update": {"labels": [{"add": l} for l in clean]}})
    return {"issue": issue_key, "labels": clean}


def comment_issue(issue_key: str, message: str) -> dict[str, Any]:
    """Post a real comment on a Jira issue — the genuine side effect REPLAY blocks."""
    body = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": message}]}],
        }
    }
    res = _post(f"/rest/api/3/issue/{issue_key}/comment", body)
    return {"id": res.get("id"), "issue": issue_key}
