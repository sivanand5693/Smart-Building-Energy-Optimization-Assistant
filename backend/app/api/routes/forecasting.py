from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.forecast import ForecastInputsMissing
from app.services.forecasting_service import ForecastService


router = APIRouter(prefix="/api/buildings", tags=["forecasts"])


class ZoneForecastOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    zone_id: int
    zone_name: str
    timestamp: datetime
    predicted_kwh: Decimal
    model_version: str


class ForecastRunResponse(BaseModel):
    building_id: int
    run_timestamp: datetime
    elapsed_ms: float
    forecasts: list[ZoneForecastOut]


@router.post(
    "/{building_id}/forecasts/run",
    response_model=ForecastRunResponse,
)
def run_forecast(
    building_id: int,
    db: Session = Depends(get_db),
) -> ForecastRunResponse:
    service = ForecastService(db)
    try:
        result = service.run_forecast(building_id)
    except ForecastInputsMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"missingInputs": exc.missing_inputs},
        )
    return ForecastRunResponse(
        building_id=result.building_id,
        run_timestamp=result.run_timestamp,
        elapsed_ms=result.elapsed_ms,
        forecasts=[ZoneForecastOut(**vars(f)) for f in result.forecasts],
    )


@router.get(
    "/{building_id}/forecasts/latest",
    response_model=list[ZoneForecastOut],
)
def latest_forecasts(
    building_id: int,
    db: Session = Depends(get_db),
) -> list[ZoneForecastOut]:
    service = ForecastService(db)
    forecasts = service.latest_for_building(building_id)
    return [ZoneForecastOut(**vars(f)) for f in forecasts]
