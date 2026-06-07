"""UC8 ExplainRecommendation — API route handlers."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.domain.explanation import (
    ExplanationForcedDbError,
    ExplanationInputsMissing,
)
from app.services.explanation_service import ExplanationService


router = APIRouter(prefix="/api/recommendations", tags=["explanations"])


class ExplanationResponse(BaseModel):
    recommendation_id: int
    text: str
    factors: dict
    cached: bool
    elapsed_ms: float
    model_version: str
    generated_at: Optional[datetime] = None


@router.post(
    "/{recommendation_id}/explain",
    response_model=ExplanationResponse,
)
def explain_recommendation(
    recommendation_id: int,
    db: Session = Depends(get_db),
) -> ExplanationResponse:
    service = ExplanationService(db)
    try:
        result = service.explain(recommendation_id)
    except ExplanationInputsMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"missingInputs": exc.missing_inputs},
        )
    except ExplanationForcedDbError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "db_error"},
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "explanation_error"},
        )
    return ExplanationResponse(
        recommendation_id=result.recommendation_id,
        text=result.text,
        factors=result.factors,
        cached=result.cached,
        elapsed_ms=result.elapsed_ms,
        model_version=result.model_version,
        generated_at=result.generated_at,
    )


@router.get(
    "/{recommendation_id}/explanation",
    response_model=ExplanationResponse,
)
def get_explanation(
    recommendation_id: int,
    db: Session = Depends(get_db),
) -> ExplanationResponse:
    service = ExplanationService(db)
    result = service.get_existing(recommendation_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "no_explanation"},
        )
    return ExplanationResponse(
        recommendation_id=result.recommendation_id,
        text=result.text,
        factors=result.factors,
        cached=True,
        elapsed_ms=result.elapsed_ms,
        model_version=result.model_version,
        generated_at=result.generated_at,
    )
