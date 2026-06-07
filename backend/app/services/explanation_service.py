"""UC8 ExplainRecommendation service (control)."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.explanation import (
    ExplanationForcedDbError,
    ExplanationInputs,
    ExplanationInputsMissing,
    ExplanationResult,
)
from app.infrastructure.adapters.explanation_adapter import (
    registry as explanation_registry,
)
from app.infrastructure.models import (
    RecommendationExplanationModel,
    SetpointRecommendationModel,
    ZoneModel,
)
from app.infrastructure.repositories.explanation_repository import (
    ExplanationRepository,
)
from app.infrastructure.repositories.forecast_repository import (
    DemandForecastRepository,
)
from app.infrastructure.repositories.occupancy_repository import (
    OccupancyRepository,
)
from app.infrastructure.repositories.recommendation_repository import (
    ZoneComfortConstraintRepository,
)


logger = logging.getLogger(__name__)


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


class ExplanationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ExplanationRepository(db)
        self.constraint_repo = ZoneComfortConstraintRepository(db)
        self.occupancy_repo = OccupancyRepository(db)
        self.forecast_repo = DemandForecastRepository(db)

    def explain(self, recommendation_id: int) -> ExplanationResult:
        start = time.perf_counter()
        try:
            return self._explain_inner(recommendation_id, start)
        except ExplanationInputsMissing:
            self.db.rollback()
            raise
        except ExplanationForcedDbError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            raise

    def _explain_inner(
        self, recommendation_id: int, start: float
    ) -> ExplanationResult:
        # 1. Recommendation
        rec = self.db.get(SetpointRecommendationModel, recommendation_id)
        if rec is None:
            raise ExplanationInputsMissing(["recommendation"])

        zone_id = rec.zone_id
        run_ts = rec.run_timestamp

        # 2. Probe each context input, accumulate missing labels sorted alpha
        missing: list[str] = []
        constraint = self.constraint_repo.for_zone(zone_id)
        if constraint is None:
            missing.append("comfort_constraints")
        forecast = self.forecast_repo.latest_for_zone_at_or_before(
            zone_id, run_ts
        )
        if forecast is None:
            missing.append("forecast")
        occupancy = self.occupancy_repo.latest_for_zone_at_or_before(
            zone_id, run_ts
        )
        if occupancy is None:
            missing.append("occupancy")

        if missing:
            raise ExplanationInputsMissing(sorted(missing))

        # 3. Cache check
        existing = self.repo.get_for_recommendation(recommendation_id)
        if existing is not None:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return ExplanationResult(
                recommendation_id=recommendation_id,
                text=existing.text,
                factors=dict(existing.factors_json),
                cached=True,
                elapsed_ms=elapsed_ms,
                model_version=existing.model_version,
                generated_at=existing.generated_at,
            )

        # 4. Build inputs + call adapter
        zone = self.db.get(ZoneModel, zone_id)
        zone_name = zone.name if zone is not None else ""
        inputs = ExplanationInputs(
            recommendation_id=recommendation_id,
            zone_id=zone_id,
            zone_name=zone_name,
            projected_savings_kwh=Decimal(rec.projected_savings_kwh),
            comfort_impact=rec.comfort_impact,
            setpoint_delta_f=Decimal(rec.setpoint_delta_f),
            occupancy_count=int(occupancy.occupancy_count),
            occupancy_timestamp=occupancy.timestamp,
            predicted_kwh=Decimal(forecast.predicted_kwh),
            occupied_min_f=Decimal(constraint.occupied_min_f),
            occupied_max_f=Decimal(constraint.occupied_max_f),
        )
        text, factors, model_version = explanation_registry.explanation.explain(
            recommendation_id, inputs
        )

        # Forced DB error lever for S14 — raise BEFORE the insert flushes so
        # the rollback proves zero new rows.
        if _consume_force_db_error():
            raise ExplanationForcedDbError("forced_db_error_for_test")

        elapsed_ms_int = int((time.perf_counter() - start) * 1000.0)
        generated_at = datetime.now(timezone.utc)
        row = RecommendationExplanationModel(
            recommendation_id=recommendation_id,
            generated_at=generated_at,
            text=text,
            factors_json=factors,
            elapsed_ms=elapsed_ms_int,
            model_version=model_version,
        )
        self.repo.save_no_commit(row)
        self.db.commit()

        logger.info(
            "explanation_generated recommendation_id=%s model_version=%s",
            recommendation_id,
            model_version,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return ExplanationResult(
            recommendation_id=recommendation_id,
            text=text,
            factors=dict(factors),
            cached=False,
            elapsed_ms=elapsed_ms,
            model_version=model_version,
            generated_at=generated_at,
        )

    def get_existing(self, recommendation_id: int) -> ExplanationResult | None:
        row = self.repo.get_for_recommendation(recommendation_id)
        if row is None:
            return None
        return ExplanationResult(
            recommendation_id=recommendation_id,
            text=row.text,
            factors=dict(row.factors_json),
            cached=True,
            elapsed_ms=0.0,
            model_version=row.model_version,
            generated_at=row.generated_at,
        )
