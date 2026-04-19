import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.building import (
    BuildingProfileInput,
    BuildingProfileResult,
    BuildingSummary,
    ZoneSummary,
    ValidationFailure,
)
from app.domain.occupancy_schedule import (
    ImportError as OccupancyImportError,
    ImportFailure,
    ImportResult,
    OccupancyRecordInput,
)
from app.infrastructure.models import BuildingModel
from app.infrastructure.repositories.building_repository import BuildingRepository
from app.infrastructure.repositories.occupancy_repository import OccupancyRepository


EXPECTED_HEADER = ["zone_id", "timestamp", "occupancy_count"]


class BuildingService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BuildingRepository(db)
        self.occupancy_repository = OccupancyRepository(db)

    # -- UC1 --------------------------------------------------------------

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
                    errors["zones"] = "each zone must have at least one device"
                    break
        if not profile.operating_schedules:
            errors["operatingSchedule"] = "operatingSchedule must contain at least one entry"
        else:
            for schedule in profile.operating_schedules:
                if schedule.start_time >= schedule.end_time:
                    errors["operatingSchedule"] = (
                        "operatingSchedule start_time must be before end_time"
                    )
                    break
        return errors

    # -- UC2 --------------------------------------------------------------

    def list_buildings_with_zones(self) -> list[BuildingSummary]:
        rows = self.db.query(BuildingModel).order_by(BuildingModel.id).all()
        return [
            BuildingSummary(
                id=b.id,
                name=b.name,
                zones=[ZoneSummary(id=z.id, name=z.name) for z in b.zones],
            )
            for b in rows
        ]

    def import_occupancy_schedule(
        self, building_id: int, csv_content: str
    ) -> ImportResult:
        errors: list[OccupancyImportError] = []

        if not csv_content or not csv_content.strip():
            errors.append(OccupancyImportError(message="file is empty"))
            raise ImportFailure(errors)

        building = self.db.get(BuildingModel, building_id)
        if building is None:
            errors.append(
                OccupancyImportError(message=f"building_id {building_id} not found")
            )
            raise ImportFailure(errors)
        valid_zone_ids = {z.id for z in building.zones}

        reader = csv.reader(io.StringIO(csv_content))
        try:
            header = next(reader)
        except StopIteration:
            errors.append(OccupancyImportError(message="file is empty"))
            raise ImportFailure(errors)

        if [h.strip() for h in header] != EXPECTED_HEADER:
            errors.append(
                OccupancyImportError(
                    message=(
                        f"header mismatch: expected {EXPECTED_HEADER}, "
                        f"got {header}"
                    )
                )
            )
            raise ImportFailure(errors)

        records: list[OccupancyRecordInput] = []
        for i, row in enumerate(reader, start=2):  # header is line 1
            if not row or all(cell.strip() == "" for cell in row):
                continue
            if len(row) != 3:
                errors.append(
                    OccupancyImportError(
                        row=i,
                        field=None,
                        message=f"row {i} has {len(row)} columns, expected 3",
                    )
                )
                continue

            zone_id_raw, timestamp_raw, count_raw = (c.strip() for c in row)

            try:
                zone_id = int(zone_id_raw)
            except ValueError:
                errors.append(
                    OccupancyImportError(
                        row=i, field="zone_id",
                        message=f"row {i}: zone_id must be an integer",
                    )
                )
                continue
            if zone_id not in valid_zone_ids:
                errors.append(
                    OccupancyImportError(
                        row=i, field="zone_id",
                        message=(
                            f"row {i}: zone_id {zone_id} does not belong to "
                            f"building {building_id}"
                        ),
                    )
                )
                continue

            try:
                ts = datetime.fromisoformat(timestamp_raw)
            except ValueError:
                errors.append(
                    OccupancyImportError(
                        row=i, field="timestamp",
                        message=f"row {i}: timestamp not ISO 8601",
                    )
                )
                continue

            try:
                count = int(count_raw)
            except ValueError:
                errors.append(
                    OccupancyImportError(
                        row=i, field="occupancy_count",
                        message=f"row {i}: occupancy_count must be an integer",
                    )
                )
                continue
            if count < 0:
                errors.append(
                    OccupancyImportError(
                        row=i, field="occupancy_count",
                        message=f"row {i}: occupancy_count must be non-negative",
                    )
                )
                continue

            records.append(
                OccupancyRecordInput(
                    zone_id=zone_id, timestamp=ts, occupancy_count=count
                )
            )

        if errors:
            raise ImportFailure(errors)

        if not records:
            raise ImportFailure(
                [OccupancyImportError(message="no data rows found")]
            )

        count = self.occupancy_repository.save_all(records)
        return ImportResult(records_imported=count)
