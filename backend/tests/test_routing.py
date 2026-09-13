import pytest

from app.data.synthetic_loader import build_synthetic_network
from app.simulation.routing import NoRouteError, shortest_route, nearest_hospital_route


@pytest.fixture(scope="module")
def network():
    return build_synthetic_network()


def test_network_has_expected_scale(network):
    assert 50 <= network.graph.number_of_nodes() <= 150
    assert 100 <= network.graph.number_of_edges() <= 400
    assert 5 <= len(network.hospitals) <= 10


def test_network_is_deterministic():
    net_a = build_synthetic_network(seed=42)
    net_b = build_synthetic_network(seed=42)
    assert net_a.graph.number_of_nodes() == net_b.graph.number_of_nodes()
    assert set(net_a.edges_by_id.keys()) == set(net_b.edges_by_id.keys())
    # same seed -> identical capacities (demo must be reproducible)
    for eid in net_a.edges_by_id:
        assert net_a.edges_by_id[eid].capacity == net_b.edges_by_id[eid].capacity


def test_normal_network_has_valid_routes(network):
    """Test 1 (Section 36): normal network has valid routes.

    Note: hospital:* nodes are intentionally dangling markers (location only,
    for the map layer) - real routing happens to their anchor_node instead
    (see nearest_hospital_route). So this test picks real junction nodes.
    """
    junctions = [n for n, d in network.graph.nodes(data=True) if d.get("node_type") == "JUNCTION"]
    origin, destination = junctions[0], junctions[-1]
    route = shortest_route(network, origin, destination)
    assert route.node_path[0] == origin
    assert route.node_path[-1] == destination
    assert route.travel_time > 0
    assert len(route.edge_ids) == len(route.node_path) - 1


def test_same_origin_destination_is_zero_cost(network):
    node = list(network.graph.nodes())[0]
    route = shortest_route(network, node, node)
    assert route.travel_time == 0.0
    assert route.edge_ids == []


def test_unreachable_node_raises(network):
    with pytest.raises(NoRouteError):
        shortest_route(network, "west_0_0", "does_not_exist")


def test_nearest_hospital_route_found(network):
    node = list(network.graph.nodes())[0]
    route = nearest_hospital_route(network, node)
    assert route is not None
    assert route.travel_time >= 0
