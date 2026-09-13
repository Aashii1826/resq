"""
Intervention model - Section 22. Three types only for the MVP.

Person 3 owns simulation/interventions.py (the actual apply/evaluate/
optimize logic). This file just defines the shared data shape so other
modules (API, frontend contracts) can be written against it now.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class InterventionType(str, Enum):
    CAPACITY_UPGRADE = "CAPACITY_UPGRADE"
    ALTERNATE_ROUTE = "ALTERNATE_ROUTE"
    SERVICE_ACCESS_IMPROVEMENT = "SERVICE_ACCESS_IMPROVEMENT"


@dataclass
class Intervention:
    intervention_id: str
    type: InterventionType
    name: str
    cost: float
    # what it targets - meaning depends on `type`:
    #   CAPACITY_UPGRADE: target_edge_id, params={"multiplier": 1.3}
    #   ALTERNATE_ROUTE: params={"source": node_id, "target": node_id, "road_type": "secondary"}
    #   SERVICE_ACCESS_IMPROVEMENT: target_hospital_id, params={"travel_time_reduction_pct": 20}
    target_edge_id: Optional[str] = None
    target_hospital_id: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "type": self.type.value,
            "name": self.name,
            "cost": self.cost,
            "target_edge_id": self.target_edge_id,
            "target_hospital_id": self.target_hospital_id,
            "params": self.params,
        }
