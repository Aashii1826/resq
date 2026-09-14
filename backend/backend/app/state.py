"""
Simple in-memory application state.

For a 2-day hackathon prototype, one shared demo Network loaded at startup
is enough - no database needed (Section 3: avoid Postgres unless
necessary). Every request works against this same network instance;
/simulate and friends operate on isolated deep copies so concurrent
requests don't corrupt each other's what-if state.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.models.network import Network
from app.simulation.demand import ODDemand, compute_baseline
from app.simulation.impact import compute_baseline_hospital_times
from app.simulation.criticality import _avg_travel_time


@dataclass
class AppState:
    network: Network
    od_pairs: List[ODDemand]
    baseline_hospital_times: Dict[str, float]
    baseline_avg_time: float
    baseline_resilience: float = 100.0


_state: Optional[AppState] = None


def init_state(mode: str = "demo") -> AppState:
    global _state
    from app.data.loader import load_network

    network = load_network(mode=mode)
    od_pairs, _stats = compute_baseline(network, num_pairs=60, iterations=4)
    hospital_times = compute_baseline_hospital_times(network)
    avg_time = _avg_travel_time(network, od_pairs)

    _state = AppState(
        network=network,
        od_pairs=od_pairs,
        baseline_hospital_times=hospital_times,
        baseline_avg_time=avg_time,
        baseline_resilience=100.0,
    )
    return _state


def get_state() -> AppState:
    if _state is None:
        return init_state()
    return _state
