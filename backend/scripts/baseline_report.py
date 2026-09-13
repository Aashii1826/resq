"""
Run: PYTHONPATH=. python3 scripts/baseline_report.py

Produces the BASELINE portion of the Section 43 milestone report, proving
graph loading -> routing -> demand -> utilization works end to end.
(Failure/cascade sections will be added by Person 2's cascade engine.)
"""

from app.data.loader import load_network
from app.simulation.demand import compute_baseline
from app.simulation.routing import shortest_route, NoRouteError


def main():
    net = load_network(mode="demo")
    od_pairs, stats = compute_baseline(net, num_pairs=60, iterations=4)

    avg_travel_time = _avg_travel_time_over_sample(net, od_pairs)

    print("BASELINE\n")
    print(f"Nodes: {net.graph.number_of_nodes()}")
    print(f"Roads: {net.graph.number_of_edges()}")
    print(f"Hospitals: {len(net.hospitals)}")
    print(f"Population zones: {len(net.zones)}")
    print()
    print(f"OD pairs simulated: {stats['od_pairs']} (unrouted: {stats['unrouted_pairs']})")
    print(f"Average travel time (sampled OD routes): {avg_travel_time:.1f} min")
    print(f"Stressed roads: {stats['stressed_edges']}")
    print(f"Overloaded roads: {stats['overloaded_edges']}")
    print()

    # show the 5 highest-utilization edges - a sanity check that the bridge
    # roads (the deliberate bottleneck) show up near the top
    top = sorted(net.edges_by_id.values(), key=lambda e: e.utilization, reverse=True)[:5]
    print("Top utilization roads:")
    for e in top:
        print(
            f"  {e.edge_id:6s} {e.source:>10s} -> {e.target:<10s} "
            f"type={e.road_type:<10s} util={e.utilization:5.2f} status={e.status.value}"
        )


def _avg_travel_time_over_sample(net, od_pairs, sample=25):
    times = []
    for od in od_pairs[:sample]:
        try:
            r = shortest_route(net, od.origin, od.destination)
            times.append(r.travel_time)
        except NoRouteError:
            continue
    return sum(times) / len(times) if times else 0.0


if __name__ == "__main__":
    main()
