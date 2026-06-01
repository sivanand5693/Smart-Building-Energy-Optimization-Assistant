"""UC4 OptimizationAdapter test double.

The active in-process double lives at:
    backend/app/infrastructure/adapters/optimization_adapter.py::OptimizationAdapterDouble

This module re-exports it so acceptance tooling can `import` it via the
expected path under tests/acceptance/support/test_doubles/.
"""
from app.infrastructure.adapters.optimization_adapter import (
    OptimizationAdapterDouble,
)

__all__ = ["OptimizationAdapterDouble"]
