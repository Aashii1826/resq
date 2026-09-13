"""
Origin-destination demand generation + traffic assignment.

Section 10 (Baseline Traffic Model) + Section 13 (used again, by the
cascade engine, after edges fail). This module owns:

  1. generate_od_pairs()   - deterministic OD matrix from population zones
  2. assign_demand()       - capacity-restrained assignment (successive
                              averages) that produces edge.current_load /
                              utilization on the Network in place

Both are pure w.r.t. the Network object passed in except that
assign_demand() mutates edge current_load/status as a side effect -
that mutation IS the "baseline load" / "post-failure load" the rest of
the system reads.
"""

import random
from dataclasses import dataclass
from typing import List

from app.config import DEMO_SEED
from app.models.network import Network
from app.simulation.routing import NoRouteError, shortest_route


@dataclass
class ODDemand:
    origin: str
    destination: str
    demand: float  # trips/vehicles per hour, illustrative unit


def generate_od_pairs(network: Network, num_pairs: int = 60, seed: int = DEMO_SEED) -> List[ODDemand]:
    """
    Deterministically generate OD pairs between population-zone anchor
    nodes, weighted loosely by population (bigger zones send/receive more
    trips). Falls back to random junctions if there are too few zones.
    """
    rng = random.Random(seed)

    zone_anchors = [z.anchor_node for z in network.zones.values() if z.anchor_node]
    zone_weights = [max(z.population, 1) for z in network.zones.values() if z.anchor_node]

    if len(zone_anchors) < 2:
        zone_anchors = list(network.graph.nodes())
        zone_weights = [1] * len(zone_anchors)

    od_pairs: List[ODDemand] = []
    attempts = 0
    while len(od_pairs) < num_pairs and attempts < num_pairs * 5:
        attempts += 1
        origin, destination = rng.choices(zone_anchors, weights=zone_weights, k=2)
        if origin == destination:
            continue
        # demand scaled by a base flow + jitter; illustrative units, not
        # calibrated to any real traffic count (Section 11 - documented assumption)
        base_demand = rng.uniform(40, 220)
        od_pairs.append(ODDemand(origin=origin, destination=destination, demand=round(base_demand, 1)))

    return od_pairs


def assign_demand(network: Network, od_pairs: List[ODDemand], iterations: int = 4) -> dict:
    """
    Capacity-restrained assignment via successive averages (a lightweight
    MSA): each iteration routes every OD pair on the *current* (congestion
    adjusted) weights, then blends the new all-or-nothing load with the
    running load so the network doesn't oscillate wildly between two
    extreme states.

    Mutates network in place (sets current_load, status, baseline_load if
    is_baseline=True is set by caller afterwards). Returns a small stats
    dict useful for logging/tests.
    """
    network.reset_loads()
    network.refresh_weights()

    unrouted = 0
    for it in range(1, iterations + 1):
        all_or_nothing_load = {eid: 0.0 for eid in network.edges_by_id}
        unrouted = 0
        for od in od_pairs:
            try:
                route = shortest_route(network, od.origin, od.destination)
            except NoRouteError:
                unrouted += 1
                continue
            for eid in route.edge_ids:
                all_or_nothing_load[eid] += od.demand

        # successive-average blend: new = old + (aon - old) / it
        for eid, edge in network.edges_by_id.items():
            if edge.status.value == "FAILED":
                edge.current_load = 0.0
                continue
            aon = all_or_nothing_load[eid]
            edge.current_load = edge.current_load + (aon - edge.current_load) / it

        network.refresh_weights()

    overloaded = sum(1 for e in network.edges_by_id.values() if e.status.value == "OVERLOADED")
    stressed = sum(1 for e in network.edges_by_id.values() if e.status.value == "STRESSED")

    return {
        "iterations": iterations,
        "od_pairs": len(od_pairs),
        "unrouted_pairs": unrouted,
        "overloaded_edges": overloaded,
        "stressed_edges": stressed,
    }


def compute_baseline(network: Network, num_pairs: int = 60, seed: int = DEMO_SEED, iterations: int = 4):
    """
    Convenience: generate OD demand, assign it, and freeze the result as
    each edge's baseline_load (so later failures can be compared against
    this baseline). Returns (od_pairs, stats).
    """
    od_pairs = generate_od_pairs(network, num_pairs=num_pairs, seed=seed)
    stats = assign_demand(network, od_pairs, iterations=iterations)
    for edge in network.edges_by_id.values():
        edge.baseline_load = edge.current_load
    return od_pairs, stats
