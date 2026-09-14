"""
Intervention engine (Sections 22-24).

Built against the real `app.models.intervention.Intervention` /
`InterventionType`, the real `Network` / `RoadEdge`, and Person 2's real
cascade.py / impact.py (commit ed6c9a9).

Three intervention types (per models/intervention.py docstring):
  CAPACITY_UPGRADE            target_edge_id, params={"multiplier": 1.3}
  ALTERNATE_ROUTE              params={"source": node_id, "target": node_id, "road_type": ...}
  SERVICE_ACCESS_IMPROVEMENT  target_hospital_id, params={"travel_time_reduction_pct": 20, "connect_from": node_id}

Unlike criticality.py (which reuses one Network object via
reset_and_rebaseline, since failures are transient), interventions
structurally change the network -- added edges, capacity multipliers --
which reset_and_rebaseline cannot undo. So every intervention is applied
to a fresh `copy.deepcopy()` of the baseline network, and both the
"baseline" (no intervention) and "new" (with intervention) runs are
scored against the SAME pre-captured BaselineSnapshot of the original,
healthy, un-intervened network -- exactly the pattern
`impact.capture_baseline_snapshot()` was built for.

Every intervention is evaluated by actually re-running the simulation,
never an arbitrary "risk reduction %" (Section 23).
"""

from __future__ import annotations

import copy
from itertools import combinations
from typing import Dict, List, Optional

from app.config import CascadeParams, ROAD_TYPE_CAPACITY, ROAD_TYPE_SPEED_KPH
from app.models.intervention import Intervention, InterventionType
from app.models.network import Network, RoadEdge
from app.simulation.cascade import simulate_failure
from app.simulation.demand import ODDemand
from app.simulation.impact import BaselineSnapshot, capture_baseline_snapshot, evaluate_impact

CAPACITY_UPGRADE_MULTIPLIER = 1.30
MAX_OPTIMIZER_CANDIDATES = 12  # brute force is fine for an MVP-scale candidate list


def apply_interventions(baseline_network: Network, interventions: List[Intervention]) -> Network:
    """Return a NEW Network with the interventions applied. Does not mutate input."""
    network = copy.deepcopy(baseline_network)

    for iv in interventions:
        if iv.type == InterventionType.CAPACITY_UPGRADE:
            if iv.target_edge_id and iv.target_edge_id in network.edges_by_id:
                edge = network.edges_by_id[iv.target_edge_id]
                multiplier = iv.params.get("multiplier", CAPACITY_UPGRADE_MULTIPLIER)
                edge.capacity = edge.capacity * multiplier

        elif iv.type == InterventionType.ALTERNATE_ROUTE:
            source = iv.params.get("source")
            target = iv.params.get("target")
            if source and target and network.graph.has_node(source) and network.graph.has_node(target):
                road_type = iv.params.get("road_type", "secondary")
                capacity = iv.params.get("capacity", ROAD_TYPE_CAPACITY.get(road_type, 1500))
                speed = iv.params.get("speed", ROAD_TYPE_SPEED_KPH.get(road_type, 40))
                length = iv.params.get("length", 500)
                for a, b in [(source, target), (target, source)]:
                    eid = f"ALT_{iv.intervention_id}_{a}_{b}"
                    if eid in network.edges_by_id:
                        continue
                    edge = RoadEdge(
                        edge_id=eid,
                        source=a,
                        target=b,
                        length=length,
                        road_type=road_type,
                        speed=speed,
                        capacity=capacity,
                        geometry=[network.node_coords(a), network.node_coords(b)],
                        metadata={"intervention_added": True, "intervention_id": iv.intervention_id},
                    )
                    network.add_road(edge)

        elif iv.type == InterventionType.SERVICE_ACCESS_IMPROVEMENT:
            if iv.target_hospital_id and iv.target_hospital_id in network.hospitals:
                hospital = network.hospitals[iv.target_hospital_id]
                anchor = hospital.metadata.get("anchor_node")
                connect_from = iv.params.get("connect_from")
                reduction_pct = iv.params.get("travel_time_reduction_pct", 20.0)

                if connect_from and anchor and network.graph.has_node(connect_from):
                    for a, b in [(connect_from, anchor), (anchor, connect_from)]:
                        eid = f"ACCESS_{iv.intervention_id}_{a}_{b}"
                        if eid in network.edges_by_id:
                            continue
                        edge = RoadEdge(
                            edge_id=eid,
                            source=a,
                            target=b,
                            length=iv.params.get("length", 300),
                            road_type="secondary",
                            speed=iv.params.get("speed", ROAD_TYPE_SPEED_KPH.get("secondary", 40)),
                            capacity=iv.params.get("capacity", ROAD_TYPE_CAPACITY.get("secondary", 2000)),
                            geometry=[network.node_coords(a), network.node_coords(b)],
                            metadata={"intervention_added": True, "intervention_id": iv.intervention_id},
                        )
                        network.add_road(edge)
                # a generic throughput boost representing improved hospital-side access
                hospital.capacity = hospital.capacity * (1 + reduction_pct / 100.0)

    network.refresh_weights()
    return network


def _resilience_for_scenario(
    network: Network,
    od_pairs: List[ODDemand],
    baseline_snapshot: BaselineSnapshot,
    failed_asset_ids: List[str],
    priority_mode: str,
    cascade_params: Optional[CascadeParams],
):
    """Run one failure scenario on `network` (mutated in place) and score it
    against the given baseline snapshot."""
    cascade_result = simulate_failure(network, failed_asset_ids, od_pairs, cascade_params)
    impact = evaluate_impact(
        network=network,
        od_pairs=od_pairs,
        baseline_access=baseline_snapshot.access,
        baseline_avg_travel_time=baseline_snapshot.avg_travel_time,
        baseline_resilience_score=baseline_snapshot.resilience_score,
        cascade_result=cascade_result,
        priority_mode=priority_mode,
    )
    return impact


def evaluate_intervention(
    baseline_network: Network,
    od_pairs: List[ODDemand],
    interventions: List[Intervention],
    failed_asset_ids: List[str],
    priority_mode: str = "balanced",
    cascade_params: Optional[CascadeParams] = None,
    baseline_snapshot: Optional[BaselineSnapshot] = None,
) -> Dict:
    """
    Apply `interventions`, run the SAME failure scenario with and without
    them, and report the actual resilience delta -- never a canned %.

    `baseline_network` is treated as read-only: both the "no intervention"
    and "with intervention" runs operate on separate deep copies of it.
    """
    if baseline_snapshot is None:
        baseline_snapshot = capture_baseline_snapshot(baseline_network, od_pairs)

    # -- run 1: same failure, no interventions --
    plain_copy = copy.deepcopy(baseline_network)
    baseline_impact = _resilience_for_scenario(
        plain_copy, od_pairs, baseline_snapshot, failed_asset_ids, priority_mode, cascade_params
    )

    # -- run 2: interventions applied first, then the same failure --
    upgraded_network = apply_interventions(baseline_network, interventions)
    new_impact = _resilience_for_scenario(
        upgraded_network, od_pairs, baseline_snapshot, failed_asset_ids, priority_mode, cascade_params
    )

    total_cost = sum(iv.cost for iv in interventions)

    return {
        "baseline_resilience": baseline_impact.resilience_score,
        "new_resilience": new_impact.resilience_score,
        "improvement": round(new_impact.resilience_score - baseline_impact.resilience_score, 1),
        "baseline_population_affected": baseline_impact.population_affected,
        "new_population_affected": new_impact.population_affected,
        "baseline_healthcare_access_percent": round(100 - baseline_impact.healthcare_access_loss_percent, 1),
        "new_healthcare_access_percent": round(100 - new_impact.healthcare_access_loss_percent, 1),
        "cost": total_cost,
    }


def optimize_interventions(
    baseline_network: Network,
    od_pairs: List[ODDemand],
    candidate_interventions: List[Intervention],
    budget: float,
    failed_asset_ids: List[str],
    priority_mode: str = "balanced",
    cascade_params: Optional[CascadeParams] = None,
) -> Dict:
    """
    Brute-force every affordable subset of candidate_interventions (fine
    for MVP-scale candidate lists, <= MAX_OPTIMIZER_CANDIDATES) and
    return the subset with the greatest resilience improvement that
    fits the budget. Every combination is scored by actually re-running
    the simulation on its own deep copy of the network.
    """
    n = len(candidate_interventions)
    if n > MAX_OPTIMIZER_CANDIDATES:
        raise ValueError(f"Brute-force optimizer is intended for <= {MAX_OPTIMIZER_CANDIDATES} candidates in the MVP")

    baseline_snapshot = capture_baseline_snapshot(baseline_network, od_pairs)

    plain_copy = copy.deepcopy(baseline_network)
    baseline_impact = _resilience_for_scenario(
        plain_copy, od_pairs, baseline_snapshot, failed_asset_ids, priority_mode, cascade_params
    )

    best = {"combo": [], "improvement": 0.0, "impact": baseline_impact, "cost": 0.0}
    combos_evaluated = 0

    for r in range(0, n + 1):
        for combo in combinations(candidate_interventions, r):
            cost = sum(iv.cost for iv in combo)
            if cost > budget:
                continue
            combos_evaluated += 1

            if r == 0:
                improvement = 0.0
                impact = baseline_impact
            else:
                upgraded_network = apply_interventions(baseline_network, list(combo))
                impact = _resilience_for_scenario(
                    upgraded_network, od_pairs, baseline_snapshot, failed_asset_ids, priority_mode, cascade_params
                )
                improvement = impact.resilience_score - baseline_impact.resilience_score

            if improvement > best["improvement"]:
                best = {"combo": list(combo), "improvement": improvement, "impact": impact, "cost": cost}

    best_impact = best["impact"]
    return {
        "recommended_interventions": best["combo"],
        "total_cost": best["cost"],
        "baseline_resilience": baseline_impact.resilience_score,
        "new_resilience": best_impact.resilience_score,
        "improvement": round(best["improvement"], 1),
        "population_exposure_before": baseline_impact.population_affected,
        "population_exposure_after": best_impact.population_affected,
        "healthcare_access_before_percent": round(100 - baseline_impact.healthcare_access_loss_percent, 1),
        "healthcare_access_after_percent": round(100 - best_impact.healthcare_access_loss_percent, 1),
        "combinations_evaluated": combos_evaluated,
    }
