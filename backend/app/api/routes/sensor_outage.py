"""UC10 HandleSensorDataOutage — API route handlers."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.sensor_outage import (
    SensorOutageForcedDbError,
    SensorOutageInputsMissing,
)
from app.services.sensor_outage_service import SensorOutageService


router = APIRouter(tags=["sensor-outage"])


class SensorOutageHandleRequest(BaseModel):
    building_id: Optional[int] = None
    affected_zone_ids: Optional[List[int]] = None
    reason: Optional[str] = None


class SensorOutageResponse(BaseModel):
    event_id: Optional[int]
    building_id: int
    affected_zone_ids: List[int]
    decision: str
    notes: str
    degraded_forecast_zone_ids: List[int]
    degraded_recommendation_ids: List[int]
    elapsed_ms: float
    declared_at: Optional[datetime] = None


class SensorOutageEventResponse(BaseModel):
    id: int
    building_id: int
    declared_at: datetime
    affected_zone_ids: List[int]
    reason: str
    decision: str
    notes: str
    elapsed_ms: int


@router.post(
    "/api/sensors/outage/handle",
    response_model=SensorOutageResponse,
)
def handle_sensor_outage(
    body: SensorOutageHandleRequest,
    db: Session = Depends(get_db),
) -> SensorOutageResponse:
    service = SensorOutageService(db)
    try:
        result = service.handle(
            building_id=body.building_id if body.building_id is not None else -1,
            affected_zone_ids=body.affected_zone_ids or [],
            reason=body.reason or "",
        )
    except SensorOutageInputsMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"missingInputs": exc.missing_inputs},
        )
    except SensorOutageForcedDbError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "db_error"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "sensor_outage_error"},
        )
    return SensorOutageResponse(
        event_id=result.event_id,
        building_id=result.building_id,
        affected_zone_ids=result.affected_zone_ids,
        decision=result.decision,
        notes=result.notes,
        degraded_forecast_zone_ids=result.degraded_forecast_zone_ids,
        degraded_recommendation_ids=result.degraded_recommendation_ids,
        elapsed_ms=result.elapsed_ms,
        declared_at=result.declared_at,
    )


@router.get(
    "/api/buildings/{building_id}/sensor-outages",
    response_model=List[SensorOutageEventResponse],
)
def list_sensor_outages(
    building_id: int,
    db: Session = Depends(get_db),
) -> List[SensorOutageEventResponse]:
    service = SensorOutageService(db)
    rows = service.list_events(building_id)
    return [
        SensorOutageEventResponse(
            id=r.id,
            building_id=r.building_id,
            declared_at=r.declared_at,
            affected_zone_ids=list(r.affected_zone_ids or []),
            reason=r.reason,
            decision=r.decision,
            notes=r.notes,
            elapsed_ms=r.elapsed_ms,
        )
        for r in rows
    ]
