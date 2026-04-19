from datetime import datetime
from pydantic import BaseModel


class OccupancyRecordInput(BaseModel):
    zone_id: int
    timestamp: datetime
    occupancy_count: int


class ImportResult(BaseModel):
    records_imported: int


class ImportError(BaseModel):
    row: int | None = None  # None for header / file-level errors
    field: str | None = None
    message: str


class ImportFailure(Exception):
    def __init__(self, errors: list[ImportError]):
        self.errors = errors
        super().__init__(str([e.message for e in errors]))
