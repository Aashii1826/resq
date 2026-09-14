from app.data.loader import load_network
from app.simulation.demand import compute_baseline
from app.simulation.criticality import rank_assets_by_criticality
from app.simulation.impact import capture_baseline_snapshot


def make_baseline():
    network = load_network(mode="demo")
    od_pairs, _ = compute_baseline(network, num_pairs=60, iterations=4)
    snapshot = capture_baseline_snapshot(network, od_pairs)
    return network, od_pairs, snapshot


def test_criticality_ranking_produces_valid_scores():
    network, od_pairs, snapshot = make_baseline()
    edge_ids = sorted(network.edges_by_id.keys())[:30]
    entries = rank_assets_by_criticality(network, od_pairs, candidate_asset_ids=edge_ids, baseline_snapshot=snapshot)
    assert len(entries) == 30
    for e in entries:
        assert 0 <= e.systemic_criticality <= 100
        assert e.systemic_rank >= 1
        assert e.traditional_rank >= 1


def test_criticality_ranking_is_sorted_descending():
    network, od_pairs, snapshot = make_baseline()
    edge_ids = sorted(network.edges_by_id.keys())[:20]
    entries = rank_assets_by_criticality(network, od_pairs, candidate_asset_ids=edge_ids, baseline_snapshot=snapshot)
    scores = [e.systemic_criticality for e in entries]
    assert scores == sorted(scores, reverse=True)


def test_ranking_leaves_network_at_a_clean_baseline():
    """rank_assets_by_criticality mutates the shared network during the scan
    but must always leave it reset (no lingering FAILED edges) afterwards."""
    network, od_pairs, snapshot = make_baseline()
    edge_ids = sorted(network.edges_by_id.keys())[:15]
    rank_assets_by_criticality(network, od_pairs, candidate_asset_ids=edge_ids, baseline_snapshot=snapshot)
    failed = [e for e in network.edges_by_id.values() if e.status.value == "FAILED"]
    assert failed == []


def test_bridge_roads_rank_among_most_critical():
    """
    Test 8 (Section 36): criticality ranking identifies the known
    bottleneck. The demo network has a deliberate structural bottleneck:
    only 3 bridge roads connect the two districts. Failing one should
    matter more, on average, than a random sample of ordinary residential
    roads.
    """
    network, od_pairs, snapshot = make_baseline()
    bridge_edges = [eid for eid, e in network.edges_by_id.items() if e.metadata.get("is_bridge")]
    assert bridge_edges, "demo network should have bridge edges"

    residential_edges = [
        eid for eid, e in network.edges_by_id.items()
        if e.road_type == "residential" and not e.metadata.get("is_bridge")
    ][:10]

    candidates = bridge_edges + residential_edges
    entries = rank_assets_by_criticality(network, od_pairs, candidate_asset_ids=candidates, baseline_snapshot=snapshot)
    by_id = {e.asset_id: e for e in entries}

    avg_bridge_score = sum(by_id[e].systemic_criticality for e in bridge_edges) / len(bridge_edges)
    avg_residential_score = sum(by_id[e].systemic_criticality for e in residential_edges) / len(residential_edges)

    assert avg_bridge_score >= avg_residential_score


def test_traditional_and_systemic_rank_can_diverge():
    """Sanity check that the two ranking systems are independently computed (Section 20)."""
    network, od_pairs, snapshot = make_baseline()
    edge_ids = sorted(network.edges_by_id.keys())[:25]
    entries = rank_assets_by_criticality(network, od_pairs, candidate_asset_ids=edge_ids, baseline_snapshot=snapshot)
    ranks_differ = any(e.systemic_rank != e.traditional_rank for e in entries)
    assert ranks_differ
