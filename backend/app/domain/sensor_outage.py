"""UC10 HandleSensorDataOutage domain types."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SensorOutageResult:
    event_id: Optional[int]
    building_id: int
    affected_zone_ids: list
    decision: str  # 'fallback' | 'paused'
    notes: str
    degraded_forecast_zone_ids: list = field(default_factory=list)
    degraded_recommendation_ids: list = field(default_factory=list)
    elapsed_ms: float = 0.0
    declared_at: Optional[datetime] = None


class SensorOutageInputsMissing(Exception):
    def __init__(self, missing_inputs: list):
        self.missing_inputs = missing_inputs
        super().__init__(f"missing inputs: {missing_inputs}")


class SensorOutageForcedDbError(Exception):
    """Test lever for S11 — service raises mid-write."""
    pass
