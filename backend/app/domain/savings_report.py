"""UC9 GenerateDailySavingsReport domain types."""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class DailySavingsReportLine:
    zone_id: int
    baseline_kwh: Decimal
    actual_kwh: Decimal
    savings_kwh: Decimal
    savings_pct: Decimal
    anomaly_flag: bool
    anomaly_reason: Optional[str] = None


@dataclass
class DailySavingsReportResult:
    report_id: Optional[int]
    building_id: int
    report_date: date
    total_baseline_kwh: Decimal
    total_actual_kwh: Decimal
    total_savings_kwh: Decimal
    total_savings_pct: Decimal
    lines: list = field(default_factory=list)
    cached: bool = False
    elapsed_ms: float = 0.0
    generated_at: Optional[datetime] = None


class SavingsInputsMissing(Exception):
    def __init__(self, missing_inputs: list):
        self.missing_inputs = missing_inputs
        super().__init__(f"missing inputs: {missing_inputs}")


class SavingsForcedDbError(Exception):
    """Test lever for S14 — service raises mid-write so the transaction rolls back."""
    pass
