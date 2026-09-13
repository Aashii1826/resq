"""
Impact engine (Sections 15-18).

Turns a Network's state (baseline or post-cascade) into the human-meaningful
numbers the rest of the product is built around:

  - hospital accessibility: per population zone, travel time to nearest
    reachable hospital, baseline vs. after-failure
  - population exposure: population in zones whose accessibility crossed
    the configured deterioration threshold (Section 17) - labelled
    "Simulated population exposure", never presented as a real estimate
  - a single 0-100 resilience score, weighted per priority mode
    (config.PRIORITY_MODE_WEIGHTS)

This module only reads/derives from the Network + a CascadeResult; it does
not run simulations itself (that's cascade.py) and does not rank assets
(that's Person 3's criticality.py, which calls both).
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.config import ACCESSIBILITY_DETERIORATION_THRESHOLD_PCT, PRIORITY_MODE_WEIGHTS
from app.models.network import Network
from app.simulation.cascade import CascadeResult
from app.simulation.demand import ODDemand
from app.simulation.routing import NoRouteError, nearest_hospital_route, shortest_route


# ---------------------------------------------------------------------------
# Hospital accessibility (Section 15-16)
# ---------------------------------------------------------------------------
@dataclass
class ZoneAccessibility:
    zone_id: str
    population: int
    travel_time_minutes: Optional[float]  # None = zone fully cut off from all hospitals

    def to_dict(self) -> Dict:
        return {
            "zone_id": self.zone_id,
            "population": self.population,
            "travel_time_minutes": (
                round(self.travel_time_minutes, 2) if self.travel_time_minutes is not None else None
            ),
        }


def compute_hospital_accessibility(network: Network) -> Dict[str, ZoneAccessibility]:
    """Travel time from every population zone's anchor node to its nearest
    reachable hospital, at the network's CURRENT state (call this once on
    the baseline network, and again after a cascade settles)."""
    result: Dict[str, ZoneAccessibility] = {}
    for zone in network.zones.values():
        travel_time = None
        if zone.anchor_node:
            route = nearest_hospital_route(network, zone.anchor_node)
            if route is not None:
                travel_time = route.travel_time
        result[zone.zone_id] = ZoneAccessibility(
            zone_id=zone.zone_id, population=zone.population, travel_time_minutes=travel_time
        )
    return result


@dataclass
class ZoneAccessibilityDelta:
    zone_id: str
    population: int
    baseline_minutes: Optional[float]
    current_minutes: Optional[float]
    accessibility_loss_minutes: float  # Section 16: max(0, post - baseline)
    deterioration_percent: float  # can be > 100 if a zone becomes fully cut off (capped, see note)
    cut_off: bool  # zone lost ALL hospital access

    def to_dict(self) -> Dict:
        return {
            "zone_id": self.zone_id,
            "population": self.population,
            "baseline_minutes": round(self.baseline_minutes, 2) if self.baseline_minutes is not None else None,
            "current_minutes": round(self.current_minutes, 2) if self.current_minutes is not None else None,
            "accessibility_loss_minutes": round(self.accessibility_loss_minutes, 2),
            "deterioration_percent": round(self.deterioration_percent, 1),
            "cut_off": self.cut_off,
        }


@dataclass
class AccessibilityImpact:
    zones: List[ZoneAccessibilityDelta]
    affected_population: int  # Section 17: population in zones over threshold
    avg_deterioration_percent: float  # headline "healthcare_access_loss_percent"
    threshold_percent: float
    cut_off_zones: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "zones": [z.to_dict() for z in self.zones],
            "affected_population": self.affected_population,
            "avg_deterioration_percent": round(self.avg_deterioration_percent, 1),
            "threshold_percent": self.threshold_percent,
            "cut_off_zones": self.cut_off_zones,
        }


# A cut-off zone (no hospital reachable at all) is scored as this many
# minutes worse than baseline for percent-deterioration purposes, capped
# rather than left as infinity - purely a display/scoring convenience.
CUT_OFF_PENALTY_MINUTES: float = 60.0


def compute_accessibility_impact(
    network: Network,
    baseline_access: Dict[str, ZoneAccessibility],
    threshold_percent: float = ACCESSIBILITY_DETERIORATION_THRESHOLD_PCT,
) -> AccessibilityImpact:
    """
    Compare the network's CURRENT accessibility (e.g. post-cascade) against
    a previously captured baseline. Flags zones whose deterioration exceeds
    `threshold_percent` and sums their population as "affected_population"
    (Section 17's "Simulated population exposure").
    """
    current_access = compute_hospital_accessibility(network)
    deltas: List[ZoneAccessibilityDelta] = []
    cut_off_zones: List[str] = []
    weighted_pct_sum = 0.0
    total_population = 0

    for zone_id, baseline in baseline_access.items():
        current = current_access.get(zone_id)
        current_minutes = current.travel_time_minutes if current else None
        baseline_minutes = baseline.travel_time_minutes

        cut_off = current_minutes is None and baseline_minutes is not None
        if cut_off:
            cut_off_zones.append(zone_id)

        effective_baseline = baseline_minutes if baseline_minutes is not None else 0.0
        effective_current = (
            current_minutes
            if current_minutes is not None
            else effective_baseline + CUT_OFF_PENALTY_MINUTES
        )

        loss_minutes = max(0.0, effective_current - effective_baseline)
        if effective_baseline > 0:
            pct = (loss_minutes / effective_baseline) * 100.0
        else:
            pct = 0.0 if loss_minutes == 0 else 100.0

        deltas.append(
            ZoneAccessibilityDelta(
                zone_id=zone_id,
                population=baseline.population,
                baseline_minutes=baseline_minutes,
                current_minutes=current_minutes,
                accessibility_loss_minutes=loss_minutes,
                deterioration_percent=pct,
                cut_off=cut_off,
            )
        )
        weighted_pct_sum += pct * baseline.population
        total_population += baseline.population

    affected_population = sum(d.population for d in deltas if d.deterioration_percent >= threshold_percent)
    avg_deterioration_percent = (weighted_pct_sum / total_population) if total_population > 0 else 0.0

    return AccessibilityImpact(
        zones=deltas,
        affected_population=affected_population,
        avg_deterioration_percent=avg_deterioration_percent,
        threshold_percent=threshold_percent,
        cut_off_zones=cut_off_zones,
    )


# ---------------------------------------------------------------------------
# Travel-time impact (network-wide, Section 18 "travel_score" input)
# ---------------------------------------------------------------------------
def average_od_travel_time(network: Network, od_pairs: List[ODDemand], sample: int = 40) -> float:
    """Average travel time (minutes) over a sample of OD pairs, at the
    network's CURRENT weights. Unrouted pairs are skipped (a fully-severed
    OD pair is instead captured via cut_off_zones / unreachable checks)."""
    times = []
    for od in od_pairs[:sample]:
        try:
            route = shortest_route(network, od.origin, od.destination)
            times.append(route.travel_time)
        except NoRouteError:
            continue
    return sum(times) / len(times) if times else 0.0


def travel_time_increase_percent(baseline_avg_minutes: float, current_avg_minutes: float) -> float:
    if baseline_avg_minutes <= 0:
        return 0.0
    return max(0.0, (current_avg_minutes - baseline_avg_minutes) / baseline_avg_minutes * 100.0)


# ---------------------------------------------------------------------------
# Resilience score (Section 18)
# ---------------------------------------------------------------------------
def _normalize_degradation(value_percent: float, cap_percent: float = 100.0) -> float:
    """Maps a 0..cap_percent degradation value to a 1.0 (no degradation) ..
    0.0 (fully degraded) sub-score. Values beyond the cap clamp to 0."""
    return max(0.0, 1.0 - min(value_percent, cap_percent) / cap_percent)


@dataclass
class ResilienceBreakdown:
    resilience_score: float
    accessibility_score: float
    travel_score: float
    population_score: float
    network_score: float
    priority_mode: str

    def to_dict(self) -> Dict:
        return {
            "resilience_score": round(self.resilience_score, 1),
            "components": {
                "accessibility_score": round(self.accessibility_score, 3),
                "travel_score": round(self.travel_score, 3),
                "population_score": round(self.population_score, 3),
                "network_score": round(self.network_score, 3),
            },
            "priority_mode": self.priority_mode,
        }


def compute_resilience_score(
    accessibility_impact: AccessibilityImpact,
    travel_time_increase_pct: float,
    total_population: int,
    total_edges: int,
    overloaded_and_failed_edges: int,
    priority_mode: str = "balanced",
) -> ResilienceBreakdown:
    """
    Composite 0-100 resilience score (Section 18). All four sub-scores are
    normalized to 1.0 = no degradation, 0.0 = fully degraded, then combined
    with the priority mode's weights from config.PRIORITY_MODE_WEIGHTS.

    These weights (and the normalization caps) are documented prototype
    assumptions (Section 38), not calibrated real-world coefficients.
    """
    weights = PRIORITY_MODE_WEIGHTS.get(priority_mode, PRIORITY_MODE_WEIGHTS["balanced"])

    accessibility_score = _normalize_degradation(accessibility_impact.avg_deterioration_percent)
    travel_score = _normalize_degradation(travel_time_increase_pct)

    population_score = (
        1.0 - min(accessibility_impact.affected_population / total_population, 1.0)
        if total_population > 0
        else 1.0
    )
    network_score = (
        1.0 - min(overloaded_and_failed_edges / total_edges, 1.0) if total_edges > 0 else 1.0
    )

    score = 100.0 * (
        weights.accessibility * accessibility_score
        + weights.travel * travel_score
        + weights.population * population_score
        + weights.network * network_score
    )

    return ResilienceBreakdown(
        resilience_score=max(0.0, min(100.0, score)),
        accessibility_score=accessibility_score,
        travel_score=travel_score,
        population_score=population_score,
        network_score=network_score,
        priority_mode=priority_mode,
    )


# ---------------------------------------------------------------------------
# Top-level convenience: baseline vs. post-cascade, in one call
# ---------------------------------------------------------------------------
@dataclass
class ImpactReport:
    """The shape cascade + impact together produce for one scenario run -
    matches ScenarioResult (Section 26 / models/scenario.py) plus the
    detail Person 3's API and Person 4's dashboard/criticality panels need."""

    resilience_score: float
    baseline_resilience_score: float
    population_affected: int
    travel_time_increase_percent: float
    healthcare_access_loss_percent: float
    cascade_depth: int
    overloaded_edges: int
    accessibility: AccessibilityImpact
    resilience_breakdown: ResilienceBreakdown
    timeline: List[dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "resilience_score": round(self.resilience_score, 1),
            "baseline_resilience_score": round(self.baseline_resilience_score, 1),
            "population_affected": self.population_affected,
            "travel_time_increase_percent": round(self.travel_time_increase_percent, 1),
            "healthcare_access_loss_percent": round(self.healthcare_access_loss_percent, 1),
            "cascade_depth": self.cascade_depth,
            "overloaded_edges": self.overloaded_edges,
            "accessibility": self.accessibility.to_dict(),
            "resilience_breakdown": self.resilience_breakdown.to_dict(),
            "timeline": self.timeline,
        }


def evaluate_impact(
    network: Network,
    od_pairs: List[ODDemand],
    baseline_access: Dict[str, ZoneAccessibility],
    baseline_avg_travel_time: float,
    baseline_resilience_score: float,
    cascade_result: CascadeResult,
    priority_mode: str = "balanced",
) -> ImpactReport:
    """
    One-stop call for Person 3's API layer: given a network in its
    POST-cascade state (i.e. call this right after cascade.simulate_failure),
    plus the pre-captured baseline snapshots, produce the full impact report.

    Baseline snapshots (`baseline_access`, `baseline_avg_travel_time`,
    `baseline_resilience_score`) should be computed ONCE on a fresh healthy
    network via `capture_baseline_snapshot()` below, then reused across many
    scenario runs so every comparison is against the same reference point.
    """
    accessibility_impact = compute_accessibility_impact(network, baseline_access)
    current_avg_travel_time = average_od_travel_time(network, od_pairs)
    tt_increase_pct = travel_time_increase_percent(baseline_avg_travel_time, current_avg_travel_time)

    total_population = sum(z.population for z in network.zones.values())
    total_edges = len(network.edges_by_id)
    overloaded_and_failed = len(cascade_result.final_overloaded_edges) + len(
        cascade_result.final_failed_edges
    )

    breakdown = compute_resilience_score(
        accessibility_impact=accessibility_impact,
        travel_time_increase_pct=tt_increase_pct,
        total_population=total_population,
        total_edges=total_edges,
        overloaded_and_failed_edges=overloaded_and_failed,
        priority_mode=priority_mode,
    )

    return ImpactReport(
        resilience_score=breakdown.resilience_score,
        baseline_resilience_score=baseline_resilience_score,
        population_affected=accessibility_impact.affected_population,
        travel_time_increase_percent=tt_increase_pct,
        healthcare_access_loss_percent=accessibility_impact.avg_deterioration_percent,
        cascade_depth=cascade_result.cascade_depth,
        overloaded_edges=len(cascade_result.final_overloaded_edges),
        accessibility=accessibility_impact,
        resilience_breakdown=breakdown,
        timeline=cascade_result.to_dict()["timeline"],
    )


@dataclass
class BaselineSnapshot:
    access: Dict[str, ZoneAccessibility]
    avg_travel_time: float
    resilience_score: float


def capture_baseline_snapshot(network: Network, od_pairs: List[ODDemand]) -> BaselineSnapshot:
    """
    Call ONCE on a healthy, baseline-loaded network (right after
    `demand.compute_baseline()`), before any failures are simulated.
    Reuse the returned snapshot for every subsequent `evaluate_impact()`
    call so all scenarios are compared against the identical reference.
    """
    access = compute_hospital_accessibility(network)
    avg_travel_time = average_od_travel_time(network, od_pairs)

    # baseline resilience = evaluate against itself (zero degradation by
    # construction, but computed the same way for consistency/testability)
    zero_impact = compute_accessibility_impact(network, access)
    total_population = sum(z.population for z in network.zones.values())
    total_edges = len(network.edges_by_id)
    breakdown = compute_resilience_score(
        accessibility_impact=zero_impact,
        travel_time_increase_pct=0.0,
        total_population=total_population,
        total_edges=total_edges,
        overloaded_and_failed_edges=0,
        priority_mode="balanced",
    )

    return BaselineSnapshot(
        access=access, avg_travel_time=avg_travel_time, resilience_score=breakdown.resilience_score
    )
