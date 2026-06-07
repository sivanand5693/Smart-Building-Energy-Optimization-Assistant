"""UC9 GenerateDailySavingsReport service (control)."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.domain.savings_report import (
    DailySavingsReportLine,
    DailySavingsReportResult,
    SavingsForcedDbError,
    SavingsInputsMissing,
)
from app.infrastructure.models import (
    BuildingModel,
    DailySavingsReportLineModel,
    DailySavingsReportModel,
)
from app.infrastructure.repositories.energy_usage_repository import (
    EnergyUsageRepository,
)
from app.infrastructure.repositories.savings_report_repository import (
    SavingsReportRepository,
)


logger = logging.getLogger(__name__)


# -- Anomaly thresholds (A1) -------------------------------------------------

SAVINGS_OVER_CONSUMPTION_RATIO = Decimal("1.10")
SAVINGS_SUSPICIOUS_LOW_RATIO = Decimal("0.5")


# -- Test lever (S14) --------------------------------------------------------

_FORCE_DB_ERROR_NEXT_REQUEST = False


def force_db_error_next_request() -> None:
    global _FORCE_DB_ERROR_NEXT_REQUEST
    _FORCE_DB_ERROR_NEXT_REQUEST = True


def _consume_force_db_error() -> bool:
    global _FORCE_DB_ERROR_NEXT_REQUEST
    flag = _FORCE_DB_ERROR_NEXT_REQUEST
    _FORCE_DB_ERROR_NEXT_REQUEST = False
    return flag


# -- Helpers -----------------------------------------------------------------

_KWH_Q = Decimal("0.001")
_PCT_Q = Decimal("0.01")
_PCT_MAX = Decimal("100.00")
_PCT_MIN = Decimal("-100.00")


def _q_kwh(v: Decimal) -> Decimal:
    return v.quantize(_KWH_Q, rounding=ROUND_HALF_UP)


def _q_pct(v: Decimal) -> Decimal:
    pct = v.quantize(_PCT_Q, rounding=ROUND_HALF_UP)
    if pct > _PCT_MAX:
        return _PCT_MAX
    if pct < _PCT_MIN:
        return _PCT_MIN
    return pct


def _savings_pct(baseline: Decimal, actual: Decimal) -> Decimal:
    if baseline == 0:
        return Decimal("0.00")
    return _q_pct((baseline - actual) / baseline * Decimal("100"))


def _classify_anomaly(
    baseline: Decimal, actual: Decimal
) -> tuple[bool, str | None]:
    if baseline <= 0:
        return (False, None)
    if actual > baseline * SAVINGS_OVER_CONSUMPTION_RATIO:
        return (True, "over_consumption")
    if actual < baseline * SAVINGS_SUSPICIOUS_LOW_RATIO:
        return (True, "suspicious_low")
    return (False, None)


# -- Service ------------------------------------------------------------------


class ReportingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SavingsReportRepository(db)
        self.usage_repo = EnergyUsageRepository(db)

    def generate(
        self, building_id: int, report_date_str: str
    ) -> DailySavingsReportResult:
        start = time.perf_counter()
        try:
            return self._generate_inner(building_id, report_date_str, start)
        except SavingsInputsMissing:
            self.db.rollback()
            raise
        except SavingsForcedDbError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def _generate_inner(
        self, building_id: int, report_date_str: str, start: float
    ) -> DailySavingsReportResult:
        # 1. Parse date
        try:
            report_date = date.fromisoformat(report_date_str)
        except (ValueError, TypeError):
            raise SavingsInputsMissing(["report_date"])

        # 2. Building
        building = self.db.get(BuildingModel, building_id)
        if building is None:
            raise SavingsInputsMissing(["building"])

        zones = list(building.zones)
        if not zones:
            # No zones means we can never have baseline+actual — surface as
            # missing baseline + actual. (Out of scope for the 17 scenarios
            # but defensively correct.)
            raise SavingsInputsMissing(["actual", "baseline"])

        # 3. Cache check
        existing = self.repo.get_for_building_date(building_id, report_date)
        if existing is not None:
            lines = self.repo.lines_for_report(existing.id)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return DailySavingsReportResult(
                report_id=existing.id,
                building_id=existing.building_id,
                report_date=existing.report_date,
                total_baseline_kwh=existing.total_baseline_kwh,
                total_actual_kwh=existing.total_actual_kwh,
                total_savings_kwh=existing.total_savings_kwh,
                total_savings_pct=existing.total_savings_pct,
                lines=[
                    DailySavingsReportLine(
                        zone_id=ln.zone_id,
                        baseline_kwh=ln.baseline_kwh,
                        actual_kwh=ln.actual_kwh,
                        savings_kwh=ln.savings_kwh,
                        savings_pct=ln.savings_pct,
                        anomaly_flag=bool(ln.anomaly_flag),
                        anomaly_reason=ln.anomaly_reason,
                    )
                    for ln in lines
                ],
                cached=True,
                elapsed_ms=elapsed_ms,
                generated_at=existing.generated_at,
            )

        # 4. Probe baseline + actual rows per zone
        rows = self.usage_repo.for_building_date(building_id, report_date)
        # Index by (zone_id, kind)
        by_zone_kind: dict[tuple[int, str], Decimal] = {}
        for r in rows:
            by_zone_kind[(r.zone_id, r.kind)] = Decimal(r.kwh)

        missing_set: set[str] = set()
        for z in zones:
            if (z.id, "baseline") not in by_zone_kind:
                missing_set.add("baseline")
            if (z.id, "actual") not in by_zone_kind:
                missing_set.add("actual")
        if missing_set:
            raise SavingsInputsMissing(sorted(missing_set))

        # 5. Compute lines + totals
        line_domains: list[DailySavingsReportLine] = []
        total_baseline = Decimal("0")
        total_actual = Decimal("0")
        for z in zones:
            baseline = by_zone_kind[(z.id, "baseline")]
            actual = by_zone_kind[(z.id, "actual")]
            savings = _q_kwh(baseline - actual)
            pct = _savings_pct(baseline, actual)
            anomaly_flag, anomaly_reason = _classify_anomaly(baseline, actual)
            line_domains.append(
                DailySavingsReportLine(
                    zone_id=z.id,
                    baseline_kwh=_q_kwh(baseline),
                    actual_kwh=_q_kwh(actual),
                    savings_kwh=savings,
                    savings_pct=pct,
                    anomaly_flag=anomaly_flag,
                    anomaly_reason=anomaly_reason,
                )
            )
            total_baseline += baseline
            total_actual += actual

        total_baseline_q = _q_kwh(total_baseline)
        total_actual_q = _q_kwh(total_actual)
        total_savings_q = _q_kwh(total_baseline - total_actual)
        total_pct = _savings_pct(total_baseline, total_actual)

        # 6. Forced DB error lever
        if _consume_force_db_error():
            raise SavingsForcedDbError("forced_db_error_for_test")

        # 7. Persist
        elapsed_ms_int = int((time.perf_counter() - start) * 1000.0)
        generated_at = datetime.now(timezone.utc)
        header = DailySavingsReportModel(
            building_id=building_id,
            report_date=report_date,
            generated_at=generated_at,
            total_baseline_kwh=total_baseline_q,
            total_actual_kwh=total_actual_q,
            total_savings_kwh=total_savings_q,
            total_savings_pct=total_pct,
            elapsed_ms=elapsed_ms_int,
        )
        line_models = [
            DailySavingsReportLineModel(
                zone_id=ln.zone_id,
                baseline_kwh=ln.baseline_kwh,
                actual_kwh=ln.actual_kwh,
                savings_kwh=ln.savings_kwh,
                savings_pct=ln.savings_pct,
                anomaly_flag=ln.anomaly_flag,
                anomaly_reason=ln.anomaly_reason,
            )
            for ln in line_domains
        ]
        self.repo.save_no_commit(header, line_models)
        self.db.commit()

        logger.info(
            "savings_report_generated building_id=%s report_date=%s lines=%d",
            building_id,
            report_date.isoformat(),
            len(line_models),
        )

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return DailySavingsReportResult(
            report_id=header.id,
            building_id=building_id,
            report_date=report_date,
            total_baseline_kwh=total_baseline_q,
            total_actual_kwh=total_actual_q,
            total_savings_kwh=total_savings_q,
            total_savings_pct=total_pct,
            lines=line_domains,
            cached=False,
            elapsed_ms=elapsed_ms,
            generated_at=generated_at,
        )
