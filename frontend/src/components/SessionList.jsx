export default function SessionList({ sessions, activeId, onSelect }) {
  if (sessions.length === 0) return <p className="muted small">No flights recorded yet.</p>;

  return (
    <ul className="flights">
      {sessions.map((s) => (
        <li
          key={s.session_id}
          className={"flight" + (s.session_id === activeId ? " is-active" : "")}
          onClick={() => onSelect(s.session_id)}
        >
          <span className={`light light--${s.status}`} title={s.status} />
          <div className="flight__main">
            <strong>{s.ticket_id}</strong>
            <small className="muted">{s.session_id}</small>
          </div>
          {s.synthetic ? (
            <span className="tag tag--synthetic" title="Hand-written demo — no real LLM">
              synthetic
            </span>
          ) : (
            <span className={`tag tag--${s.mode}`}>{s.mode}</span>
          )}
        </li>
      ))}
    </ul>
  );
}
