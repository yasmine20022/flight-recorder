<div align="center">

# ✈️ Flight Recorder for AI Agents

**A black box for LLM agents — record every decision, replay it safely, and explore what-if scenarios without ever touching the real world.**

[![Tests](https://img.shields.io/badge/tests-57%20passing-2fe6a8)](#testing)
[![Backend](https://img.shields.io/badge/backend-FastAPI%20%2B%20LangGraph-ff7a1a)](#tech-stack)
[![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-ff7a1a)](#tech-stack)
[![LLM](https://img.shields.io/badge/LLM-Groq%20(free)-2fe6a8)](#tech-stack)

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Tech Stack](#tech-stack)
5. [Project Structure](#project-structure)
6. [Getting Started](#getting-started)
7. [Usage](#usage)
8. [REST API Reference](#rest-api-reference)
9. [The Trace Format](#the-trace-format)
10. [Testing](#testing)
11. [Advanced / Compliance Features](#advanced--compliance-features)
12. [Design Decisions](#design-decisions)
13. [Project Status](#project-status)

---

## Overview

### The problem

An AI agent that triages enterprise Jira tickets makes **different decisions on every run**. When it gets one wrong — a bad assignment, an email sent in error, a malformed query — it is nearly impossible to understand *why* without re-running it, which fires **new, real, irreversible actions** against the live system.

### The solution

**Flight Recorder** is a transparent layer that sits invisibly between the agent and all of its tools. It:

- **Records** absolutely everything — every LLM prompt and every tool call — **without modifying the agent's code**;
- **Replays** any past execution in a perfectly safe environment, substituting recorded results for real calls so **no real action is ever triggered**;
- lets you run **What-If** scenarios: change one step in a past run and watch the agent re-reason live, then compare the two trajectories side by side.

### The analogy

> An aircraft's black box. You never need to re-fly the plane to understand an incident — everything was already recorded, and you replay the exact data on a grounded simulator.

The demo domain is an agent that triages simulated **Jira** IT-support tickets.

---

## Key Features

| Feature | Description |
|---|---|
| 🎙️ **Transparent capture** | A LangChain callback handler records every LLM call and tool call into SQLite — the agent's code is never touched. |
| ▶️ **Deterministic replay** | Re-injects recorded LLM/tool outputs. **Zero real calls**; side-effecting tools (e.g. notifications) are blocked. Proven with counters. |
| ↯ **What-If divergence** | Override one tool's output at any step, re-run the agent **live**, and compare the original vs. new trajectory side by side. |
| 🛰️ **Real-LLM provenance** | Each LLM step records the **model name and tokens billed** by Groq — visible proof a step really hit the LLM. |
| 🔍 **Anomaly detection** | Flags reasoning loops, suspicious arguments, failed tools, runaway length, and missing decisions. |
| 🔒 **Tamper-evident signing** | Per-step SHA-256 hash chain + HMAC-SHA256 signature; any edit to a trace breaks verification. |
| 📄 **Compliance PDF export** | One-click auditor-ready report: metadata, integrity block, anomalies, full trace. |
| 🐳 **Sandboxed replay** | A network-isolated, read-only Docker container proves replay needs no external access. |
| 🛩️ **Cockpit UI** | Aviation black-box theme with a step-by-step playback scrubber, instrument gauges, light/dark mode. |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  TICKET ──▶  AGENT (LangGraph ReAct)  ──▶  SIMULATED TOOLS                  │
│             reasons & decides              search_kb · query_db            │
│                    │                       get_user_info · send_notification│
│                    │                              │                         │
│                    └──────────────┬───────────────┘                         │
│                                   ▼                                         │
│                      INTERCEPTION LAYER  (LangChain callbacks)              │
│                      captures every step — transparently                   │
│                                   ▼                                         │
│                      TRACE STORAGE  (SQLite: sessions + steps)              │
│                                   │                                         │
│              ┌────────────────────┼────────────────────┐                   │
│              ▼                    ▼                     ▼                   │
│        REPLAY ENGINE        WHAT-IF ENGINE       AUDIT (anomalies,         │
│        (0 real calls)       (override + re-run)   signature, PDF)          │
│              └────────────────────┼────────────────────┘                   │
│                                   ▼                                         │
│                      REST API (FastAPI)  ──▶  COCKPIT UI (React)            │
└──────────────────────────────────────────────────────────────────────────┘
```

**The core idea:** interception happens entirely through LangChain's native callback system
(`on_chat_model_start`, `on_llm_end`, `on_tool_start`, `on_tool_end`). The agent is observed,
never modified.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Agent** | [LangGraph](https://langchain-ai.github.io/langgraph/) ReAct agent (checkpointable) |
| **LLM** | [Groq](https://console.groq.com) — **free tier**, `llama-3.1-8b-instant`, temperature 0 |
| **Backend** | Python 3.10+, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) |
| **Storage** | SQLite (sessions, steps, simulated ticket history) |
| **Validation** | Pydantic v2 |
| **Reports** | ReportLab (PDF) |
| **Frontend** | React 18 + [Vite](https://vitejs.dev/) |
| **Tests** | pytest |
| **Containerization** | Docker + Docker Compose |

---

## Project Structure

```
flight-recorder/
├── backend/
│   ├── flight_recorder/
│   │   ├── config.py                # settings (Groq key, paths, signing secret)
│   │   ├── agent/
│   │   │   ├── graph.py             # LangGraph ReAct triage agent
│   │   │   ├── tools.py             # the 4 simulated tools
│   │   │   ├── overrides.py         # tool-output pinning (What-If)
│   │   │   └── data_loader.py       # loads KB / users / tickets
│   │   ├── core/
│   │   │   ├── schemas.py           # Pydantic models = the contract
│   │   │   ├── storage.py           # SQLite persistence
│   │   │   ├── recorder.py          # ⭐ interception callback handler
│   │   │   ├── runner.py            # record a live run
│   │   │   ├── replay.py            # deterministic replay engine
│   │   │   ├── whatif.py            # divergence engine
│   │   │   ├── anomalies.py         # anomaly detector
│   │   │   ├── signing.py           # hash chain + HMAC signing
│   │   │   └── report.py            # compliance PDF
│   │   └── api/main.py              # FastAPI app
│   ├── data/                        # simulated enterprise data (JSON + SQLite)
│   ├── scripts/                     # CLI demos (run, record, replay, what-if, reset)
│   ├── tests/                       # pytest suite
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   └── src/
│       ├── App.jsx                  # cockpit shell
│       ├── api.js                   # live API client
│       └── components/              # FlightPath, InstrumentBar, PlaybackControls, …
├── docs/
│   ├── CONTRACT.md                  # frozen API + trace contract
│   └── SANDBOX.md                   # isolated-replay guide
├── docker-compose.yml
└── README.md
```

---

## Getting Started

### Prerequisites

- **Python** 3.10+
- **Node.js** 18+
- A **free Groq API key** — get one at [console.groq.com](https://console.groq.com) (no credit card).

### 1. Backend

```bash
cd backend

# create an isolated environment
python -m venv .venv
.venv\Scripts\Activate.ps1            # Windows PowerShell
# source .venv/bin/activate           # macOS / Linux

pip install -r requirements.txt

# configure the LLM key
cp .env.example .env                  # then set GROQ_API_KEY in .env

# start the API
uvicorn flight_recorder.api.main:app --reload
# → http://127.0.0.1:8000
```

> **PowerShell note:** chain commands with `;` (not `&&`). Example: `python -m venv .venv ; .venv\Scripts\Activate.ps1`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

The UI talks **only** to the live backend. If the backend is offline it shows a clear
message with a retry button — it never renders fake data.

### Environment variables (`backend/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | Free Groq key (required for live runs) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | LLM model |
| `DATABASE_PATH` | `flight_recorder.db` | SQLite trace DB |
| `SIGNING_SECRET` | `dev-…-change-me` | HMAC secret for trace signing |

---

## Usage

### In the UI

1. **▶ Run & record** — type any IT ticket; the agent runs live and its trace is captured.
2. **Playback** — press ▶ to step through the recording waypoint by waypoint.
3. **↻ Replay safely** — re-run from the recording with **0 real calls**; notifications are blocked.
4. **↯ What-If** — pick a tool step, edit its output, and re-run live to compare trajectories.
5. **Audit** — view the signature, anomalies, and export the compliance **PDF**.

### CLI scripts (`backend/`)

| Command | What it does |
|---|---|
| `python -m scripts.run_triage` | Run the agent on several tickets (shows dynamic routing) |
| `python -m scripts.record_run` | Run live + capture a full trace into the DB |
| `python -m scripts.replay_demo` | Replay a stored trace — proves `real calls = 0` |
| `python -m scripts.whatif_demo` | Override a tool and re-run, original vs. new decision |
| `python -m scripts.reset_db` | Reset to a clean demo state |

### Demo scenario (the pitch)

> An agent triages a ticket and **misassigns** it. Open the recording, inspect the faulty
> step, **replay** it (proving zero real actions), then run **What-If** on the faulty value —
> the agent re-reasons and reaches the **correct** decision.
>
> *"We just corrected an AI agent in production — without modifying a single ticket, without
> redeploying a line of code, and without re-running the live agent."*

---

## REST API Reference

Base path: `/api`

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/sessions` | List recorded sessions (summary) |
| `GET` | `/sessions/{id}` | Full session with steps |
| `POST` | `/runs` | Run the agent live on a ticket, capture & store the trace |
| `POST` | `/sessions/{id}/replay` | Deterministic replay → trace + `real_calls`/`intercepted_calls` |
| `POST` | `/sessions/{id}/whatif` | Override a tool output, re-run live, return both trajectories |
| `GET` | `/sessions/{id}/anomalies` | Anomaly findings for the session |
| `GET` | `/sessions/{id}/signature` | HMAC signature + per-step hash chain |
| `GET` | `/sessions/{id}/report.pdf` | Compliance PDF report |

Interactive docs are available at `http://127.0.0.1:8000/docs`.

---

## The Trace Format

A **session** is one execution; it contains an ordered list of fine-grained **steps**
(an LLM call and a tool call are separate steps). This shape is the frozen contract between
backend and frontend — see [`docs/CONTRACT.md`](docs/CONTRACT.md).

```jsonc
{
  "session_id": "run_2026-06-17_4854ea",
  "ticket_id": "JSM-5001",
  "ticket_text": "Outlook is not sending or receiving email…",
  "status": "completed",
  "mode": "live",                  // live | replay | whatif
  "synthetic": false,              // true only for hand-written demo data
  "steps": [
    {
      "step_number": 1,
      "type": "llm_call",
      "duration_ms": 729,
      "prompt": "You are an IT triage agent…",
      "response": "(decided to call: search_kb)",
      "model": "llama-3.1-8b-instant",   // proof of a real LLM call
      "tokens": 1271
    },
    {
      "step_number": 2,
      "type": "tool_call",
      "tool_name": "search_kb",
      "input":  { "query": "outlook email not sending" },
      "output": { "found": true, "id": "KB-50", "category": "Email & Collaboration" }
    }
  ]
}
```

### The four simulated tools

| Tool | Backing data | Side effect |
|---|---|---|
| `search_kb(query)` | 28-article knowledge base (JSON) | none |
| `query_db(category)` | ticket history (SQLite) — returns stats + SLA | none |
| `get_user_info(team)` | 20-person org directory (JSON) | none |
| `send_notification(user, msg)` | appends to a log file | **yes — blocked during replay** |

> Tools are **simulated by design**: they stand in for real Jira/Atlassian systems so the
> agent can be observed and replayed with zero real-world risk.

---

## Testing

```bash
cd backend

# full suite (deterministic + live LLM tests)
pytest -q

# deterministic only (no network, no tokens)
pytest --ignore=tests/test_agent_live.py --ignore=tests/test_capture_live.py -q
```

- **57 deterministic tests** cover schemas, storage, the four tools, the interception
  recorder, replay, what-if overrides, anomalies, signing, the PDF, and every API endpoint.
- **Live tests** exercise the real Groq LLM and **skip gracefully** when no key is configured
  or the free-tier rate limit is hit (environmental, not a failure).

---

## Advanced / Compliance Features

| Feature | Module | Highlight |
|---|---|---|
| **Anomaly detection** | `core/anomalies.py` | Reasoning loops, out-of-domain recipients, tool errors, runaway length, missing decision |
| **Cryptographic signing** | `core/signing.py` | SHA-256 hash chain + HMAC-SHA256 — editing any byte breaks verification |
| **Compliance PDF** | `core/report.py` | Auditor report with integrity block + full trace |
| **Docker sandbox** | `Dockerfile`, `docker-compose.yml` | Replay in a `network_mode: none`, read-only container — see [`docs/SANDBOX.md`](docs/SANDBOX.md) |

```bash
# Run the API in a container
docker compose up --build api

# Replay inside a network-isolated, read-only sandbox (the safety proof)
docker compose --profile sandbox run --build replay-sandbox
```

---

## Design Decisions

- **LangGraph over a plain agent executor** — native checkpoints make replay and What-If cheap.
- **Free LLM provider (Groq)** — `llama-3.1-8b-instant` has a generous free daily token budget.
- **Fine-grained steps** — LLM calls and tool calls are separate, mirroring what the callbacks capture.
- **Deterministic replay** — recorded LLM *and* tool outputs are re-injected; calling the LLM again would re-diverge.
- **What-If = override a tool output** at step *N*, then go live from *N+1* — robust and easy to reason about.
- **Defensive tools** — `send_notification` rejects any recipient outside the known directory, preventing hallucinated emails.

---

## Project Status

| Milestone | Status |
|---|---|
| Foundations & frozen contract | ✅ |
| ReAct triage agent + 4 simulated tools | ✅ |
| Interception & capture (no agent changes) | ✅ |
| Deterministic replay | ✅ |
| Cockpit UI (playback, light/dark) | ✅ |
| What-If divergence | ✅ |
| Anomaly detection · signing · PDF · Docker sandbox | ✅ |

---

<div align="center">

*Built as a hackathon project — a black box that makes AI agents debuggable, auditable, and safe to investigate.*

</div>
