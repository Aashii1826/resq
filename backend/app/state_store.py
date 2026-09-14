"""
Process-wide store for the loaded baseline network + demand + baseline
snapshot + criticality cache. Module-level singleton -- no DB/auth/
multi-tenancy for the MVP.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.data.loader import load_network
from app.models.intervention import Intervention, InterventionType
from app.models.network import Network
from app.simulation.criticality import (
    CRITICALITY_CACHE_FILE,
    CriticalityEntry,
    load_criticality_cache,
    rank_assets_by_criticality,
    save_criticality_cache,
)
from app.simulation.demand import ODDemand, compute_baseline
from app.simulation.impact import BaselineSnapshot, capture_baseline_snapshot


class Store:
    def __init__(self):
        self.network: Optional[Network] = None
        self.od_pairs: Optional[List[ODDemand]] = None
        self.baseline_snapshot: Optional[BaselineSnapshot] = None
        self._interventions: Dict[str, Intervention] = {}

    def load_demo(self):
        network = load_network(mode="demo")
        od_pairs, _stats = compute_baseline(network, num_pairs=60, iterations=4)
        self.network = network
        self.od_pairs = od_pairs
        self.baseline_snapshot = capture_baseline_snapshot(network, od_pairs)
        self._register_demo_interventions()
        return network

    def get_network(self) -> Network:
        if self.network is None:
            self.load_demo()
        return self.network

    def get_od_pairs(self) -> List[ODDemand]:
        if self.od_pairs is None:
            self.load_demo()
        return self.od_pairs

    def get_baseline_snapshot(self) -> BaselineSnapshot:
        if self.baseline_snapshot is None:
            self.load_demo()
        return self.baseline_snapshot

    def _register_demo_interventions(self):
        network = self.network
        # bridge roads are the deliberate bottleneck -- great upgrade candidates
        bridge_edges = [e.edge_id for e in network.edges_by_id.values() if e.metadata.get("is_bridge")]
        other_edges = sorted(
            eid for eid, e in network.edges_by_id.items() if not e.metadata.get("is_bridge")
        )
        candidate_edges = (bridge_edges + other_edges)[:6]

        self._interventions = {}
        for i, eid in enumerate(candidate_edges):
            iv_id = f"upgrade_{i}"
            self._interventions[iv_id] = Intervention(
                intervention_id=iv_id,
                type=InterventionType.CAPACITY_UPGRADE,
                name=f"Upgrade capacity of {eid}",
                cost=2_00_00_000 + i * 50_00_000,  # illustrative INR costs
                target_edge_id=eid,
                params={"multiplier": 1.3},
            )

        hospital_ids = list(network.hospitals.keys())[:3]
        zone_anchors = [z.anchor_node for z in network.zones.values() if z.anchor_node][:3]
        for i, hid in enumerate(hospital_ids):
            iv_id = f"access_{i}"
            connect_from = zone_anchors[i] if i < len(zone_anchors) else None
            self._interventions[iv_id] = Intervention(
                intervention_id=iv_id,
                type=InterventionType.SERVICE_ACCESS_IMPROVEMENT,
                name=f"Improve access to {hid}",
                cost=1_50_00_000,
                target_hospital_id=hid,
                params={"travel_time_reduction_pct": 20, "connect_from": connect_from},
            )

    def get_candidate_interventions(self) -> List[Intervention]:
        if not self._interventions:
            self._register_demo_interventions()
        return list(self._interventions.values())

    def get_criticality(
        self, priority_mode: str = "balanced", force_recalculate: bool = False, top_n: Optional[int] = None
    ) -> List[CriticalityEntry]:
        if not force_recalculate:
            cached = load_criticality_cache(CRITICALITY_CACHE_FILE)
            if cached:
                return cached[:top_n] if top_n else cached
        entries = rank_assets_by_criticality(
            self.get_network(),
            self.get_od_pairs(),
            priority_mode=priority_mode,
            baseline_snapshot=self.get_baseline_snapshot(),
        )
        save_criticality_cache(entries, CRITICALITY_CACHE_FILE)
        return entries[:top_n] if top_n else entries


store = Store()
