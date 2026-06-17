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

Fields not relevant to a step's `type` are `null`.

### Example

See [`backend/flight_recorder/core/schemas.py`](../backend/flight_recorder/core/schemas.py)
for the authoritative Pydantic models and
[`frontend/src/mock_data.json`](../frontend/src/mock_data.json) for a full example the UI
develops against.

---

## 2. REST API (FastAPI, base path `/api`)

| Method | Path                              | Sprint | Description                                              |
|--------|-----------------------------------|--------|----------------------------------------------------------|
| GET    | `/api/health`                     | 0      | Liveness probe → `{"status": "ok"}`                      |
| GET    | `/api/sessions`                   | 0      | List sessions (summary, **no** `steps`)                  |
| GET    | `/api/sessions/{session_id}`      | 0      | Full session **with** `steps`                            |
| POST   | `/api/runs`                       | 1      | Run agent live on a ticket → returns new session         |
| POST   | `/api/sessions/{session_id}/replay` | 3    | Deterministic replay → returns replayed session + counters |
| POST   | `/api/sessions/{session_id}/whatif` | 5    | Divergence from a step → returns original + new trajectory |

Endpoints for sprints 1/3/5 are **stubbed** in Sprint 0 (documented shape, `501 Not Implemented`).

### `GET /api/sessions` response
```json
[
  { "session_id": "run_2026-06-17_001", "ticket_id": "JSM-2847",
    "status": "completed", "mode": "live", "created_at": "2026-06-17T09:00:00Z" }
]
```

### `GET /api/sessions/{session_id}` response
Full **Session object** including `steps` (see section 1).

### `POST /api/runs` request (Sprint 1)
```json
{ "ticket_id": "JSM-2847", "ticket_text": "Cannot connect to VPN..." }
```

### Replay response will include proof counters (Sprint 3)
```json
{ "session": { ... }, "real_calls": 0, "intercepted_calls": 6 }
```
