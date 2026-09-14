"""
Intervention engine.

Three intervention types (Section 22):
  CAPACITY_UPGRADE           - multiply a road's capacity
  ALTERNATE_ROUTE            - add a new redundant road between two nodes
  SERVICE_ACCESS_IMPROVEMENT - reduce effective travel time to a hospital

evaluate_intervention() actually reruns the simulation before/after - no
made-up "risk reduction %" numbers (Section 23).

optimize_interventions() brute-forces combinations against a budget
(Section 24) - fine for 6-10 candidates at hackathon scale.
"""

import itertools
from dataclasses import dataclass, field
from typing import List, Optional

from app.models.intervention import Intervention, InterventionType
from app.models.network import Network, RoadEdge
from app.simulation.cascade import simulate_failure
from app.simulation.criticality import _avg_travel_time  # reuse the same sampling helper
from app.simulation.demand import ODDemand
from app.simulation.impact import (
    compute_baseline_hospital_times,
    compute_impact,
    compute_resilience_score,
)


def apply_intervention(network: Network, intervention: Intervention) -> Optional[str]:
    """
    Mutates `network` in place. Returns the id of any new edge created
    (for ALTERNATE_ROUTE), else None. Caller is responsible for restoring
    the network afterwards if they need the pre-intervention state again.
    """
    if intervention.type == InterventionType.CAPACITY_UPGRADE:
        edge = network.get_edge(intervention.target_edge_id)
        multiplier = intervention.params.get("multiplier", 1.3)
        edge.capacity = edge.capacity * multiplier
        return None

    elif intervention.type == InterventionType.ALTERNATE_ROUTE:
        source = intervention.params["source"]
        target = intervention.params["target"]
        road_type = intervention.params.get("road_type", "secondary")
        from app.config import ROAD_TYPE_CAPACITY, ROAD_TYPE_SPEED_KPH

        length = intervention.params.get("length", 400.0)
        new_edge = RoadEdge(
            edge_id=f"intervention:{intervention.intervention_id}",
            source=source,
            target=target,
            length=length,
            road_type=road_type,
            speed=ROAD_TYPE_SPEED_KPH.get(road_type, 40),
            capacity=ROAD_TYPE_CAPACITY.get(road_type, 2000),
            geometry=[network.node_coords(source), network.node_coords(target)],
            metadata={"added_by_intervention": intervention.intervention_id},
        )
        network.add_road(new_edge)
        # bidirectional by default so it's actually useful for rerouting
        reverse_edge = RoadEdge(
            edge_id=f"intervention:{intervention.intervention_id}:rev",
            source=target,
            target=source,
            length=length,
            road_type=road_type,
            speed=ROAD_TYPE_SPEED_KPH.get(road_type, 40),
            capacity=ROAD_TYPE_CAPACITY.get(road_type, 2000),
            geometry=[network.node_coords(target), network.node_coords(source)],
            metadata={"added_by_intervention": intervention.intervention_id},
        )
        network.add_road(reverse_edge)
        network.refresh_weights()
        return new_edge.edge_id

    elif intervention.type == InterventionType.SERVICE_ACCESS_IMPROVEMENT:
        hospital = network.hospitals[intervention.target_hospital_id]
        reduction_pct = intervention.params.get("travel_time_reduction_pct", 20)
        # modelled as speeding up every road directly incident to the
        # hospital's anchor node (dedicated access road / triage improvements)
        anchor = hospital.metadata["anchor_node"]
        for u, v, data in list(network.graph.in_edges(anchor, data=True)) + list(
            network.graph.out_edges(anchor, data=True)
        ):
            edge = network.edges_by_id[data["edge_id"]]
            edge.speed = edge.speed * (1 + reduction_pct / 100.0)
        network.refresh_weights()
        return None

    raise ValueError(f"Unknown intervention type: {intervention.type}")


@dataclass
class InterventionEvaluation:
    intervention_ids: List[str]
    cost: float
    baseline_resilience: float
    new_resilience: float
    resilience_improvement: float
    baseline_population_affected: int
    new_population_affected: int
    population_exposure_reduction: int

    def to_dict(self) -> dict:
        return {
            "intervention_ids": self.intervention_ids,
            "cost": self.cost,
            "baseline_resilience": self.baseline_resilience,
            "new_resilience": self.new_resilience,
            "resilience_improvement": round(self.resilience_improvement, 1),
            "baseline_population_affected": self.baseline_population_affected,
            "new_population_affected": self.new_population_affected,
            "population_exposure_reduction": self.population_exposure_reduction,
        }


def _resilience_and_population_for_failure(
    network: Network,
    od_pairs: List[ODDemand],
    failed_assets: List[str],
    priority_mode: str,
):
    baseline_times = compute_baseline_hospital_times(network)
    baseline_avg_time = _avg_travel_time(network, od_pairs)

    cascade = simulate_failure(network, od_pairs, failed_assets)
    current_avg_time = _avg_travel_time(network, od_pairs)
    impact = compute_impact(network, baseline_times, baseline_avg_time, current_avg_time)
    resilience = compute_resilience_score(impact, network, priority_mode)
    return resilience, impact.population_affected


def evaluate_intervention(
    network: Network,
    od_pairs: List[ODDemand],
    interventions: List[Intervention],
    failed_assets: List[str],
    priority_mode: str = "balanced",
) -> InterventionEvaluation:
    """
    Rerun the SAME failure scenario with and without the given
    interventions applied first, and diff the results (Section 23 - no
    made-up percentages).
    """
    # baseline: failure, no interventions
    baseline_net = _deep_copy_network(network)
    baseline_resilience, baseline_pop = _resilience_and_population_for_failure(
        baseline_net, od_pairs, failed_assets, priority_mode
    )

    # with interventions applied first, then the same failure
    intervened_net = _deep_copy_network(network)
    for interv in interventions:
        apply_intervention(intervened_net, interv)
    new_resilience, new_pop = _resilience_and_population_for_failure(
        intervened_net, od_pairs, failed_assets, priority_mode
    )

    total_cost = sum(i.cost for i in interventions)

    return InterventionEvaluation(
        intervention_ids=[i.intervention_id for i in interventions],
        cost=total_cost,
        baseline_resilience=baseline_resilience,
        new_resilience=new_resilience,
        resilience_improvement=new_resilience - baseline_resilience,
        baseline_population_affected=baseline_pop,
        new_population_affected=new_pop,
        population_exposure_reduction=max(0, baseline_pop - new_pop),
    )


def optimize_interventions(
    network: Network,
    od_pairs: List[ODDemand],
    candidate_interventions: List[Intervention],
    failed_assets: List[str],
    budget: float,
    priority_mode: str = "balanced",
) -> Optional[InterventionEvaluation]:
    """
    Brute-force every feasible combination of candidate interventions
    (fine for 6-10 candidates - Section 24) and return the one with the
    best resilience_improvement that fits the budget.
    """
    best: Optional[InterventionEvaluation] = None

    for r in range(1, len(candidate_interventions) + 1):
        for combo in itertools.combinations(candidate_interventions, r):
            cost = sum(i.cost for i in combo)
            if cost > budget:
                continue
            evaluation = evaluate_intervention(
                network, od_pairs, list(combo), failed_assets, priority_mode
            )
            if best is None or evaluation.resilience_improvement > best.resilience_improvement:
                best = evaluation

    return best


def _deep_copy_network(network: Network) -> Network:
    """
    A full deep copy is simplest/safest for the brute-force optimizer
    (many independent what-if branches). Fine at this network scale
    (hundreds of edges) for a 2-day prototype.
    """
    import copy

    return copy.deepcopy(network)
