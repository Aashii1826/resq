# RESQ — Architecture & Interfaces

The core engine (graph loading, routing, demand, capacity/utilization) is
built and tested. This is what cascade simulation, criticality ranking,
interventions, the API, and the frontend all build on top of.

## Run it

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
PYTHONPATH=. python3 scripts/baseline_report.py
PYTHONPATH=. python3 -m pytest tests/ -v
```

## What exists

- `app/config.py` — every tunable assumption lives here: capacities, the
  congestion curve, resilience weights per priority mode, cascade
  iteration limits. Change numbers here, not scattered through the codebase.
- `app/models/asset.py` — `Asset`, `AssetType`, `AssetStatus`, `PopulationZone`
- `app/models/network.py` — `RoadEdge`, `Network` (wraps a NetworkX DiGraph;
  never touch `network.graph` edge dicts directly, go through the typed
  methods below)
- `app/models/scenario.py` — `Scenario`, `ScenarioResult` (the standard
  shape every simulation run should return)
- `app/models/intervention.py` — `Intervention`, `InterventionType` (the
  shape to build the apply/evaluate/optimize logic against)
- `app/data/loader.py` — `load_network(mode="demo"|"real", area_name=..., bbox=...)`
  — always call this, never `synthetic_loader`/`osm_loader` directly, so
  the real→synthetic fallback actually works if OSM data is unavailable
- `app/simulation/routing.py` — `shortest_route(network, origin, destination) -> Route`,
  `nearest_hospital_route(network, origin) -> Optional[Route]`
- `app/simulation/demand.py` — `generate_od_pairs()`, `assign_demand()`,
  `compute_baseline()`

## Key Network methods

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

## Cascade pattern

The traffic assignment in `demand.py::assign_demand()` already IS a
capacity-restrained iterative loop (successive averages) — call it again
after `fail_edge()` to get the post-failure redistributed load. Reuse the
same `od_pairs` list across every cascade step; demand itself doesn't
change, only routing does, so there's no need to regenerate it.

```python
od_pairs, _ = compute_baseline(net)      # do this once, before any failure
net.fail_edge("R41")
stats = assign_demand(net, od_pairs, iterations=4)  # redistributes traffic
```

## Still to build

- `simulation/cascade.py` — the iterative failure→redistribution→
  restabilization loop (fail an asset, re-route, find newly overloaded
  edges, repeat until stable or max iterations, track cascade depth)
- `simulation/impact.py` — hospital accessibility loss, population
  exposure, resilience score (weights already live in
  `config.PRIORITY_MODE_WEIGHTS`, no need to invent them)
- `simulation/criticality.py` — systemic criticality ranking + comparison
  against standard graph centrality
- `simulation/interventions.py` — apply/evaluate/optimize logic for the
  three intervention types
- `api/*.py` — FastAPI app and endpoints (network, baseline, simulate,
  criticality, intervention evaluate/optimize, scenario compare)
- `frontend/` — the whole thing: map, dashboard, cascade timeline,
  criticality panel, intervention planner

## Demo network shape

Two 8×7 grids ("west" and "east" districts, ~112 junction nodes)
connected by only **3 bridge roads** — that's the deliberate structural
bottleneck. 8 hospitals, 18 population zones anchored to real junctions.
Seed 42 is fully deterministic — same graph, same OD pairs, same
everything, every run. Good target for a cascade demo: fail one of the 3
bridge edges and watch the other two absorb all cross-district traffic.

```python
>>> [e.edge_id for e in net.edges_by_id.values() if e.metadata.get("is_bridge")]
```