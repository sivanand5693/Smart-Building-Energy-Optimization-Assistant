from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.applied_change import ApplyForcedDbError, ApplyInputsMissing
from app.domain.plan_adaptation import AdaptInputsMissing, OccupancyChange
from app.services.adapt_plan_service import AdaptPlanService
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


# -- UC6 AdaptPlanToOccupancyChange ------------------------------------------


class OccupancyChangeIn(BaseModel):
    zone_id: int
    new_occupancy_count: int


class AdaptPlanRequest(BaseModel):
    occupancy_changes: list[OccupancyChangeIn]


class RevisedRecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    building_id: int
    zone_id: int
    zone_name: str
    run_timestamp: datetime
    setpoint_delta_f: Decimal
    projected_savings_kwh: Decimal
    comfort_impact: str
    rank: int
    model_version: str


class AdaptPlanResponse(BaseModel):
    building_id: int
    decision: str
    reason: str
    active_plan_run_timestamp: datetime
    new_run_timestamp: Optional[datetime] = None
    changed_zone_ids: list[int]
    requested_at: datetime
    elapsed_ms: float
    revised_recommendations: list[RevisedRecommendationOut]


class AdaptDecisionOut(BaseModel):
    id: int
    building_id: int
    decision: str
    reason: str
    active_plan_run_timestamp: datetime
    new_run_timestamp: Optional[datetime] = None
    changed_zone_ids: list[int]
    requested_at: datetime
    elapsed_ms: int


@router.post(
    "/{building_id}/plan/adapt",
    response_model=AdaptPlanResponse,
)
def adapt_plan(
    building_id: int,
    body: AdaptPlanRequest,
    db: Session = Depends(get_db),
) -> AdaptPlanResponse:
    service = AdaptPlanService(db)
    try:
        result = service.adapt(
            building_id,
            [
                OccupancyChange(
                    zone_id=c.zone_id,
                    new_occupancy_count=c.new_occupancy_count,
                )
                for c in body.occupancy_changes
            ],
        )
    except AdaptInputsMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"missingInputs": exc.missing_inputs},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "adapt_error"},
        )
    return AdaptPlanResponse(
        building_id=result.building_id,
        decision=result.decision,
        reason=result.reason,
        active_plan_run_timestamp=result.active_plan_run_timestamp,
        new_run_timestamp=result.new_run_timestamp,
        changed_zone_ids=result.changed_zone_ids,
        requested_at=result.requested_at,
        elapsed_ms=result.elapsed_ms,
        revised_recommendations=[
            RevisedRecommendationOut(**vars(r))
            for r in result.revised_recommendations
        ],
    )


@router.get(
    "/{building_id}/plan/adaptations",
    response_model=list[AdaptDecisionOut],
)
def list_adaptations(
    building_id: int,
    db: Session = Depends(get_db),
) -> list[AdaptDecisionOut]:
    service = AdaptPlanService(db)
    rows = service.list_for_building(building_id)
    return [AdaptDecisionOut(**vars(r)) for r in rows]
