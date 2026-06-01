from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from app.domain.recommendation import Candidate
from app.infrastructure.models import (
    DemandForecastModel,
    ZoneComfortConstraintModel,
)


# -- Protocol ----------------------------------------------------------------

class OptimizationAdapter(Protocol):
    def recommend(
        self,
        zone_id: int,
        forecast: DemandForecastModel,
        constraints: ZoneComfortConstraintModel,
    ) -> list[Candidate]: ...


# -- Production stub ---------------------------------------------------------

class _NotWiredOptimization:
    def recommend(
        self,
        zone_id: int,
        forecast: DemandForecastModel,
        constraints: ZoneComfortConstraintModel,
    ) -> list[Candidate]:
        raise NotImplementedError(
            "real OptimizationAdapter not wired (UC4 deferred)"
        )


# -- Deterministic test double ----------------------------------------------

class OptimizationAdapterDouble:
    """Deterministic recommender.

    Default behavior per zone: emits one candidate with setpoint_delta_f=+1.0,
    projected_savings_kwh = zone_id * 1.0 + 0.5, comfort_impact="minor".
    When `force_infeasible(zone_id)` is set, the candidate's delta is +50.0 so
    the service's feasibility filter drops it.
    """

    def __init__(self) -> None:
        self._forced_infeasible: set[int] = set()

    def force_infeasible(self, zone_id: int) -> None:
        self._forced_infeasible.add(zone_id)

    def reset(self) -> None:
        self._forced_infeasible.clear()

    def recommend(
        self,
        zone_id: int,
        forecast: DemandForecastModel,
        constraints: ZoneComfortConstraintModel,
    ) -> list[Candidate]:
        if zone_id in self._forced_infeasible:
            delta = Decimal("50.00")
        else:
            delta = Decimal("1.00")
        savings = (Decimal(zone_id) * Decimal("1.0") + Decimal("0.5")).quantize(
            Decimal("0.001")
        )
        return [
            Candidate(
                setpoint_delta_f=delta,
                projected_savings_kwh=savings,
                comfort_impact="minor",
                model_version="opt-double-1.0",
            )
        ]


# -- Module-level registry --------------------------------------------------

class OptimizationRegistry:
    optimization: OptimizationAdapter

    def __init__(self) -> None:
        self.optimization = _NotWiredOptimization()


registry = OptimizationRegistry()


def use_test_doubles() -> None:
    registry.optimization = OptimizationAdapterDouble()
