"""
Central configuration for RESQ simulation assumptions.

Everything here is a PROTOTYPE ASSUMPTION, not an official/municipal figure.
Keep it in one place so it's easy to inspect, cite, and tune live during a demo.
"""

from dataclasses import dataclass, field
from typing import Dict


# ---------------------------------------------------------------------------
# Road capacities (vehicles/hour equivalent, illustrative only)
# ---------------------------------------------------------------------------
ROAD_TYPE_CAPACITY: Dict[str, int] = {
    "motorway": 5000,
    "trunk": 4000,
    "primary": 3000,
    "secondary": 2000,
    "tertiary": 1200,
    "residential": 600,
    "unclassified": 500,
}

# Free-flow speeds in km/h, used when OSM doesn't provide a speed tag
ROAD_TYPE_SPEED_KPH: Dict[str, int] = {
    "motorway": 80,
    "trunk": 60,
    "primary": 50,
    "secondary": 40,
    "tertiary": 30,
    "residential": 25,
    "unclassified": 25,
}

# Per-lane capacity bump when lane count is known (multiplier per extra lane
# beyond 1), applied on top of the base ROAD_TYPE_CAPACITY.
CAPACITY_PER_EXTRA_LANE_MULTIPLIER: float = 0.6


# ---------------------------------------------------------------------------
# Congestion state thresholds
# ---------------------------------------------------------------------------
STRESSED_UTILIZATION: float = 0.80
OVERLOADED_UTILIZATION: float = 1.00


def congestion_multiplier(utilization: float) -> float:
    """
    Maps utilization -> travel-time multiplier.
    Piecewise linear, matches the brief's example function.
    Kept as a pure function so simulation/cascade code can swap it out.
    """
    if utilization <= STRESSED_UTILIZATION:
        return 1.0
    elif utilization <= OVERLOADED_UTILIZATION:
        return 1.0 + 1.5 * (utilization - STRESSED_UTILIZATION)
    else:
        return 1.3 + 3.0 * (utilization - OVERLOADED_UTILIZATION)


# ---------------------------------------------------------------------------
# Cascade / simulation loop parameters
# ---------------------------------------------------------------------------
@dataclass
class CascadeParams:
    max_iterations: int = 8
    # stop early if the max change in any edge's utilization is below this
    convergence_epsilon: float = 0.01


# ---------------------------------------------------------------------------
# Resilience score weighting (Section 18) - prototype assumption, documented
# ---------------------------------------------------------------------------
@dataclass
class ResilienceWeights:
    accessibility: float = 0.30
    travel: float = 0.25
    population: float = 0.25
    network: float = 0.20


PRIORITY_MODE_WEIGHTS: Dict[str, ResilienceWeights] = {
    "balanced": ResilienceWeights(0.30, 0.25, 0.25, 0.20),
    "emergency_access": ResilienceWeights(0.50, 0.15, 0.20, 0.15),
    "population_protection": ResilienceWeights(0.20, 0.15, 0.50, 0.15),
    "mobility": ResilienceWeights(0.15, 0.55, 0.10, 0.20),
}


# ---------------------------------------------------------------------------
# Population impact threshold (Section 17)
# ---------------------------------------------------------------------------
ACCESSIBILITY_DETERIORATION_THRESHOLD_PCT: float = 20.0

# Random seed used everywhere for determinism (demo mode must be reproducible)
DEMO_SEED: int = 42
