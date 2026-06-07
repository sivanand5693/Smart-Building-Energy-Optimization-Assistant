from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.recommendation import RankedRecommendation


@dataclass
class OccupancyChange:
    zone_id: int
    new_occupancy_count: int


@dataclass
class AdaptDecision:
    id: int
    building_id: int
    decision: str
    reason: str
    active_plan_run_timestamp: datetime
    new_run_timestamp: Optional[datetime]
    changed_zone_ids: list[int]
    requested_at: datetime
    elapsed_ms: int


@dataclass
class AdaptPlanResult:
    building_id: int
    decision: str
    reason: str
    active_plan_run_timestamp: datetime
    new_run_timestamp: Optional[datetime]
    changed_zone_ids: list[int]
    requested_at: datetime
    elapsed_ms: float
    revised_recommendations: list[RankedRecommendation] = field(default_factory=list)


class AdaptInputsMissing(Exception):
    def __init__(self, missing_inputs: list[str]):
        self.missing_inputs = missing_inputs
        super().__init__(f"missing inputs: {missing_inputs}")
