"""Re-export of the in-tree UC8 ExplanationAdapter double.

Keeping the canonical class in ``backend/app/infrastructure/adapters/
explanation_adapter.py`` mirrors the ``OptimizationAdapterDouble`` /
``DeviceStateAdapterDouble`` pattern so the FastAPI app can wire it under
``TESTING=1`` without importing the ``tests`` package at runtime. This module
exists so the harness-design convention ("test doubles live under
tests/acceptance/support/test_doubles/") still resolves a real file.
"""
from app.infrastructure.adapters.explanation_adapter import (  # noqa: F401
    ExplanationAdapterDouble,
)
