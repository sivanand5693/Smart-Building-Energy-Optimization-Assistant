"""UC8 ExplainRecommendation domain types."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class ExplanationInputs:
    """Bundle of context the ExplanationAdapter needs to produce text."""

    recommendation_id: int
    zone_id: int
    zone_name: str
    projected_savings_kwh: Decimal
    comfort_impact: str
    setpoint_delta_f: Decimal
    occupancy_count: int
    occupancy_timestamp: Optional[datetime]
    predicted_kwh: Decimal
    occupied_min_f: Decimal
    occupied_max_f: Decimal


@dataclass
class ExplanationResult:
    recommendation_id: int
    text: str
    factors: dict
    cached: bool
    elapsed_ms: float
    model_version: str
    generated_at: Optional[datetime] = None


class ExplanationInputsMissing(Exception):
    def __init__(self, missing_inputs: list):
        self.missing_inputs = missing_inputs
        super().__init__(f"missing inputs: {missing_inputs}")


class ExplanationForcedDbError(Exception):
    """Test lever for S14 — service raises mid-write so the transaction rolls back."""
    pass
