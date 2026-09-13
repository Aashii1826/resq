"""
Road edge model + Network wrapper.

Network wraps a NetworkX DiGraph so the rest of the codebase (routing,
demand, cascade, criticality, interventions) never has to touch raw
networkx attribute dicts directly - they go through typed accessors here.

G = (V, E)
  V = road junctions (+ hospitals attached as special nodes)
  E = road segments (RoadEdge)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from app.config import ROAD_TYPE_CAPACITY, ROAD_TYPE_SPEED_KPH, congestion_multiplier
from app.models.asset import Asset, AssetStatus, AssetType, PopulationZone


class EdgeStatus(str, Enum):
    HEALTHY = "HEALTHY"
    STRESSED = "STRESSED"
    OVERLOADED = "OVERLOADED"
    FAILED = "FAILED"


@dataclass
class RoadEdge:
    edge_id: str
    source: str
    target: str
    length: float  # meters
    road_type: str
    speed: float  # km/h
    capacity: float
    baseline_load: float = 0.0
    current_load: float = 0.0
    status: EdgeStatus = EdgeStatus.HEALTHY
    geometry: Optional[List[Tuple[float, float]]] = None  # list of (lat, lon)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def free_flow_travel_time(self) -> float:
        """Minutes, at free-flow speed."""
        if self.speed <= 0:
            return float("inf")
        return (self.length / 1000.0) / self.speed * 60.0

    @property
    def utilization(self) -> float:
        if self.capacity <= 0:
            return 0.0
        return self.current_load / self.capacity

    @property
    def travel_time(self) -> float:
        """Congestion-adjusted travel time in minutes. This is the routing weight."""
        if self.status == EdgeStatus.FAILED:
            return float("inf")
        return self.free_flow_travel_time * congestion_multiplier(self.utilization)

    def refresh_status(self) -> None:
        if self.status == EdgeStatus.FAILED:
            return
        u = self.utilization
        if u > 1.0:
            self.status = EdgeStatus.OVERLOADED
        elif u >= 0.80:
            self.status = EdgeStatus.STRESSED
        else:
            self.status = EdgeStatus.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "length": self.length,
            "road_type": self.road_type,
            "speed": self.speed,
            "travel_time": round(self.travel_time, 3) if self.travel_time != float("inf") else None,
            "free_flow_travel_time": round(self.free_flow_travel_time, 3),
            "capacity": self.capacity,
            "baseline_load": round(self.baseline_load, 2),
            "current_load": round(self.current_load, 2),
            "utilization": round(self.utilization, 4),
            "status": self.status.value,
            "geometry": self.geometry,
            "metadata": self.metadata,
        }


class Network:
    """
    Wraps a directed NetworkX graph of the road network plus attached
    hospitals and population zones.

    Node ids are junction ids (strings). Each edge in self.graph carries
    a single attribute "edge" pointing to a RoadEdge instance - this is the
    source of truth; networkx's own weight is refreshed from it before routing.
    """

    def __init__(self):
        self.graph: nx.DiGraph = nx.DiGraph()
        self.hospitals: Dict[str, Asset] = {}
        self.zones: Dict[str, PopulationZone] = {}
        self.edges_by_id: Dict[str, RoadEdge] = {}
        self.source: str = "unknown"  # "synthetic" or "osm:<area>"

    # -- node / junction helpers -------------------------------------------------
    def add_junction(self, node_id: str, lat: float, lon: float, **attrs) -> None:
        self.graph.add_node(node_id, lat=lat, lon=lon, node_type="JUNCTION", **attrs)

    def node_coords(self, node_id: str) -> Tuple[float, float]:
        data = self.graph.nodes[node_id]
        return data["lat"], data["lon"]

    # -- edge helpers --------------------------------------------------------
    def add_road(self, edge: RoadEdge) -> None:
        self.edges_by_id[edge.edge_id] = edge
        self.graph.add_edge(edge.source, edge.target, edge_id=edge.edge_id, weight=edge.travel_time)

    def get_edge(self, edge_id: str) -> RoadEdge:
        return self.edges_by_id[edge_id]

    def edge_between(self, u: str, v: str) -> Optional[RoadEdge]:
        data = self.graph.get_edge_data(u, v)
        if data is None:
            return None
        return self.edges_by_id[data["edge_id"]]

    def refresh_weights(self) -> None:
        """Push each RoadEdge's current travel_time into the nx graph as edge weight."""
        for u, v, data in self.graph.edges(data=True):
            edge = self.edges_by_id[data["edge_id"]]
            edge.refresh_status()
            data["weight"] = edge.travel_time

    def reset_loads(self) -> None:
        for edge in self.edges_by_id.values():
            edge.current_load = 0.0
            edge.status = EdgeStatus.HEALTHY if edge.status != EdgeStatus.FAILED else EdgeStatus.FAILED

    def fail_edge(self, edge_id: str) -> None:
        edge = self.edges_by_id[edge_id]
        edge.status = EdgeStatus.FAILED
        edge.current_load = 0.0

    def fail_junction(self, node_id: str) -> List[str]:
        """Fail all edges incident to a junction. Returns affected edge_ids."""
        affected = []
        for u, v, data in list(self.graph.in_edges(node_id, data=True)) + list(
            self.graph.out_edges(node_id, data=True)
        ):
            self.fail_edge(data["edge_id"])
            affected.append(data["edge_id"])
        return affected

    def restore_all(self) -> None:
        for edge in self.edges_by_id.values():
            edge.status = EdgeStatus.HEALTHY
            edge.current_load = 0.0

    # -- hospitals / zones -----------------------------------------------------
    def add_hospital(self, hospital: Asset, anchor_node: str) -> None:
        hospital.metadata["anchor_node"] = anchor_node
        self.hospitals[hospital.id] = hospital
        self.graph.add_node(
            f"hospital:{hospital.id}",
            lat=hospital.latitude,
            lon=hospital.longitude,
            node_type="HOSPITAL",
        )

    def add_zone(self, zone: PopulationZone) -> None:
        self.zones[zone.zone_id] = zone

    # -- summary -----------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "nodes": self.graph.number_of_nodes(),
            "roads": self.graph.number_of_edges(),
            "hospitals": len(self.hospitals),
            "zones": len(self.zones),
        }

    def to_geojson(self) -> Dict[str, Any]:
        """Serialize roads as a GeoJSON FeatureCollection for the frontend map."""
        features = []
        for edge in self.edges_by_id.values():
            if edge.geometry:
                coords = [[lon, lat] for lat, lon in edge.geometry]
            else:
                slat, slon = self.node_coords(edge.source)
                tlat, tlon = self.node_coords(edge.target)
                coords = [[slon, slat], [tlon, tlat]]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": edge.to_dict(),
                }
            )
        return {"type": "FeatureCollection", "features": features}
