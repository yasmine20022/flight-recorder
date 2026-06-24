# Data Documentation — Flight Recorder for AI Agents

The system uses two kinds of data: the **business data** the agent reads/writes, and the
**trace data** the recorder captures.

## 1. Business data (what the agent operates on)

| Source | Used by | Real or local |
|---|---|---|
| **Real Jira Cloud** (project `KAN`, REST API v3) | `search_kb`, `query_db`, `get_user_info`, `send_notification` | **Real** when `JIRA_*` is configured |
| `backend/data/kb_articles.json` (28 articles) | `search_kb` fallback | Local mock (offline safety net) |
| `backend/data/users.json` (23 users) | `get_user_info` fallback | Local mock |
| `backend/data/tickets_seed.json` (34 tickets) | `query_db` fallback (seeds `data/tickets.db`) | Local mock |

When Jira is configured the agent **reads real past tickets** (resolved issues), **assigns a
real Jira user**, **posts a real comment**, and **writes real labels** (`ai-triaged`, the
routed team, the priority) on the triaged issue after each run. The local JSON is only a
fallback when Jira is unreachable.

### Categories / labels (the routing taxonomy)

`Network`, `Identity & Access`, `Email & Collaboration`, `Hardware`, `Software`, `Database`,
`Security`, `Cloud`, `Telephony`, `Backend`, `Frontend`.

Multi-word categories are normalised to single-token Jira labels (`Identity & Access →
IdentityAccess`) by `jira_client.label_for`, used identically for seeding and searching.

### Distribution (seeded resolved history in Jira `KAN`)

~34 resolved tickets across all categories, e.g. Network 6 · Identity & Access 5 ·
Email & Collaboration 3 · Hardware 4 · Software 3 · Database 3 · Security 3 · Cloud 2 ·
Telephony 1 · Backend 3 · Frontend 1. Each carries a `priority` (Low/Medium/High/Critical)
and a resolved status.

## 2. Trace data (what the recorder stores)

SQLite at `backend/flight_recorder.db`. Schema (see [CONTRACT.md](CONTRACT.md)):

```
sessions(session_id PK, ticket_id, ticket_text, status, mode, created_at, synthetic)
steps(step_id PK, session_id FK, step_number, type, content JSON, UNIQUE(session_id, step_number))
```

- **`sessions.mode`** ∈ `live` (RECORD) · `replay` (REPLAY) · `whatif` (WHATIF).
- **`steps.type`** ∈ `llm_call` · `tool_call`. The full step (prompt/response/model/tokens or
  tool input/output, plus the serialized `ai_message` used for deterministic replay) is stored
  as JSON in `content`.

### Step schema (the contract)

| Field | Present for | Description |
|---|---|---|
| `step_number`, `type`, `timestamp`, `duration_ms` | all | order, kind, timing |
| `prompt`, `response`, `model`, `tokens` | `llm_call` | exact prompt/response + provenance |
| `tool_name`, `input`, `output` | `tool_call` | exact tool I/O |
| `ai_message` | `llm_call` | serialized decision (tool calls) for proxy replay |

## 3. Provenance you can verify in the UI

Every step shows its **source** (`source: "jira"` vs `"local"`) and, for LLM steps, the real
model id + tokens billed. Each session is **HMAC-signed** (tamper-evident), and the compliance
PDF embeds the digest + signature.
