"""Test-only control endpoints. Mounted only when TESTING=1."""
from decimal import Decimal
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
from app.infrastructure.adapters.optimization_adapter import (
    OptimizationAdapterDouble,
    registry as opt_registry,
)
from app.infrastructure.adapters.device_control_adapter import (
    DeviceControlAdapterDouble,
    registry as device_control_registry,
)
from app.infrastructure.models import ZoneComfortConstraintModel
from app.infrastructure.repositories.applied_change_repository import (
    DeviceRepository,
)
from app.infrastructure.repositories.recommendation_repository import (
    ZoneComfortConstraintRepository,
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


class SetOccupancyPayload(BaseModel):
    zone_id: int
    occupancy_count: int
    timestamp: Optional[str] = None  # ISO; default 1970-01-01 so it sits well
                                     # before any plan run_timestamp


@router.post("/occupancy/set_for_zone")
def set_occupancy_for_zone(
    body: SetOccupancyPayload,
    db: Session = Depends(get_db),
) -> dict:
    # Wipe existing rows for the zone so the materiality baseline lookup is
    # deterministic, then insert one row with the requested count + ts.
    db.execute(
        text("DELETE FROM occupancy_records WHERE zone_id = :z"),
        {"z": body.zone_id},
    )
    ts_clause = body.timestamp or "1970-01-01T00:00:00"
    db.execute(
        text(
            "INSERT INTO occupancy_records (zone_id, timestamp, occupancy_count)"
            " VALUES (:z, CAST(:t AS timestamp), :c)"
        ),
        {"z": body.zone_id, "t": ts_clause, "c": body.occupancy_count},
    )
    db.commit()
    return {"ok": True}


# -- UC4 test-support --------------------------------------------------------

class SeedConstraintsPayload(BaseModel):
    zone_id: int
    min_setpoint_f: Optional[float] = 65.0
    max_setpoint_f: Optional[float] = 78.0
    occupied_min_f: Optional[float] = 68.0
    occupied_max_f: Optional[float] = 75.0
    unoccupied_min_f: Optional[float] = 65.0
    unoccupied_max_f: Optional[float] = 78.0


class ZoneOnlyPayload(BaseModel):
    zone_id: int


class ForceStalePayload(BaseModel):
    zone_id: int
    hours_old: int


@router.post("/comfort_constraints/seed")
def seed_constraints(
    body: SeedConstraintsPayload,
    db: Session = Depends(get_db),
) -> dict:
    repo = ZoneComfortConstraintRepository(db)
    repo.upsert(
        ZoneComfortConstraintModel(
            zone_id=body.zone_id,
            min_setpoint_f=Decimal(str(body.min_setpoint_f)),
            max_setpoint_f=Decimal(str(body.max_setpoint_f)),
            occupied_min_f=Decimal(str(body.occupied_min_f)),
            occupied_max_f=Decimal(str(body.occupied_max_f)),
            unoccupied_min_f=Decimal(str(body.unoccupied_min_f)),
            unoccupied_max_f=Decimal(str(body.unoccupied_max_f)),
        )
    )
    return {"ok": True}


@router.post("/comfort_constraints/clear")
def clear_constraints(
    body: ZoneOnlyPayload,
    db: Session = Depends(get_db),
) -> dict:
    ZoneComfortConstraintRepository(db).delete(body.zone_id)
    return {"ok": True}


@router.post("/forecasts/force_stale")
def force_stale_forecast(
    body: ForceStalePayload,
    db: Session = Depends(get_db),
) -> dict:
    db.execute(
        text(
            "UPDATE demand_forecasts SET timestamp = NOW() - (:h || ' hours')::interval "
            "WHERE zone_id = :z"
        ),
        {"h": body.hours_old, "z": body.zone_id},
    )
    db.commit()
    return {"ok": True}


@router.post("/forecasts/clear_for_zone")
def clear_forecasts_for_zone(
    body: ZoneOnlyPayload,
    db: Session = Depends(get_db),
) -> dict:
    db.execute(
        text("DELETE FROM demand_forecasts WHERE zone_id = :z"),
        {"z": body.zone_id},
    )
    db.commit()
    return {"ok": True}


@router.post("/optimization_double/force_infeasible")
def force_infeasible(body: ZoneOnlyPayload) -> dict:
    assert isinstance(opt_registry.optimization, OptimizationAdapterDouble)
    opt_registry.optimization.force_infeasible(body.zone_id)
    return {"ok": True}


@router.post("/optimization_double/reset")
def reset_optimization_double() -> dict:
    if isinstance(opt_registry.optimization, OptimizationAdapterDouble):
        opt_registry.optimization.reset()
    return {"ok": True}


# -- UC5 test-support --------------------------------------------------------


class DeviceControlDirectivePayload(BaseModel):
    recommendation_id: int
    outcome: str = "dispatched"
    error_code: Optional[str] = None
    adapter_message: Optional[str] = None
    latency_ms: Optional[int] = None


@router.post("/device_control/directive")
def device_control_directive(body: DeviceControlDirectivePayload) -> dict:
    assert isinstance(
        device_control_registry.device_control, DeviceControlAdapterDouble
    )
    device_control_registry.device_control.set_directive(
        recommendation_id=body.recommendation_id,
        outcome=body.outcome,
        error_code=body.error_code,
        adapter_message=body.adapter_message,
        latency_ms=body.latency_ms,
    )
    return {"ok": True}


@router.post("/device_control/reset")
def device_control_reset() -> dict:
    if isinstance(
        device_control_registry.device_control, DeviceControlAdapterDouble
    ):
        device_control_registry.device_control.reset()
    return {"ok": True}


@router.post("/device_control/force_db_error")
def device_control_force_db_error() -> dict:
    assert isinstance(
        device_control_registry.device_control, DeviceControlAdapterDouble
    )
    device_control_registry.device_control.force_db_error_next_apply()
    return {"ok": True}


@router.get("/device_control/calls")
def device_control_calls() -> dict:
    if isinstance(
        device_control_registry.device_control, DeviceControlAdapterDouble
    ):
        return {"calls": device_control_registry.device_control.calls()}
    return {"calls": []}


class ClearDevicesPayload(BaseModel):
    zone_id: int


@router.post("/devices/clear_for_zone")
def clear_devices_for_zone(
    body: ClearDevicesPayload,
    db: Session = Depends(get_db),
) -> dict:
    deleted = DeviceRepository(db).delete_hvac_for_zone(body.zone_id)
    return {"ok": True, "deleted": deleted}


# -- UC7 test-support --------------------------------------------------------


class SetDeltaForZonePayload(BaseModel):
    zone_id: int
    setpoint_delta_f: float


@router.post("/recommendations/set_delta_for_zone")
def set_delta_for_zone(
    body: SetDeltaForZonePayload,
    db: Session = Depends(get_db),
) -> dict:
    """Override the latest setpoint_recommendations row's setpoint_delta_f for
    a zone (in the most recent run). Used by UC7 scenarios for crisp math."""
    db.execute(
        text(
            "UPDATE setpoint_recommendations SET setpoint_delta_f = :d "
            "WHERE zone_id = :z AND run_timestamp = ("
            "  SELECT MAX(run_timestamp) FROM setpoint_recommendations "
            "  WHERE zone_id = :z)"
        ),
        {"d": body.setpoint_delta_f, "z": body.zone_id},
    )
    db.commit()
    return {"ok": True}


@router.post("/recommendations/clear_for_zone")
def clear_recs_for_zone(
    body: ZoneOnlyPayload,
    db: Session = Depends(get_db),
) -> dict:
    """Delete all setpoint_recommendations rows for the given zone. Used by
    UC7-S10 (partial plan coverage)."""
    db.execute(
        text("DELETE FROM setpoint_recommendations WHERE zone_id = :z"),
        {"z": body.zone_id},
    )
    db.commit()
    return {"ok": True}


@router.post("/comfort_risk/force_db_error")
def comfort_risk_force_db_error() -> dict:
    """S14 — make the next ComfortRiskService.run raise mid-write."""
    from app.services.comfort_risk_service import force_db_error_next_run

    force_db_error_next_run()
    return {"ok": True}


# -- UC8 test-support --------------------------------------------------------


class CopyRecommendationFieldsPayload(BaseModel):
    src_zone_id: int
    dst_zone_id: int


@router.post("/recommendations/copy_fields_between_zones")
def copy_recommendation_fields_between_zones(
    body: CopyRecommendationFieldsPayload,
    db: Session = Depends(get_db),
) -> dict:
    """UC8 S04 — copy the latest setpoint_recommendations row's deterministic
    factor fields (projected_savings_kwh, comfort_impact, setpoint_delta_f)
    from src zone onto dst zone so the two zones present identical inputs to
    the ExplanationAdapter."""
    db.execute(
        text(
            "UPDATE setpoint_recommendations dst "
            "SET projected_savings_kwh = src.projected_savings_kwh, "
            "    comfort_impact = src.comfort_impact, "
            "    setpoint_delta_f = src.setpoint_delta_f "
            "FROM ( "
            "  SELECT projected_savings_kwh, comfort_impact, setpoint_delta_f "
            "  FROM setpoint_recommendations "
            "  WHERE zone_id = :s "
            "  ORDER BY run_timestamp DESC LIMIT 1 "
            ") src "
            "WHERE dst.zone_id = :d AND dst.run_timestamp = ("
            "  SELECT MAX(run_timestamp) FROM setpoint_recommendations "
            "  WHERE zone_id = :d)"
        ),
        {"s": body.src_zone_id, "d": body.dst_zone_id},
    )
    db.commit()
    return {"ok": True}


@router.post("/explanation/reset")
def explanation_reset() -> dict:
    """UC8 — reset the ExplanationAdapter double's invocation counter."""
    from app.infrastructure.adapters.explanation_adapter import (
        registry as explanation_registry,
    )

    adapter = explanation_registry.explanation
    reset_fn = getattr(adapter, "reset", None)
    if callable(reset_fn):
        reset_fn()
    return {"ok": True}


@router.get("/explanation/calls")
def explanation_calls() -> dict:
    """UC8 — return the double's invocation counter (S03 idempotency oracle)."""
    from app.infrastructure.adapters.explanation_adapter import (
        registry as explanation_registry,
    )

    adapter = explanation_registry.explanation
    calls = getattr(adapter, "calls_count", 0)
    return {"calls": int(calls)}


@router.post("/explanation/force_db_error")
def explanation_force_db_error() -> dict:
    """UC8 S14 — make the next ExplanationService.explain raise mid-write."""
    from app.services.explanation_service import force_db_error_next_request

    force_db_error_next_request()
    return {"ok": True}
