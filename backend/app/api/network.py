"""GET /network, GET /hospitals, GET /baseline (Section 26)."""

from __future__ import annotations

from fastapi import APIRouter

from app.state_store import store

router = APIRouter(tags=["network"])


@router.get("/network")
def get_network():
    network = store.get_network()
    nodes = [
        {"id": n, "lat": data["lat"], "lon": data["lon"], "node_type": data.get("node_type", "JUNCTION")}
        for n, data in network.graph.nodes(data=True)
    ]
    edges = [edge.to_dict() for edge in network.edges_by_id.values()]
    return {"nodes": nodes, "edges": edges}


@router.get("/network/geojson")
def get_network_geojson():
    """Convenience endpoint for a MapLibre/Leaflet GeoJSON source."""
    return store.get_network().to_geojson()


@router.get("/hospitals")
def get_hospitals():
    network = store.get_network()
    return [h.to_dict() for h in network.hospitals.values()]


@router.get("/baseline")
def get_baseline():
    network = store.get_network()
    snapshot = store.get_baseline_snapshot()
    summary = network.summary()
    return {
        **summary,
        "resilience_score": snapshot.resilience_score,
        "average_travel_time_minutes": round(snapshot.avg_travel_time, 1),
    }
