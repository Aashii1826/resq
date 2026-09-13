import pytest

from app.data.synthetic_loader import build_synthetic_network
from app.simulation.demand import generate_od_pairs, assign_demand, compute_baseline


@pytest.fixture
def network():
    return build_synthetic_network()


def test_generate_od_pairs_count_and_determinism(network):
    pairs_a = generate_od_pairs(network, num_pairs=40, seed=42)
    pairs_b = generate_od_pairs(network, num_pairs=40, seed=42)
    assert len(pairs_a) == 40
    assert [(p.origin, p.destination, p.demand) for p in pairs_a] == [
        (p.origin, p.destination, p.demand) for p in pairs_b
    ]


def test_od_pairs_never_self_loop(network):
    pairs = generate_od_pairs(network, num_pairs=50)
    for p in pairs:
        assert p.origin != p.destination


def test_assign_demand_produces_nonzero_load(network):
    pairs = generate_od_pairs(network, num_pairs=40)
    stats = assign_demand(network, pairs, iterations=3)
    total_load = sum(e.current_load for e in network.edges_by_id.values())
    assert total_load > 0
    assert stats["unrouted_pairs"] >= 0


def test_baseline_load_is_frozen_after_compute_baseline(network):
    od_pairs, stats = compute_baseline(network, num_pairs=40, iterations=3)
    for edge in network.edges_by_id.values():
        assert edge.baseline_load == edge.current_load


def test_baseline_network_is_mostly_healthy(network):
    """Sanity check: a reasonable baseline shouldn't be a gridlocked mess."""
    compute_baseline(network, num_pairs=60, iterations=4)
    overloaded = sum(1 for e in network.edges_by_id.values() if e.status.value == "OVERLOADED")
    total = len(network.edges_by_id)
    assert overloaded / total < 0.10  # fewer than 10% overloaded at baseline
