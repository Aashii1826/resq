"""
Criticality engine (Sections 19-20).

Built against the REAL cascade.py / impact.py (Person 2, commit
ed6c9a9) rather than a placeholder. Key pattern borrowed straight from
their docstrings: capture ONE baseline snapshot, then reuse
`cascade.reset_and_rebaseline()` between candidates instead of
deep-copying the whole Network per candidate -- much faster over ~100+
candidate edges, and it's the exact tool Person 2 built for this.

For every candidate road edge:
  1. simulate its failure on the shared Network
  2. evaluate_impact() against the pre-captured baseline snapshot
  3. reset_and_rebaseline() to undo it before the next candidate
  4. combine several normalized impact metrics into a single 0-100
     Systemic Criticality Score

Separately compute traditional edge-betweenness centrality so the
API/UI can show the headline differentiator:

    Road R41
    Traditional centrality rank: #23
    Systemic criticality rank:   #1
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import networkx as nx

from app.config import CascadeParams
from app.models.network import Network
from app.simulation.cascade import reset_and_rebaseline, simulate_failure
from app.simulation.demand import ODDemand
from app.simulation.impact import BaselineSnapshot, capture_baseline_snapshot, evaluate_impact

# Weights combining the raw impact metrics into one systemic score.
# Prototype assumption, documented here (Section 38) -- not measured.
CRITICALITY_METRIC_WEIGHTS = {
    "population_exposure": 0.25,
    "travel_time_increase": 0.20,
    "healthcare_access_loss": 0.25,
    "overloaded_edges": 0.15,
    "cascade_depth": 0.10,
    "redundancy_loss": 0.05,
}

CRITICALITY_CACHE_FILE = "data/demo/criticality_cache.json"


@dataclass
class CriticalityEntry:
    asset_id: str
    systemic_criticality: float  # 0-100
    systemic_rank: int = 0
    traditional_centrality: float = 0.0
    traditional_rank: int = 0
    resilience_after_failure: float = 0.0
    population_exposure: int = 0
    travel_time_increase_pct: float = 0.0
    healthcare_access_loss_pct: float = 0.0
    overloaded_edges: int = 0
    cascade_depth: int = 0
    redundancy_loss: float = 0.0


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _redundancy_loss(network: Network, asset_id: str) -> float:
    """
    Proxy for 'loss of redundancy': edge-connectivity between the edge's
    two endpoints, on an undirected collapse of the graph. connectivity
    of 1 means this edge is a bridge (or one of very few parallels) ->
    max redundancy loss. Higher score = worse if this edge fails.
    """
    edge = network.edges_by_id.get(asset_id)
    if edge is None:
        return 0.0
    try:
        UG = nx.Graph(network.graph)
        connectivity = nx.edge_connectivity(UG, edge.source, edge.target)
    except Exception:
        connectivity = 1
    return _clamp01(1.0 / max(connectivity, 1))


def _betweenness_for_edges(network: Network) -> Dict[str, float]:
    """Traditional graph metric: edge betweenness centrality (undirected, free-flow-time weighted)."""
    UG = nx.Graph()
    for u, v, data in network.graph.edges(data=True):
        edge = network.edges_by_id[data["edge_id"]]
        w = edge.free_flow_travel_time
        if UG.has_edge(u, v):
            UG[u][v]["weight"] = min(UG[u][v]["weight"], w)
        else:
            UG.add_edge(u, v, weight=w)

    try:
        eb = nx.edge_betweenness_centrality(UG, weight="weight")
    except Exception:
        eb = nx.edge_betweenness_centrality(UG)

    out: Dict[str, float] = {}
    for u, v, data in network.graph.edges(data=True):
        key = (u, v) if (u, v) in eb else (v, u)
        out[data["edge_id"]] = eb.get(key, 0.0)
    return out


def rank_assets_by_criticality(
    network: Network,
    od_pairs: List[ODDemand],
    candidate_asset_ids: Optional[List[str]] = None,
    priority_mode: str = "balanced",
    max_candidates: Optional[int] = None,
    cascade_params: Optional[CascadeParams] = None,
    baseline_snapshot: Optional[BaselineSnapshot] = None,
) -> List[CriticalityEntry]:
    """
    Simulate failure of each candidate road edge (one at a time, on the
    SAME network object, resetting between runs) and rank by systemic
    impact.

    IMPORTANT: this mutates `network` during the scan but always leaves
    it restored to a fresh baseline afterwards (final reset_and_rebaseline
    call), so callers can keep using the same Network object afterwards.

    O(num_candidates) full cascade simulations -- for the demo this
    should be precomputed and cached (Section 37; save_criticality_cache
    / load_criticality_cache below) rather than run on every request.
    """
    if candidate_asset_ids is None:
        candidate_asset_ids = sorted(network.edges_by_id.keys())
    if max_candidates:
        candidate_asset_ids = candidate_asset_ids[:max_candidates]

    if baseline_snapshot is None:
        baseline_snapshot = capture_baseline_snapshot(network, od_pairs)

    betweenness = _betweenness_for_edges(network)
    weights = CRITICALITY_METRIC_WEIGHTS
    entries: List[CriticalityEntry] = []
    total_edges = max(1, len(network.edges_by_id))

    for asset_id in candidate_asset_ids:
        cascade_result = simulate_failure(network, [asset_id], od_pairs, cascade_params)
        impact = evaluate_impact(
            network=network,
            od_pairs=od_pairs,
            baseline_access=baseline_snapshot.access,
            baseline_avg_travel_time=baseline_snapshot.avg_travel_time,
            baseline_resilience_score=baseline_snapshot.resilience_score,
            cascade_result=cascade_result,
            priority_mode=priority_mode,
        )
        redundancy = _redundancy_loss(network, asset_id)

        pop_component = _clamp01(impact.population_affected / 50000.0)
        travel_component = _clamp01(impact.travel_time_increase_percent / 100.0)
        health_component = _clamp01(impact.healthcare_access_loss_percent / 100.0)
        overload_component = _clamp01((impact.overloaded_edges / total_edges) / 0.5)
        depth_component = _clamp01(impact.cascade_depth / 6.0)

        systemic_score = 100 * (
            weights["population_exposure"] * pop_component
            + weights["travel_time_increase"] * travel_component
            + weights["healthcare_access_loss"] * health_component
            + weights["overloaded_edges"] * overload_component
            + weights["cascade_depth"] * depth_component
            + weights["redundancy_loss"] * redundancy
        )

        entries.append(
            CriticalityEntry(
                asset_id=asset_id,
                systemic_criticality=round(systemic_score, 1),
                traditional_centrality=round(betweenness.get(asset_id, 0.0), 4),
                resilience_after_failure=impact.resilience_score,
                population_exposure=impact.population_affected,
                travel_time_increase_pct=impact.travel_time_increase_percent,
                healthcare_access_loss_pct=impact.healthcare_access_loss_percent,
                overloaded_edges=impact.overloaded_edges,
                cascade_depth=impact.cascade_depth,
                redundancy_loss=round(redundancy, 3),
            )
        )

        # undo this candidate's failure before testing the next one
        reset_and_rebaseline(network, od_pairs)

    entries.sort(key=lambda e: e.systemic_criticality, reverse=True)
    for rank, e in enumerate(entries, start=1):
        e.systemic_rank = rank

    by_centrality = sorted(entries, key=lambda e: e.traditional_centrality, reverse=True)
    for rank, e in enumerate(by_centrality, start=1):
        e.traditional_rank = rank

    entries.sort(key=lambda e: e.systemic_rank)
    return entries


def save_criticality_cache(entries: List[CriticalityEntry], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump([e.__dict__ for e in entries], f, indent=2)


def load_criticality_cache(path: str) -> Optional[List[CriticalityEntry]]:
    if not os.path.exists(path):
        return None
    with open(path) as f:
        raw = json.load(f)
    return [CriticalityEntry(**r) for r in raw]
