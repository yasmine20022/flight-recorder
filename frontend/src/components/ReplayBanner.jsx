export default function ReplayBanner({ result }) {
  return (
    <div className="replay-banner">
      <div className="replay-banner__title">
        ▶ Replay complete — no real action was triggered
      </div>
      <div className="replay-banner__counters">
        <span className="counter counter--ok">Real calls: {result.real_calls}</span>
        <span className="counter">Intercepted: {result.intercepted_calls}</span>
        <span className="counter counter--block">send_notification: BLOCKED</span>
      </div>
    </div>
  );
}
