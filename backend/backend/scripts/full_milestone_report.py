"""
Run: PYTHONPATH=. python3 scripts/full_milestone_report.py

Reproduces the exact BASELINE -> FAILURE -> CASCADE -> IMPACT report
format from the project brief (Section 43), using the real engine
end-to-end: graph -> routing -> demand -> failure -> cascade -> impact ->
resilience score.
"""

from app.data.loader import load_network
from app.simulation.cascade import simulate_failure
from app.simulation.demand import compute_baseline
from app.simulation.impact import compute_baseline_hospital_times, compute_impact, compute_resilience_score
from app.simulation.routing import NoRouteError, shortest_route


def avg_travel_time(network, od_pairs, sample=25):
    times = []
    for od in od_pairs[:sample]:
        try:
            times.append(shortest_route(network, od.origin, od.destination).travel_time)
        except NoRouteError:
            continue
    return sum(times) / len(times) if times else 0.0


def main():
    net = load_network(mode="demo")
    od_pairs, stats = compute_baseline(net, num_pairs=60, iterations=4)
    baseline_hospital_times = compute_baseline_hospital_times(net)
    baseline_avg_time = avg_travel_time(net, od_pairs)
    baseline_impact = compute_impact(net, baseline_hospital_times, baseline_avg_time, baseline_avg_time)
    baseline_resilience = compute_resilience_score(baseline_impact, net)
    baseline_overloaded = sum(1 for e in net.edges_by_id.values() if e.status.value == "OVERLOADED")

    print("BASELINE\n")
    print(f"Nodes: {net.graph.number_of_nodes()}")
    print(f"Roads: {net.graph.number_of_edges()}")
    print(f"Hospitals: {len(net.hospitals)}")
    print()
    print(f"Average travel time: {baseline_avg_time:.1f} min")
    print(f"Overloaded roads: {baseline_overloaded}")
    print("\n" + "-" * 32 + "\n")

    # pick the demo's known bottleneck: one of the 3 bridge roads
    bridge_edges = [e.edge_id for e in net.edges_by_id.values() if e.metadata.get("is_bridge")]
    failed_asset = bridge_edges[0]

    print("FAILURE\n")
    print(f"Failed asset: {failed_asset}")
    print("\n" + "-" * 32 + "\n")

    cascade = simulate_failure(net, od_pairs, [failed_asset])

    print("CASCADE\n")
    for step in cascade.steps:
        if step.iteration == 0:
            print(f"Step {step.iteration}:\n{failed_asset} failed\n")
            continue
        if step.newly_overloaded:
            print(f"Step {step.iteration}:\n{len(step.newly_overloaded)} roads overloaded\n")
        elif step.newly_stressed:
            print(f"Step {step.iteration}:\n{len(step.newly_stressed)} roads stressed\n")
        elif "stabilized" in step.label.lower():
            print(f"Step {step.iteration}:\nNetwork stabilized\n")
    print("-" * 32 + "\n")

    current_avg_time = avg_travel_time(net, od_pairs)
    impact = compute_impact(net, baseline_hospital_times, baseline_avg_time, current_avg_time)
    resilience = compute_resilience_score(impact, net)

    print("IMPACT\n")
    print(f"Population exposed: {impact.population_affected:,}")
    print(f"Average travel time: {impact.travel_time_increase_percent:+.0f}%")
    print(f"Healthcare accessibility: {-impact.healthcare_access_loss_percent:.0f}%")
    print(f"Cascade depth: {cascade.cascade_depth}")
    print()
    print("System resilience:")
    print(f"{baseline_resilience:.0f} -> {resilience:.0f}")


if __name__ == "__main__":
    main()
