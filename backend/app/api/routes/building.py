from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.building import (
    BuildingProfileInput,
    BuildingProfileResult,
    BuildingSummary,
    ValidationFailure,
)
from app.domain.occupancy_schedule import ImportFailure, ImportResult
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


@router.get("", response_model=list[BuildingSummary])
def list_buildings(db: Session = Depends(get_db)) -> list[BuildingSummary]:
    service = BuildingService(db)
    return service.list_buildings_with_zones()


@router.post(
    "/{building_id}/occupancy",
    response_model=ImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_occupancy(
    building_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportResult:
    content_bytes = await file.read()
    csv_content = content_bytes.decode("utf-8", errors="replace")
    service = BuildingService(db)
    try:
        return service.import_occupancy_schedule(building_id, csv_content)
    except ImportFailure as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "errors": [
                    {"row": e.row, "field": e.field, "message": e.message}
                    for e in exc.errors
                ]
            },
        )
