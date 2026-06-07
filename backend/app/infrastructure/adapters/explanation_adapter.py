"""ExplanationAdapter — UC8 boundary.

The Protocol declares the contract. The production binding raises
NotImplementedError (real Claude API wiring deferred per A1). The acceptance
test double is defined inline below, matching the pattern of
``optimization_adapter.py`` so the FastAPI app can wire it without importing
the ``tests`` package at runtime.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from app.domain.explanation import ExplanationInputs


class ExplanationAdapter(Protocol):
    def explain(
        self,
        recommendation_id: int,
        inputs: ExplanationInputs,
    ) -> tuple[str, dict, str]:
        """Return (text, factors, model_version)."""
        ...


# -- Production stub ---------------------------------------------------------


class _NotWiredExplanation:
    def explain(
        self,
        recommendation_id: int,
        inputs: ExplanationInputs,
    ) -> tuple[str, dict, str]:
        raise NotImplementedError(
            "real ExplanationAdapter not wired (UC8 deferred)"
        )


# -- Deterministic test double ----------------------------------------------


_DOUBLE_MODEL_VERSION = "explanation-double-v1"


def _fmt_savings(value: Decimal) -> str:
    return f"{Decimal(value):.3f}"


class ExplanationAdapterDouble:
    """Deterministic templated explanation generator.

    The text contains case-insensitive ``energy``, ``comfort``, ``occupancy``
    substrings plus the formatted savings, the comfort_impact word, and the
    integer occupancy count. The invocation counter is exposed via
    ``calls_count`` so S03 can verify idempotency.
    """

    def __init__(self) -> None:
        self._calls = 0

    @property
    def calls_count(self) -> int:
        return self._calls

    def reset(self) -> None:
        self._calls = 0

    def explain(
        self,
        recommendation_id: int,
        inputs: ExplanationInputs,
    ) -> tuple[str, dict, str]:
        self._calls += 1
        savings = _fmt_savings(inputs.projected_savings_kwh)
        impact = inputs.comfort_impact
        count = int(inputs.occupancy_count)
        text = (
            f"This recommendation projects energy savings of {savings} kWh "
            f"with {impact} comfort impact for a zone currently showing "
            f"{count} occupants in the latest occupancy snapshot."
        )
        factors = {
            "energy": f"{savings} kWh",
            "comfort": impact,
            "occupancy": f"{count} occupants",
        }
        return text, factors, _DOUBLE_MODEL_VERSION


# -- Module-level registry --------------------------------------------------


class ExplanationRegistry:
    explanation: ExplanationAdapter

    def __init__(self) -> None:
        self.explanation = _NotWiredExplanation()


registry = ExplanationRegistry()


def use_test_doubles() -> None:
    registry.explanation = ExplanationAdapterDouble()
