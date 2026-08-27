from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alternative_data.service import AlternativeDataService
from app.data.service import DataLineageService, FeatureStore
from app.db.session import get_session
from app.models.data import (
    Dataset,
    DatasetSnapshot,
    DatasetVersion,
    FeatureDefinition,
    FeatureVersion,
)
from app.schemas.data import (
    DatasetLineageResponse,
    DatasetResponse,
    DatasetSnapshotCreateRequest,
    DatasetSnapshotResponse,
    DatasetVersionResponse,
    FeatureMaterializationResponse,
    FeatureMaterializeRequest,
    FeatureRegisterRequest,
    FeatureResponse,
    FeatureVersionResponse,
)

router = APIRouter(tags=["research-data"])


@router.get("/data-catalog")
def data_catalog(session: Annotated[Session, Depends(get_session)]) -> dict[str, object]:
    """Agent- and dashboard-safe catalog: only persisted inputs are advertised."""
    return AlternativeDataService(session).catalog()


@router.get("/datasets", response_model=list[DatasetResponse])
def list_datasets(session: Annotated[Session, Depends(get_session)]) -> list[DatasetResponse]:
    return [
        DatasetResponse.model_validate(item)
        for item in session.scalars(select(Dataset).order_by(Dataset.name))
    ]


@router.get("/datasets/{dataset_id}/versions", response_model=list[DatasetVersionResponse])
def list_versions(
    dataset_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[DatasetVersionResponse]:
    if session.get(Dataset, dataset_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dataset not found")
    return [
        DatasetVersionResponse.model_validate(item)
        for item in session.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version)
        )
    ]


@router.get("/datasets/{dataset_id}/lineage", response_model=list[DatasetLineageResponse])
def dataset_lineage(
    dataset_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[DatasetLineageResponse]:
    if session.get(Dataset, dataset_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dataset not found")
    return [
        DatasetLineageResponse.model_validate(item)
        for item in DataLineageService(session).lineage(dataset_id)
    ]


@router.get("/datasets/snapshots", response_model=list[DatasetSnapshotResponse])
def list_snapshots(
    session: Annotated[Session, Depends(get_session)],
) -> list[DatasetSnapshotResponse]:
    return [
        DatasetSnapshotResponse.model_validate(item)
        for item in session.scalars(select(DatasetSnapshot).order_by(DatasetSnapshot.created_at))
    ]


@router.post(
    "/datasets/snapshots",
    response_model=DatasetSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    request: DatasetSnapshotCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> DatasetSnapshotResponse:
    snapshot = DataLineageService(session).create_snapshot(
        request.name,
        request.dataset_version_ids,
        feature_set=request.feature_set,
    )
    session.commit()
    return DatasetSnapshotResponse.model_validate(snapshot)


@router.get("/features", response_model=list[FeatureResponse])
def list_features(session: Annotated[Session, Depends(get_session)]) -> list[FeatureResponse]:
    return [
        FeatureResponse.model_validate(item)
        for item in session.scalars(select(FeatureDefinition).order_by(FeatureDefinition.name))
    ]


@router.post(
    "/features", response_model=FeatureVersionResponse, status_code=status.HTTP_201_CREATED
)
def register_feature(
    request: FeatureRegisterRequest, session: Annotated[Session, Depends(get_session)]
) -> FeatureVersionResponse:
    feature = FeatureStore(session).register(
        name=request.name,
        version=request.version,
        implementation=request.implementation,
        lookback=request.lookback,
        parameters=request.parameters,
    )
    session.commit()
    return FeatureVersionResponse.model_validate(feature)


@router.get("/features/{feature_id}/versions", response_model=list[FeatureVersionResponse])
def feature_versions(
    feature_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[FeatureVersionResponse]:
    if session.get(FeatureDefinition, feature_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feature not found")
    return [
        FeatureVersionResponse.model_validate(item)
        for item in session.scalars(
            select(FeatureVersion)
            .where(FeatureVersion.feature_definition_id == feature_id)
            .order_by(FeatureVersion.version)
        )
    ]


@router.post(
    "/features/{feature_version_id}/materialize",
    response_model=FeatureMaterializationResponse,
)
def materialize_feature(
    feature_version_id: UUID,
    request: FeatureMaterializeRequest,
    session: Annotated[Session, Depends(get_session)],
) -> FeatureMaterializationResponse:
    frame = FeatureStore(session).compute(
        request.dataset_version_id,
        feature_version_id,
        parameters=request.parameters,
    )
    session.commit()
    return FeatureMaterializationResponse(
        dataset_version_id=request.dataset_version_id,
        feature_version_id=feature_version_id,
        row_count=frame.height,
        columns=frame.columns,
    )
