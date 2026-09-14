import { useState } from 'react'
import { optimizeInterventions } from '../services/api'

const CANDIDATES = [
  { id: 'upgrade_j17', label: 'Upgrade J17', type: 'capacity_upgrade', cost: 3 },
  { id: 'alt_route', label: 'Create alternate route', type: 'alternate_route', cost: 4 },
  { id: 'hospital_access', label: 'Improve hospital access', type: 'service_access', cost: 2 },
]

export default function InterventionPlannerPanel() {
  const [budget, setBudget] = useState(5)
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)

  async function handleOptimize() {
    setRunning(true)
    setResult(null)
    try {
      const res = await optimizeInterventions({ candidates: CANDIDATES, budget })
      setResult(res)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div style={styles.panel}>
      <div style={styles.title}>Resilience planner</div>

      <div style={styles.budgetRow}>
        <span style={styles.label}>Available budget</span>
        <div style={styles.budgetInput}>
          <span style={styles.currency}>₹</span>
          <input
            type="number"
            value={budget}
            min={0}
            onChange={(e) => setBudget(Number(e.target.value))}
            style={styles.input}
          />
          <span style={styles.currencyUnit}>Cr</span>
        </div>
      </div>

      <div style={styles.candidates}>
        {CANDIDATES.map((c) => (
          <div key={c.id} style={styles.candidateRow}>
            <span style={styles.candidateLabel}>{c.label}</span>
            <span style={styles.candidateCost}>₹{c.cost} Cr</span>
          </div>
        ))}
      </div>

      <button style={styles.findButton} onClick={handleOptimize} disabled={running}>
        {running ? 'Evaluating combinations…' : 'Find best plan'}
      </button>

      {result && (
        <div style={styles.result}>
          <div style={styles.resultTitle}>Recommended plan</div>
          {result.recommended_interventions.map((r) => (
            <div key={r.id} style={styles.resultItem}>+ {r.label}</div>
          ))}

          <div style={styles.resultDivider} />

          <div style={styles.resultRow}>
            <span style={styles.label}>Cost</span>
            <span style={styles.value}>₹{result.total_cost} Cr</span>
          </div>
          <div style={styles.resultRow}>
            <span style={styles.label}>Resilience</span>
            <span style={styles.value}>
              {result.baseline_resilience} <ArrowGain /> {result.new_resilience}
            </span>
          </div>
          <div style={styles.resultRow}>
            <span style={styles.label}>Population exposure reduced</span>
            <span style={{ ...styles.value, color: 'var(--status-healthy)' }}>
              −{result.population_exposure_reduction.toLocaleString()}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

function ArrowGain() {
  return <span style={{ color: 'var(--accent)', margin: '0 4px' }}>→</span>
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
    marginBottom: 12,
  },
  budgetRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  label: {
    fontSize: 13,
    color: 'var(--text-secondary)',
  },
  budgetInput: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    background: 'var(--bg-panel-raised)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '4px 8px',
  },
  currency: {
    fontFamily: 'var(--font-mono)',
    fontSize: 13,
    color: 'var(--text-tertiary)',
  },
  currencyUnit: {
    fontFamily: 'var(--font-mono)',
    fontSize: 12,
    color: 'var(--text-tertiary)',
  },
  input: {
    width: 44,
    background: 'transparent',
    border: 'none',
    color: 'var(--text-primary)',
    fontFamily: 'var(--font-mono)',
    fontSize: 13,
    textAlign: 'right',
  },
  candidates: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    marginBottom: 14,
  },
  candidateRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 12,
    padding: '4px 0',
    borderBottom: '1px solid var(--border-soft)',
  },
  candidateLabel: {
    color: 'var(--text-secondary)',
  },
  candidateCost: {
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-tertiary)',
  },
  findButton: {
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
  result: {
    marginTop: 14,
    paddingTop: 12,
    borderTop: '1px solid var(--border-soft)',
  },
  resultTitle: {
    fontSize: 12,
    color: 'var(--accent)',
    marginBottom: 8,
    fontWeight: 600,
  },
  resultItem: {
    fontSize: 13,
    padding: '2px 0',
  },
  resultDivider: {
    height: 1,
    background: 'var(--border-soft)',
    margin: '10px 0',
  },
  resultRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '4px 0',
  },
  value: {
    fontFamily: 'var(--font-mono)',
    fontSize: 13,
  },
}
