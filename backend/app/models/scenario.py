"""
Scenario model - a named set of one or more asset failures (+ optional
interventions applied first) to be run through the simulation engine.

Kept intentionally minimal here; Person 2 (cascade/impact) and Person 3
(criticality/intervention/API) will build the actual evaluation logic on
top of this shape. Defining it now means both can code against a stable
interface instead of waiting.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Scenario:
    scenario_id: str
    name: str
    failed_asset_ids: List[str] = field(default_factory=list)  # road/junction ids
    intervention_ids: List[str] = field(default_factory=list)  # applied before failure
    priority_mode: str = "balanced"  # see config.PRIORITY_MODE_WEIGHTS
    description: Optional[str] = None


@dataclass
class ScenarioResult:
    """
    Standard shape every simulation run should produce, regardless of
    whether it came from /simulate, /intervention/evaluate, or
    /scenario/compare. Matches the API response shape in Section 26.
    """
    scenario_id: str
    resilience_score: float
    population_affected: int
    travel_time_increase_percent: float
    healthcare_access_loss_percent: float
    cascade_depth: int
    overloaded_edges: int
    timeline: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "resilience_score": round(self.resilience_score, 1),
            "population_affected": self.population_affected,
            "travel_time_increase_percent": round(self.travel_time_increase_percent, 1),
            "healthcare_access_loss_percent": round(self.healthcare_access_loss_percent, 1),
            "cascade_depth": self.cascade_depth,
            "overloaded_edges": self.overloaded_edges,
            "timeline": self.timeline,
        }
