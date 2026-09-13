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

- **Person 2**: `simulation/cascade.py` (the step 1–10 iteration loop from
  Section 13, cascade depth tracking per Section 14), `simulation/impact.py`
  (hospital accessibility loss, population exposure, resilience score —
  weights already live in `config.PRIORITY_MODE_WEIGHTS`)
- **Person 3**: `simulation/criticality.py`, `simulation/interventions.py`,
  all of `api/*.py` (FastAPI app + the 8 endpoints from Section 26)
- **Person 4**: entire `frontend/`

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
