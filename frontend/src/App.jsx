import { useEffect, useState, useCallback } from 'react'
import NetworkMap from './components/NetworkMap'
import DashboardPanel from './components/DashboardPanel'
import FailureInteractionPanel from './components/FailureInteractionPanel'
import CriticalAssetsPanel from './components/CriticalAssetsPanel'
import InterventionPlannerPanel from './components/InterventionPlannerPanel'
import CascadeTimeline from './components/CascadeTimeline'
import { getNetwork, getBaseline, simulateFailure } from './services/api'

export default function App() {
  const [edges, setEdges] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState(null)
  const [simResult, setSimResult] = useState(null)
  const [simulating, setSimulating] = useState(false)
  const [priorityMode, setPriorityMode] = useState('balanced')

  useEffect(() => {
    getNetwork().then((res) => setEdges(res.edges))
    getBaseline().then(setMetrics)
  }, [])

  // once a simulation runs, merge its edge statuses into the display edges
  const displayEdges = simResult
  ? edges.map((e) => {
      const updated = simResult.edges?.find(
        (u) => u.edge_id === e.edge_id
      )

      return {
        ...e,
        status: updated?.status || e.status || 'HEALTHY',
        utilization: updated?.utilization ?? e.utilization,
      }
    })
  : edges

  const selectedEdge = displayEdges.find((e) => e.edge_id === selectedEdgeId)

  const handleSimulate = useCallback(async (edgeId) => {
    setSimulating(true)
    try {
      const res = await simulateFailure({ failedAssets: [edgeId], priorityMode })
      setSimResult(res)
      setMetrics({
        resilience_score: res.resilience_score,
        population_affected: res.population_affected,
        healthcare_access_loss_percent: res.healthcare_access_loss_percent,
        travel_time_increase_percent: res.travel_time_increase_percent,
        overloaded_edges: res.overloaded_edges,
        avg_travel_time_min: metrics?.avg_travel_time_min,
      })
    } finally {
      setSimulating(false)
    }
  }, [priorityMode, metrics])

  function handleTimelineStep(index) {
    // future: could re-render edge state per-iteration once backend sends
    // per-step edge snapshots; for now the final state is shown throughout
  }

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <div style={styles.brand}>
          <span style={styles.brandMark}>RESQ</span>
          <span style={styles.brandSub}>Urban resilience command center</span>
        </div>

        <div style={styles.modeSelector}>
          {['balanced', 'emergency_access', 'population_protection', 'mobility'].map((mode) => (
            <button
              key={mode}
              onClick={() => setPriorityMode(mode)}
              style={{
                ...styles.modeButton,
                ...(priorityMode === mode ? styles.modeButtonActive : {}),
              }}
            >
              {mode.replace('_', ' ')}
            </button>
          ))}
        </div>
      </header>

      <div style={styles.body}>
        <div style={styles.mapArea}>
          <NetworkMap
            edges={displayEdges}
            onSelectRoad={setSelectedEdgeId}
            selectedEdgeId={selectedEdgeId}
          />
        </div>

        <aside style={styles.sidebar}>
          <DashboardPanel metrics={metrics} loading={simulating} />
          <FailureInteractionPanel
            selectedEdge={selectedEdge}
            onSimulate={handleSimulate}
            simulating={simulating}
          />
          <CriticalAssetsPanel onSelectAsset={setSelectedEdgeId} />
          <InterventionPlannerPanel />
        </aside>
      </div>

      <CascadeTimeline timeline={simResult?.timeline} onStep={handleTimelineStep} />
    </div>
  )
}

const styles = {
  app: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 20px',
    borderBottom: '1px solid var(--border)',
    background: 'var(--bg-panel)',
    flexShrink: 0,
  },
  brand: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 12,
  },
  brandMark: {
    fontFamily: 'var(--font-display)',
    fontWeight: 700,
    fontSize: 18,
    letterSpacing: '0.02em',
    color: 'var(--accent)',
  },
  brandSub: {
    fontSize: 12,
    color: 'var(--text-secondary)',
  },
  modeSelector: {
    display: 'flex',
    gap: 6,
  },
  modeButton: {
    background: 'var(--bg-panel-raised)',
    border: '1px solid var(--border)',
    color: 'var(--text-secondary)',
    borderRadius: 'var(--radius-sm)',
    padding: '6px 12px',
    fontSize: 12,
    cursor: 'pointer',
    textTransform: 'capitalize',
    fontFamily: 'var(--font-display)',
  },
  modeButtonActive: {
    background: 'var(--accent)',
    color: '#16140f',
    borderColor: 'var(--accent)',
    fontWeight: 600,
  },
  body: {
    display: 'flex',
    flex: 1,
    minHeight: 0,
  },
  mapArea: {
    flex: 1,
    minWidth: 0,
  },
  sidebar: {
    width: 320,
    flexShrink: 0,
    background: 'var(--bg-base)',
    borderLeft: '1px solid var(--border)',
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
    overflowY: 'auto',
  },
}
