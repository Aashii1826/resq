"""POST /intervention/evaluate, POST /intervention/optimize, POST /scenario/compare"""

import copy
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.models.intervention import Intervention, InterventionType
from app.simulation.cascade import simulate_failure
from app.simulation.impact import compute_impact, compute_resilience_score
from app.simulation.interventions import evaluate_intervention, optimize_interventions
from app.simulation.routing import shortest_route
from app.state import get_state

router = APIRouter()


class InterventionSpec(BaseModel):
    intervention_id: str
    type: InterventionType
    name: str
    cost: float
    target_edge_id: Optional[str] = None
    target_hospital_id: Optional[str] = None
    params: dict = {}


def _to_intervention(spec: InterventionSpec) -> Intervention:
    return Intervention(
        intervention_id=spec.intervention_id,
        type=spec.type,
        name=spec.name,
        cost=spec.cost,
        target_edge_id=spec.target_edge_id,
        target_hospital_id=spec.target_hospital_id,
        params=spec.params,
    )


class EvaluateRequest(BaseModel):
    failed_assets: List[str]
    interventions: List[InterventionSpec]
    priority_mode: str = "balanced"


@router.post("/intervention/evaluate")
def intervention_evaluate(req: EvaluateRequest):
    state = get_state()
    network = copy.deepcopy(state.network)
    interventions = [_to_intervention(s) for s in req.interventions]
    result = evaluate_intervention(
        network, state.od_pairs, interventions, req.failed_assets, req.priority_mode
    )
    return result.to_dict()


class OptimizeRequest(BaseModel):
    failed_assets: List[str]
    candidate_interventions: List[InterventionSpec]
    budget: float
    priority_mode: str = "balanced"


@router.post("/intervention/optimize")
def intervention_optimize(req: OptimizeRequest):
    state = get_state()
    network = copy.deepcopy(state.network)
    candidates = [_to_intervention(s) for s in req.candidate_interventions]
    best = optimize_interventions(
        network, state.od_pairs, candidates, req.failed_assets, req.budget, req.priority_mode
    )
    if best is None:
        return {"recommended": None, "message": "No feasible combination within budget"}
    return {"recommended": best.to_dict()}


class ScenarioSpec(BaseModel):
    scenario_id: str
    name: str
    failed_assets: List[str]
    priority_mode: str = "balanced"


class CompareRequest(BaseModel):
    scenarios: List[ScenarioSpec]


def _avg_time(network, od_pairs, sample=25):
    times = []
    for od in od_pairs[:sample]:
        try:
            times.append(shortest_route(network, od.origin, od.destination).travel_time)
        except Exception:
            continue
    return sum(times) / len(times) if times else 0.0


@router.post("/scenario/compare")
def scenario_compare(req: CompareRequest):
    state = get_state()
    results = []
    for scenario in req.scenarios:
        network = copy.deepcopy(state.network)
        cascade = simulate_failure(network, state.od_pairs, scenario.failed_assets)
        current_avg = _avg_time(network, state.od_pairs)
        impact = compute_impact(
            network, state.baseline_hospital_times, state.baseline_avg_time, current_avg
        )
        resilience = compute_resilience_score(impact, network, scenario.priority_mode)
        results.append(
            {
                "scenario_id": scenario.scenario_id,
                "name": scenario.name,
                "resilience_score": resilience,
                "population_affected": impact.population_affected,
                "travel_time_increase_percent": round(impact.travel_time_increase_percent, 1),
                "healthcare_access_loss_percent": round(impact.healthcare_access_loss_percent, 1),
                "overloaded_edges": impact.overloaded_edges,
                "cascade_depth": cascade.cascade_depth,
            }
        )
    return {"scenarios": results}
