from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Protocol

from app.domain.applied_change import ApplyForcedDbError, DispatchOutcome


# -- Protocol ----------------------------------------------------------------


class DeviceControlAdapter(Protocol):
    def dispatch(
        self,
        device_id: int,
        zone_id: int,
        setpoint_delta_f: Decimal,
        run_timestamp: datetime,
        recommendation_id: int,
    ) -> DispatchOutcome:  # pragma: no cover
        ...


# -- Production stub ---------------------------------------------------------


class _NotWiredDeviceControl:
    def dispatch(
        self,
        device_id: int,
        zone_id: int,
        setpoint_delta_f: Decimal,
        run_timestamp: datetime,
        recommendation_id: int,
    ) -> DispatchOutcome:
        raise NotImplementedError(
            "real DeviceControlAdapter not wired (UC5 deferred)"
        )


# -- Deterministic test double ----------------------------------------------


class DeviceControlAdapterDouble:
    """Deterministic device-control double.

    - Default: returns dispatched/ok with latency 5 ms and logs the call.
    - `set_directive(rec_id, outcome, error_code, adapter_message, latency_ms)`
      programs the next dispatch for that recommendation_id.
    - `force_db_error_next_apply()` makes the next dispatch raise so the route
      maps it to 500 (atomicity test S15).
    """

    def __init__(self) -> None:
        self._directives: dict[int, dict] = {}
        self._calls: list[dict] = []
        self._force_db_error: bool = False

    def reset(self) -> None:
        self._directives.clear()
        self._calls.clear()
        self._force_db_error = False

    def set_directive(
        self,
        recommendation_id: int,
        outcome: str = "dispatched",
        error_code: Optional[str] = None,
        adapter_message: Optional[str] = None,
        latency_ms: Optional[int] = None,
    ) -> None:
        self._directives[recommendation_id] = {
            "outcome": outcome,
            "error_code": error_code,
            "adapter_message": adapter_message or (
                "ok" if outcome == "dispatched" else "directive failure"
            ),
            "latency_ms": 5 if latency_ms is None else latency_ms,
        }

    def force_db_error_next_apply(self) -> None:
        self._force_db_error = True

    def calls(self) -> list[dict]:
        return list(self._calls)

    def dispatch(
        self,
        device_id: int,
        zone_id: int,
        setpoint_delta_f: Decimal,
        run_timestamp: datetime,
        recommendation_id: int,
    ) -> DispatchOutcome:
        if self._force_db_error:
            self._force_db_error = False
            raise ApplyForcedDbError("forced_db_error_for_test")

        self._calls.append(
            {
                "recommendation_id": recommendation_id,
                "device_id": device_id,
                "zone_id": zone_id,
                "setpoint_delta_f": str(setpoint_delta_f),
            }
        )
        d = self._directives.get(recommendation_id)
        if d is None:
            return DispatchOutcome(
                status="dispatched",
                error_code=None,
                adapter_message="ok",
                latency_ms=5,
            )
        return DispatchOutcome(
            status=d["outcome"],
            error_code=d["error_code"],
            adapter_message=d["adapter_message"],
            latency_ms=d["latency_ms"],
        )


# -- Registry ---------------------------------------------------------------


class DeviceControlRegistry:
    device_control: DeviceControlAdapter

    def __init__(self) -> None:
        self.device_control = _NotWiredDeviceControl()


registry = DeviceControlRegistry()


def use_test_doubles() -> None:
    registry.device_control = DeviceControlAdapterDouble()
