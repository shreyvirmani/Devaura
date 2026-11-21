"""Devaura Evaluation & Benchmark Relational Database Models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvaluationRunRecord(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    localization_accuracy_top1: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    localization_accuracy_top3: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    root_cause_accuracy: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence_precision: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    patch_success_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    verification_pass_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    regression_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    false_repair_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    average_attempts: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    safety_violations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    summary_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    bug_results: Mapped[List["EvaluationBugResultRecord"]] = relationship(
        "EvaluationBugResultRecord", back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class EvaluationBugResultRecord(Base):
    __tablename__ = "evaluation_bug_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    bug_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(String(30), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    localization_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    root_cause_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    patch_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    regression_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts_used: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    failure_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    result_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped["EvaluationRunRecord"] = relationship("EvaluationRunRecord", back_populates="bug_results")
