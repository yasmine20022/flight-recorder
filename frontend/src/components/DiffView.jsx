// Multi-ticket decision diff: original vs corrected, with green FIXED badges.
export default function DiffView({ report, onBack, onRefresh, refreshing }) {
  return (
    <div className="panel diff">
      <div className="diff__head">
        <button className="btn" onClick={onBack}>← Back to recorder</button>
        <span className="diff__title">⇄ DECISION DIFF · {report.fixed_count}/{report.rows.length} FIXED</span>
        <button className="btn btn--ai" onClick={onRefresh} disabled={refreshing} style={{ marginLeft: "auto", width: "auto" }}>
          {refreshing ? "Recomputing…" : "↻ Recompute"}
        </button>
      </div>

      {report.rows.length === 0 ? (
        <p className="muted small">No runs to diff yet — record a few first.</p>
      ) : (
        <div className="diff__rows">
          {report.rows.map((r) => (
            <div key={r.session_id} className={"diff__row" + (r.fixed ? " is-fixed" : "")}>
              <div className="diff__ticket">
                {r.ticket_id}
                {r.fixed && <span className="fixedbadge">✔ FIXED</span>}
              </div>
              <div className="diff__cols">
                <div className="diff__col diff__col--orig">
                  <div className="diff__h">ORIGINAL · {r.original_score}/10</div>
                  <pre>{r.original_decision}</pre>
                </div>
                <div className="diff__col diff__col--fixed">
                  <div className="diff__h">CORRECTED · {r.fixed_score}/10</div>
                  <pre>{r.fixed_decision}</pre>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
