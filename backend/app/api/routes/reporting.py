"""UC9 GenerateDailySavingsReport — API route handlers."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.savings_report import (
    DailySavingsReportResult,
    SavingsForcedDbError,
    SavingsInputsMissing,
)
from app.services.reporting_service import ReportingService


router = APIRouter(prefix="/api/buildings", tags=["savings-reports"])


class SavingsReportRunRequest(BaseModel):
    report_date: Optional[str] = None


class SavingsReportLineResponse(BaseModel):
    zone_id: int
    baseline_kwh: Decimal
    actual_kwh: Decimal
    savings_kwh: Decimal
    savings_pct: Decimal
    anomaly_flag: bool
    anomaly_reason: Optional[str] = None


class DailySavingsReportResponse(BaseModel):
    report_id: Optional[int]
    building_id: int
    report_date: date
    total_baseline_kwh: Decimal
    total_actual_kwh: Decimal
    total_savings_kwh: Decimal
    total_savings_pct: Decimal
    lines: List[SavingsReportLineResponse]
    cached: bool
    elapsed_ms: float
    generated_at: Optional[datetime] = None


def _to_response(result: DailySavingsReportResult) -> DailySavingsReportResponse:
    return DailySavingsReportResponse(
        report_id=result.report_id,
        building_id=result.building_id,
        report_date=result.report_date,
        total_baseline_kwh=result.total_baseline_kwh,
        total_actual_kwh=result.total_actual_kwh,
        total_savings_kwh=result.total_savings_kwh,
        total_savings_pct=result.total_savings_pct,
        lines=[
            SavingsReportLineResponse(
                zone_id=ln.zone_id,
                baseline_kwh=ln.baseline_kwh,
                actual_kwh=ln.actual_kwh,
                savings_kwh=ln.savings_kwh,
                savings_pct=ln.savings_pct,
                anomaly_flag=ln.anomaly_flag,
                anomaly_reason=ln.anomaly_reason,
            )
            for ln in result.lines
        ],
        cached=result.cached,
        elapsed_ms=result.elapsed_ms,
        generated_at=result.generated_at,
    )


@router.post(
    "/{building_id}/savings-reports/run",
    response_model=DailySavingsReportResponse,
)
def run_savings_report(
    building_id: int,
    body: SavingsReportRunRequest,
    db: Session = Depends(get_db),
) -> DailySavingsReportResponse:
    if body.report_date is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"missingInputs": ["report_date"]},
        )
    service = ReportingService(db)
    try:
        result = service.generate(building_id, body.report_date)
    except SavingsInputsMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"missingInputs": exc.missing_inputs},
        )
    except SavingsForcedDbError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "db_error"},
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "savings_report_error"},
        )
    return _to_response(result)


@router.get(
    "/{building_id}/savings-reports",
    response_model=DailySavingsReportResponse,
)
def get_savings_report(
    building_id: int,
    date_str: str = Query(..., alias="date"),
    db: Session = Depends(get_db),
) -> DailySavingsReportResponse:
    from app.infrastructure.repositories.savings_report_repository import (
        SavingsReportRepository,
    )
    from datetime import date as _date

    try:
        report_date = _date.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"missingInputs": ["report_date"]},
        )

    repo = SavingsReportRepository(db)
    existing = repo.get_for_building_date(building_id, report_date)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "no_report"},
        )
    lines = repo.lines_for_report(existing.id)
    result = DailySavingsReportResult(
        report_id=existing.id,
        building_id=existing.building_id,
        report_date=existing.report_date,
        total_baseline_kwh=existing.total_baseline_kwh,
        total_actual_kwh=existing.total_actual_kwh,
        total_savings_kwh=existing.total_savings_kwh,
        total_savings_pct=existing.total_savings_pct,
        lines=[
            type("L", (), dict(
                zone_id=ln.zone_id,
                baseline_kwh=ln.baseline_kwh,
                actual_kwh=ln.actual_kwh,
                savings_kwh=ln.savings_kwh,
                savings_pct=ln.savings_pct,
                anomaly_flag=bool(ln.anomaly_flag),
                anomaly_reason=ln.anomaly_reason,
            ))
            for ln in lines
        ],
        cached=True,
        elapsed_ms=0.0,
        generated_at=existing.generated_at,
    )
    return _to_response(result)
