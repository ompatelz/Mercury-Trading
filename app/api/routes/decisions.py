from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.governance.schemas import DecisionResponse
from app.governance.service import DecisionService

router = APIRouter(tags=["governance"])


@router.get("/decisions", response_model=list[DecisionResponse])
def list_decisions(
    session: Annotated[Session, Depends(get_session)],
    campaign_id: UUID | None = None,
    experiment_id: UUID | None = None,
    strategy_id: UUID | None = None,
    decision_type: str | None = None,
    outcome: str | None = None,
) -> list[DecisionResponse]:
    service = DecisionService(session)
    return [
        _response(service, item.id)
        for item in service.list_decisions(
            campaign_id=campaign_id,
            experiment_id=experiment_id,
            strategy_id=strategy_id,
            decision_type=decision_type,
            outcome=outcome,
        )
    ]


@router.get("/decisions/{decision_id}", response_model=DecisionResponse)
def get_decision(
    decision_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> DecisionResponse:
    return _response(DecisionService(session), decision_id)


@router.get("/experiments/{experiment_id}/decisions", response_model=list[DecisionResponse])
def experiment_decisions(
    experiment_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[DecisionResponse]:
    service = DecisionService(session)
    return [
        _response(service, item.id) for item in service.list_decisions(experiment_id=experiment_id)
    ]


@router.get("/campaigns/{campaign_id}/timeline", response_model=list[DecisionResponse])
def campaign_timeline(
    campaign_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[DecisionResponse]:
    service = DecisionService(session)
    return [
        _response(service, item.id)
        for item in reversed(service.list_decisions(campaign_id=campaign_id))
    ]


@router.get("/strategies/{strategy_id}/lineage", response_model=list[DecisionResponse])
def strategy_lineage(
    strategy_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[DecisionResponse]:
    service = DecisionService(session)
    return [_response(service, item.id) for item in service.list_decisions(strategy_id=strategy_id)]


def _response(service: DecisionService, decision_id: UUID) -> DecisionResponse:
    payload = service.explain(decision_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return DecisionResponse.model_validate(payload)
