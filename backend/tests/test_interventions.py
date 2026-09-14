from app.data.loader import load_network
from app.simulation.demand import compute_baseline
from app.models.intervention import Intervention, InterventionType
from app.simulation.interventions import evaluate_intervention, optimize_interventions


def make_baseline():
    network = load_network(mode="demo")
    od_pairs, _ = compute_baseline(network, num_pairs=60, iterations=4)
    return network, od_pairs


def _pick_heavily_loaded_edge(network):
    return max(network.edges_by_id.values(), key=lambda e: e.baseline_load).edge_id


def test_capacity_upgrade_improves_or_maintains_resilience():
    network, od_pairs = make_baseline()
    failed_edge = _pick_heavily_loaded_edge(network)
    target = next(eid for eid in network.edges_by_id if eid != failed_edge)

    iv = Intervention(
        intervention_id="test_upgrade", type=InterventionType.CAPACITY_UPGRADE,
        name="test upgrade", cost=1.0, target_edge_id=target, params={"multiplier": 2.0},
    )
    result = evaluate_intervention(network, od_pairs, [iv], [failed_edge])
    assert result["new_resilience"] >= result["baseline_resilience"] - 0.01
    assert result["cost"] == 1.0


def test_baseline_network_is_not_mutated_by_evaluation():
    """evaluate_intervention must treat baseline_network as read-only."""
    network, od_pairs = make_baseline()
    edge_id = _pick_heavily_loaded_edge(network)
    original_status = {eid: e.status for eid, e in network.edges_by_id.items()}

    iv = Intervention(
        intervention_id="test_upgrade", type=InterventionType.CAPACITY_UPGRADE,
        name="test upgrade", cost=1.0, target_edge_id=edge_id, params={"multiplier": 2.0},
    )
    evaluate_intervention(network, od_pairs, [iv], [edge_id])

    after_status = {eid: e.status for eid, e in network.edges_by_id.items()}
    assert original_status == after_status


def test_alternate_route_intervention_applies_without_error():
    network, od_pairs = make_baseline()
    failed_edge = _pick_heavily_loaded_edge(network)
    nodes = list(network.graph.nodes())
    iv = Intervention(
        intervention_id="test_alt", type=InterventionType.ALTERNATE_ROUTE,
        name="test alt route", cost=2.0, params={"source": nodes[0], "target": nodes[5]},
    )
    result = evaluate_intervention(network, od_pairs, [iv], [failed_edge])
    assert "new_resilience" in result


def test_service_access_intervention_applies_without_error():
    network, od_pairs = make_baseline()
    failed_edge = _pick_heavily_loaded_edge(network)
    hospital_id = next(iter(network.hospitals.keys()))
    zone_anchor = next(z.anchor_node for z in network.zones.values() if z.anchor_node)
    iv = Intervention(
        intervention_id="test_access", type=InterventionType.SERVICE_ACCESS_IMPROVEMENT,
        name="test access", cost=1.5, target_hospital_id=hospital_id,
        params={"connect_from": zone_anchor, "travel_time_reduction_pct": 25},
    )
    result = evaluate_intervention(network, od_pairs, [iv], [failed_edge])
    assert "new_resilience" in result


def test_optimizer_never_exceeds_budget():
    network, od_pairs = make_baseline()
    failed_edge = _pick_heavily_loaded_edge(network)
    edge_ids = sorted(network.edges_by_id.keys())[:5]

    candidates = [
        Intervention(
            intervention_id=f"iv_{i}", type=InterventionType.CAPACITY_UPGRADE,
            name=f"upgrade {eid}", cost=(i + 1) * 10.0, target_edge_id=eid,
        )
        for i, eid in enumerate(edge_ids)
    ]
    budget = 25.0
    result = optimize_interventions(network, od_pairs, candidates, budget, [failed_edge])
    assert result["total_cost"] <= budget
    assert result["combinations_evaluated"] > 0


def test_optimizer_finds_nonnegative_improvement_when_affordable():
    network, od_pairs = make_baseline()
    failed_edge = _pick_heavily_loaded_edge(network)
    edge_ids = sorted(network.edges_by_id.keys())[:4]
    candidates = [
        Intervention(
            intervention_id=f"iv_{i}", type=InterventionType.CAPACITY_UPGRADE,
            name=f"upgrade {eid}", cost=1.0, target_edge_id=eid, params={"multiplier": 1.5},
        )
        for i, eid in enumerate(edge_ids)
    ]
    result = optimize_interventions(network, od_pairs, candidates, budget=10.0, failed_asset_ids=[failed_edge])
    assert result["improvement"] >= 0.0
