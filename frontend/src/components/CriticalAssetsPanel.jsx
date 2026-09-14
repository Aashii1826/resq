import { useEffect, useState } from 'react'
import { getCriticality } from '../services/api'

export default function CriticalAssetsPanel({ onSelectAsset }) {
  const [ranked, setRanked] = useState(null)
  const [expandedId, setExpandedId] = useState(null)

  useEffect(() => {
    getCriticality().then((res) => setRanked(res.ranked))
  }, [])

  return (
    <div style={styles.panel}>
      <div style={styles.title}>Top systemic risks</div>

      {!ranked && <div style={styles.loading}>Computing…</div>}

      {ranked && (
        <div style={styles.list}>
          {ranked.map((item, i) => {
            const expanded = expandedId === item.edge_id
            const rankGap = item.traditional_centrality_rank - item.systemic_rank
            return (
              <div key={item.edge_id} style={styles.item}>
                <button
                  style={styles.itemRow}
                  onClick={() => {
                    setExpandedId(expanded ? null : item.edge_id)
                    onSelectAsset?.(item.edge_id)
                  }}
                >
                  <span style={styles.rank}>{i + 1}</span>
                  <span style={styles.name}>{item.name}</span>
                  <span style={styles.score}>{item.systemic_criticality}</span>
                </button>

                {expanded && (
                  <div style={styles.detail}>
                    <div style={styles.detailRow}>
                      <span style={styles.detailLabel}>Systemic criticality</span>
                      <span style={styles.detailValue}>{item.systemic_criticality}</span>
                    </div>
                    <div style={styles.detailRow}>
                      <span style={styles.detailLabel}>Traditional centrality rank</span>
                      <span style={styles.detailValue}>#{item.traditional_centrality_rank}</span>
                    </div>
                    <div style={styles.detailRow}>
                      <span style={styles.detailLabel}>Systemic risk rank</span>
                      <span style={styles.detailValue}>#{item.systemic_rank}</span>
                    </div>
                    {rankGap > 3 && (
                      <div style={styles.insight}>
                        Ranked #{item.traditional_centrality_rank} by traffic alone, but
                        #{item.systemic_rank} by actual system impact — an easy-to-miss risk.
                      </div>
                    )}
                    <div style={styles.detailRow}>
                      <span style={styles.detailLabel}>Primary impact</span>
                      <span style={styles.detailValue}>{item.primary_impact}</span>
                    </div>
                    <div style={styles.detailRow}>
                      <span style={styles.detailLabel}>Affected population</span>
                      <span style={styles.detailValue}>{item.population_exposed.toLocaleString()}</span>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
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
  loading: {
    fontFamily: 'var(--font-mono)',
    fontSize: 12,
    color: 'var(--text-tertiary)',
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  item: {
    borderBottom: '1px solid var(--border-soft)',
  },
  itemRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    width: '100%',
    background: 'none',
    border: 'none',
    padding: '8px 0',
    cursor: 'pointer',
    color: 'var(--text-primary)',
    textAlign: 'left',
  },
  rank: {
    fontFamily: 'var(--font-mono)',
    fontSize: 12,
    color: 'var(--text-tertiary)',
    width: 16,
  },
  name: {
    flex: 1,
    fontSize: 13,
  },
  score: {
    fontFamily: 'var(--font-mono)',
    fontSize: 13,
    color: 'var(--accent)',
    fontWeight: 600,
  },
  detail: {
    padding: '4px 0 12px 26px',
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
  },
  detailLabel: {
    fontSize: 12,
    color: 'var(--text-secondary)',
  },
  detailValue: {
    fontFamily: 'var(--font-mono)',
    fontSize: 12,
  },
  insight: {
    marginTop: 4,
    padding: '8px 10px',
    background: 'var(--bg-panel-raised)',
    border: '1px solid var(--border-soft)',
    borderRadius: 'var(--radius-sm)',
    fontSize: 12,
    lineHeight: 1.5,
    color: 'var(--text-secondary)',
  },
}
