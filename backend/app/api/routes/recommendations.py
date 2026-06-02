from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.recommendation import RecommendationInputsMissing
from app.services.recommendation_service import RecommendationService


router = APIRouter(prefix="/api/buildings", tags=["recommendations"])


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int | None = None
    building_id: int
    zone_id: int
    zone_name: str
    run_timestamp: datetime
    setpoint_delta_f: Decimal
    projected_savings_kwh: Decimal
    comfort_impact: str
    rank: int
    model_version: str


class RecommendationRunResponse(BaseModel):
    building_id: int
    run_timestamp: datetime
    elapsed_ms: float
    recommendations: list[RecommendationOut]


@router.post(
    "/{building_id}/recommendations/run",
    response_model=RecommendationRunResponse,
)
def run_recommendations(
    building_id: int,
    db: Session = Depends(get_db),
) -> RecommendationRunResponse:
    service = RecommendationService(db)
    try:
        result = service.run(building_id)
    except RecommendationInputsMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"missingInputs": exc.missing_inputs},
        )
    return RecommendationRunResponse(
        building_id=result.building_id,
        run_timestamp=result.run_timestamp,
        elapsed_ms=result.elapsed_ms,
        recommendations=[RecommendationOut(**vars(r)) for r in result.recommendations],
    )


@router.get(
    "/{building_id}/recommendations/latest",
    response_model=list[RecommendationOut],
)
def latest_recommendations(
    building_id: int,
    db: Session = Depends(get_db),
) -> list[RecommendationOut]:
    service = RecommendationService(db)
    recs = service.latest_for_building(building_id)
    return [RecommendationOut(**vars(r)) for r in recs]
