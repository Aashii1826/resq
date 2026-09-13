"""
Routing engine.

Thin, well-tested wrapper around networkx shortest-path so every other
module (demand, cascade, criticality, interventions) computes routes the
same way. Weight = RoadEdge.travel_time (already congestion-adjusted -
see Network.refresh_weights()).
"""

from dataclasses import dataclass
from typing import List, Optional

import networkx as nx

from app.models.network import Network


class NoRouteError(Exception):
    """Raised when no path exists between two nodes (e.g. district cut off)."""


@dataclass
class Route:
    origin: str
    destination: str
    node_path: List[str]
    edge_ids: List[str]
    travel_time: float  # minutes, sum of current edge.travel_time along path

    @property
    def hop_count(self) -> int:
        return len(self.edge_ids)


def shortest_route(network: Network, origin: str, destination: str) -> Route:
    """
    Compute the lowest-travel-time route between origin and destination
    using the network's current edge weights (call network.refresh_weights()
    first if edges changed).
    """
    if origin == destination:
        return Route(origin, destination, [origin], [], 0.0)

    try:
        node_path = nx.shortest_path(network.graph, origin, destination, weight="weight")
    except nx.NetworkXNoPath as exc:
        raise NoRouteError(f"No route from {origin} to {destination}") from exc
    except nx.NodeNotFound as exc:
        raise NoRouteError(str(exc)) from exc

    edge_ids: List[str] = []
    total_time = 0.0
    for u, v in zip(node_path[:-1], node_path[1:]):
        data = network.graph.get_edge_data(u, v)
        edge = network.edges_by_id[data["edge_id"]]
        edge_ids.append(edge.edge_id)
        total_time += edge.travel_time

    return Route(origin, destination, node_path, edge_ids, total_time)


def nearest_hospital_route(network: Network, origin: str) -> Optional[Route]:
    """
    Find the fastest route from `origin` to the nearest reachable hospital's
    anchor node. Returns None if no hospital is reachable at all (fully cut
    off zone - a meaningful cascade outcome in itself).
    """
    best: Optional[Route] = None
    for hospital in network.hospitals.values():
        anchor = hospital.metadata["anchor_node"]
        try:
            route = shortest_route(network, origin, anchor)
        except NoRouteError:
            continue
        if best is None or route.travel_time < best.travel_time:
            best = route
    return best


def all_pairs_reachable(network: Network, origin: str, destinations: List[str]) -> List[Route]:
    """Convenience batch helper; skips unreachable destinations rather than raising."""
    routes = []
    for dest in destinations:
        try:
            routes.append(shortest_route(network, origin, dest))
        except NoRouteError:
            continue
    return routes
