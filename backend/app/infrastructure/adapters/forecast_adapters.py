from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from app.domain.forecast import ForecastFeatures


# -- Protocols ---------------------------------------------------------------

class WeatherAdapter(Protocol):
    def current_for_building(self, building_id: int) -> dict | None: ...


class DeviceStateAdapter(Protocol):
    def current_for_zone(self, zone_id: int) -> dict | None: ...


class ForecastModelAdapter(Protocol):
    def predict(
        self, zone_id: int, features: ForecastFeatures
    ) -> tuple[Decimal, str]: ...


# -- Production stubs (UC3 acceptance does not require real impls) -----------

class _NotWiredWeather:
    def current_for_building(self, building_id: int) -> dict | None:
        raise NotImplementedError("real WeatherAdapter not wired (UC3 deferred)")


class _NotWiredDeviceState:
    def current_for_zone(self, zone_id: int) -> dict | None:
        raise NotImplementedError("real DeviceStateAdapter not wired (UC3 deferred)")


class _NotWiredForecastModel:
    def predict(
        self, zone_id: int, features: ForecastFeatures
    ) -> tuple[Decimal, str]:
        raise NotImplementedError("real ForecastModelAdapter not wired (UC3 deferred)")


# -- Deterministic test doubles ----------------------------------------------

class WeatherAdapterDouble:
    def __init__(self) -> None:
        self._store: dict[int, dict] = {}

    def seed(self, building_id: int, payload: dict) -> None:
        self._store[building_id] = payload

    def clear(self, building_id: int) -> None:
        self._store.pop(building_id, None)

    def reset(self) -> None:
        self._store.clear()

    def current_for_building(self, building_id: int) -> dict | None:
        return self._store.get(building_id)


class DeviceStateAdapterDouble:
    def __init__(self) -> None:
        self._store: dict[int, dict] = {}

    def seed(self, zone_id: int, payload: dict) -> None:
        self._store[zone_id] = payload

    def clear(self, zone_id: int) -> None:
        self._store.pop(zone_id, None)

    def reset(self) -> None:
        self._store.clear()

    def current_for_zone(self, zone_id: int) -> dict | None:
        return self._store.get(zone_id)


class ForecastModelDouble:
    """Deterministic predictor: predicted_kwh = zone_id*1.5 + occupancy*0.1."""

    def predict(
        self, zone_id: int, features: ForecastFeatures
    ) -> tuple[Decimal, str]:
        value = Decimal(zone_id) * Decimal("1.5") + Decimal(features.occupancy_count) * Decimal("0.1")
        return value.quantize(Decimal("0.001")), "double-1.0"


# -- Module-level registry (mutated by app startup) --------------------------

class AdapterRegistry:
    weather: WeatherAdapter
    device_state: DeviceStateAdapter
    forecast_model: ForecastModelAdapter

    def __init__(self) -> None:
        self.weather = _NotWiredWeather()
        self.device_state = _NotWiredDeviceState()
        self.forecast_model = _NotWiredForecastModel()


registry = AdapterRegistry()


def use_test_doubles() -> None:
    """Swap registry to deterministic doubles. Called at app startup when TESTING=1."""
    registry.weather = WeatherAdapterDouble()
    registry.device_state = DeviceStateAdapterDouble()
    registry.forecast_model = ForecastModelDouble()
