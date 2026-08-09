from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.memory.schemas import MemoryLessonResponse, MemorySearchRequest, MemorySearchResult
from app.memory.service import ResearchMemoryService

router = APIRouter(tags=["memory"])


@router.get("/experiments/{experiment_id}/memory", response_model=list[MemoryLessonResponse])
def get_experiment_memory(
    experiment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[MemoryLessonResponse]:
    return [
        MemoryLessonResponse.model_validate(lesson)
        for lesson in ResearchMemoryService(session).get_for_experiment(experiment_id)
    ]


@router.post("/memory/search", response_model=list[MemorySearchResult])
def search_memory(
    request: MemorySearchRequest,
    session: Annotated[Session, Depends(get_session)],
) -> list[MemorySearchResult]:
    return ResearchMemoryService(session).search(request)
