// Multi-run pattern analysis (feature 2): aggregate stats + LLM-found structural weaknesses.
function StatBlock({ title, data }) {
  const entries = Object.entries(data || {}).sort((a, b) => b[1] - a[1]);
  const max = entries.reduce((m, [, v]) => Math.max(m, v), 1);
  return (
    <div className="ins-stat">
      <div className="ins-stat__title">{title}</div>
      {entries.length === 0 ? (
        <div className="ins-stat__empty">—</div>
      ) : (
        entries.map(([k, v]) => (
          <div key={k} className="ins-bar">
            <span className="ins-bar__k" title={k}>{k}</span>
            <span className="ins-bar__track"><span className="ins-bar__fill" style={{ width: `${(v / max) * 100}%` }} /></span>
            <span className="ins-bar__v">{v}</span>
          </div>
        ))
      )}
    </div>
  );
}

function List({ title, items, tone }) {
  return (
    <div className={`ins-list ins-list--${tone}`}>
      <div className="ins-list__title">{title}</div>
      {items?.length ? (
        <ul>{items.map((it, k) => <li key={k}>{it}</li>)}</ul>
      ) : (
        <p className="muted small">No items.</p>
      )}
    </div>
  );
}

export default function InsightsView({ report, onBack }) {
  return (
    <div className="panel insights">
      <div className="insights__head">
        <button className="btn" onClick={onBack}>← Back to recorder</button>
        <span className="insights__title">📊 AGENT INSIGHTS · {report.total_runs} runs analysed</span>
      </div>

      {report.summary && <div className="insights__summary">{report.summary}</div>}

      <div className="insights__grid">
        <StatBlock title="Routed team" data={report.by_team} />
        <StatBlock title="Priority" data={report.by_priority} />
        <StatBlock title="Anomalies" data={report.anomaly_counts} />
        <StatBlock title="Models used" data={report.model_usage} />
      </div>

      <div className="insights__cols">
        <List title="⚠ Structural weaknesses" items={report.weaknesses} tone="warn" />
        <List title="✔ Recommendations" items={report.recommendations} tone="good" />
      </div>

      <div className="insights__foot">
        avg {report.avg_steps} steps/run · {report.flagged_runs}/{report.total_runs} runs flagged with anomalies
      </div>
    </div>
  );
}
