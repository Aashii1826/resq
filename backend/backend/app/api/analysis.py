"""POST /simulate, POST /criticality"""

import copy
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.simulation.cascade import simulate_failure
from app.simulation.criticality import compute_and_cache_criticality, load_cached_criticality, rank_assets_by_criticality
from app.simulation.impact import compute_impact, compute_resilience_score
from app.simulation.routing import shortest_route
from app.state import get_state

router = APIRouter()


class SimulateRequest(BaseModel):
    failed_assets: List[str]
    priority_mode: str = "balanced"


def _avg_time(network, od_pairs, sample=25):
    times = []
    for od in od_pairs[:sample]:
        try:
            times.append(shortest_route(network, od.origin, od.destination).travel_time)
        except Exception:
            continue
    return sum(times) / len(times) if times else 0.0


@router.post("/simulate")
def simulate(req: SimulateRequest):
    state = get_state()
    # isolated copy so this run doesn't corrupt the shared baseline network
    network = copy.deepcopy(state.network)

    cascade = simulate_failure(network, state.od_pairs, req.failed_assets)
    current_avg = _avg_time(network, state.od_pairs)
    impact = compute_impact(
        network, state.baseline_hospital_times, state.baseline_avg_time, current_avg
    )
    resilience = compute_resilience_score(impact, network, req.priority_mode)

    return {
        "resilience_score": resilience,
        "population_affected": impact.population_affected,
        "travel_time_increase_percent": round(impact.travel_time_increase_percent, 1),
        "healthcare_access_loss_percent": round(impact.healthcare_access_loss_percent, 1),
        "cascade_depth": cascade.cascade_depth,
        "overloaded_edges": impact.overloaded_edges,
        "timeline": [s.to_dict() for s in cascade.steps],
    }


class CriticalityRequest(BaseModel):
    priority_mode: str = "balanced"
    use_cache: bool = True
    top_n: int = 15


@router.post("/criticality")
def criticality(req: CriticalityRequest):
    state = get_state()

    if req.use_cache:
        cached = load_cached_criticality()
        if cached:
            return {"cached": True, "results": cached[: req.top_n]}

    # no cache yet - compute + cache (slow path, meant to be triggered
    # manually, not on every UI load - Section 37)
    network = copy.deepcopy(state.network)
    results = compute_and_cache_criticality(network, state.od_pairs, priority_mode=req.priority_mode)
    return {"cached": False, "results": [r.to_dict() for r in results[: req.top_n]]}
