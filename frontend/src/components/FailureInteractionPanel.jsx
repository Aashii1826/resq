export default function FailureInteractionPanel({ selectedEdge, onSimulate, simulating }) {
  if (!selectedEdge) {
    return (
      <div style={styles.panel}>
        <div style={styles.title}>Road detail</div>
        <div style={styles.empty}>Click a road on the map to inspect it.</div>
      </div>
    )
  }

  const { edge_id, road_type, status, utilization, capacity } = selectedEdge

  return (
    <div style={styles.panel}>
      <div style={styles.title}>Road detail</div>
      <div style={styles.roadId}>{edge_id.toUpperCase()}</div>
      <div style={styles.roadType}>{road_type}</div>

      <div style={styles.row}>
        <span style={styles.label}>Status</span>
        <span style={{ ...styles.value, color: statusColor(status) }}>{status}</span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Utilization</span>
        <span style={styles.value}>
          {utilization != null ? `${Math.round(utilization * 100)}%` : '—'}
        </span>
      </div>
      <div style={styles.row}>
        <span style={styles.label}>Capacity</span>
        <span style={styles.value}>{capacity?.toLocaleString() ?? '—'}</span>
      </div>

      <button
        style={styles.failButton}
        onClick={() => onSimulate(edge_id)}
        disabled={simulating || status === 'FAILED'}
      >
        {status === 'FAILED'
          ? 'Already failed'
          : simulating
          ? 'Running cascade…'
          : 'Simulate failure'}
      </button>
    </div>
  )
}

function statusColor(status) {
  return {
    HEALTHY: 'var(--status-healthy)',
    STRESSED: 'var(--status-stressed)',
    OVERLOADED: 'var(--status-overloaded)',
    FAILED: 'var(--status-failed)',
  }[status] || 'var(--text-primary)'
}

const styles = {
  panel: {
    background: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '16px 18px',
  },
  title: {
    fontSize: 12,
    color: 'var(--text-secondary)',
    marginBottom: 10,
  },
  empty: {
    fontSize: 13,
    color: 'var(--text-tertiary)',
    lineHeight: 1.5,
  },
  roadId: {
    fontFamily: 'var(--font-mono)',
    fontSize: 18,
    fontWeight: 600,
  },
  roadType: {
    fontSize: 12,
    color: 'var(--text-tertiary)',
    textTransform: 'capitalize',
    marginBottom: 12,
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '5px 0',
  },
  label: {
    fontSize: 13,
    color: 'var(--text-secondary)',
  },
  value: {
    fontFamily: 'var(--font-mono)',
    fontSize: 13,
  },
  failButton: {
    marginTop: 14,
    width: '100%',
    background: 'var(--accent)',
    color: '#16140f',
    border: 'none',
    borderRadius: 'var(--radius-sm)',
    padding: '10px 0',
    fontFamily: 'var(--font-display)',
    fontWeight: 600,
    fontSize: 13,
    cursor: 'pointer',
  },
}
