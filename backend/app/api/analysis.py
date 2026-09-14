"""POST /criticality, POST /intervention/evaluate, POST /intervention/optimize (Sections 19-24, 26)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import (
    CandidateInterventionsResponse,
    CriticalityEntryOut,
    CriticalityRequest,
    CriticalityResponse,
    InterventionEvaluateRequest,
    InterventionEvaluateResponse,
    InterventionOptimizeRequest,
    InterventionOptimizeResponse,
    InterventionSpec,
)
from app.models.intervention import Intervention
from app.simulation.interventions import evaluate_intervention, optimize_interventions
from app.state_store import store

router = APIRouter(tags=["analysis"])


@router.post("/criticality", response_model=CriticalityResponse)
def get_criticality(req: CriticalityRequest):
    entries = store.get_criticality(
        priority_mode=req.priority_mode, force_recalculate=req.force_recalculate, top_n=req.top_n
    )
    return CriticalityResponse(entries=[CriticalityEntryOut(**e.__dict__) for e in entries])


def _spec_to_intervention(spec: InterventionSpec) -> Intervention:
    return Intervention(
        intervention_id=spec.intervention_id,
        type=spec.type,
        name=spec.name,
        cost=spec.cost,
        target_edge_id=spec.target_edge_id,
        target_hospital_id=spec.target_hospital_id,
        params=spec.params,
    )


def _intervention_to_spec(iv: Intervention) -> InterventionSpec:
    return InterventionSpec(
        intervention_id=iv.intervention_id,
        type=iv.type,
        name=iv.name,
        cost=iv.cost,
        target_edge_id=iv.target_edge_id,
        target_hospital_id=iv.target_hospital_id,
        params=iv.params,
    )


@router.post("/intervention/evaluate", response_model=InterventionEvaluateResponse)
def post_evaluate_intervention(req: InterventionEvaluateRequest):
    network = store.get_network()
    od_pairs = store.get_od_pairs()
    baseline_snapshot = store.get_baseline_snapshot()
    interventions = [_spec_to_intervention(s) for s in req.interventions]
    result = evaluate_intervention(
        network, od_pairs, interventions, req.failed_assets, req.priority_mode,
        baseline_snapshot=baseline_snapshot,
    )
    return InterventionEvaluateResponse(**result)


@router.post("/intervention/optimize", response_model=InterventionOptimizeResponse)
def post_optimize_intervention(req: InterventionOptimizeRequest):
    network = store.get_network()
    od_pairs = store.get_od_pairs()
    candidates = [_spec_to_intervention(s) for s in req.candidate_interventions]
    result = optimize_interventions(network, od_pairs, candidates, req.budget, req.failed_assets, req.priority_mode)

    return InterventionOptimizeResponse(
        recommended_interventions=[_intervention_to_spec(iv) for iv in result["recommended_interventions"]],
        total_cost=result["total_cost"],
        baseline_resilience=result["baseline_resilience"],
        new_resilience=result["new_resilience"],
        improvement=result["improvement"],
        population_exposure_before=result["population_exposure_before"],
        population_exposure_after=result["population_exposure_after"],
        healthcare_access_before_percent=result["healthcare_access_before_percent"],
        healthcare_access_after_percent=result["healthcare_access_after_percent"],
        combinations_evaluated=result["combinations_evaluated"],
    )


@router.get("/intervention/candidates", response_model=CandidateInterventionsResponse)
def get_candidate_interventions():
    """Convenience endpoint so the frontend can populate the Resilience Planner panel."""
    ivs = store.get_candidate_interventions()
    return CandidateInterventionsResponse(candidates=[_intervention_to_spec(iv) for iv in ivs])
