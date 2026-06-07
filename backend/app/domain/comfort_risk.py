from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class ComfortRiskAlert:
    zone_id: int
    zone_name: str
    projected_temp_f: Decimal
    occupied_min_f: Decimal
    occupied_max_f: Decimal
    risk_score: Decimal
    direction: str  # 'above' | 'below'
    mitigation: str


@dataclass
class ComfortRiskRunResult:
    building_id: int
    decision: str  # 'alert' | 'pass'
    alerts_count: int
    source_run_timestamp: Optional[datetime]
    elapsed_ms: float
    alerts: list[ComfortRiskAlert] = field(default_factory=list)
    run_at: Optional[datetime] = None


class ComfortRiskInputsMissing(Exception):
    def __init__(self, missing_inputs: list[str]):
        self.missing_inputs = missing_inputs
        super().__init__(f"missing inputs: {missing_inputs}")


class ComfortRiskForcedDbError(Exception):
    """Test lever for S14 — service raises mid-write so the transaction rolls back."""
    pass
