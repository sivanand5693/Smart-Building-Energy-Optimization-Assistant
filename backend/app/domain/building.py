from datetime import time
from pydantic import BaseModel, Field


class DeviceInput(BaseModel):
    device_type: str = ""
    device_name: str | None = None


class ZoneInput(BaseModel):
    name: str = ""
    devices: list[DeviceInput] = Field(default_factory=list)


class OperatingScheduleInput(BaseModel):
    days_of_week: str = ""
    start_time: time
    end_time: time


class BuildingProfileInput(BaseModel):
    building_name: str = ""
    zones: list[ZoneInput] = Field(default_factory=list)
    operating_schedules: list[OperatingScheduleInput] = Field(default_factory=list)


class BuildingProfileResult(BaseModel):
    building_id: int
    name: str


class ZoneSummary(BaseModel):
    id: int
    name: str


class BuildingSummary(BaseModel):
    id: int
    name: str
    zones: list[ZoneSummary]


class ValidationFailure(Exception):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__(str(errors))
