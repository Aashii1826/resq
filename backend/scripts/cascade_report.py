"""
Run: PYTHONPATH=. python3 scripts/cascade_report.py

Extends Person 1's baseline_report.py with the FAILURE / CASCADE / IMPACT
sections from the Section 43 milestone target - proves cascade.py +
impact.py work end to end on top of the foundation layer.
"""

from app.data.loader import load_network
from app.simulation.cascade import simulate_failure
from app.simulation.demand import compute_baseline
from app.simulation.impact import capture_baseline_snapshot, evaluate_impact


def main():
    net = load_network(mode="demo")
    od_pairs, stats = compute_baseline(net, num_pairs=60, iterations=4)
    snapshot = capture_baseline_snapshot(net, od_pairs)

    print("BASELINE\n")
    summary = net.summary()
    print(f"Nodes: {summary['nodes']}")
    print(f"Roads: {summary['roads']}")
    print(f"Hospitals: {summary['hospitals']}")
    print(f"Population zones: {summary['zones']}")
    print(f"Average travel time: {snapshot.avg_travel_time:.1f} min")
    print(f"Overloaded roads: {stats['overloaded_edges']}")
    print(f"System resilience: {snapshot.resilience_score:.0f} / 100")

    bridge_id = next(e.edge_id for e in net.edges_by_id.values() if e.metadata.get("is_bridge"))

    print("\n" + "-" * 32)
    print("\nFAILURE\n")
    print(f"Failed asset: {bridge_id}")

    cascade_result = simulate_failure(net, [bridge_id], od_pairs)

    print("\n" + "-" * 32)
    print("\nCASCADE\n")
    for step in cascade_result.timeline:
        print(f"Step {step.step}:")
        detail_bits = []
        if step.newly_failed:
            detail_bits.append(f"{len(step.newly_failed)} newly failed")
        if step.newly_stressed:
            detail_bits.append(f"{len(step.newly_stressed)} roads newly stressed")
        if step.newly_overloaded:
            detail_bits.append(f"{len(step.newly_overloaded)} roads newly overloaded")
        detail = ", ".join(detail_bits) if detail_bits else step.label
        print(f"  {detail}")

    report = evaluate_impact(
        network=net,
        od_pairs=od_pairs,
        baseline_access=snapshot.access,
        baseline_avg_travel_time=snapshot.avg_travel_time,
        baseline_resilience_score=snapshot.resilience_score,
        cascade_result=cascade_result,
        priority_mode="balanced",
    )

    print("\n" + "-" * 32)
    print("\nIMPACT\n")
    print(f"Population exposed: {report.population_affected:,}")
    print(f"Average travel time: +{report.travel_time_increase_percent:.0f}%")
    print(f"Healthcare accessibility: -{report.healthcare_access_loss_percent:.0f}%")
    print(f"Cascade depth: {report.cascade_depth}")
    print(f"Overloaded roads: {report.overloaded_edges}")
    if cascade_result.unreachable_hospital_zones:
        print(f"Zones fully cut off from hospitals: {cascade_result.unreachable_hospital_zones}")
    print()
    print(f"System resilience:")
    print(f"  {snapshot.resilience_score:.0f} -> {report.resilience_score:.0f}")


if __name__ == "__main__":
    main()
