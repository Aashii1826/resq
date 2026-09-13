import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { getNetwork, getHospitals } from '../services/api'

const STATUS_COLOR = {
  HEALTHY: '#4cc9a0',
  STRESSED: '#ffc94a',
  OVERLOADED: '#ff7a45',
  FAILED: '#ff4d4d',
}
const STATUS_WIDTH = {
  HEALTHY: 1.5,
  STRESSED: 2.5,
  OVERLOADED: 3.5,
  FAILED: 4,
}

function edgesToGeoJSON(edges) {
  return {
    type: 'FeatureCollection',
    features: edges.map((e) => ({
      type: 'Feature',
      properties: {
        edge_id: e.edge_id,
        road_type: e.road_type,
        status: e.status || 'HEALTHY',
        utilization: e.utilization,
        color: STATUS_COLOR[e.status] || STATUS_COLOR.HEALTHY,
        width: STATUS_WIDTH[e.status] || STATUS_WIDTH.HEALTHY,
      },
      geometry: { type: 'LineString', coordinates: e.coords },
    })),
  }
}

function hospitalsToGeoJSON(hospitals) {
  return {
    type: 'FeatureCollection',
    features: hospitals.map((h) => ({
      type: 'Feature',
      properties: { id: h.id, name: h.name },
      geometry: { type: 'Point', coordinates: [h.lon, h.lat] },
    })),
  }
}

// A blank, neutral basemap style — no external tile dependency, keeps the
// map's own signal (road status, not tile styling) the visual focus.
const BLANK_STYLE = {
  version: 8,
  sources: {},
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#100e0a' } },
  ],
}

export default function NetworkMap({ edges, onSelectRoad, selectedEdgeId }) {
  console.log('NETWORK EDGES:', edges)
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const [hospitals, setHospitals] = useState([])
  const [ready, setReady] = useState(false)

  useEffect(() => {
    getHospitals().then((res) => setHospitals(res.hospitals))
  }, [])

  useEffect(() => {
    if (mapRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BLANK_STYLE,
      center: [77.635, 12.98],
      zoom: 13.2,
      attributionControl: false,
    })
    mapRef.current = map

    map.on('load', () => {
      map.addSource('roads', { type: 'geojson', data: edgesToGeoJSON(edges) })
      map.addLayer({
        id: 'roads-line',
        type: 'line',
        source: 'roads',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': ['get', 'color'],
          'line-width': ['get', 'width'],
          'line-opacity': 0.92,
        },
      })
      map.addLayer({
        id: 'roads-selected',
        type: 'line',
        source: 'roads',
        filter: ['==', 'edge_id', '__none__'],
        paint: {
          'line-color': '#ffb020',
          'line-width': 6,
          'line-opacity': 0.35,
          'line-blur': 2,
        },
      })

      map.addSource('hospitals', { type: 'geojson', data: hospitalsToGeoJSON([]) })
      map.addLayer({
        id: 'hospitals-halo',
        type: 'circle',
        source: 'hospitals',
        paint: {
          'circle-radius': 8,
          'circle-color': '#f2efe6',
          'circle-opacity': 0.12,
        },
      })
      map.addLayer({
        id: 'hospitals-point',
        type: 'circle',
        source: 'hospitals',
        paint: {
          'circle-radius': 4,
          'circle-color': '#f2efe6',
          'circle-stroke-color': '#100e0a',
          'circle-stroke-width': 1.5,
        },
      })

      map.on('click', 'roads-line', (e) => {
        const props = e.features[0].properties
        onSelectRoad?.(props.edge_id)
      })
      map.on('mouseenter', 'roads-line', () => (map.getCanvas().style.cursor = 'pointer'))
      map.on('mouseleave', 'roads-line', () => (map.getCanvas().style.cursor = ''))

      setReady(true)
    })
return () => {
  map.remove()
  mapRef.current = null
}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // update road data when edges change (after a simulation)
 // update road data when edges change
useEffect(() => {
  const map = mapRef.current
  if (!map || !ready || edges.length === 0) return

  const src = map.getSource('roads')
  if (src) {
    src.setData(edgesToGeoJSON(edges))
  }

  // Fit the map to the actual road network
  const coordinates = edges.flatMap((e) => e.coords)

  if (coordinates.length > 0) {
    const bounds = coordinates.reduce(
      (bounds, coord) => bounds.extend(coord),
      new maplibregl.LngLatBounds(coordinates[0], coordinates[0])
    )

    map.fitBounds(bounds, {
      padding: 60,
      maxZoom: 14,
    })
  }
}, [edges, ready])

  // update hospitals once loaded
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || hospitals.length === 0) return
    const src = map.getSource('hospitals')
    if (src) src.setData(hospitalsToGeoJSON(hospitals))
  }, [hospitals, ready])

  // highlight selection
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.setFilter('roads-selected', ['==', 'edge_id', selectedEdgeId || '__none__'])
  }, [selectedEdgeId, ready])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <MapLegend />
    </div>
  )
}

function MapLegend() {
  const items = [
    { label: 'Healthy', color: STATUS_COLOR.HEALTHY },
    { label: 'Stressed', color: STATUS_COLOR.STRESSED },
    { label: 'Overloaded', color: STATUS_COLOR.OVERLOADED },
    { label: 'Failed', color: STATUS_COLOR.FAILED },
  ]
  return (
    <div
      style={{
        position: 'absolute', bottom: 16, left: 16,
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)', padding: '10px 14px',
        fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)',
        display: 'flex', gap: 16,
      }}
    >
      {items.map((it) => (
        <div key={it.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 12, height: 3, background: it.color, borderRadius: 2, display: 'inline-block' }} />
          {it.label}
        </div>
      ))}
    </div>
  )
}
