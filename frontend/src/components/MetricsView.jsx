// The M1–M6 evaluation dashboard — six cards, each with its real value and measurement protocol.
function tone(m) {
  // 0–100 scale: green high, amber mid, red low. M3 is "points gained" → always positive/neutral.
  if (m.display === "n/a") return "muted";
  if (m.id === "M3") return m.value > 0 ? "good" : "muted";
  if (m.value >= 80) return "good";
  if (m.value >= 50) return "warn";
  return "bad";
}

function Card({ m }) {
  return (
    <div className={`metric metric--${tone(m)}`}>
      <div className="metric__head">
        <span className="metric__id">{m.id}</span>
        {m.ai && <span className="metric__ai">AI</span>}
      </div>
      <div className="metric__value">{m.display}</div>
      <div className="metric__name">{m.name}</div>
      <div className="metric__detail">{m.detail}</div>
      <details className="metric__proto">
        <summary>protocol</summary>
        <p>{m.protocol}</p>
      </details>
    </div>
  );
}

export default function MetricsView({ report, onBack, onRefresh, refreshing }) {
  return (
    <div className="panel metrics">
      <div className="metrics__head">
        <button className="btn" onClick={onBack}>← Back to recorder</button>
        <span className="metrics__title">📈 EVALUATION · M1–M6 · {report.total_runs} runs</span>
        <button className="btn btn--ai" onClick={onRefresh} disabled={refreshing} style={{ width: "auto", marginLeft: "auto" }}>
          {refreshing ? "Recomputing…" : "↻ Recompute"}
        </button>
      </div>
      <div className="metrics__grid">
        {report.metrics.map((m) => <Card key={m.id} m={m} />)}
      </div>
      <p className="metrics__foot muted small">
        Generated {report.generated_at} · deterministic metrics measured over all runs; AI metrics sampled.
      </p>
    </div>
  );
}
