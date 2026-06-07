import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    building,
    comfort_risk,
    explanations,
    forecasting,
    plans,
    recommendations,
    reporting,
)
from app.infrastructure.adapters.device_control_adapter import (
    use_test_doubles as use_device_control_test_doubles,
)
from app.infrastructure.adapters.explanation_adapter import (
    use_test_doubles as use_explanation_test_doubles,
)
from app.infrastructure.adapters.forecast_adapters import use_test_doubles
from app.infrastructure.adapters.optimization_adapter import (
    use_test_doubles as use_optimization_test_doubles,
)

app = FastAPI(title="Smart Building Energy Optimization Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(building.router)
app.include_router(forecasting.router)
app.include_router(recommendations.router)
app.include_router(plans.router)
app.include_router(comfort_risk.router)
app.include_router(explanations.router)
app.include_router(reporting.router)


if os.environ.get("TESTING") == "1":
    use_test_doubles()
    use_optimization_test_doubles()
    use_device_control_test_doubles()
    use_explanation_test_doubles()
    from app.api.routes import test_support  # noqa: WPS433

    app.include_router(test_support.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
