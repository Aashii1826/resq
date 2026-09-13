# RESQ — Interfaces from Person 1 (Foundation layer)

Status: **P0.1–P0.4 done and tested** (graph loading, routing, demand,
capacity/utilization). This is what the rest of the team builds on.

Run it yourself:
```bash
cd backend
pip install -r requirements.txt --break-system-packages
PYTHONPATH=. python3 scripts/baseline_report.py
PYTHONPATH=. python3 -m pytest tests/ -v
```

## What exists

- `app/config.py` — every tunable assumption (capacities, congestion curve,
  resilience weights per priority mode, cascade iteration limits). **Change
  numbers here, not scattered through the codebase.**
- `app/models/asset.py` — `Asset`, `AssetType`, `AssetStatus`, `PopulationZone`
- `app/models/network.py` — `RoadEdge`, `Network` (wraps a NetworkX DiGraph;
  never touch `network.graph` edge dicts directly, go through the typed
  methods below)
- `app/models/scenario.py` — `Scenario`, `ScenarioResult` (the standard
  shape every simulation run should return — matches API section 26)
- `app/models/intervention.py` — `Intervention`, `InterventionType` (stub
  shape for Person 3 to implement apply/evaluate logic against)
- `app/data/loader.py` — `load_network(mode="demo"|"real", area_name=..., bbox=...)`
  — **always call this**, never `synthetic_loader`/`osm_loader` directly, so
  the real→synthetic fallback (Section 35) actually works
- `app/simulation/routing.py` — `shortest_route(network, origin, destination) -> Route`,
  `nearest_hospital_route(network, origin) -> Optional[Route]`
- `app/simulation/demand.py` — `generate_od_pairs()`, `assign_demand()`,
  `compute_baseline()`

## Key Network methods you'll use

```python
net = load_network(mode="demo")          # deterministic 120-node city
net.fail_edge(edge_id)                   # sets status=FAILED, load=0
net.fail_junction(node_id)               # fails all incident edges, returns list of edge_ids
net.refresh_weights()                    # MUST call after any status/load change,
                                          # before routing again (recomputes travel_time)
net.restore_all()                        # reset all edges to HEALTHY for a fresh run
net.to_geojson()                         # FeatureCollection for the frontend map
net.summary()                            # {nodes, roads, hospitals, zones, source}
edge = net.get_edge(edge_id)             # RoadEdge, has .utilization / .status / .travel_time
```

**Important pattern for Person 2 (cascade engine):** the assignment in
`demand.py::assign_demand()` already IS a capacity-restrained iterative
loop (successive averages) — you can call it again after `fail_edge()` to
get the post-failure redistributed load. Re-run it each cascade step with
the same `od_pairs` list (don't regenerate OD pairs mid-cascade — demand
itself doesn't change, only routing does).

```python
od_pairs, _ = compute_baseline(net)      # do this once, before any failure
net.fail_edge("R41")
stats = assign_demand(net, od_pairs, iterations=4)  # redistributes traffic
```

## What's deliberately NOT here (yours to build)

- **Person 2 — done, see below.**
- **Person 3**: `simulation/criticality.py`, `simulation/interventions.py`,
  all of `api/*.py` (FastAPI app + the 8 endpoints from Section 26)
- **Person 4**: entire `frontend/`

---

## Interfaces from Person 2 (Cascade & Impact layer)

Status: **cascade.py + impact.py done and tested** (13 new tests, all
passing alongside Person 1's 11). This is what Person 3's criticality
ranking and intervention optimizer are built on top of.

Run it yourself:
```bash
cd backend
PYTHONPATH=. python3 scripts/cascade_report.py
PYTHONPATH=. python3 -m pytest tests/ -v
```

### `app/simulation/cascade.py`

```python
from app.simulation.cascade import simulate_failure, reset_and_rebaseline

result = simulate_failure(net, ["R389"], od_pairs)   # net + od_pairs from
                                                       # compute_baseline()
result.cascade_depth            # int - how many hops the disruption propagated
result.stabilized               # bool
result.final_overloaded_edges   # List[str]
result.final_failed_edges       # List[str]
result.unreachable_hospital_zones  # List[str] - zones fully cut off
result.timeline                 # List[CascadeStepState] - one per iteration,
                                 # drives the frontend cascade timeline (Section 30)
result.to_dict()                # JSON-ready

# IMPORTANT: simulate_failure() mutates `net` in place (fails edges,
# reassigns load). To run another scenario on the SAME network object:
reset_and_rebaseline(net, od_pairs)   # restores HEALTHY + re-assigns baseline load
```

For Person 3's criticality scan (many failures against the same network)
and intervention before/after comparisons: call `reset_and_rebaseline()`
between runs, or just call `load_network(mode="demo")` fresh each time if
you'd rather not deal with mutation at all - both are cheap at this scale
(120 nodes / ~400 edges).

### `app/simulation/impact.py`

```python
from app.simulation.impact import capture_baseline_snapshot, evaluate_impact

# ONCE, right after compute_baseline(), before any failures:
snapshot = capture_baseline_snapshot(net, od_pairs)
# snapshot.access               Dict[zone_id, ZoneAccessibility] (baseline)
# snapshot.avg_travel_time      float, minutes
# snapshot.resilience_score     float, ~100 on a healthy network

# after simulate_failure():
report = evaluate_impact(
    network=net, od_pairs=od_pairs,
    baseline_access=snapshot.access,
    baseline_avg_travel_time=snapshot.avg_travel_time,
    baseline_resilience_score=snapshot.resilience_score,
    cascade_result=result,
    priority_mode="balanced",   # or "emergency_access" / "population_protection" / "mobility"
)
report.resilience_score                 # 0-100
report.population_affected              # int - Section 17 "Simulated population exposure"
report.travel_time_increase_percent
report.healthcare_access_loss_percent
report.cascade_depth
report.overloaded_edges
report.accessibility                    # AccessibilityImpact - per-zone detail for the map/panels
report.resilience_breakdown             # ResilienceBreakdown - per-component scores (Section 18)
report.timeline                         # same as cascade result, JSON-ready
report.to_dict()                        # matches models/scenario.py::ScenarioResult shape,
                                         # ready to drop straight into a /simulate response
```

**Pattern for Person 3 (criticality + interventions):** for a criticality
scan, run `capture_baseline_snapshot()` once, then for each candidate
asset: `reset_and_rebaseline()` -> `simulate_failure([asset_id], od_pairs)`
-> `evaluate_impact(...)` -> read `report.resilience_score` (lower =
more critical) or build your own weighted criticality formula from
`report.accessibility`, `report.cascade_depth`, `report.overloaded_edges`,
etc. (Section 19's metric list). For intervention before/after (Section
23): snapshot once, run the SAME failure with and without the intervention
applied to the network first, and diff the two `report.resilience_score`
values.

## Demo network shape (so you can design around it)

Two 8×7 grids ("west" and "east" districts, ~112 junction nodes) connected
by **only 3 bridge roads** — that's the deliberate structural bottleneck.
8 hospitals, 18 population zones anchored to real junctions. Seed 42 is
fully deterministic — same graph, same OD pairs, same everything, every run.
Good bottleneck test target for a cascade demo: fail one of the 3 bridge
edges and watch the other two absorb all cross-district traffic.

```python
>>> [e.edge_id for e in net.edges_by_id.values() if e.metadata.get("is_bridge")]
```
