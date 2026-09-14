"""Pydantic request/response schemas for the API layer (Section 26)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.intervention import InterventionType


# ---------------------------------------------------------------------------
# /simulate, /scenario/compare
# ---------------------------------------------------------------------------
class SimulateRequest(BaseModel):
    failed_assets: List[str] = Field(..., description="Road edge_ids or junction node ids to fail")
    priority_mode: str = Field("balanced", description="balanced|emergency_access|population_protection|mobility")
    applied_interventions: List[str] = Field(default_factory=list, description="Intervention ids to apply before failing")


class SimulateResponse(BaseModel):
    resilience_score: float
    baseline_resilience_score: float
    population_affected: int
    travel_time_increase_percent: float
    healthcare_access_loss_percent: float
    cascade_depth: int
    overloaded_edges: int
    stabilized: bool
    unreachable_hospital_zones: List[str] = Field(default_factory=list)
    # raw timeline steps, shape = CascadeStepState.to_dict():
    # {step, label, newly_failed, newly_stressed, newly_overloaded,
    #  overloaded_edges, stressed_edges, failed_edges, unrouted_pairs, max_utilization_delta}
    timeline: List[Dict[str, Any]]
    priority_mode: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScenarioDefinition(BaseModel):
    name: str
    failed_assets: List[str] = Field(default_factory=list)
    applied_interventions: List[str] = Field(default_factory=list)
    priority_mode: str = "balanced"


class ScenarioCompareRequest(BaseModel):
    scenarios: List[ScenarioDefinition]


class ScenarioResultOut(BaseModel):
    name: str
    resilience_score: float
    population_affected: int
    travel_time_increase_percent: float
    healthcare_access_loss_percent: float
    overloaded_edges: int
    cascade_depth: int


class ScenarioCompareResponse(BaseModel):
    baseline: ScenarioResultOut
    scenarios: List[ScenarioResultOut]


# ---------------------------------------------------------------------------
# /criticality
# ---------------------------------------------------------------------------
class CriticalityRequest(BaseModel):
    priority_mode: str = "balanced"
    force_recalculate: bool = False
    top_n: int = 10


class CriticalityEntryOut(BaseModel):
    asset_id: str
    systemic_criticality: float
    systemic_rank: int
    traditional_centrality: float
    traditional_rank: int
    resilience_after_failure: float
    population_exposure: int
    travel_time_increase_pct: float
    healthcare_access_loss_pct: float
    overloaded_edges: int
    cascade_depth: int
    redundancy_loss: float


class CriticalityResponse(BaseModel):
    entries: List[CriticalityEntryOut]


# ---------------------------------------------------------------------------
# /intervention/*
# ---------------------------------------------------------------------------
class InterventionSpec(BaseModel):
    intervention_id: str
    type: InterventionType
    name: str
    cost: float
    target_edge_id: Optional[str] = None
    target_hospital_id: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class InterventionEvaluateRequest(BaseModel):
    interventions: List[InterventionSpec]
    failed_assets: List[str] = Field(default_factory=list)
    priority_mode: str = "balanced"


class InterventionEvaluateResponse(BaseModel):
    baseline_resilience: float
    new_resilience: float
    improvement: float
    baseline_population_affected: int
    new_population_affected: int
    baseline_healthcare_access_percent: float
    new_healthcare_access_percent: float
    cost: float


class InterventionOptimizeRequest(BaseModel):
    candidate_interventions: List[InterventionSpec]
    budget: float
    failed_assets: List[str] = Field(default_factory=list)
    priority_mode: str = "balanced"


class InterventionOptimizeResponse(BaseModel):
    recommended_interventions: List[InterventionSpec]
    total_cost: float
    baseline_resilience: float
    new_resilience: float
    improvement: float
    population_exposure_before: int
    population_exposure_after: int
    healthcare_access_before_percent: float
    healthcare_access_after_percent: float
    combinations_evaluated: int


class CandidateInterventionsResponse(BaseModel):
    candidates: List[InterventionSpec]
