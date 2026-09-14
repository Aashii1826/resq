"""POST /simulate, POST /scenario/compare (Sections 25-26)."""

from __future__ import annotations

import copy

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioResultOut,
    SimulateRequest,
    SimulateResponse,
)
from app.simulation.cascade import simulate_failure
from app.simulation.impact import evaluate_impact
from app.simulation.interventions import apply_interventions
from app.state_store import store

router = APIRouter(tags=["scenarios"])


def _resolve_interventions(ids):
    catalog = {iv.intervention_id: iv for iv in store.get_candidate_interventions()}
    resolved = []
    for iid in ids:
        iv = catalog.get(iid)
        if iv is None:
            raise HTTPException(status_code=400, detail=f"Unknown intervention id: {iid}")
        resolved.append(iv)
    return resolved


def _run_scenario(failed_assets, applied_interventions, priority_mode):
    """
    Runs one scenario WITHOUT mutating the shared store network: either a
    deep copy (no interventions) or apply_interventions() (which already
    returns a fresh copy) is used as the working network.
    """
    network = store.get_network()
    od_pairs = store.get_od_pairs()
    baseline_snapshot = store.get_baseline_snapshot()

    if applied_interventions:
        ivs = _resolve_interventions(applied_interventions)
        working_network = apply_interventions(network, ivs)
    else:
        working_network = copy.deepcopy(network)

    cascade_result = simulate_failure(working_network, failed_assets, od_pairs)
    impact = evaluate_impact(
        network=working_network,
        od_pairs=od_pairs,
        baseline_access=baseline_snapshot.access,
        baseline_avg_travel_time=baseline_snapshot.avg_travel_time,
        baseline_resilience_score=baseline_snapshot.resilience_score,
        cascade_result=cascade_result,
        priority_mode=priority_mode,
    )
    return baseline_snapshot, impact, cascade_result


@router.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest):
    baseline_snapshot, impact, cascade_result = _run_scenario(
        req.failed_assets, req.applied_interventions, req.priority_mode
    )

    return SimulateResponse(
        resilience_score=impact.resilience_score,
        baseline_resilience_score=baseline_snapshot.resilience_score,
        population_affected=impact.population_affected,
        travel_time_increase_percent=impact.travel_time_increase_percent,
        healthcare_access_loss_percent=impact.healthcare_access_loss_percent,
        cascade_depth=impact.cascade_depth,
        overloaded_edges=impact.overloaded_edges,
        stabilized=cascade_result.stabilized,
        unreachable_hospital_zones=cascade_result.unreachable_hospital_zones,
        timeline=impact.timeline,
        priority_mode=req.priority_mode,
        metadata={
            "failed_assets": req.failed_assets,
            "final_failed_edges": cascade_result.final_failed_edges,
        },
    )


@router.post("/scenario/compare", response_model=ScenarioCompareResponse)
def compare_scenarios(req: ScenarioCompareRequest):
    baseline_snapshot = store.get_baseline_snapshot()
    baseline_result = ScenarioResultOut(
        name="baseline",
        resilience_score=baseline_snapshot.resilience_score,
        population_affected=0,
        travel_time_increase_percent=0.0,
        healthcare_access_loss_percent=0.0,
        overloaded_edges=0,
        cascade_depth=0,
    )

    results = []
    for sc in req.scenarios:
        _, impact, cascade_result = _run_scenario(sc.failed_assets, sc.applied_interventions, sc.priority_mode)
        results.append(
            ScenarioResultOut(
                name=sc.name,
                resilience_score=impact.resilience_score,
                population_affected=impact.population_affected,
                travel_time_increase_percent=impact.travel_time_increase_percent,
                healthcare_access_loss_percent=impact.healthcare_access_loss_percent,
                overloaded_edges=impact.overloaded_edges,
                cascade_depth=impact.cascade_depth,
            )
        )

    return ScenarioCompareResponse(baseline=baseline_result, scenarios=results)
