"""API routes for workspace sessions, saved AOIs, and analysis history persistence."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, select

from satquery.api.dependencies import get_database
from satquery.db.models import (
    AnalysisResultModel,
    AoiModel,
    WorkspaceModel,
)
from satquery.db.session import Database

router = APIRouter(tags=["persistence"])


# Pydantic Schemas
class AoiRecordCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source: str = Field(default="polygon")
    area_sqkm: float = Field(default=0.0)
    geometry: dict[str, Any]
    bounds: list[float]
    workspace_id: str | None = None
    validation_status: str = Field(default="valid")
    validation_json: dict[str, Any] | None = None


class AoiRecordResponse(BaseModel):
    id: str
    workspace_id: str | None
    name: str
    source: str
    area_sqkm: float
    geometry: dict[str, Any]
    bounds: list[float]
    validation_status: str
    created_at: datetime
    updated_at: datetime


class AnalysisHistoryCreate(BaseModel):
    analysis_type: str
    title: str
    query_text: str | None = None
    result: dict[str, Any]
    workspace_id: str | None = None


class AnalysisHistoryResponse(BaseModel):
    id: str
    workspace_id: str | None
    analysis_type: str
    title: str
    query_text: str | None
    status: str
    result: dict[str, Any]
    created_at: datetime


class WorkspaceCreate(BaseModel):
    name: str = Field(default="Analysis Workspace")
    state: str = Field(default="active")


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    state: str
    created_at: datetime
    updated_at: datetime
    aois: list[AoiRecordResponse] = []
    results_count: int = 0
    reports_count: int = 0


# Workspace routes
@router.get(
    "/workspaces", response_model=list[WorkspaceResponse], summary="List persisted workspaces"
)
async def list_workspaces(
    database: Annotated[Database, Depends(get_database)],
) -> list[WorkspaceResponse]:
    async with database.session() as session:
        stmt = select(WorkspaceModel).order_by(desc(WorkspaceModel.updated_at))
        result = await session.execute(stmt)
        models = result.scalars().all()

        responses: list[WorkspaceResponse] = []
        for ws in models:
            aoi_stmt = select(AoiModel).where(AoiModel.workspace_id == ws.id)
            aois_res = await session.execute(aoi_stmt)
            aoi_models = aois_res.scalars().all()

            aoi_list = [
                AoiRecordResponse(
                    id=a.id,
                    workspace_id=a.workspace_id,
                    name=a.name,
                    source=a.source,
                    area_sqkm=a.area_sqkm,
                    geometry=json.loads(a.geometry_json),
                    bounds=json.loads(a.bounds_json),
                    validation_status=a.validation_status,
                    created_at=a.created_at,
                    updated_at=a.updated_at,
                )
                for a in aoi_models
            ]

            responses.append(
                WorkspaceResponse(
                    id=ws.id,
                    name=ws.name,
                    state=ws.state,
                    created_at=ws.created_at,
                    updated_at=ws.updated_at,
                    aois=aoi_list,
                    results_count=0,
                    reports_count=0,
                )
            )
        return responses


@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
async def create_workspace(
    payload: WorkspaceCreate,
    database: Annotated[Database, Depends(get_database)],
) -> WorkspaceResponse:
    ws_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    model = WorkspaceModel(
        id=ws_id,
        name=payload.name,
        state=payload.state,
        created_at=now,
        updated_at=now,
    )
    async with database.session() as session:
        session.add(model)
        await session.commit()
        await session.refresh(model)

    return WorkspaceResponse(
        id=model.id,
        name=model.name,
        state=model.state,
        created_at=model.created_at,
        updated_at=model.updated_at,
        aois=[],
        results_count=0,
        reports_count=0,
    )


@router.delete("/workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: str,
    database: Annotated[Database, Depends(get_database)],
) -> None:
    async with database.session() as session:
        stmt = delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
        await session.execute(stmt)
        await session.commit()


# AOI Persistence routes
@router.get("/aois", response_model=list[AoiRecordResponse], summary="List all saved AOIs")
async def list_saved_aois(
    database: Annotated[Database, Depends(get_database)],
    workspace_id: str | None = Query(default=None),
) -> list[AoiRecordResponse]:
    async with database.session() as session:
        stmt = select(AoiModel).order_by(desc(AoiModel.updated_at))
        if workspace_id:
            stmt = stmt.where(AoiModel.workspace_id == workspace_id)
        result = await session.execute(stmt)
        models = result.scalars().all()

        return [
            AoiRecordResponse(
                id=a.id,
                workspace_id=a.workspace_id,
                name=a.name,
                source=a.source,
                area_sqkm=a.area_sqkm,
                geometry=json.loads(a.geometry_json),
                bounds=json.loads(a.bounds_json),
                validation_status=a.validation_status,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in models
        ]


@router.post(
    "/aois",
    response_model=AoiRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save an Area of Interest",
)
async def save_aoi(
    payload: AoiRecordCreate,
    database: Annotated[Database, Depends(get_database)],
) -> AoiRecordResponse:
    aoi_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    model = AoiModel(
        id=aoi_id,
        workspace_id=payload.workspace_id,
        name=payload.name,
        source=payload.source,
        area_sqkm=payload.area_sqkm,
        geometry_json=json.dumps(payload.geometry),
        bounds_json=json.dumps(payload.bounds),
        validation_status=payload.validation_status,
        validation_json=json.dumps(payload.validation_json) if payload.validation_json else None,
        created_at=now,
        updated_at=now,
    )
    async with database.session() as session:
        session.add(model)
        await session.commit()
        await session.refresh(model)

    return AoiRecordResponse(
        id=model.id,
        workspace_id=model.workspace_id,
        name=model.name,
        source=model.source,
        area_sqkm=model.area_sqkm,
        geometry=payload.geometry,
        bounds=payload.bounds,
        validation_status=model.validation_status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.delete("/aois/{aoi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_aoi(
    aoi_id: str,
    database: Annotated[Database, Depends(get_database)],
) -> None:
    async with database.session() as session:
        stmt = delete(AoiModel).where(AoiModel.id == aoi_id)
        await session.execute(stmt)
        await session.commit()


# Analysis History routes
@router.get(
    "/history", response_model=list[AnalysisHistoryResponse], summary="List analysis history"
)
async def list_analysis_history(
    database: Annotated[Database, Depends(get_database)],
    workspace_id: str | None = Query(default=None),
) -> list[AnalysisHistoryResponse]:
    async with database.session() as session:
        stmt = select(AnalysisResultModel).order_by(desc(AnalysisResultModel.created_at))
        if workspace_id:
            stmt = stmt.where(AnalysisResultModel.workspace_id == workspace_id)
        result = await session.execute(stmt)
        models = result.scalars().all()

        return [
            AnalysisHistoryResponse(
                id=r.id,
                workspace_id=r.workspace_id,
                analysis_type=r.analysis_type,
                title=r.title,
                query_text=r.query_text,
                status=r.status,
                result=json.loads(r.result_json),
                created_at=r.created_at,
            )
            for r in models
        ]


@router.post(
    "/history",
    response_model=AnalysisHistoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an analysis result to history",
)
async def record_analysis_history(
    payload: AnalysisHistoryCreate,
    database: Annotated[Database, Depends(get_database)],
) -> AnalysisHistoryResponse:
    result_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    model = AnalysisResultModel(
        id=result_id,
        workspace_id=payload.workspace_id,
        analysis_type=payload.analysis_type,
        title=payload.title,
        query_text=payload.query_text,
        status="completed",
        result_json=json.dumps(payload.result),
        created_at=now,
    )
    async with database.session() as session:
        session.add(model)
        await session.commit()
        await session.refresh(model)

    return AnalysisHistoryResponse(
        id=model.id,
        workspace_id=model.workspace_id,
        analysis_type=model.analysis_type,
        title=model.title,
        query_text=model.query_text,
        status=model.status,
        result=payload.result,
        created_at=model.created_at,
    )


@router.delete("/history/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_result(
    result_id: str,
    database: Annotated[Database, Depends(get_database)],
) -> None:
    async with database.session() as session:
        stmt = delete(AnalysisResultModel).where(AnalysisResultModel.id == result_id)
        await session.execute(stmt)
        await session.commit()
