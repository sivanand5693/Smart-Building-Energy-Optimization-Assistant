"""Test-only control endpoints. Mounted only when TESTING=1."""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.infrastructure.adapters.forecast_adapters import (
    DeviceStateAdapterDouble,
    ForecastModelDouble,
    WeatherAdapterDouble,
    registry,
)


router = APIRouter(prefix="/api/_test", tags=["test-support"])


class SeedDoublePayload(BaseModel):
    kind: str  # "weather" | "device_state"
    building_id: Optional[int] = None
    zone_id: Optional[int] = None
    payload: dict


class ClearDoublePayload(BaseModel):
    kind: str
    building_id: Optional[int] = None
    zone_id: Optional[int] = None


class ClearOccupancyPayload(BaseModel):
    zone_id: int


@router.post("/forecast_doubles")
def seed_double(body: SeedDoublePayload) -> dict:
    if body.kind == "weather":
        assert isinstance(registry.weather, WeatherAdapterDouble)
        registry.weather.seed(body.building_id or 0, body.payload)
    elif body.kind == "device_state":
        assert isinstance(registry.device_state, DeviceStateAdapterDouble)
        registry.device_state.seed(body.zone_id or 0, body.payload)
    else:
        return {"ok": False, "error": f"unknown kind {body.kind}"}
    return {"ok": True}


@router.post("/forecast_doubles/clear")
def clear_double(body: ClearDoublePayload) -> dict:
    if body.kind == "weather":
        assert isinstance(registry.weather, WeatherAdapterDouble)
        registry.weather.clear(body.building_id or 0)
    elif body.kind == "device_state":
        assert isinstance(registry.device_state, DeviceStateAdapterDouble)
        registry.device_state.clear(body.zone_id or 0)
    else:
        return {"ok": False, "error": f"unknown kind {body.kind}"}
    return {"ok": True}


@router.post("/forecast_doubles/reset")
def reset_doubles() -> dict:
    if isinstance(registry.weather, WeatherAdapterDouble):
        registry.weather.reset()
    if isinstance(registry.device_state, DeviceStateAdapterDouble):
        registry.device_state.reset()
    # ForecastModelDouble is stateless
    _ = ForecastModelDouble  # silence unused-import lint
    return {"ok": True}


@router.post("/clear_occupancy_for_zone")
def clear_occupancy_for_zone(
    body: ClearOccupancyPayload,
    db: Session = Depends(get_db),
) -> dict:
    db.execute(
        text("DELETE FROM occupancy_records WHERE zone_id = :z"),
        {"z": body.zone_id},
    )
    db.commit()
    return {"ok": True}
