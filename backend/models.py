from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PipelineSession(Base):
    __tablename__ = "pipeline_sessions"

    id = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="running", index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    progress = Column(Integer, nullable=False, default=0)
    current_stage = Column(String, nullable=True)
    inputs = Column(JSON, nullable=False, default=dict)
    outputs = Column(JSON, nullable=False, default=dict)
    ai_interventions = Column(JSON, nullable=False, default=list)
    logs = Column(JSON, nullable=False, default=list)
    stages = Column(JSON, nullable=False, default=dict)
    error = Column(Text, nullable=True)

