"""
Generic infrastructure asset model.

This is intentionally generic (Section 39 - Extensibility) so that later
infra types (POWER, WATER, FIRE STATIONS, TRANSIT, TELECOM...) can reuse
the same shape without touching the simulation engine.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class AssetType(str, Enum):
    ROAD = "ROAD"
    JUNCTION = "JUNCTION"
    HOSPITAL = "HOSPITAL"
    EMERGENCY = "EMERGENCY"
    UTILITY = "UTILITY"


class AssetStatus(str, Enum):
    HEALTHY = "HEALTHY"
    STRESSED = "STRESSED"
    OVERLOADED = "OVERLOADED"
    FAILED = "FAILED"


@dataclass
class Asset:
    id: str
    type: AssetType
    name: str
    latitude: float
    longitude: float
    capacity: float = 0.0
    baseline_load: float = 0.0
    current_load: float = 0.0
    status: AssetStatus = AssetStatus.HEALTHY
    criticality: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def utilization(self) -> float:
        if self.capacity <= 0:
            return 0.0
        return self.current_load / self.capacity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "capacity": self.capacity,
            "baseline_load": self.baseline_load,
            "current_load": self.current_load,
            "utilization": round(self.utilization, 4),
            "status": self.status.value,
            "criticality": self.criticality,
            "metadata": self.metadata,
        }


@dataclass
class PopulationZone:
    """A demand/population zone used for OD demand and accessibility impact."""
    zone_id: str
    latitude: float
    longitude: float
    population: int
    # nearest graph node id this zone connects into the network at
    anchor_node: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "population": self.population,
            "anchor_node": self.anchor_node,
        }
