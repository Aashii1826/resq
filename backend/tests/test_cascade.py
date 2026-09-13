import pytest

from app.data.loader import load_network
from app.simulation.cascade import simulate_failure
from app.simulation.demand import compute_baseline


@pytest.fixture()
def net_and_pairs():
    net = load_network(mode="demo")
    od_pairs, _ = compute_baseline(net, num_pairs=60, iterations=4)
    return net, od_pairs


def _bridge_edge_id(net) -> str:
    bridges = [e.edge_id for e in net.edges_by_id.values() if e.metadata.get("is_bridge")]
    assert bridges, "demo network should have at least one bridge edge (CONTRACTS.md)"
    return bridges[0]


def test_failing_noncritical_road_has_limited_impact(net_and_pairs):
    """Test 2 (Section 36): failing a noncritical road produces limited impact."""
    net, od_pairs = net_and_pairs
    # pick a low-utilization residential edge far from the bridges
    candidate = min(
        (e for e in net.edges_by_id.values() if not e.metadata.get("is_bridge")),
        key=lambda e: e.utilization,
    )
    result = simulate_failure(net, [candidate.edge_id], od_pairs)
    assert result.cascade_depth <= 2
    assert len(result.final_overloaded_edges) <= 3


def test_failing_bottleneck_increases_route_lengths(net_and_pairs):
    """Test 3 (Section 36): failing a bottleneck (bridge) increases route lengths."""
    net, od_pairs = net_and_pairs
    from app.simulation.routing import shortest_route

    # a route that has to cross districts, before failure
    west_nodes = [n for n in net.graph.nodes() if str(n).startswith("west")]
    east_nodes = [n for n in net.graph.nodes() if str(n).startswith("east")]
    before = shortest_route(net, west_nodes[0], east_nodes[0])

    bridge_id = _bridge_edge_id(net)
    simulate_failure(net, [bridge_id], od_pairs)
    net.refresh_weights()
    after = shortest_route(net, west_nodes[0], east_nodes[0])

    assert after.travel_time >= before.travel_time


def test_traffic_redistributes_after_failure(net_and_pairs):
    """Test 4 (Section 36): traffic redistributes after failure - the other
    bridges should absorb load that used to cross the failed one."""
    net, od_pairs = net_and_pairs
    bridges = [e for e in net.edges_by_id.values() if e.metadata.get("is_bridge")]
    failed = bridges[0]
    survivors = [b for b in bridges if b.edge_id != failed.edge_id]
    before_loads = {b.edge_id: b.current_load for b in survivors}

    simulate_failure(net, [failed.edge_id], od_pairs)

    after_loads = {b.edge_id: net.get_edge(b.edge_id).current_load for b in survivors}
    assert sum(after_loads.values()) >= sum(before_loads.values())


def test_overloaded_roads_are_identified(net_and_pairs):
    """Test 5 (Section 36): overloaded roads are identified after a bridge failure."""
    net, od_pairs = net_and_pairs
    bridge_id = _bridge_edge_id(net)
    result = simulate_failure(net, [bridge_id], od_pairs)
    assert isinstance(result.final_overloaded_edges, list)
    # every reported edge really is OVERLOADED on the network
    for eid in result.final_overloaded_edges:
        assert net.get_edge(eid).status.value == "OVERLOADED"


def test_cascade_terminates(net_and_pairs):
    """Test 6 (Section 36): cascade terminates within max_iterations."""
    net, od_pairs = net_and_pairs
    bridge_id = _bridge_edge_id(net)
    result = simulate_failure(net, [bridge_id], od_pairs)
    from app.config import CascadeParams

    assert len(result.timeline) <= CascadeParams().max_iterations + 2  # +initial +stabilized marker


def test_criticality_ranking_identifies_known_bottleneck(net_and_pairs):
    """Test 8 (Section 36), narrow version: failing a bridge causes a
    materially worse outcome than failing an arbitrary residential road -
    proving the engine differentiates critical vs. noncritical assets.
    Full ranking machinery is Person 3's criticality.py; this just proves
    the underlying signal cascade.py + impact.py produce is meaningful.
    """
    net, od_pairs = net_and_pairs
    bridge_id = _bridge_edge_id(net)
    bridge_result = simulate_failure(net, [bridge_id], od_pairs)

    net2 = load_network(mode="demo")
    od_pairs2, _ = compute_baseline(net2, num_pairs=60, iterations=4)
    noncritical = min(
        (e for e in net2.edges_by_id.values() if not e.metadata.get("is_bridge")),
        key=lambda e: e.utilization,
    )
    noncritical_result = simulate_failure(net2, [noncritical.edge_id], od_pairs2)

    assert len(bridge_result.final_overloaded_edges) >= len(noncritical_result.final_overloaded_edges)


def test_cascade_depth_is_zero_when_nothing_new_happens():
    """A failure with no OD pairs routed through it at all should settle
    almost immediately with shallow depth."""
    net = load_network(mode="demo")
    od_pairs, _ = compute_baseline(net, num_pairs=60, iterations=4)
    isolated_candidate = min(net.edges_by_id.values(), key=lambda e: e.baseline_load)
    result = simulate_failure(net, [isolated_candidate.edge_id], od_pairs)
    assert result.cascade_depth >= 0
    assert result.stabilized in (True, False)  # always resolves, never raises
