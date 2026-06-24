import { useCallback, useEffect, useState } from "react";
import { live, checkOnline } from "./api.js";
import SessionList from "./components/SessionList.jsx";
import FlightPath from "./components/FlightPath.jsx";
import GraphView from "./components/GraphView.jsx";
import StepDetail from "./components/StepDetail.jsx";
import NewRun from "./components/NewRun.jsx";
import InstrumentBar from "./components/InstrumentBar.jsx";
import PlaybackControls from "./components/PlaybackControls.jsx";
import WhatIfEditor from "./components/WhatIfEditor.jsx";
import WhatIfPromptEditor from "./components/WhatIfPromptEditor.jsx";
import WhatIfCompare from "./components/WhatIfCompare.jsx";
import AuditBar from "./components/AuditBar.jsx";
import AiPanel from "./components/AiPanel.jsx";
import InsightsView from "./components/InsightsView.jsx";
import MetricsView from "./components/MetricsView.jsx";
import AnalyzeView from "./components/AnalyzeView.jsx";
import DiffView from "./components/DiffView.jsx";

const PLAYBACK_INTERVAL_MS = 850;

export default function App() {
  const [online, setOnline] = useState(null); // null = checking, true, false
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [replayResult, setReplayResult] = useState(null);
  const [replaying, setReplaying] = useState(false);
  const [whatifResult, setWhatifResult] = useState(null);
  const [whatifRunning, setWhatifRunning] = useState(false);
  const [agentPrompts, setAgentPrompts] = useState(null);
  const [audit, setAudit] = useState({ signature: null, anomalies: null });
  const [error, setError] = useState(null);
  const [view, setView] = useState("timeline"); // "timeline" | "graph"
  const [insights, setInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [diff, setDiff] = useState(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("fr-theme") || "light");

  const steps = activeSession?.steps ?? [];
  const selectedStep = steps[cursor] ?? null;

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("fr-theme", theme);
  }, [theme]);

  const refreshSessions = useCallback(async () => {
    const list = await live.listSessions();
    setSessions(list);
    return list;
  }, []);

  // Load the audit strip (signature + anomalies) for any stored session — live or replay.
  const loadAudit = useCallback((sessionId) => {
    setAudit({ signature: null, anomalies: null });
    Promise.all([live.signature(sessionId), live.anomalies(sessionId)])
      .then(([signature, anomalies]) => setAudit({ signature, anomalies }))
      .catch(() => setAudit({ signature: null, anomalies: null }));
  }, []);

  const connect = useCallback(async () => {
    setError(null);
    const ok = await checkOnline();
    setOnline(ok);
    if (ok) {
      try {
        await refreshSessions();
        live.agentPrompt().then(setAgentPrompts).catch(() => setAgentPrompts(null));
      } catch (e) {
        setError(e.message);
      }
    }
  }, [refreshSessions]);

  useEffect(() => {
    connect();
  }, [connect]);

  // Playback engine: advance the cursor like a tape while "playing".
  useEffect(() => {
    if (!playing || !activeSession) return undefined;
    if (cursor >= steps.length - 1) {
      setPlaying(false);
      return undefined;
    }
    const id = setTimeout(() => setCursor((c) => c + 1), PLAYBACK_INTERVAL_MS);
    return () => clearTimeout(id);
  }, [playing, cursor, activeSession, steps.length]);

  async function openSession(sessionId) {
    try {
      const session = await live.getSession(sessionId);
      setActiveSession(session);
      setCursor(0);
      setPlaying(false);
      setReplayResult(null);
      loadAudit(sessionId);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleRecorded(sessionId) {
    await refreshSessions();
    await openSession(sessionId);
  }

  async function handleReplay() {
    if (!activeSession) return;
    setReplaying(true);
    setError(null);
    try {
      const result = await live.replay(activeSession.session_id);
      setReplayResult(result);
      setActiveSession(result.session);
      setCursor(0);
      setPlaying(true);
      // The replay is now a stored, first-class session: load its audit too.
      loadAudit(result.session.session_id);
      refreshSessions();
    } catch (e) {
      setError(e.message);
    } finally {
      setReplaying(false);
    }
  }

  async function handleWhatIf(toolName, newOutput) {
    if (!activeSession) return;
    setWhatifRunning(true);
    setError(null);
    try {
      const result = await live.whatif(activeSession.session_id, toolName, newOutput);
      setWhatifResult(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setWhatifRunning(false);
    }
  }

  async function handleWhatIfPrompt(systemPrompt) {
    if (!activeSession) return;
    setWhatifRunning(true);
    setError(null);
    try {
      const result = await live.whatifPrompt(activeSession.session_id, systemPrompt);
      setWhatifResult(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setWhatifRunning(false);
    }
  }

  async function handleCounterfactual(ticketText) {
    if (!activeSession) return;
    setWhatifRunning(true);
    setError(null);
    try {
      const result = await live.whatifTicket(activeSession.session_id, ticketText);
      setWhatifResult(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setWhatifRunning(false);
    }
  }

  async function openInsights() {
    setInsightsLoading(true);
    setError(null);
    try {
      setInsights(await live.patterns());
    } catch (e) {
      setError(e.message);
    } finally {
      setInsightsLoading(false);
    }
  }

  async function openMetrics(refresh = false) {
    setMetricsLoading(true);
    setError(null);
    try {
      setMetrics(await live.metrics(refresh));
    } catch (e) {
      setError(e.message);
    } finally {
      setMetricsLoading(false);
    }
  }

  async function openDiff(refresh = false) {
    setDiffLoading(true);
    setError(null);
    try {
      setDiff(await live.diff(2, refresh));
    } catch (e) {
      setError(e.message);
    } finally {
      setDiffLoading(false);
    }
  }

  const startPlay = () => {
    if (cursor >= steps.length - 1) setCursor(0);
    setPlaying(true);
  };
  const stepForward = () => {
    setPlaying(false);
    setCursor((c) => Math.min(c + 1, steps.length - 1));
  };
  const reset = () => {
    setPlaying(false);
    setCursor(0);
  };

  const canReplay = activeSession && activeSession.mode !== "replay";
  // Live AND replay sessions are real recorded runs: they get the full toolset
  // (audit strip + What-If divergence), unlike hand-written synthetic demos.
  const isRecordedRun =
    activeSession && !activeSession.synthetic &&
    (activeSession.mode === "live" || activeSession.mode === "replay");

  return (
    <div className="app">
      <header className="app__header">
        <div className="brand">
          ✈️ <b>Flight Recorder</b> <span>for AI Agents</span>
        </div>
        <div className="console-status">
          {activeSession && (
            <span className={`recmode recmode--${activeSession.mode}`}>
              {activeSession.mode === "replay" ? "◉ SIMULATOR MODE" : "■ FLIGHT DATA"}
            </span>
          )}
          <span className={`badge badge--${online ? "live" : "mock"}`}>
            {online === null ? "CONNECTING…" : online ? "LIVE API" : "BACKEND OFFLINE"}
          </span>
          <button
            className="theme-toggle"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
        </div>
      </header>

      {error && <p className="error">⚠ {error}</p>}

      {online === false && (
        <div className="offline">
          <p>⚠ Cannot reach the backend at <code>http://127.0.0.1:8000</code>.</p>
          <p className="muted small">
            Start it: <code>cd backend &amp;&amp; uvicorn flight_recorder.api.main:app --reload</code>
          </p>
          <button className="btn btn--primary" onClick={connect}>↻ Retry connection</button>
        </div>
      )}

      {online && (whatifResult ? (
        <WhatIfCompare result={whatifResult} onBack={() => setWhatifResult(null)} />
      ) : metrics ? (
        <MetricsView
          report={metrics}
          onBack={() => setMetrics(null)}
          onRefresh={() => openMetrics(true)}
          refreshing={metricsLoading}
        />
      ) : diff ? (
        <DiffView
          report={diff}
          onBack={() => setDiff(null)}
          onRefresh={() => openDiff(true)}
          refreshing={diffLoading}
        />
      ) : insights ? (
        <InsightsView report={insights} onBack={() => setInsights(null)} />
      ) : (
        <div className="layout">
          <aside className="panel">
            <h2 className="panel__title">Flights</h2>
            <NewRun onRecorded={handleRecorded} />
            <hr className="sep" />
            <SessionList
              sessions={sessions}
              activeId={activeSession?.session_id}
              onSelect={openSession}
            />
            <hr className="sep" />
            <button className="btn btn--metrics" onClick={() => openMetrics(false)} disabled={metricsLoading}>
              {metricsLoading ? "Computing M1–M6…" : "📈 Metrics (M1–M6)"}
            </button>
            <button className="btn btn--ai" onClick={openInsights} disabled={insightsLoading}>
              {insightsLoading ? "Analysing all runs…" : "📊 Insights (all runs)"}
            </button>
            <button className="btn btn--autofix" onClick={() => openDiff(false)} disabled={diffLoading}>
              {diffLoading ? "Auto-fixing & diffing…" : "⇄ Diff (FIXED badges)"}
            </button>
          </aside>

          <main className="panel">
            <div className="panel__head">
              <h2 className="panel__title">Flight Data Recorder</h2>
              {activeSession && (
                <div className="viewtoggle">
                  <button className={view === "timeline" ? "is-on" : ""} onClick={() => setView("timeline")}>≣ Timeline</button>
                  <button className={view === "graph" ? "is-on" : ""} onClick={() => setView("graph")}>⌗ Graph</button>
                  <button className={view === "analyze" ? "is-on" : ""} onClick={() => setView("analyze")}>◆ Analyze</button>
                </div>
              )}
            </div>
            {activeSession ? (
              <>
                <InstrumentBar session={activeSession} replay={replayResult} />
                {isRecordedRun && (audit.signature || audit.anomalies) && (
                  <AuditBar
                    sessionId={activeSession.session_id}
                    signature={audit.signature}
                    anomalies={audit.anomalies}
                  />
                )}
                <PlaybackControls
                  playing={playing}
                  cursor={cursor}
                  total={steps.length}
                  onPlay={startPlay}
                  onPause={() => setPlaying(false)}
                  onStep={stepForward}
                  onReset={reset}
                  onReplay={handleReplay}
                  canReplay={canReplay}
                  replaying={replaying}
                />
                {view === "analyze" ? (
                  <AnalyzeView session={activeSession} />
                ) : view === "graph" ? (
                  <GraphView
                    session={activeSession}
                    cursor={cursor}
                    anomalySteps={new Set((audit.anomalies || []).map((a) => a.step_number).filter(Boolean))}
                    onSelect={(i) => {
                      setPlaying(false);
                      setCursor(i);
                    }}
                  />
                ) : (
                  <FlightPath
                    session={activeSession}
                    cursor={cursor}
                    anomalySteps={new Set((audit.anomalies || []).map((a) => a.step_number).filter(Boolean))}
                    onSelect={(i) => {
                      setPlaying(false);
                      setCursor(i);
                    }}
                  />
                )}
              </>
            ) : (
              <p className="muted small">
                Select a flight, or click ▶ Run &amp; record to capture a real agent run.
              </p>
            )}
          </main>

          <aside className="panel">
            <h2 className="panel__title">Black Box Readout</h2>
            <StepDetail step={selectedStep} />
            {isRecordedRun && selectedStep?.type === "tool_call" && (
              <>
                <hr className="sep" />
                <WhatIfEditor step={selectedStep} onRun={handleWhatIf} running={whatifRunning} />
              </>
            )}
            {isRecordedRun && selectedStep?.type === "llm_call" && (
              <>
                <hr className="sep" />
                <WhatIfPromptEditor
                  prompts={agentPrompts}
                  onRun={handleWhatIfPrompt}
                  running={whatifRunning}
                />
              </>
            )}
            {isRecordedRun && (
              <>
                <hr className="sep" />
                <AiPanel
                  session={activeSession}
                  onCounterfactual={handleCounterfactual}
                  busy={whatifRunning}
                />
              </>
            )}
          </aside>
        </div>
      ))}
    </div>
  );
}
