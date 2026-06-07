from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.comfort_risk import (
    ComfortRiskForcedDbError,
    ComfortRiskInputsMissing,
)
from app.services.comfort_risk_service import ComfortRiskService


router = APIRouter(prefix="/api/buildings", tags=["comfort-risk"])


class ComfortRiskAlertOut(BaseModel):
    zone_id: int
    zone_name: str
    projected_temp_f: Decimal
    occupied_min_f: Decimal
    occupied_max_f: Decimal
    risk_score: Decimal
    direction: str
    mitigation: str


class ComfortRiskRunResponse(BaseModel):
    building_id: int
    decision: str
    alerts_count: int
    source_run_timestamp: Optional[datetime] = None
    run_at: Optional[datetime] = None
    elapsed_ms: float
    alerts: list[ComfortRiskAlertOut]


@router.post(
    "/{building_id}/comfort-risk/run",
    response_model=ComfortRiskRunResponse,
)
def run_comfort_risk(
    building_id: int,
    db: Session = Depends(get_db),
) -> ComfortRiskRunResponse:
    service = ComfortRiskService(db)
    try:
        result = service.run(building_id)
    except ComfortRiskInputsMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"missingInputs": exc.missing_inputs},
        )
    except ComfortRiskForcedDbError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "db_error"},
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "comfort_risk_error"},
        )
    return ComfortRiskRunResponse(
        building_id=result.building_id,
        decision=result.decision,
        alerts_count=result.alerts_count,
        source_run_timestamp=result.source_run_timestamp,
        run_at=result.run_at,
        elapsed_ms=result.elapsed_ms,
        alerts=[ComfortRiskAlertOut(**vars(a)) for a in result.alerts],
    )


@router.get(
    "/{building_id}/comfort-risk/latest",
    response_model=Optional[ComfortRiskRunResponse],
)
def latest_comfort_risk(
    building_id: int,
    db: Session = Depends(get_db),
) -> Optional[ComfortRiskRunResponse]:
    service = ComfortRiskService(db)
    result = service.latest_for_building(building_id)
    if result is None:
        return None
    return ComfortRiskRunResponse(
        building_id=result.building_id,
        decision=result.decision,
        alerts_count=result.alerts_count,
        source_run_timestamp=result.source_run_timestamp,
        run_at=result.run_at,
        elapsed_ms=result.elapsed_ms,
        alerts=[ComfortRiskAlertOut(**vars(a)) for a in result.alerts],
    )
