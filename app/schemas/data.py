from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DatasetVersionResponse(BaseModel):
    id: UUID
    dataset_id: UUID
    version: int
    symbols: list[str]
    provider: str
    frequency: str
    start_timestamp: datetime
    end_timestamp: datetime
    schema_version: str
    row_count: int
    checksum: str
    storage_location: str
    adjustment_policy: str
    quality_report: dict[str, Any]
    model_config = {"from_attributes": True}


class DatasetResponse(BaseModel):
    id: UUID
    name: str
    model_config = {"from_attributes": True}


class DatasetLineageResponse(BaseModel):
    child_dataset_version_id: UUID
    parent_dataset_version_id: UUID | None
    transformation: str
    transformation_version: str
    parameters: dict[str, Any]
    created_at: datetime
    model_config = {"from_attributes": True}


class DatasetSnapshotCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    dataset_version_ids: list[UUID] = Field(min_length=1)
    feature_set: list[dict[str, Any]] = Field(default_factory=list)


class DatasetSnapshotResponse(BaseModel):
    id: UUID
    name: str
    dataset_version_ids: list[str]
    universe: list[str]
    feature_set: list[dict[str, Any]]
    fingerprint: str
    created_at: datetime
    model_config = {"from_attributes": True}


class FeatureVersionResponse(BaseModel):
    id: UUID
    feature_definition_id: UUID
    version: str
    input_schema: dict[str, Any]
    parameters: dict[str, Any]
    implementation: str
    lookback: int
    code_metadata: dict[str, Any]
    model_config = {"from_attributes": True}


class FeatureResponse(BaseModel):
    id: UUID
    name: str
    model_config = {"from_attributes": True}


class FeatureRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=32)
    implementation: str
    lookback: int = Field(ge=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class FeatureMaterializeRequest(BaseModel):
    dataset_version_id: UUID
    parameters: dict[str, Any] = Field(default_factory=dict)


class FeatureMaterializationResponse(BaseModel):
    dataset_version_id: UUID
    feature_version_id: UUID
    row_count: int
    columns: list[str]
