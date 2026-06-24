# Contract — Flight Recorder for AI Agents

> **This file is FROZEN.** It is the boundary between backend (agent/storage/replay) and
> frontend (UI). Do not change the trace shape or endpoint signatures without telling the
> whole team. Everything else in the project is free to evolve.

---

## 1. Trace format (the single source of truth)

A **session** is one execution of the agent on one ticket. It contains an ordered list of **steps**.

### Session object

| Field         | Type     | Description                                              |
|---------------|----------|----------------------------------------------------------|
| `session_id`  | string   | Unique id, e.g. `run_2026-06-17_001`                     |
| `ticket_id`   | string   | The Jira ticket being processed, e.g. `JSM-2847`         |
| `ticket_text` | string   | Raw ticket description fed to the agent                  |
| `status`      | string   | `running` \| `completed` \| `error`                      |
| `mode`        | string   | `live` \| `replay` \| `whatif`                           |
| `created_at`  | string   | ISO-8601 UTC timestamp                                   |
| `steps`       | Step[]   | Ordered list of steps (may be empty while `running`)     |

### Step object

A step is **fine-grained**: an LLM call and a tool call are two separate steps.

| Field         | Type            | Present for          | Description                                  |
|---------------|-----------------|----------------------|----------------------------------------------|
| `step_number` | int             | all                  | 1-based order in the session                 |
| `type`        | string          | all                  | `llm_call` \| `tool_call`                    |
| `timestamp`   | string          | all                  | ISO-8601 UTC                                 |
| `duration_ms` | int             | all                  | Wall-clock duration of the step              |
| `prompt`      | string \| null  | `llm_call`           | Exact prompt sent to the LLM                 |
| `response`    | string \| null  | `llm_call`           | Exact LLM response                           |
| `tool_name`   | string \| null  | `tool_call`          | One of the simulated tools                   |
| `input`       | object \| null  | `tool_call`          | Exact tool arguments                         |
| `output`      | object \| null  | `tool_call`          | Exact tool result                            |
| `model`       | string \| null  | `llm_call`           | Provider model id (proof the call hit Groq)  |
| `tokens`      | int \| null     | `llm_call`           | Total tokens billed for the call             |
| `ai_message`  | object \| null  | `llm_call`           | Internal: serialized AIMessage so the proxy can replay the exact tool-call decision (not shown in UI) |

Fields not relevant to a step's `type` are `null`.

### Example

See [`backend/flight_recorder/core/schemas.py`](../backend/flight_recorder/core/schemas.py)
for the authoritative Pydantic models.

---

## 2. REST API (FastAPI, base path `/api`)

| Method | Path                              | Description                                              |
|--------|-----------------------------------|----------------------------------------------------------|
| GET    | `/api/health`                     | Liveness probe → `{"status": "ok"}`                      |
| GET    | `/api/sessions`                   | List sessions (summary, **no** `steps`)                  |
| GET    | `/api/sessions/{session_id}`      | Full session **with** `steps`                            |
| POST   | `/api/runs`                       | Run agent live on a ticket → returns new session         |
| POST   | `/api/sessions/{session_id}/replay` | Deterministic replay → replayed session + counters. Optional `?engine=proxy` re-runs the agent with the LLM served from cache by the proxy |
| POST   | `/api/sessions/{session_id}/whatif` | Divergence run → returns original + new trajectory     |
| GET    | `/api/agent/prompt`               | The agent's current (buggy) + corrected system prompts   |
| GET    | `/api/sessions/{session_id}/anomalies` | Audit findings for a session                        |
| GET    | `/api/sessions/{session_id}/signature` | Tamper-evident HMAC signature of the trace          |
| GET    | `/api/sessions/{session_id}/report.pdf` | Compliance PDF export                               |

All endpoints are **fully implemented**.

### `GET /api/sessions` response
```json
[
  { "session_id": "run_2026-06-17_001", "ticket_id": "JSM-2847",
    "status": "completed", "mode": "live", "created_at": "2026-06-17T09:00:00Z" }
]
```

### `GET /api/sessions/{session_id}` response
Full **Session object** including `steps` (see section 1).

### `POST /api/runs` request
```json
{ "ticket_id": "JSM-2847", "ticket_text": "Cannot connect to VPN..." }
```

### Replay response includes proof counters
```json
{ "session": { ... }, "real_calls": 0, "intercepted_calls": 6 }
```

### `POST /api/sessions/{id}/whatif` request — one correction is required
```json
// tool override:
{ "tool_name": "get_user_info", "new_output": { "name": "Grace Kim", "email": "grace.kim@corp.example" } }
// OR prompt injection (re-run with corrected instructions):
{ "system_prompt": "...corrected agent instructions..." }
```
Response: `{ "original": {Session}, "whatif": {Session}, "overridden_tool": "...", "override_kind": "tool" | "system_prompt" }`
