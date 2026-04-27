import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import building, forecasting
from app.infrastructure.adapters.forecast_adapters import use_test_doubles

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


if os.environ.get("TESTING") == "1":
    use_test_doubles()
    from app.api.routes import test_support  # noqa: WPS433

    app.include_router(test_support.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
