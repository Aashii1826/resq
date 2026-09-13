# RESQ — Urban Cascading Infrastructure Failure & Resilience

> RESQ doesn't just tell planners what failed. It shows how failure
> propagates, identifies the infrastructure that matters most to the
> entire system, and determines where limited intervention can prevent
> the greatest downstream damage.

2-day hackathon prototype. MVP scope: road network (primary) + hospitals
(secondary) + population accessibility (impact layer). See `CONTRACTS.md`
for module interfaces between team members.

## Team split

| Person | Owns |
|---|---|
| **1 (foundation)** | Repo scaffold, models, synthetic + OSM data loaders, routing engine, OD demand & traffic assignment — **done, tested (11/11 passing)** |
| **2 (cascade & impact)** | `simulation/cascade.py`, `simulation/impact.py` — iterative failure propagation, hospital accessibility loss, resilience score |
| **3 (criticality & intervention & API)** | `simulation/criticality.py`, `simulation/interventions.py`, all FastAPI endpoints |
| **4 (frontend)** | React/Vite + MapLibre app: map, dashboard, cascade timeline, criticality panel, intervention planner |

## Quickstart (backend, what exists today)

```bash
cd backend
pip install -r requirements.txt --break-system-packages
PYTHONPATH=. python3 scripts/baseline_report.py   # proves graph->routing->demand works
PYTHONPATH=. python3 -m pytest tests/ -v          # 11 tests, all green
```

Sample output:

```
BASELINE

Nodes: 120
Roads: 394
Hospitals: 8
Population zones: 18

OD pairs simulated: 60 (unrouted: 0)
Average travel time (sampled OD routes): 4.6 min
Stressed roads: 2
Overloaded roads: 0
```

## Architecture

```
data (loader.py dispatches to synthetic_loader.py or osm_loader.py)
   ↓
models (Asset, RoadEdge, Network, Scenario, Intervention)
   ↓
simulation
   routing.py    ✅ done — shortest path, congestion-weighted
   demand.py     ✅ done — OD generation + capacity-restrained assignment
   cascade.py    ⬜ Person 2
   impact.py     ⬜ Person 2
   criticality.py ⬜ Person 3
   interventions.py ⬜ Person 3
   ↓
api/*.py        ⬜ Person 3 (FastAPI, 8 endpoints per spec Section 26)
   ↓
frontend/       ⬜ Person 4 (React + MapLibre)
```

## Data: real vs modelled

**Real/observed** (when using `mode="real"` OSM loading): road geometry,
junction locations, hospital locations.

**Modelled/assumed** (always, documented in `app/config.py`): road
capacities by type, OD travel demand, congestion multiplier curve,
resilience score weights, intervention costs. None of these are official
municipal traffic counts — they're illustrative prototype parameters,
intentionally centralized and easy to tune live during the demo.

## Demo network

Deterministic synthetic city (seed 42, always reproducible): two 8×7 grid
districts ("west"/"east") joined by exactly **3 bridge roads** — a
deliberate structural bottleneck, good for showing dramatic cascades. 120
nodes, 394 directed road edges (197 unique bidirectional segments), 8
hospitals, 18 population zones.
