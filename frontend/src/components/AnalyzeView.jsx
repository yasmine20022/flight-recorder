import { useEffect, useState } from "react";
import { live } from "../api.js";

const tone = (s) => (s >= 7 ? "good" : s >= 4 ? "warn" : "bad");

// ANALYZE mode (the 4th mode): auto-loads the AI root-cause analysis + the independent judge.
export default function AnalyzeView({ session }) {
  const [rca, setRca] = useState(null);
  const [judg, setJudg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    setLoading(true); setErr(null); setRca(null); setJudg(null);
    Promise.allSettled([live.rca(session.session_id), live.judge(session.session_id)])
      .then(([r, j]) => {
        if (!alive) return;
        if (r.status === "fulfilled") setRca(r.value);
        else setErr(r.reason?.message || "RCA failed");
        if (j.status === "fulfilled") setJudg(j.value);
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [session.session_id]);

  return (
    <div className="analyze">
      <div className="analyze__mode">◆ ANALYZE MODE · AI root-cause + independent judge</div>
      {loading && <p className="muted small">🧠 Diagnosing this run… (root-cause + Mistral judge)</p>}
      {err && <p className="error small">⚠ {err}</p>}

      {judg && (
        <div className="analyze__judge">
          <div className="analyze__judgerow">
            <span className={`verdict verdict--${judg.verdict}`}>{judg.verdict}</span>
            <span className={`scorepill scorepill--${tone(judg.score)}`}>{judg.score}/10</span>
            <span className="analyze__by">judged by {judg.model}</span>
          </div>
          <p className="ai__text">{judg.rationale}</p>
          {judg.issues?.length > 0 && (
            <ul className="ai__list">{judg.issues.map((i, k) => <li key={k}>{i}</li>)}</ul>
          )}
        </div>
      )}

      {rca && (
        <div className="analyze__rca">
          <div className="analyze__label">ROOT CAUSE · confidence {rca.confidence}%</div>
          <p className="analyze__cause">{rca.root_cause}</p>
          {rca.faulty_quote && (
            <>
              <div className="analyze__label">⚑ EXACT FAULTY RULE QUOTED FROM THE PROMPT</div>
              <blockquote className="analyze__quote">“{rca.faulty_quote}”</blockquote>
            </>
          )}
          {rca.fix_summary && (
            <>
              <div className="analyze__label">SUGGESTED FIX</div>
              <p className="ai__text">✔ {rca.fix_summary}</p>
            </>
          )}
          <div className="analyze__by">RCA by {rca.model}</div>
        </div>
      )}
    </div>
  );
}
