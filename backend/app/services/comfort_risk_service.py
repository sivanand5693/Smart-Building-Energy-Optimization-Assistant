"""UC7 DetectComfortViolationRisk service (control)."""
import logging
import time
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.domain.comfort_risk import (
    ComfortRiskAlert,
    ComfortRiskForcedDbError,
    ComfortRiskInputsMissing,
    ComfortRiskRunResult,
)
from app.infrastructure.adapters.forecast_adapters import registry as adapter_registry
from app.infrastructure.models import (
    BuildingModel,
    ComfortRiskAlertModel,
    ComfortRiskRunModel,
)
from app.infrastructure.repositories.comfort_risk_repository import (
    ComfortRiskRepository,
)
from app.infrastructure.repositories.recommendation_repository import (
    SetpointRecommendationRepository,
    ZoneComfortConstraintRepository,
)


logger = logging.getLogger(__name__)

COMFORT_RISK_THRESHOLD = Decimal("0.5")
_HALF = Decimal("0.5")
_RISK_QUANT = Decimal("0.001")
_TEMP_QUANT = Decimal("0.01")


# -- Test lever (S14) --------------------------------------------------------

_FORCE_DB_ERROR_NEXT_RUN = False


def force_db_error_next_run() -> None:
    global _FORCE_DB_ERROR_NEXT_RUN
    _FORCE_DB_ERROR_NEXT_RUN = True


def _consume_force_db_error() -> bool:
    global _FORCE_DB_ERROR_NEXT_RUN
    flag = _FORCE_DB_ERROR_NEXT_RUN
    _FORCE_DB_ERROR_NEXT_RUN = False
    return flag


def _round_half(value: Decimal) -> Decimal:
    """Round to nearest 0.5 using half-up."""
    return (value / _HALF).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * _HALF


def _format_half(value: Decimal) -> str:
    """Format a half-increment Decimal as e.g. '3.0' / '3.5'."""
    rounded = value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded:.1f}"


class ComfortRiskService:
    def __init__(self, db: Session):
        self.db = db
        self.rec_repo = SetpointRecommendationRepository(db)
        self.constraint_repo = ZoneComfortConstraintRepository(db)
        self.risk_repo = ComfortRiskRepository(db)

    def run(self, building_id: int) -> ComfortRiskRunResult:
        start = time.perf_counter()
        run_at = datetime.now(timezone.utc)

        try:
            return self._run_inner(building_id, start, run_at)
        except ComfortRiskInputsMissing:
            self.db.rollback()
            raise
        except ComfortRiskForcedDbError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def _run_inner(
        self,
        building_id: int,
        start: float,
        run_at: datetime,
    ) -> ComfortRiskRunResult:
        # 1. Building
        building = self.db.get(BuildingModel, building_id)
        if building is None:
            raise ComfortRiskInputsMissing(["building"])

        # 2. Active-or-proposed plan timestamp (A3)
        active_ts = self.rec_repo.latest_run_timestamp_for_building(building_id)
        if active_ts is None:
            raise ComfortRiskInputsMissing(["plan"])

        # 3. Snapshot delta per zone in the latest run
        rows = self.rec_repo.latest_rows_for_building(building_id, active_ts)
        delta_by_zone: dict[int, Decimal] = {
            r.zone_id: Decimal(r.setpoint_delta_f) for r in rows
        }

        # 4. Evaluate each zone in zone_id ASC order
        zones = sorted(list(building.zones), key=lambda z: z.id)
        alerts: list[ComfortRiskAlert] = []
        evaluable_zones = 0  # zones with delta + device_state present
        constraint_present = 0  # zones with comfort constraint present

        for z in zones:
            delta = delta_by_zone.get(z.id)
            if delta is None:
                continue
            state = adapter_registry.device_state.current_for_zone(z.id)
            if state is None or "setpoint_f" not in state:
                continue
            evaluable_zones += 1
            constraint = self.constraint_repo.for_zone(z.id)
            if constraint is None:
                continue
            constraint_present += 1

            current_setpoint = Decimal(str(state["setpoint_f"]))
            occ_min = Decimal(constraint.occupied_min_f)
            occ_max = Decimal(constraint.occupied_max_f)
            band_width = occ_max - occ_min
            if band_width <= 0:
                # Defensive — not in scenarios
                continue
            projected = (current_setpoint + delta).quantize(_TEMP_QUANT)

            above_dev = projected - occ_max
            below_dev = occ_min - projected
            deviation = max(above_dev, below_dev, Decimal("0"))
            raw_risk = deviation / band_width
            if raw_risk > Decimal("1"):
                raw_risk = Decimal("1")
            risk = raw_risk.quantize(_RISK_QUANT, rounding=ROUND_HALF_UP)

            if risk >= COMFORT_RISK_THRESHOLD:
                if above_dev > 0:
                    direction = "above"
                    delta_temp = above_dev
                    mitigation = (
                        f"Reduce setpoint by {_format_half(_round_half(delta_temp))}"
                        f"°F to return to comfort band."
                    )
                else:
                    direction = "below"
                    delta_temp = below_dev
                    mitigation = (
                        f"Increase setpoint by {_format_half(_round_half(delta_temp))}"
                        f"°F to return to comfort band."
                    )
                alerts.append(
                    ComfortRiskAlert(
                        zone_id=z.id,
                        zone_name=z.name,
                        projected_temp_f=projected,
                        occupied_min_f=occ_min,
                        occupied_max_f=occ_max,
                        risk_score=risk,
                        direction=direction,
                        mitigation=mitigation,
                    )
                )

        # 5. Collapse: ≥1 evaluable zone but ZERO had constraints → 400
        if evaluable_zones > 0 and constraint_present == 0:
            raise ComfortRiskInputsMissing(["comfort_constraints"])

        decision = "alert" if alerts else "pass"
        alerts_count = len(alerts)
        elapsed_ms_int = int((time.perf_counter() - start) * 1000.0)

        # 6. Persist run + alerts inside a single transaction
        run_row = ComfortRiskRunModel(
            building_id=building_id,
            run_at=run_at,
            decision=decision,
            alerts_count=alerts_count,
            elapsed_ms=elapsed_ms_int,
            source_run_timestamp=active_ts,
        )
        self.risk_repo.save_run_no_commit(run_row)

        # Forced DB error lever for S14 — raise AFTER the run row is flushed
        # but BEFORE alerts/commit, so rollback proves atomicity.
        if _consume_force_db_error():
            raise ComfortRiskForcedDbError("forced_db_error_for_test")

        alert_rows = [
            ComfortRiskAlertModel(
                run_id=run_row.id,
                zone_id=a.zone_id,
                projected_temp_f=a.projected_temp_f,
                occupied_min_f=a.occupied_min_f,
                occupied_max_f=a.occupied_max_f,
                risk_score=a.risk_score,
                direction=a.direction,
                mitigation=a.mitigation,
            )
            for a in alerts
        ]
        self.risk_repo.save_alerts_no_commit(alert_rows)

        self.db.commit()

        if decision == "pass":
            logger.info(
                "comfort_risk_pass building_id=%s source_run=%s",
                building_id,
                active_ts.isoformat(),
            )
        else:
            logger.info(
                "comfort_risk_alert building_id=%s alerts=%s source_run=%s",
                building_id,
                alerts_count,
                active_ts.isoformat(),
            )

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return ComfortRiskRunResult(
            building_id=building_id,
            decision=decision,
            alerts_count=alerts_count,
            source_run_timestamp=active_ts,
            elapsed_ms=elapsed_ms,
            alerts=alerts,
            run_at=run_at,
        )

    def latest_for_building(
        self, building_id: int
    ) -> ComfortRiskRunResult | None:
        run = self.risk_repo.latest_for_building(building_id)
        if run is None:
            return None
        alert_rows = self.risk_repo.alerts_for_run(run.id)
        # Look up zone names
        building = self.db.get(BuildingModel, building_id)
        names = {z.id: z.name for z in (building.zones if building else [])}
        alerts = [
            ComfortRiskAlert(
                zone_id=a.zone_id,
                zone_name=names.get(a.zone_id, ""),
                projected_temp_f=Decimal(a.projected_temp_f),
                occupied_min_f=Decimal(a.occupied_min_f),
                occupied_max_f=Decimal(a.occupied_max_f),
                risk_score=Decimal(a.risk_score),
                direction=a.direction,
                mitigation=a.mitigation,
            )
            for a in alert_rows
        ]
        return ComfortRiskRunResult(
            building_id=run.building_id,
            decision=run.decision,
            alerts_count=run.alerts_count,
            source_run_timestamp=run.source_run_timestamp,
            elapsed_ms=float(run.elapsed_ms),
            alerts=alerts,
            run_at=run.run_at,
        )
