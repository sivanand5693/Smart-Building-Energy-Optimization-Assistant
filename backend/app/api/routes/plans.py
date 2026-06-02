from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.applied_change import ApplyForcedDbError, ApplyInputsMissing
from app.services.apply_plan_service import ApplyPlanService


router = APIRouter(prefix="/api/buildings", tags=["plans"])


class ApplyPlanRequest(BaseModel):
    recommendation_ids: list[int]


class AppliedChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recommendation_id: int
    building_id: int
    zone_id: int
    applied_at: datetime
    setpoint_delta_f: Decimal
    status: str
    error_code: Optional[str] = None
    adapter_message: str
    latency_ms: int


class ApplyPlanResponse(BaseModel):
    building_id: int
    applied_at: datetime
    elapsed_ms: float
    results: list[AppliedChangeOut]


@router.post(
    "/{building_id}/plans/apply",
    response_model=ApplyPlanResponse,
)
def apply_plan(
    building_id: int,
    body: ApplyPlanRequest,
    db: Session = Depends(get_db),
) -> ApplyPlanResponse:
    service = ApplyPlanService(db)
    try:
        result = service.apply(building_id, body.recommendation_ids)
    except ApplyInputsMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"missingInputs": exc.missing_inputs},
        )
    except ApplyForcedDbError:
        # S15: simulate unrecoverable DB error; ensure session is rolled back.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "db_error"},
        )
    return ApplyPlanResponse(
        building_id=result.building_id,
        applied_at=result.applied_at,
        elapsed_ms=result.elapsed_ms,
        results=[AppliedChangeOut(**vars(r)) for r in result.results],
    )


@router.get(
    "/{building_id}/plans/latest",
    response_model=list[AppliedChangeOut],
)
def latest_plan(
    building_id: int,
    db: Session = Depends(get_db),
) -> list[AppliedChangeOut]:
    service = ApplyPlanService(db)
    rows = service.latest_for_building(building_id)
    return [AppliedChangeOut(**vars(r)) for r in rows]
