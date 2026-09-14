"""
Criticality engine.

For each candidate road, actually simulate its failure and measure the
resulting systemic damage (population exposure, travel time increase,
healthcare access loss, overloaded edges, cascade depth) - then combine
into a 0-100 Systemic Criticality Score.

Also computes traditional betweenness centrality so the UI can show the
"a well-connected road isn't necessarily the most damaging one to lose"
comparison (Section 20) - this is the project's strongest point, so the
rank comparison must come from real numbers, not narrative.

Running a full cascade per candidate edge is the expensive part - see
Section 37 (cache it, don't recompute on every UI load). rank_assets_by_criticality
accepts a candidate subset for speed; compute_and_cache_criticality() writes
a JSON file the API should read from at runtime.
"""

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import networkx as nx

from app.models.network import Network
from app.simulation.cascade import simulate_failure
from app.simulation.demand import ODDemand
from app.simulation.impact import (
    compute_baseline_hospital_times,
    compute_impact,
    compute_resilience_score,
)
from app.simulation.routing import shortest_route


@dataclass
class CriticalityResult:
    asset_id: str
    systemic_criticality: float  # 0-100, higher = more damaging to lose
    betweenness_centrality: float  # 0-1 raw networkx value
    systemic_rank: int = 0
    centrality_rank: int = 0
    population_affected: int = 0
    travel_time_increase_percent: float = 0.0
    healthcare_access_loss_percent: float = 0.0
    cascade_depth: int = 0
    overloaded_edges: int = 0

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "systemic_criticality": round(self.systemic_criticality, 1),
            "betweenness_centrality": round(self.betweenness_centrality, 4),
            "systemic_rank": self.systemic_rank,
            "centrality_rank": self.centrality_rank,
            "population_affected": self.population_affected,
            "travel_time_increase_percent": round(self.travel_time_increase_percent, 1),
            "healthcare_access_loss_percent": round(self.healthcare_access_loss_percent, 1),
            "cascade_depth": self.cascade_depth,
            "overloaded_edges": self.overloaded_edges,
        }


def _clone_network_state(network: Network) -> Dict:
    """Cheap snapshot of the mutable per-edge state, so we can restore
    without rebuilding the whole graph after each candidate's failure test."""
    return {
        eid: (edge.status, edge.current_load, edge.baseline_load)
        for eid, edge in network.edges_by_id.items()
    }


def _restore_network_state(network: Network, snapshot: Dict) -> None:
    for eid, (status, load, baseline) in snapshot.items():
        edge = network.edges_by_id[eid]
        edge.status, edge.current_load, edge.baseline_load = status, load, baseline
    network.refresh_weights()


def _avg_travel_time(network: Network, od_pairs: List[ODDemand], sample: int = 25) -> float:
    times = []
    for od in od_pairs[:sample]:
        try:
            times.append(shortest_route(network, od.origin, od.destination).travel_time)
        except Exception:
            continue
    return sum(times) / len(times) if times else 0.0


def compute_betweenness_centrality(network: Network) -> Dict[str, float]:
    """Edge betweenness centrality, keyed by edge_id (traditional graph metric)."""
    edge_bc = nx.edge_betweenness_centrality(network.graph, weight="weight", normalized=True)
    result = {}
    for (u, v), score in edge_bc.items():
        data = network.graph.get_edge_data(u, v)
        if data:
            result[data["edge_id"]] = score
    return result


def rank_assets_by_criticality(
    network: Network,
    od_pairs: List[ODDemand],
    candidate_edge_ids: Optional[List[str]] = None,
    priority_mode: str = "balanced",
) -> List[CriticalityResult]:
    """
    For each candidate edge: fail it, run the cascade, measure impact,
    restore, repeat. Returns results sorted by systemic_criticality desc,
    with both systemic_rank and centrality_rank filled in.
    """
    if candidate_edge_ids is None:
        # default: skip the tiniest residential segments for speed - still
        # covers every road type that plausibly matters for a demo
        candidate_edge_ids = [
            eid for eid, e in network.edges_by_id.items() if e.road_type != "residential"
        ]

    baseline_times = compute_baseline_hospital_times(network)
    baseline_avg_time = _avg_travel_time(network, od_pairs)
    betweenness = compute_betweenness_centrality(network)

    results: List[CriticalityResult] = []
    for edge_id in candidate_edge_ids:
        snapshot = _clone_network_state(network)

        cascade = simulate_failure(network, od_pairs, [edge_id])
        current_avg_time = _avg_travel_time(network, od_pairs)
        impact = compute_impact(network, baseline_times, baseline_avg_time, current_avg_time)
        resilience = compute_resilience_score(impact, network, priority_mode)
        systemic_criticality = round(100.0 - resilience, 1)

        results.append(
            CriticalityResult(
                asset_id=edge_id,
                systemic_criticality=systemic_criticality,
                betweenness_centrality=betweenness.get(edge_id, 0.0),
                population_affected=impact.population_affected,
                travel_time_increase_percent=impact.travel_time_increase_percent,
                healthcare_access_loss_percent=impact.healthcare_access_loss_percent,
                cascade_depth=cascade.cascade_depth,
                overloaded_edges=impact.overloaded_edges,
            )
        )

        _restore_network_state(network, snapshot)

    # rank by systemic criticality (desc)
    results.sort(key=lambda r: r.systemic_criticality, reverse=True)
    for i, r in enumerate(results, start=1):
        r.systemic_rank = i

    # rank the same set by traditional centrality (desc) for comparison
    by_centrality = sorted(results, key=lambda r: r.betweenness_centrality, reverse=True)
    for i, r in enumerate(by_centrality, start=1):
        r.centrality_rank = i

    return results


DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "demo" / "criticality_cache.json"


def compute_and_cache_criticality(
    network: Network,
    od_pairs: List[ODDemand],
    candidate_edge_ids: Optional[List[str]] = None,
    priority_mode: str = "balanced",
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> List[CriticalityResult]:
    """Run the full scan once and persist it - the API should read the
    cached file at request time rather than recomputing (Section 37)."""
    results = rank_assets_by_criticality(network, od_pairs, candidate_edge_ids, priority_mode)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump([r.to_dict() for r in results], f, indent=2)
    return results


def load_cached_criticality(cache_path: Path = DEFAULT_CACHE_PATH) -> List[dict]:
    if not cache_path.exists():
        return []
    with open(cache_path) as f:
        return json.load(f)
