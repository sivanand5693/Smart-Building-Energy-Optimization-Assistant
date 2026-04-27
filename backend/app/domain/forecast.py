from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class ForecastFeatures:
    occupancy_count: int
    weather_temp_c: float
    device_on_count: int


@dataclass
class ZoneForecast:
    zone_id: int
    zone_name: str
    timestamp: datetime
    predicted_kwh: Decimal
    model_version: str


@dataclass
class ForecastRunResult:
    building_id: int
    run_timestamp: datetime
    elapsed_ms: float
    forecasts: list[ZoneForecast] = field(default_factory=list)


class ForecastInputsMissing(Exception):
    def __init__(self, missing_inputs: list[str]):
        self.missing_inputs = missing_inputs
        super().__init__(f"missing inputs: {missing_inputs}")
