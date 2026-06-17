import { reportUrl } from "../api.js";

// Audit & integrity strip: cryptographic signature, anomaly findings, PDF export.
export default function AuditBar({ sessionId, signature, anomalies }) {
  const counts = (anomalies ?? []).reduce((acc, a) => {
    acc[a.severity] = (acc[a.severity] || 0) + 1;
    return acc;
  }, {});
  const total = anomalies?.length ?? 0;

  return (
    <div className="audit">
      <div className="audit__row">
        {signature && (
          <span className={"audit__chip " + (signature.verified ? "is-ok" : "is-bad")}>
            🔒 {signature.verified ? "SIGNED & VERIFIED" : "SIGNATURE INVALID"}
            <code>{signature.digest.slice(0, 12)}…</code>
          </span>
        )}

        {total === 0 ? (
          <span className="audit__chip is-clean">✓ NO ANOMALIES</span>
        ) : (
          <span className="audit__chip is-warn">
            ⚠ {total} ANOMAL{total > 1 ? "IES" : "Y"}
            {counts.critical ? ` · ${counts.critical} critical` : ""}
          </span>
        )}

        <a className="audit__chip audit__pdf" href={reportUrl(sessionId)} target="_blank" rel="noreferrer">
          ⬇ Export compliance PDF
        </a>
      </div>

      {total > 0 && (
        <ul className="audit__list">
          {anomalies.map((a, i) => (
            <li key={i} className={`audit__finding sev-${a.severity}`}>
              <span className="audit__sev">{a.severity}</span>
              {a.step_number ? <span className="audit__step">step {a.step_number}</span> : null}
              <span>{a.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
