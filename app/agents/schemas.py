from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AgentVersionResponse(BaseModel):
    id: UUID
    name: str
    version: str
    role: str
    model: str
    prompt_version: str
    config: dict[str, Any]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowVersionResponse(BaseModel):
    id: UUID
    name: str
    version: str
    backtester_version: str
    retrieval_config: dict[str, Any]
    tool_versions: dict[str, str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
