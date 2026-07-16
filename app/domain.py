from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(StrEnum):
    OPEN = "open"
    PLANNED = "planned"
    APPROVED = "approved"
    RESOLVED = "resolved"


class ExecutionStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"


class Evidence(BaseModel):
    source: str
    observed_at: datetime = Field(default_factory=utcnow)
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    rule_id: str
    title: str
    severity: Severity
    resource_id: str
    description: str
    evidence: list[Evidence]
    remediation_action: str
    rollback_action: str | None = None
    status: FindingStatus = FindingStatus.OPEN
    created_at: datetime = Field(default_factory=utcnow)


class ScanResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    provider: str
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime = Field(default_factory=utcnow)
    findings: list[Finding]


class RemediationPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    finding_id: str
    action: str
    target: str
    rationale: str
    expected_impact: str
    rollback: str | None = None
    requires_approval: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class ApprovalRequest(BaseModel):
    approver: str = Field(min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=500)


class Approval(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    plan_id: str
    approver: str
    comment: str | None = None
    approved_at: datetime = Field(default_factory=utcnow)


class Execution(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    plan_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING_APPROVAL
    verification: str | None = None
    audit: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class ScanRequest(BaseModel):
    provider: str = "mock"
