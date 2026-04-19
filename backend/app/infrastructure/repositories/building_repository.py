from sqlalchemy.orm import Session

from app.domain.building import BuildingProfileInput
from app.infrastructure.models import (
    BuildingModel,
    ZoneModel,
    DeviceModel,
    OperatingScheduleModel,
)


class BuildingRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, profile: BuildingProfileInput) -> BuildingModel:
        building = BuildingModel(name=profile.building_name)
        for zone_input in profile.zones:
            zone = ZoneModel(name=zone_input.name)
            for device_input in zone_input.devices:
                zone.devices.append(
                    DeviceModel(
                        device_type=device_input.device_type,
                        device_name=device_input.device_name,
                    )
                )
            building.zones.append(zone)
        for schedule_input in profile.operating_schedules:
            building.operating_schedules.append(
                OperatingScheduleModel(
                    days_of_week=schedule_input.days_of_week,
                    start_time=schedule_input.start_time,
                    end_time=schedule_input.end_time,
                )
            )
        self.db.add(building)
        self.db.commit()
        self.db.refresh(building)
        return building
