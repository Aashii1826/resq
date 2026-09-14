import { useEffect, useState } from 'react'

export default function CascadeTimeline({ timeline, onStep }) {
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    setIndex(0)
  }, [timeline])

  useEffect(() => {
    onStep?.(index)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, timeline])

  useEffect(() => {
    if (!playing) return
    if (index >= (timeline?.length ?? 1) - 1) {
      setPlaying(false)
      return
    }
    const t = setTimeout(() => setIndex((i) => i + 1), 900)
    return () => clearTimeout(t)
  }, [playing, index, timeline])

  if (!timeline || timeline.length === 0) {
    return (
      <div style={styles.bar}>
        <span style={styles.idleText}>Cascade timeline — run a failure to populate</span>
      </div>
    )
  }

  const current = timeline[index]

  return (
    <div style={styles.bar}>
      <button
        style={styles.playButton}
        onClick={() => setPlaying((p) => !p)}
        disabled={index >= timeline.length - 1 && !playing}
      >
        {playing ? '⏸' : '▶'}
      </button>

      <div style={styles.track}>
        {timeline.map((step, i) => (
          <button
            key={step.iteration}
            style={{
              ...styles.tick,
              background: i <= index ? 'var(--accent)' : 'var(--border)',
            }}
            onClick={() => {
              setPlaying(false)
              setIndex(i)
            }}
            title={step.label}
          />
        ))}
      </div>

      <div style={styles.label}>
        <span style={styles.tPlus}>T+{current.iteration}</span>
        <span style={styles.stepLabel}>{current.label}</span>
        <span style={styles.util}>mean util {(current.mean_utilization * 100).toFixed(1)}%</span>
      </div>
    </div>
  )
}

const styles = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    background: 'var(--bg-panel)',
    borderTop: '1px solid var(--border)',
    padding: '10px 20px',
  },
  idleText: {
    fontSize: 12,
    color: 'var(--text-tertiary)',
    fontFamily: 'var(--font-mono)',
  },
  playButton: {
    background: 'var(--bg-panel-raised)',
    border: '1px solid var(--border)',
    color: 'var(--text-primary)',
    borderRadius: '50%',
    width: 30,
    height: 30,
    cursor: 'pointer',
    fontSize: 12,
    flexShrink: 0,
  },
  track: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    flex: 1,
  },
  tick: {
    height: 6,
    flex: 1,
    border: 'none',
    borderRadius: 3,
    cursor: 'pointer',
    padding: 0,
  },
  label: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 12,
    fontFamily: 'var(--font-mono)',
    fontSize: 12,
    color: 'var(--text-secondary)',
    minWidth: 340,
    justifyContent: 'flex-end',
  },
  tPlus: {
    color: 'var(--accent)',
    fontWeight: 600,
  },
  stepLabel: {
    color: 'var(--text-primary)',
  },
  util: {
    color: 'var(--text-tertiary)',
  },
}
