import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.recommendation import (
    Candidate,
    RankedRecommendation,
    RecommendationInputsMissing,
    RecommendationRunResult,
)
from app.infrastructure.adapters.optimization_adapter import registry
from app.infrastructure.models import (
    BuildingModel,
    DemandForecastModel,
    SetpointRecommendationModel,
    ZoneComfortConstraintModel,
)
from app.infrastructure.repositories.forecast_repository import (
    DemandForecastRepository,
)
from app.infrastructure.repositories.recommendation_repository import (
    SetpointRecommendationRepository,
    ZoneComfortConstraintRepository,
)


STALENESS_THRESHOLD = timedelta(hours=24)


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db
        self.forecast_repo = DemandForecastRepository(db)
        self.constraint_repo = ZoneComfortConstraintRepository(db)
        self.rec_repo = SetpointRecommendationRepository(db)

    def run(self, building_id: int) -> RecommendationRunResult:
        """Public entry-point used by the route handler. Commits on success."""
        return self.run_within(building_id, db=self.db, commit=True)

    def run_within(
        self,
        building_id: int,
        *,
        db: Session,
        commit: bool = False,
    ) -> RecommendationRunResult:
        """Shared implementation. When ``commit=False`` the new rows are
        flushed but not committed — the caller owns the transaction (UC6 A7).
        """
        # Allow the caller to pass in a session (UC6 reuses the same session
        # so the whole adapt request is one transaction). Rebind repos.
        if db is not self.db:
            self.db = db
            self.forecast_repo = DemandForecastRepository(db)
            self.constraint_repo = ZoneComfortConstraintRepository(db)
            self.rec_repo = SetpointRecommendationRepository(db)

        start = time.perf_counter()
        run_ts = datetime.now(timezone.utc)

        building = self.db.get(BuildingModel, building_id)
        if building is None:
            raise RecommendationInputsMissing(["building"])

        zones = list(building.zones)
        if not zones:
            raise RecommendationInputsMissing(["zones"])

        # 1. Forecast freshness check (latest <= 24h old for every zone)
        forecasts_per_zone: dict[int, DemandForecastModel] = {}
        for z in zones:
            f = self.forecast_repo.latest_for_zone(z.id)
            if f is None:
                raise RecommendationInputsMissing(["forecast"])
            ts = f.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if (run_ts - ts) > STALENESS_THRESHOLD:
                raise RecommendationInputsMissing(["forecast"])
            forecasts_per_zone[z.id] = f

        # 2. Comfort constraints
        constraints_per_zone: dict[int, ZoneComfortConstraintModel] = {}
        for z in zones:
            c = self.constraint_repo.for_zone(z.id)
            if c is None:
                raise RecommendationInputsMissing(["comfort_constraints"])
            constraints_per_zone[z.id] = c

        # 3. Generate + filter candidates per zone
        zone_name_by_id = {z.id: z.name for z in zones}
        flat: list[tuple[int, Candidate]] = []
        for z in zones:
            c = constraints_per_zone[z.id]
            f = forecasts_per_zone[z.id]
            baseline = (Decimal(c.occupied_min_f) + Decimal(c.occupied_max_f)) / Decimal(2)
            cands = registry.optimization.recommend(z.id, f, c)
            for cand in cands:
                new_setpoint = baseline + Decimal(cand.setpoint_delta_f)
                if (
                    new_setpoint < Decimal(c.min_setpoint_f)
                    or new_setpoint > Decimal(c.max_setpoint_f)
                ):
                    continue  # infeasible
                if cand.projected_savings_kwh < 0:
                    continue
                flat.append((z.id, cand))

        # 4. Rank: -savings DESC, zone_id ASC, setpoint_delta_f ASC
        flat.sort(
            key=lambda pair: (
                -pair[1].projected_savings_kwh,
                pair[0],
                pair[1].setpoint_delta_f,
            )
        )

        # 5. Persist
        rows: list[SetpointRecommendationModel] = []
        for idx, (zone_id, cand) in enumerate(flat, start=1):
            row = SetpointRecommendationModel(
                building_id=building_id,
                zone_id=zone_id,
                run_timestamp=run_ts,
                setpoint_delta_f=cand.setpoint_delta_f,
                projected_savings_kwh=cand.projected_savings_kwh,
                comfort_impact=cand.comfort_impact,
                rank=idx,
                model_version=cand.model_version,
            )
            rows.append(row)

        if rows:
            if commit:
                self.rec_repo.save_all(rows)
            else:
                self.rec_repo.save_all_no_commit(rows)

        ranked: list[RankedRecommendation] = []
        for row in rows:
            ranked.append(
                RankedRecommendation(
                    id=row.id,
                    building_id=row.building_id,
                    zone_id=row.zone_id,
                    zone_name=zone_name_by_id.get(row.zone_id, ""),
                    run_timestamp=row.run_timestamp,
                    setpoint_delta_f=row.setpoint_delta_f,
                    projected_savings_kwh=row.projected_savings_kwh,
                    comfort_impact=row.comfort_impact,
                    rank=row.rank,
                    model_version=row.model_version,
                )
            )

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return RecommendationRunResult(
            building_id=building_id,
            run_timestamp=run_ts,
            elapsed_ms=elapsed_ms,
            recommendations=ranked,
        )

    def latest_for_building(self, building_id: int) -> list[RankedRecommendation]:
        rows = self.rec_repo.latest_for_building(building_id)
        building = self.db.get(BuildingModel, building_id)
        zone_names = {z.id: z.name for z in building.zones} if building else {}
        return [
            RankedRecommendation(
                id=r.id,
                building_id=r.building_id,
                zone_id=r.zone_id,
                zone_name=zone_names.get(r.zone_id, ""),
                run_timestamp=r.run_timestamp,
                setpoint_delta_f=r.setpoint_delta_f,
                projected_savings_kwh=r.projected_savings_kwh,
                comfort_impact=r.comfort_impact,
                rank=r.rank,
                model_version=r.model_version,
            )
            for r in rows
        ]
