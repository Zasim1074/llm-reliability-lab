from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class CacheEntry(Base):
    __tablename__ = "cache_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    namespace: Mapped[str] = mapped_column(String(100), index=True)
    query: Mapped[str] = mapped_column(Text)
    normalized_query: Mapped[str] = mapped_column(String(1000), index=True)
    response: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[list[float]]] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    invalidated: Mapped[bool] = mapped_column(Boolean, default=False)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    type: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), index=True, default="completed")
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    dataset_ref: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EvaluationRecord(Base):
    __tablename__ = "evaluation_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    prompt: Mapped[str] = mapped_column(Text)
    reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    candidate: Mapped[str] = mapped_column(Text)
    scores: Mapped[dict] = mapped_column(JSON)
    overall: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SecurityRecord(Base):
    __tablename__ = "security_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    cases: Mapped[int] = mapped_column(Integer)
    blocked: Mapped[int] = mapped_column(Integer)
    successful: Mapped[int] = mapped_column(Integer)
    results: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
