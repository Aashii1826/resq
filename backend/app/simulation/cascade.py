"""
Cascading failure engine (Section 13 - the most important part of the project).

Given a set of already-failed assets, this module runs the iterative
failure -> redistribution -> restabilization loop:

    1. mark assets FAILED, remove them from active routing
    2. re-route affected demand on the current (congestion-adjusted) graph
    3. recalculate utilization / flag stressed & overloaded edges
    4. increase their travel cost (already handled by Network.refresh_weights
       + config.congestion_multiplier - see app/config.py)
    5. re-route again on the new costs
    6. repeat until the network stabilizes or max_iterations is hit

This module does NOT generate OD demand and does NOT decide what "baseline"
means - it consumes a Network that already has a baseline established via
`app.simulation.demand.compute_baseline()`, and the *same* od_pairs list
passed in by the caller (Section 13 note: demand doesn't change mid-cascade,
only routing does).

Cascade depth (Section 14) is tracked as the number of *newly* affected
edges/hospitals-of-interest per iteration, collapsed into "the iteration at
which the network stopped producing new stressed/overloaded/unreachable
edges" - i.e. how many hops of secondary effects the failure produced.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from app.config import CascadeParams
from app.models.network import EdgeStatus, Network
from app.simulation.demand import ODDemand, assign_demand


@dataclass
class CascadeStepState:
    """Snapshot of the network at one cascade iteration - drives the
    frontend's cascade timeline (Section 30)."""

    step: int
    label: str
    newly_failed: List[str] = field(default_factory=list)
    newly_stressed: List[str] = field(default_factory=list)
    newly_overloaded: List[str] = field(default_factory=list)
    overloaded_edges: int = 0
    stressed_edges: int = 0
    failed_edges: int = 0
    unrouted_pairs: int = 0
    max_utilization_delta: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "step": self.step,
            "label": self.label,
            "newly_failed": self.newly_failed,
            "newly_stressed": self.newly_stressed,
            "newly_overloaded": self.newly_overloaded,
            "overloaded_edges": self.overloaded_edges,
            "stressed_edges": self.stressed_edges,
            "failed_edges": self.failed_edges,
            "unrouted_pairs": self.unrouted_pairs,
            "max_utilization_delta": round(self.max_utilization_delta, 4),
        }


@dataclass
class CascadeResult:
    """Full outcome of a cascade run - the shared shape cascade.py hands to
    impact.py, criticality.py, and interventions.py."""

    failed_asset_ids: List[str]
    timeline: List[CascadeStepState]
    cascade_depth: int
    stabilized: bool
    final_stressed_edges: List[str]
    final_overloaded_edges: List[str]
    final_failed_edges: List[str]
    unreachable_hospital_zones: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "failed_asset_ids": self.failed_asset_ids,
            "cascade_depth": self.cascade_depth,
            "stabilized": self.stabilized,
            "final_stressed_edges": self.final_stressed_edges,
            "final_overloaded_edges": self.final_overloaded_edges,
            "final_failed_edges": self.final_failed_edges,
            "unreachable_hospital_zones": self.unreachable_hospital_zones,
            "timeline": [s.to_dict() for s in self.timeline],
        }


def _status_sets(network: Network) -> Dict[str, Set[str]]:
    stressed, overloaded, failed = set(), set(), set()
    for edge in network.edges_by_id.values():
        if edge.status == EdgeStatus.STRESSED:
            stressed.add(edge.edge_id)
        elif edge.status == EdgeStatus.OVERLOADED:
            overloaded.add(edge.edge_id)
        elif edge.status == EdgeStatus.FAILED:
            failed.add(edge.edge_id)
    return {"stressed": stressed, "overloaded": overloaded, "failed": failed}


def simulate_failure(
    network: Network,
    failed_asset_ids: List[str],
    od_pairs: List[ODDemand],
    params: Optional[CascadeParams] = None,
) -> CascadeResult:
    """
    Run the cascading-failure loop.

    Args:
        network: a Network already carrying a computed baseline (baseline_load
            set via compute_baseline). This function mutates it in place -
            callers that need to preserve the original baseline should pass
            a fresh network (e.g. `load_network()` again) or restore it via
            `network.restore_all()` + re-`assign_demand` afterwards.
        failed_asset_ids: road edge_ids (and/or junction node_ids - junctions
            are expanded to their incident edges) to fail as the *initial*
            trigger, at step 0.
        od_pairs: the same OD list used to compute the baseline. Demand does
            not change during a cascade, only routing does.
        params: cascade loop tuning (max_iterations, convergence_epsilon).
            Defaults to config.CascadeParams().

    Returns:
        CascadeResult with the full step-by-step timeline and final state.
    """
    params = params or CascadeParams()
    timeline: List[CascadeStepState] = []

    # -- Step 1-2: mark initial failures -------------------------------------
    initially_failed: List[str] = []
    for asset_id in failed_asset_ids:
        if asset_id in network.edges_by_id:
            network.fail_edge(asset_id)
            initially_failed.append(asset_id)
        elif asset_id in network.graph.nodes:
            initially_failed.extend(network.fail_junction(asset_id))
        # unknown ids are silently ignored - caller/API layer should validate

    network.refresh_weights()
    prev_sets = {"stressed": set(), "overloaded": set(), "failed": set(initially_failed)}
    prev_utilization = {eid: 0.0 for eid in network.edges_by_id}

    timeline.append(
        CascadeStepState(
            step=0,
            label="Primary failure",
            newly_failed=initially_failed,
            failed_edges=len(initially_failed),
        )
    )

    stabilized = False
    depth = 0  # counts iterations that produced a genuinely new effect

    for it in range(1, params.max_iterations + 1):
        # -- Step 3-6: redistribute traffic on the current graph -------------
        stats = assign_demand(network, od_pairs, iterations=4)
        network.refresh_weights()

        current_sets = _status_sets(network)
        newly_stressed = sorted(current_sets["stressed"] - prev_sets["stressed"])
        newly_overloaded = sorted(current_sets["overloaded"] - prev_sets["overloaded"])
        newly_failed = sorted(current_sets["failed"] - prev_sets["failed"])

        max_delta = 0.0
        for eid, edge in network.edges_by_id.items():
            delta = abs(edge.utilization - prev_utilization.get(eid, 0.0))
            if delta > max_delta:
                max_delta = delta

        step_label = _label_for_iteration(it, newly_stressed, newly_overloaded, newly_failed)
        timeline.append(
            CascadeStepState(
                step=it,
                label=step_label,
                newly_failed=newly_failed,
                newly_stressed=newly_stressed,
                newly_overloaded=newly_overloaded,
                overloaded_edges=len(current_sets["overloaded"]),
                stressed_edges=len(current_sets["stressed"]),
                failed_edges=len(current_sets["failed"]),
                unrouted_pairs=stats["unrouted_pairs"],
                max_utilization_delta=max_delta,
            )
        )

        produced_new_effect = bool(newly_stressed or newly_overloaded or newly_failed)
        if produced_new_effect:
            depth = it

        prev_sets = current_sets
        prev_utilization = {eid: e.utilization for eid, e in network.edges_by_id.items()}

        # -- Step 10: convergence check ---------------------------------------
        if max_delta < params.convergence_epsilon and not produced_new_effect:
            stabilized = True
            timeline.append(
                CascadeStepState(
                    step=it + 1,
                    label="Network stabilized",
                    overloaded_edges=len(current_sets["overloaded"]),
                    stressed_edges=len(current_sets["stressed"]),
                    failed_edges=len(current_sets["failed"]),
                )
            )
            break
    else:
        # loop exhausted max_iterations without an explicit break
        stabilized = False

    final_sets = _status_sets(network)
    unreachable_zones = _unreachable_hospital_zones(network)

    return CascadeResult(
        failed_asset_ids=initially_failed,
        timeline=timeline,
        cascade_depth=depth,
        stabilized=stabilized,
        final_stressed_edges=sorted(final_sets["stressed"]),
        final_overloaded_edges=sorted(final_sets["overloaded"]),
        final_failed_edges=sorted(final_sets["failed"]),
        unreachable_hospital_zones=unreachable_zones,
    )


def _label_for_iteration(
    it: int, newly_stressed: List[str], newly_overloaded: List[str], newly_failed: List[str]
) -> str:
    """Human-readable timeline label (Section 30) - best-effort description
    of what kind of effect this iteration mainly produced."""
    if it == 1:
        return "Traffic redistribution"
    if newly_overloaded or newly_failed:
        return "Secondary overload" if it == 2 else "Tertiary route changes"
    if newly_stressed:
        return "Traffic redistribution"
    return "Network settling"


def _unreachable_hospital_zones(network: Network) -> List[str]:
    """Zones whose anchor node currently cannot reach ANY hospital at all -
    the most severe form of healthcare accessibility loss (feeds impact.py
    but also useful standalone as a cascade signal)."""
    from app.simulation.routing import nearest_hospital_route

    unreachable = []
    for zone in network.zones.values():
        if not zone.anchor_node:
            continue
        route = nearest_hospital_route(network, zone.anchor_node)
        if route is None:
            unreachable.append(zone.zone_id)
    return unreachable


def reset_and_rebaseline(network: Network, od_pairs: List[ODDemand]) -> None:
    """Convenience for callers (criticality/interventions) that need to run
    many cascades back-to-back on the same Network object: restore all
    edges to HEALTHY and re-assign the baseline load before the next
    simulate_failure() call, so failures don't stack across runs."""
    network.restore_all()
    assign_demand(network, od_pairs, iterations=4)
