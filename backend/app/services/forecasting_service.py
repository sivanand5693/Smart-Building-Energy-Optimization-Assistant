import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.forecast import (
    ForecastFeatures,
    ForecastInputsMissing,
    ForecastRunResult,
    ZoneForecast,
)
from app.infrastructure.adapters.forecast_adapters import registry
from app.infrastructure.models import BuildingModel, DemandForecastModel
from app.infrastructure.repositories.forecast_repository import (
    DemandForecastRepository,
)
from app.infrastructure.repositories.occupancy_repository import OccupancyRepository


class ForecastService:
    def __init__(self, db: Session):
        self.db = db
        self.forecast_repo = DemandForecastRepository(db)
        self.occupancy_repo = OccupancyRepository(db)

    def run_forecast(self, building_id: int) -> ForecastRunResult:
        start = time.perf_counter()

        building = self.db.get(BuildingModel, building_id)
        if building is None:
            raise ForecastInputsMissing(["building"])

        zones = list(building.zones)
        if not zones:
            raise ForecastInputsMissing(["zones"])

        # 1. Occupancy snapshots per zone
        occupancy_per_zone: dict[int, int] = {}
        for z in zones:
            rec = self.occupancy_repo.latest_for_zone(z.id)
            if rec is None:
                raise ForecastInputsMissing(["occupancy"])
            occupancy_per_zone[z.id] = rec.occupancy_count

        # 2. Weather
        weather = registry.weather.current_for_building(building_id)
        if not weather:
            raise ForecastInputsMissing(["weather"])

        # 3. Device state per zone
        device_state_per_zone: dict[int, dict] = {}
        for z in zones:
            ds = registry.device_state.current_for_zone(z.id)
            if not ds:
                raise ForecastInputsMissing(["device_state"])
            device_state_per_zone[z.id] = ds

        # 4. Predict + persist atomically
        run_ts = datetime.now(timezone.utc)
        rows: list[DemandForecastModel] = []
        forecasts: list[ZoneForecast] = []
        for z in zones:
            features = ForecastFeatures(
                occupancy_count=occupancy_per_zone[z.id],
                weather_temp_c=float(weather.get("temp_c", 0.0)),
                device_on_count=int(device_state_per_zone[z.id].get("on_count", 0)),
            )
            kwh, model_version = registry.forecast_model.predict(z.id, features)
            row = DemandForecastModel(
                zone_id=z.id,
                timestamp=run_ts,
                predicted_kwh=kwh,
                model_version=model_version,
            )
            rows.append(row)
            forecasts.append(
                ZoneForecast(
                    zone_id=z.id,
                    zone_name=z.name,
                    timestamp=run_ts,
                    predicted_kwh=kwh,
                    model_version=model_version,
                )
            )

        self.forecast_repo.save_all(rows)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return ForecastRunResult(
            building_id=building_id,
            run_timestamp=run_ts,
            elapsed_ms=elapsed_ms,
            forecasts=forecasts,
        )

    def latest_for_building(self, building_id: int) -> list[ZoneForecast]:
        rows = self.forecast_repo.latest_for_building(building_id)
        building = self.db.get(BuildingModel, building_id)
        zone_names = {z.id: z.name for z in building.zones} if building else {}
        return [
            ZoneForecast(
                zone_id=r.zone_id,
                zone_name=zone_names.get(r.zone_id, ""),
                timestamp=r.timestamp,
                predicted_kwh=r.predicted_kwh,
                model_version=r.model_version,
            )
            for r in rows
        ]
