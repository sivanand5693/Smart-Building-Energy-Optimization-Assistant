from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class Candidate:
    """Output of the OptimizationAdapter for a single zone."""

    setpoint_delta_f: Decimal
    projected_savings_kwh: Decimal
    comfort_impact: str  # one of 'none', 'minor', 'moderate'
    model_version: str


@dataclass
class RankedRecommendation:
    building_id: int
    zone_id: int
    zone_name: str
    run_timestamp: datetime
    setpoint_delta_f: Decimal
    projected_savings_kwh: Decimal
    comfort_impact: str
    rank: int
    model_version: str


@dataclass
class RecommendationRunResult:
    building_id: int
    run_timestamp: datetime
    elapsed_ms: float
    recommendations: list[RankedRecommendation] = field(default_factory=list)


class RecommendationInputsMissing(Exception):
    def __init__(self, missing_inputs: list[str]):
        self.missing_inputs = missing_inputs
        super().__init__(f"missing inputs: {missing_inputs}")
