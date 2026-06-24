<div align="center">

# ✈️ Flight Recorder for AI Agents

**A black box for LLM agents — record every decision, replay it safely, diagnose failures with AI, and improve the agent automatically.**

[![Tests](https://img.shields.io/badge/tests-86%20passing-2fe6a8)](#5-run-the-tests)
[![Backend](https://img.shields.io/badge/backend-FastAPI%20%2B%20LangGraph-ff7a1a)](#tech-stack)
[![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-ff7a1a)](#tech-stack)
[![Agent](https://img.shields.io/badge/agent-Groq%20(Llama)-2fe6a8)](#tech-stack)
[![Judge](https://img.shields.io/badge/judge-Mistral-orange)](#ai-in-every-layer)
[![Jira](https://img.shields.io/badge/data-real%20Jira%20Cloud-0052CC)](#optional-connect-a-real-jira)

</div>

---

## Overview

An AI agent that triages Jira tickets makes **different decisions on every run**. When it gets one wrong, you can't understand *why* without re-running it — which fires **new, real, irreversible actions**.

**Flight Recorder** is a transparent black box for that agent. It **records** every LLM call and tool call, **replays** any run with zero real calls, lets you run **What-If** corrections, and uses AI to **judge, diagnose, and auto-fix** the agent.

> Like an aircraft's black box: you never re-fly the plane to investigate an incident — you replay the recorded data on a grounded simulator.

### The 4 modes

| Mode | What it does |
|---|---|
| 🔴 **RECORD** | Run the agent live; capture every step into SQLite (agent code untouched). |
| ▶️ **REPLAY** | Re-run from cached responses — **0 real LLM calls, 0 side effects** (notifications blocked). |
| ↯ **WHATIF** | Override a tool output, the system prompt, **or reword the ticket**, re-run live, compare trajectories. |
| ◆ **ANALYZE** | An **independent Mistral judge** scores the decision; AI **root-cause analysis** quotes the exact faulty prompt rule; **auto-fix** rewrites the prompt and re-runs. |

### AI in every layer

| Layer | Model | Role |
|---|---|---|
| Triage agent | **Groq** (Llama, tool-calling) | makes the decisions |
| LLM-as-Judge (no ground truth) | **Mistral** (independent provider) | scores decision quality |
| Auto-fix RCA + pattern insights | Groq (Llama 3.3 70B) | diagnoses & rewrites the prompt |

---

## Key Features

- 🎙️ **Transparent capture** — a LangChain callback records every LLM/tool call; the agent is never modified.
- ▶️ **Deterministic replay** — a proxy serves cached responses: zero real calls, side effects blocked, provable counters.
- ↯ **What-If** — diverge by tool output, corrected system prompt, or reworded ticket; side-by-side compare.
- 🔗 **Real Jira Cloud** — reads real past tickets, assigns a real user, posts a real comment, and **writes real labels** per run (with a local mock fallback).
- 🧑‍⚖️ **LLM-as-Judge** — an independent Mistral model rates each decision, no ground truth needed.
- 🤖 **Closed-loop auto-fix** — diagnose → generate corrected prompt → re-run → judge confirms the gain.
- 📈 **6-metric dashboard (M1–M6)** — triage accuracy, replay fidelity, What-If improvement, AI step quality, side-effect prevention, RCA confidence.
- 📊 **Multi-run pattern insights** + **⇄ decision diff** with green **FIXED** badges.
- 🔒 **Tamper-evident signing** (SHA-256 hash chain + HMAC) and 📄 **compliance PDF export**.
- 🛩️ **Cockpit UI** with a Timeline / Graph / Analyze view, playback scrubber, light/dark themes.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent | LangGraph ReAct agent + Groq (Llama), temperature 0 |
| Judge | Mistral API (OpenAI-compatible, JSON mode) |
| Backend | Python 3.10+, FastAPI, Uvicorn, Pydantic v2 |
| Storage | SQLite (sessions + steps) |
| Data | Real Jira Cloud REST API v3 (with local JSON/SQLite fallback) |
| Reports | ReportLab (PDF) |
| Frontend | React 18 + Vite |
| Tests | pytest (86) |

---

# 🚀 Getting Started — open & run the project

### Prerequisites

- **Python 3.10+**  and  **Node.js 18+**
- A **free Groq API key** — [console.groq.com](https://console.groq.com) (no credit card). **Required.**
- *(Optional)* a **free Mistral API key** — [console.mistral.ai](https://console.mistral.ai) — for the independent judge.
- *(Optional)* a **free Atlassian Jira** site — for real ticket data instead of the local mock.

---

### 1. Backend — install & configure

```bash
cd backend

# create an isolated environment
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate          # macOS / Linux

pip install -r requirements.txt

# create your local config from the template
copy .env.example .env               # Windows
# cp .env.example .env                # macOS / Linux
```

Open **`backend/.env`** and fill it in:

```ini
# --- required ---
GROQ_API_KEY=gsk_your_free_key_here
GROQ_MODEL=llama-3.1-8b-instant

# --- optional: independent LLM-judge (Mistral) ---
MISTRAL_API_KEY=                     # leave blank to judge with Groq instead
MISTRAL_MODEL=mistral-small-latest

# --- optional: connect a REAL Jira (else local mock is used) ---
JIRA_BASE_URL=                       # https://your-site.atlassian.net
JIRA_EMAIL=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=                    # e.g. KAN

# --- storage / signing ---
DATABASE_PATH=flight_recorder.db
```

| Variable | Required? | Purpose |
|---|---|---|
| `GROQ_API_KEY` | ✅ yes | the triage agent's LLM (free) |
| `GROQ_MODEL` | default set | agent model (6 are selectable in the UI) |
| `MISTRAL_API_KEY` | optional | independent judge; blank → judge with Groq |
| `JIRA_BASE_URL` / `EMAIL` / `API_TOKEN` / `PROJECT_KEY` | optional | real Jira; blank → local mock data |

> The app works fully **offline with mock data** if you only set `GROQ_API_KEY`.

---

### 2. Start the backend

```bash
# from backend/ with the venv active
uvicorn flight_recorder.api.main:app --reload
```

→ API at **http://127.0.0.1:8000** · interactive docs at **http://127.0.0.1:8000/docs**

---

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

→ UI at **http://localhost:5173**. Click **▶ Run & record**, type a problem, and watch the agent run. The UI talks only to the live backend (no fake data).

---

### 4. *(Optional)* Connect a real Jira

1. Create a free site: <https://www.atlassian.com/software/jira/free>
2. Create an API token: <https://id.atlassian.com/manage-profile/security/api-tokens>
3. Fill `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` in `backend/.env`
4. Verify the connection, then seed demo tickets:
   ```bash
   cd backend
   python -m scripts.check_jira     # should print: Authenticated as: <you>
   python -m scripts.seed_jira      # creates ~34 real tickets + a demo one
   ```
5. **Restart** the backend. Now `query_db`, `search_kb`, `get_user_info`, `send_notification`
   all use your real Jira, and each run writes real **labels** on the triaged issue.

---

### 5. Run the tests

```bash
cd backend

# fast, deterministic — no network, no tokens (recommended)
pytest -q --ignore=tests/test_agent_live.py --ignore=tests/test_capture_live.py

# full suite incl. live LLM tests (skips gracefully without a key / on rate limit)
pytest -q
```

**86 deterministic tests** cover storage, the tools, the interception recorder, replay, all
What-If modes, the LLM-judge, auto-fix, patterns, the M1–M6 metrics, RCA, the diff, anomalies,
signing, the PDF, and every API endpoint (LLM calls are mocked).

---

## Using the UI

| Action | Where |
|---|---|
| **▶ Run & record** | pick an LLM (6 models), describe a problem → a ticket is auto-created & triaged |
| **Timeline / Graph / ◆ Analyze** | view toggle in the center panel |
| **◆ Analyze** | auto-loads the **Mistral judge** verdict + **root-cause analysis** (quotes the faulty prompt rule) |
| **↻ Replay safely** | re-run with 0 real calls, side effects blocked |
| **↯ What-If / 🤖 Auto-fix** | right panel — override a step, or let the AI generate & validate a fix |
| **📈 Metrics (M1–M6)** · **📊 Insights** · **⇄ Diff (FIXED)** | left panel dashboards |
| **⬇ Export compliance PDF** | signed, auditor-ready report |

---

## REST API (base `/api`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health`, `/models`, `/jira/status` | probes & config |
| `GET` | `/sessions`, `/sessions/{id}` | list / full session |
| `POST` | `/runs` | run agent live (auto-creates the ticket), capture & store |
| `POST` | `/sessions/{id}/replay?engine=proxy\|live\|reemit` | deterministic / live replay |
| `POST` | `/sessions/{id}/whatif` | diverge by `tool_name`+`new_output`, `system_prompt`, or `ticket_text` |
| `GET` | `/agent/prompt` | current (buggy) + corrected system prompts |
| `GET` | `/sessions/{id}/judge` | LLM-as-Judge (Mistral) score |
| `GET` | `/sessions/{id}/rca` | root-cause analysis (ANALYZE mode) |
| `POST` | `/sessions/{id}/autofix` | closed-loop diagnose → fix → re-run → judge |
| `GET` | `/patterns`, `/metrics`, `/diff` | multi-run insights · M1–M6 · FIXED diff |
| `GET` | `/sessions/{id}/anomalies`, `/signature`, `/report.pdf` | audit & compliance |

---

## Documentation

- [`docs/EVALUATION.md`](docs/EVALUATION.md) — the M1–M6 metrics: protocol + real values.
- [`docs/DATA.md`](docs/DATA.md) — data sources, schema, labels, distribution.
- [`docs/CONTRACT.md`](docs/CONTRACT.md) — the frozen API + trace contract.
- [`docs/SANDBOX.md`](docs/SANDBOX.md) — isolated-replay guide.

---

<div align="center">

*A black box that makes AI agents debuggable, auditable, and self-improving — recorded on a real agent, judged by an independent model.*

</div>
