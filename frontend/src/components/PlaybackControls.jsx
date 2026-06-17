// Black-box "tape" controls: step through the recorded run like scrubbing a recorder.
export default function PlaybackControls({
  playing,
  cursor,
  total,
  onPlay,
  onPause,
  onStep,
  onReset,
  onReplay,
  canReplay,
  replaying,
}) {
  const pct = total ? Math.round(((cursor + 1) / total) * 100) : 0;

  return (
    <div className="playback">
      <div className="playback__btns">
        <button className="ctrl" onClick={onReset} title="Restart">⏮</button>
        {playing ? (
          <button className="ctrl ctrl--primary" onClick={onPause} title="Pause">⏸</button>
        ) : (
          <button className="ctrl ctrl--primary" onClick={onPlay} title="Play recording">▶</button>
        )}
        <button className="ctrl" onClick={onStep} title="Step forward">⏭</button>
        <span className="playback__pos">{total ? cursor + 1 : 0}/{total}</span>
      </div>

      <div className="playback__bar">
        <div className="playback__fill" style={{ width: `${pct}%` }} />
      </div>

      {canReplay && (
        <button className="btn btn--primary" onClick={onReplay} disabled={replaying}>
          {replaying ? "Replaying…" : "↻ Replay safely"}
        </button>
      )}
    </div>
  );
}
