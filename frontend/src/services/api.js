// API service layer.
//
// Every function here matches an endpoint from the build spec (Section 26):
//   GET  /network
//   GET  /hospitals
//   GET  /baseline
//   POST /simulate
//   POST /criticality
//   POST /intervention/evaluate
//   POST /intervention/optimize
//   POST /scenario/compare
//
// USE_MOCK=true lets the frontend team build and demo fully before the
// backend is live. Flip it to false (or set VITE_API_BASE) once Person 3's
// FastAPI service is up — no component code should need to change, since
// the mock responses are shaped exactly like the real ones.

import { MOCK_EDGES, MOCK_NODES, MOCK_HOSPITALS, BOTTLENECK_EDGE_ID } from '../data/mockNetwork'

const USE_MOCK = true
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// ---------------------------------------------------------------------------
// GET /network
// ---------------------------------------------------------------------------
export async function getNetwork() {
  if (USE_MOCK) {
    await delay(150)
    return {
      nodes: MOCK_NODES,
      edges: MOCK_EDGES.map((e) => ({ ...e, status: 'HEALTHY', utilization: 0 })),
    }
  }
  const res = await fetch(`${API_BASE}/network`)
  return res.json()
}

// ---------------------------------------------------------------------------
// GET /hospitals
// ---------------------------------------------------------------------------
export async function getHospitals() {
  if (USE_MOCK) {
    await delay(100)
    return { hospitals: MOCK_HOSPITALS }
  }
  const res = await fetch(`${API_BASE}/hospitals`)
  return res.json()
}

// ---------------------------------------------------------------------------
// GET /baseline
// ---------------------------------------------------------------------------
export async function getBaseline() {
  if (USE_MOCK) {
    await delay(200)
    return {
      resilience_score: 91.2,
      population_affected: 0,
      travel_time_increase_percent: 0,
      healthcare_access_loss_percent: 0,
      cascade_depth: 0,
      overloaded_edges: 5,
      avg_travel_time_min: 10.2,
    }
  }
  const res = await fetch(`${API_BASE}/baseline`)
  return res.json()
}

// ---------------------------------------------------------------------------
// POST /simulate   body: { failed_assets: [edge_id, ...], priority_mode }
// ---------------------------------------------------------------------------
export async function simulateFailure({ failedAssets, priorityMode = 'balanced' }) {
  if (USE_MOCK) {
    await delay(600)
    return mockSimulate(failedAssets)
  }
  const res = await fetch(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ failed_assets: failedAssets, priority_mode: priorityMode }),
  })
  return res.json()
}

// ---------------------------------------------------------------------------
// POST /criticality
// ---------------------------------------------------------------------------
export async function getCriticality({ priorityMode = 'balanced' } = {}) {
  if (USE_MOCK) {
    await delay(400)
    return mockCriticality()
  }
  const res = await fetch(`${API_BASE}/criticality`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ priority_mode: priorityMode }),
  })
  return res.json()
}

// ---------------------------------------------------------------------------
// POST /intervention/evaluate   body: { intervention }
// ---------------------------------------------------------------------------
export async function evaluateIntervention(intervention) {
  if (USE_MOCK) {
    await delay(500)
    return mockEvaluateIntervention(intervention)
  }
  const res = await fetch(`${API_BASE}/intervention/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intervention }),
  })
  return res.json()
}

// ---------------------------------------------------------------------------
// POST /intervention/optimize   body: { candidate_interventions, budget }
// ---------------------------------------------------------------------------
export async function optimizeInterventions({ candidates, budget }) {
  if (USE_MOCK) {
    await delay(900)
    return mockOptimize(candidates, budget)
  }
  const res = await fetch(`${API_BASE}/intervention/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_interventions: candidates, budget }),
  })
  return res.json()
}

// ---------------------------------------------------------------------------
// POST /scenario/compare   body: { scenarios: [...] }
// ---------------------------------------------------------------------------
export async function compareScenarios(scenarios) {
  if (USE_MOCK) {
    await delay(700)
    return mockCompareScenarios(scenarios)
  }
  const res = await fetch(`${API_BASE}/scenario/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenarios }),
  })
  return res.json()
}

// ===========================================================================
// MOCK IMPLEMENTATIONS
// Shaped to match the exact response contract in Section 26 of the build
// spec, so nothing downstream needs to change when the real API replaces this.
// ===========================================================================

function mockSimulate(failedAssets) {
  const isBottleneck = failedAssets.includes(BOTTLENECK_EDGE_ID)
  const edgeStatuses = MOCK_EDGES.map((e) => {
    if (failedAssets.includes(e.edge_id)) {
      return { edge_id: e.edge_id, status: 'FAILED', utilization: null }
    }
    if (isBottleneck && Math.abs(hashStr(e.edge_id)) % 11 === 0) {
      return { edge_id: e.edge_id, status: 'OVERLOADED', utilization: 1.24 }
    }
    if (isBottleneck && Math.abs(hashStr(e.edge_id)) % 7 === 0) {
      return { edge_id: e.edge_id, status: 'STRESSED', utilization: 0.87 }
    }
    return { edge_id: e.edge_id, status: 'HEALTHY', utilization: 0.31 }
  })

  const timeline = isBottleneck
    ? [
        { iteration: 0, label: 'Primary failure', mean_utilization: 0.041 },
        { iteration: 1, label: 'Traffic redistribution', mean_utilization: 0.058 },
        { iteration: 2, label: 'Secondary overload', mean_utilization: 0.071 },
        { iteration: 3, label: 'Healthcare accessibility degradation', mean_utilization: 0.074 },
        { iteration: 4, label: 'Network stabilization', mean_utilization: 0.074 },
      ]
    : [
        { iteration: 0, label: 'Primary failure', mean_utilization: 0.038 },
        { iteration: 1, label: 'Network stabilization', mean_utilization: 0.039 },
      ]

  return {
    resilience_score: isBottleneck ? 61.4 : 88.1,
    population_affected: isBottleneck ? 18400 : 0,
    travel_time_increase_percent: isBottleneck ? 38.2 : 3.1,
    healthcare_access_loss_percent: isBottleneck ? 27.4 : 0.5,
    cascade_depth: isBottleneck ? 4 : 1,
    overloaded_edges: isBottleneck ? 14 : 5,
    od_pairs_disconnected: isBottleneck ? 22 : 0,
    timeline,
    edges: edgeStatuses,
  }
}

function mockCriticality() {
  const ranked = [
    { edge_id: BOTTLENECK_EDGE_ID, name: 'Bridge J17', systemic_criticality: 94, systemic_rank: 1, traditional_centrality_rank: 14, population_exposed: 18400, primary_impact: 'Healthcare accessibility', secondary_impact: 'Traffic redistribution' },
    { edge_id: 'e41', name: 'Road R41', systemic_criticality: 88, systemic_rank: 2, traditional_centrality_rank: 3, population_exposed: 9200, primary_impact: 'Traffic redistribution', secondary_impact: 'Overloaded alternates' },
    { edge_id: 'e8', name: 'Junction J08', systemic_criticality: 82, systemic_rank: 3, traditional_centrality_rank: 1, population_exposed: 7600, primary_impact: 'Network overload', secondary_impact: 'Travel time' },
    { edge_id: 'e22', name: 'Road R22', systemic_criticality: 77, systemic_rank: 4, traditional_centrality_rank: 6, population_exposed: 5100, primary_impact: 'Travel time', secondary_impact: 'None significant' },
    { edge_id: 'e19', name: 'Road R19', systemic_criticality: 73, systemic_rank: 5, traditional_centrality_rank: 2, population_exposed: 4300, primary_impact: 'Traffic redistribution', secondary_impact: 'None significant' },
  ]
  return { ranked }
}

function mockEvaluateIntervention(intervention) {
  const upliftMap = { capacity_upgrade: 8, alternate_route: 14, service_access: 11 }
  const uplift = upliftMap[intervention.type] || 6
  return {
    baseline_resilience: 61.4,
    new_resilience: Math.min(100, 61.4 + uplift),
    population_exposure_before: 18400,
    population_exposure_after: Math.max(0, 18400 - uplift * 900),
    cost: intervention.cost,
  }
}

function mockOptimize(candidates, budget) {
  const affordable = (candidates || []).filter((c) => c.cost <= budget)
  const chosen = affordable.slice(0, 2)
  const totalCost = chosen.reduce((s, c) => s + c.cost, 0)
  return {
    recommended_interventions: chosen,
    total_cost: totalCost,
    baseline_resilience: 61.4,
    new_resilience: 79.0,
    improvement: 17.6,
    population_exposure_reduction: 10300,
  }
}

function mockCompareScenarios(scenarios) {
  return {
    results: scenarios.map((s, i) => ({
      scenario_id: s.id || `scenario_${i}`,
      label: s.label,
      resilience_score: [61.4, 88.1, 47.2, 79.0][i] ?? 70,
      population_affected: [18400, 0, 26100, 8100][i] ?? 0,
      healthcare_access_loss_percent: [27.4, 0.5, 41.0, 12.0][i] ?? 5,
      travel_time_increase_percent: [38.2, 3.1, 52.0, 18.0][i] ?? 10,
      overloaded_edges: [14, 5, 21, 8][i] ?? 6,
      cascade_depth: [4, 1, 5, 2][i] ?? 1,
    })),
  }
}

function hashStr(str) {
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i)
    h |= 0
  }
  return h
}
