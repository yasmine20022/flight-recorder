import { useCallback, useEffect, useState } from "react";
import { live, checkOnline } from "./api.js";
import SessionList from "./components/SessionList.jsx";
import FlightPath from "./components/FlightPath.jsx";
import StepDetail from "./components/StepDetail.jsx";
import NewRun from "./components/NewRun.jsx";
import InstrumentBar from "./components/InstrumentBar.jsx";
import PlaybackControls from "./components/PlaybackControls.jsx";
import WhatIfEditor from "./components/WhatIfEditor.jsx";
import WhatIfCompare from "./components/WhatIfCompare.jsx";
import AuditBar from "./components/AuditBar.jsx";

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
  const [audit, setAudit] = useState({ signature: null, anomalies: null });
  const [error, setError] = useState(null);
  const [theme, setTheme] = useState(() => localStorage.getItem("fr-theme") || "dark");

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

  const connect = useCallback(async () => {
    setError(null);
    const ok = await checkOnline();
    setOnline(ok);
    if (ok) {
      try {
        await refreshSessions();
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
      setAudit({ signature: null, anomalies: null });
      Promise.all([live.signature(sessionId), live.anomalies(sessionId)])
        .then(([signature, anomalies]) => setAudit({ signature, anomalies }))
        .catch(() => setAudit({ signature: null, anomalies: null }));
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
          </aside>

          <main className="panel">
            <h2 className="panel__title">Flight Data Recorder</h2>
            {activeSession ? (
              <>
                <InstrumentBar session={activeSession} replay={replayResult} />
                {activeSession.mode === "live" && (audit.signature || audit.anomalies) && (
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
                <FlightPath
                  session={activeSession}
                  cursor={cursor}
                  anomalySteps={new Set((audit.anomalies || []).map((a) => a.step_number).filter(Boolean))}
                  onSelect={(i) => {
                    setPlaying(false);
                    setCursor(i);
                  }}
                />
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
            {activeSession?.mode === "live" && selectedStep?.type === "tool_call" && (
              <>
                <hr className="sep" />
                <WhatIfEditor step={selectedStep} onRun={handleWhatIf} running={whatifRunning} />
              </>
            )}
          </aside>
        </div>
      ))}
    </div>
  );
}
