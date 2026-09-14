"""GET /network, GET /hospitals, GET /baseline"""

from fastapi import APIRouter

from app.state import get_state

router = APIRouter()


@router.get("/network")
def get_network():
    state = get_state()
    return state.network.to_geojson()


@router.get("/hospitals")
def get_hospitals():
    state = get_state()
    return [h.to_dict() for h in state.network.hospitals.values()]


@router.get("/baseline")
def get_baseline():
    state = get_state()
    return {
        "summary": state.network.summary(),
        "resilience_score": state.baseline_resilience,
        "avg_travel_time_min": round(state.baseline_avg_time, 2),
        "overloaded_edges": sum(
            1 for e in state.network.edges_by_id.values() if e.status.value == "OVERLOADED"
        ),
        "stressed_edges": sum(
            1 for e in state.network.edges_by_id.values() if e.status.value == "STRESSED"
        ),
    }
