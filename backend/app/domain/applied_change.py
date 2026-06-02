from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class DispatchOutcome:
    """Outcome of a single DeviceControlAdapter.dispatch call."""

    status: str  # 'dispatched' | 'failed'
    error_code: Optional[str]
    adapter_message: str
    latency_ms: int


@dataclass
class AppliedChange:
    recommendation_id: int
    building_id: int
    zone_id: int
    applied_at: datetime
    setpoint_delta_f: Decimal
    status: str
    error_code: Optional[str]
    adapter_message: str
    latency_ms: int


@dataclass
class ApplyPlanRunResult:
    building_id: int
    applied_at: datetime
    elapsed_ms: float
    results: list[AppliedChange] = field(default_factory=list)


class ApplyInputsMissing(Exception):
    def __init__(self, missing_inputs: list[str]):
        self.missing_inputs = missing_inputs
        super().__init__(f"missing inputs: {missing_inputs}")


class ApplyForcedDbError(RuntimeError):
    """Raised by the test double to simulate an unrecoverable batch error."""
