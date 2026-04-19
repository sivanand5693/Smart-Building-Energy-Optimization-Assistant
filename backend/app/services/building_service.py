from sqlalchemy.orm import Session

from app.domain.building import (
    BuildingProfileInput,
    BuildingProfileResult,
    ValidationFailure,
)
from app.infrastructure.repositories.building_repository import BuildingRepository


class BuildingService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BuildingRepository(db)

    def register_building_profile(
        self, profile: BuildingProfileInput
    ) -> BuildingProfileResult:
        errors = self._validate(profile)
        if errors:
            raise ValidationFailure(errors)

        saved = self.repository.save(profile)
        return BuildingProfileResult(building_id=saved.id, name=saved.name)

    def _validate(self, profile: BuildingProfileInput) -> dict[str, str]:
        errors: dict[str, str] = {}

        if not profile.building_name or not profile.building_name.strip():
            errors["buildingName"] = "buildingName is required"

        if not profile.zones:
            errors["zones"] = "zones must contain at least one zone"
        else:
            for zone in profile.zones:
                if not zone.devices:
                    errors["zones"] = (
                        "each zone must have at least one device"
                    )
                    break

        if not profile.operating_schedules:
            errors["operatingSchedule"] = (
                "operatingSchedule must contain at least one entry"
            )
        else:
            for schedule in profile.operating_schedules:
                if schedule.start_time >= schedule.end_time:
                    errors["operatingSchedule"] = (
                        "operatingSchedule start_time must be before end_time"
                    )
                    break

        return errors
