// Mock network data, structurally identical to what GET /network will return
// once Person 3's API is live. Deliberately mirrors backend/app/data/synthetic_loader.py
// (a grid with one deliberate chokepoint bridge) so the map tells the same story.
//
// Coordinates are lon/lat, matching GeoJSON / MapLibre convention.

const BASE_LAT = 12.95
const BASE_LON = 77.60
const LAT_STEP = 0.006
const LON_STEP = 0.007
const ROWS = 10
const COLS = 12
const MID_COL = Math.floor(COLS / 2)
const BOTTLENECK_ROW = Math.floor(ROWS / 2)

function seededRandom(seed) {
  let s = seed
  return () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff
    return s / 0x7fffffff
  }
}

const rand = seededRandom(42)

function buildNodes() {
  const nodes = {}
  let id = 0
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const isEdgeNode = r === 0 || r === ROWS - 1 || c === 0 || c === COLS - 1
      if (!isEdgeNode && rand() < 0.06) continue
      nodes[`${r}_${c}`] = {
        id: id++,
        r, c,
        lon: BASE_LON + c * LON_STEP + (rand() - 0.5) * 0.0006,
        lat: BASE_LAT + r * LAT_STEP + (rand() - 0.5) * 0.0006,
      }
    }
  }
  return nodes
}

function roadType(r, c) {
  const majorRow = r % 3 === 0
  const majorCol = c % 4 === 0
  if (majorRow && majorCol) return 'trunk'
  if (majorRow || majorCol) return (r + c) % 2 === 0 ? 'primary' : 'secondary'
  if ((r + c) % 5 === 0) return 'tertiary'
  return 'residential'
}

const CAPACITY = {
  trunk: 4000, primary: 3000, secondary: 2000, tertiary: 1200, residential: 600,
}

function buildEdges(nodes) {
  const edges = []
  let eid = 0
  const key = (r, c) => `${r}_${c}`

  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      if (!nodes[key(r, c)]) continue
      const a = nodes[key(r, c)]

      // horizontal — skip the seam between mid_col-1 and mid_col except at the bottleneck row
      if (nodes[key(r, c + 1)]) {
        const isSeam = c === MID_COL - 1
        if (!isSeam || r === BOTTLENECK_ROW) {
          const b = nodes[key(r, c + 1)]
          const type = roadType(r, c)
          edges.push({
            edge_id: `e${eid++}`,
            source: a.id, target: b.id,
            coords: [[a.lon, a.lat], [b.lon, b.lat]],
            road_type: type,
            capacity: Math.round(CAPACITY[type] * (0.85 + 0.3 * rand())),
            is_bottleneck: isSeam && r === BOTTLENECK_ROW,
          })
        }
      }
      // vertical
      if (nodes[key(r + 1, c)]) {
        const b = nodes[key(r + 1, c)]
        const type = roadType(r, c)
        edges.push({
          edge_id: `e${eid++}`,
          source: a.id, target: b.id,
          coords: [[a.lon, a.lat], [b.lon, b.lat]],
          road_type: type,
          capacity: Math.round(CAPACITY[type] * (0.85 + 0.3 * rand())),
          is_bottleneck: false,
        })
      }
    }
  }
  return edges
}

const nodes = buildNodes()
export const MOCK_EDGES = buildEdges(nodes)
export const MOCK_NODES = Object.values(nodes)

export const MOCK_HOSPITALS = [
  { id: 'hosp_0', name: 'Hospital A', lon: BASE_LON + 1 * LON_STEP, lat: BASE_LAT + 1 * LAT_STEP },
  { id: 'hosp_1', name: 'Hospital B', lon: BASE_LON + 9 * LON_STEP, lat: BASE_LAT + 1 * LAT_STEP },
  { id: 'hosp_2', name: 'Hospital C', lon: BASE_LON + 5 * LON_STEP, lat: BASE_LAT + 4 * LAT_STEP },
  { id: 'hosp_3', name: 'Hospital D', lon: BASE_LON + 11 * LON_STEP, lat: BASE_LAT + 5 * LAT_STEP },
  { id: 'hosp_4', name: 'Hospital E', lon: BASE_LON + 1 * LON_STEP, lat: BASE_LAT + 7 * LAT_STEP },
  { id: 'hosp_5', name: 'Hospital F', lon: BASE_LON + 7 * LON_STEP, lat: BASE_LAT + 8 * LAT_STEP },
  { id: 'hosp_6', name: 'Hospital G', lon: BASE_LON + 3 * LON_STEP, lat: BASE_LAT + 9 * LAT_STEP },
  { id: 'hosp_7', name: 'Hospital H', lon: BASE_LON + 10 * LON_STEP, lat: BASE_LAT + 3 * LAT_STEP },
]

export const BOTTLENECK_EDGE_ID = MOCK_EDGES.find(e => e.is_bottleneck)?.edge_id || null
