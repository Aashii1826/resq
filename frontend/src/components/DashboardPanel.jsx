function StatRow({ label, value, unit, tone }) {
  return (
    <div style={styles.statRow}>
      <span style={styles.statLabel}>{label}</span>
      <span style={{ ...styles.statValue, color: tone || 'var(--text-primary)' }}>
        {value}
        {unit && <span style={styles.statUnit}> {unit}</span>}
      </span>
    </div>
  )
}

function toneForResilience(score) {
  if (score >= 80) return 'var(--status-healthy)'
  if (score >= 60) return 'var(--status-stressed)'
  return 'var(--status-overloaded)'
}

export default function DashboardPanel({ metrics, loading }) {
  if (!metrics) {
    return (
      <div style={styles.panel}>
        <div style={styles.title}>System resilience</div>
        <div style={styles.loading}>Loading baseline…</div>
      </div>
    )
  }

  const {
    resilience_score,
    population_affected,
    healthcare_access_loss_percent,
    travel_time_increase_percent,
    overloaded_edges,
    avg_travel_time_min,
  } = metrics

  return (
    <div style={{ ...styles.panel, opacity: loading ? 0.6 : 1 }}>
      <div style={styles.title}>System resilience</div>
      <div style={styles.heroScore}>
        <span style={{ ...styles.heroNumber, color: toneForResilience(resilience_score) }}>
          {resilience_score}
        </span>
        <span style={styles.heroMax}>/ 100</span>
      </div>

      <div style={styles.divider} />

      <StatRow
        label="Population exposure"
        value={population_affected?.toLocaleString() ?? '—'}
        tone={population_affected > 0 ? 'var(--status-overloaded)' : 'var(--status-healthy)'}
      />
      <StatRow
        label="Healthcare access loss"
        value={healthcare_access_loss_percent != null ? `-${healthcare_access_loss_percent}` : '0'}
        unit="%"
        tone={healthcare_access_loss_percent > 15 ? 'var(--status-overloaded)' : undefined}
      />
      <StatRow
        label="Travel time change"
        value={travel_time_increase_percent != null ? `+${travel_time_increase_percent}` : '0'}
        unit="%"
        tone={travel_time_increase_percent > 20 ? 'var(--status-stressed)' : undefined}
      />
      <StatRow
        label="Avg travel time"
        value={avg_travel_time_min ?? '—'}
        unit="min"
      />
      <StatRow
        label="Overloaded links"
        value={overloaded_edges ?? 0}
        tone={overloaded_edges > 8 ? 'var(--status-overloaded)' : undefined}
      />
    </div>
  )
}

const styles = {
  panel: {
    background: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '16px 18px',
    transition: 'opacity 150ms ease',
  },
  title: {
    fontSize: 12,
    color: 'var(--text-secondary)',
    marginBottom: 10,
    letterSpacing: '0.02em',
  },
  loading: {
    fontFamily: 'var(--font-mono)',
    fontSize: 12,
    color: 'var(--text-tertiary)',
  },
  heroScore: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 6,
    marginBottom: 14,
  },
  heroNumber: {
    fontFamily: 'var(--font-mono)',
    fontSize: 40,
    fontWeight: 600,
    lineHeight: 1,
  },
  heroMax: {
    fontFamily: 'var(--font-mono)',
    fontSize: 14,
    color: 'var(--text-tertiary)',
  },
  divider: {
    height: 1,
    background: 'var(--border-soft)',
    margin: '4px 0 12px',
  },
  statRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    padding: '6px 0',
  },
  statLabel: {
    fontSize: 13,
    color: 'var(--text-secondary)',
  },
  statValue: {
    fontFamily: 'var(--font-mono)',
    fontSize: 14,
    fontWeight: 500,
  },
  statUnit: {
    fontSize: 11,
    color: 'var(--text-tertiary)',
  },
}
