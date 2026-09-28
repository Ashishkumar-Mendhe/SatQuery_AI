"""SQLAlchemy models for SatQuery domain persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from satquery.db.base import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class WorkspaceModel(Base):
    """Container representing a user workspace session."""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Analysis Workspace")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )

    aois: Mapped[list[AoiModel]] = relationship(
        "AoiModel", back_populates="workspace", cascade="all, delete-orphan"
    )
    scenes: Mapped[list[SavedSceneModel]] = relationship(
        "SavedSceneModel", back_populates="workspace", cascade="all, delete-orphan"
    )
    results: Mapped[list[AnalysisResultModel]] = relationship(
        "AnalysisResultModel", back_populates="workspace", cascade="all, delete-orphan"
    )
    reports: Mapped[list[ReportModel]] = relationship(
        "ReportModel", back_populates="workspace", cascade="all, delete-orphan"
    )


class AoiModel(Base):
    """Persisted Area of Interest."""

    __tablename__ = "aois"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="polygon")
    area_sqkm: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    geometry_json: Mapped[str] = mapped_column(Text, nullable=False)
    bounds_json: Mapped[str] = mapped_column(Text, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="valid")
    validation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )

    workspace: Mapped[WorkspaceModel | None] = relationship("WorkspaceModel", back_populates="aois")


class SavedSceneModel(Base):
    """Persisted satellite scene reference within a workspace."""

    __tablename__ = "saved_scenes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    collection_id: Mapped[str] = mapped_column(String(128), nullable=False)
    scene_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="primary")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    workspace: Mapped[WorkspaceModel | None] = relationship(
        "WorkspaceModel", back_populates="scenes"
    )


class AnalysisResultModel(Base):
    """Persisted historical analysis or query result."""

    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True
    )
    analysis_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    workspace: Mapped[WorkspaceModel | None] = relationship(
        "WorkspaceModel", back_populates="results"
    )


class ReportModel(Base):
    """Persisted report record and snapshot metadata."""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True
    )
    result_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )

    workspace: Mapped[WorkspaceModel | None] = relationship(
        "WorkspaceModel", back_populates="reports"
    )
