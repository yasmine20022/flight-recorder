import { useState } from "react";
import { live } from "../api.js";

function ScorePill({ score }) {
  const tone = score >= 7 ? "good" : score >= 4 ? "warn" : "bad";
  return <span className={`scorepill scorepill--${tone}`}>{score}/10</span>;
}

// Per-run AI analysis: LLM-judge (feature 4), auto-fix closed loop (feature 1),
// and counterfactual ticket rephrasing (feature 5).
export default function AiPanel({ session, onCounterfactual, busy }) {
  const [judg, setJudg] = useState(null);
  const [judging, setJudging] = useState(false);
  const [fix, setFix] = useState(null);
  const [fixing, setFixing] = useState(false);
  const [cf, setCf] = useState("");
  const [err, setErr] = useState(null);

  async function doJudge() {
    setJudging(true); setErr(null);
    try { setJudg(await live.judge(session.session_id)); }
    catch (e) { setErr(e.message); }
    finally { setJudging(false); }
  }
  async function doFix() {
    setFixing(true); setErr(null); setFix(null);
    try { setFix(await live.autofix(session.session_id)); }
    catch (e) { setErr(e.message); }
    finally { setFixing(false); }
  }

  return (
    <div className="ai">
      <div className="ai__title">🧠 AI ANALYSIS</div>

      {/* feature 4 — LLM-as-Judge */}
      <button className="btn btn--ai" onClick={doJudge} disabled={judging}>
        {judging ? "Judging…" : "🧑‍⚖️ Judge decision quality"}
      </button>
      {judg && (
        <div className="ai__card">
          <div className="ai__row">
            <span className={`verdict verdict--${judg.verdict}`}>{judg.verdict}</span>
            <ScorePill score={judg.score} />
          </div>
          <p className="ai__text">{judg.rationale}</p>
          {judg.issues?.length > 0 && (
            <ul className="ai__list">{judg.issues.map((i, k) => <li key={k}>{i}</li>)}</ul>
          )}
          <div className="ai__by">independent judge · {judg.model}</div>
        </div>
      )}

      {/* feature 1 — auto-fix closed loop */}
      <button className="btn btn--autofix" onClick={doFix} disabled={fixing}>
        {fixing ? "Diagnosing & re-running… (~1 min)" : "🤖 Auto-fix this run"}
      </button>
      {fix && (
        <div className="ai__card">
          <div className="ai__label">ROOT CAUSE (AI-diagnosed)</div>
          <p className="ai__text">{fix.root_cause}</p>
          <div className="ai__ba">
            <div className="ba ba--before">
              <div className="ba__h">BEFORE <ScorePill score={fix.original_judgment.score} /></div>
              <pre>{fix.original_decision}</pre>
            </div>
            <div className="ba ba--after">
              <div className="ba__h">AFTER <ScorePill score={fix.fixed_judgment.score} /></div>
              <pre>{fix.fixed_decision}</pre>
            </div>
          </div>
          <div className={"ai__bar " + (fix.improved ? "is-up" : "is-flat")}>
            {fix.improved
              ? `✔ Auto-fix raised decision quality ${fix.original_judgment.score} → ${fix.fixed_judgment.score}/10`
              : "= No measurable improvement"}
          </div>
          <details className="ai__details">
            <summary>Show AI-generated corrected prompt</summary>
            <pre>{fix.corrected_prompt}</pre>
          </details>
        </div>
      )}

      {/* feature 5 — counterfactual ticket */}
      <div className="ai__label">COUNTERFACTUAL · reword the ticket</div>
      <textarea
        className="ai__cf" rows={2} value={cf} disabled={busy}
        onChange={(e) => setCf(e.target.value)}
        placeholder="e.g. Backend API 500 error on /api/payments"
      />
      <button
        className="btn btn--whatif"
        onClick={() => cf.trim() && onCounterfactual(cf.trim())}
        disabled={busy || !cf.trim()}
      >
        {busy ? "Diverging…" : "↯ Re-run on reworded ticket"}
      </button>

      {err && <p className="error small">⚠ {err}</p>}
    </div>
  );
}
