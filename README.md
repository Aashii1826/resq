# RESQ

**When one piece of a city breaks, what happens to everything connected to it?**

RESQ is a decision-support tool for urban resilience planning. Roads, hospitals, and the people who depend on them are all connected — a single road closure doesn't just cause a detour, it can overload other roads, cut off ambulance routes, and leave entire neighborhoods without fast access to care. Most infrastructure monitoring looks at assets one at a time. RESQ looks at the whole chain reaction.

Built for [hackathon name] in 2 days.

## What it does

Pick a road on the map, fail it, and watch what happens:
- Traffic reroutes in real time through the network
- Nearby roads get overloaded as they absorb the extra load
- Hospital accessibility for surrounding neighborhoods degrades
- The system tells you exactly how much worse things got — not just that they did

Then it goes a step further: RESQ ranks every road and junction by how much damage its failure would actually cause (not just how "connected" it looks on paper), and recommends where to spend a limited resilience budget for the biggest possible improvement.

**The core insight:** a road that looks unimportant by traditional network metrics can be the single most damaging point of failure in the whole system — because failure impact depends on the whole cascade, not just how many roads connect to it.

## How it works

```
MAP → BREAK → PROPAGATE → MEASURE → RANK → INTERVENE → COMPARE
```

1. A road network is simulated with realistic traffic demand and capacity
2. Failing a road triggers an iterative cascade — traffic redistributes, new bottlenecks form, the network keeps adjusting until it settles
3. Impact is measured in concrete terms: population affected, travel time increase, hospital access loss
4. Every road/junction gets a systemic criticality score, compared against standard graph centrality
5. Candidate interventions (capacity upgrades, alternate routes, better hospital access) get tested by actually re-running the simulation, not guessed
6. A budget-constrained optimizer finds the intervention combo with the biggest resilience payoff

## Team

| Person | Working on |
|---|---|
| 1 | Core engine — city graph, routing, traffic simulation |
| 2 | Cascade propagation + impact scoring |
| 3 | Criticality ranking + intervention optimizer + API |
| 4 | Frontend — map, dashboard, timeline |

See `CONTRACTS.md` for how the pieces fit together.

## Running it

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
PYTHONPATH=. python3 scripts/baseline_report.py
```

You should see something like:

```
BASELINE
Nodes: 120   Roads: 394   Hospitals: 8
Stressed roads: 2   Overloaded roads: 0
```

That confirms the simulation engine is working end to end — city generated, traffic simulated, everything measurable.

Run the tests:
```bash
PYTHONPATH=. python3 -m pytest tests/ -v
```

## The demo city

A synthetic urban network, generated the same way every time (so the live demo never breaks): two neighborhoods connected by just **3 bridge roads** — a deliberate chokepoint that makes for a dramatic, obvious cascade when one of them fails. 120 junctions, 8 hospitals, 18 population zones.

## A note on the numbers

Real road geometry and hospital/facility locations come from OpenStreetMap when available. Traffic demand, road capacity assumptions, congestion behavior, and intervention costs are **modelled, not measured** — they're documented, configurable prototype parameters (see `app/config.py`), not official traffic counts. We say this clearly in the UI too. Nothing here should be read as real municipal data.
