from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.building import (
    BuildingProfileInput,
    BuildingProfileResult,
    ValidationFailure,
)
from app.services.building_service import BuildingService

router = APIRouter(prefix="/api/buildings", tags=["buildings"])


@router.post(
    "",
    response_model=BuildingProfileResult,
    status_code=status.HTTP_201_CREATED,
)
def register_building_profile(
    profile: BuildingProfileInput,
    db: Session = Depends(get_db),
) -> BuildingProfileResult:
    service = BuildingService(db)
    try:
        return service.register_building_profile(profile)
    except ValidationFailure as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": exc.errors},
        )
