from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .db import (
    ApprovalRecord,
    ExecutionRecord,
    FindingRecord,
    RemediationPlanRecord,
    ScanRecord,
    create_session_factory,
)
from .domain import Approval, Execution, Finding, RemediationPlan, ScanResult


class Store(Protocol):
    def save_scan(self, scan: ScanResult) -> None: ...

    def list_findings(self) -> list[Finding]: ...

    def get_finding(self, finding_id: str) -> Finding | None: ...

    def save_finding(self, finding: Finding) -> None: ...

    def save_plan(self, plan: RemediationPlan) -> None: ...

    def get_plan(self, plan_id: str) -> RemediationPlan | None: ...

    def save_approval(self, approval: Approval) -> None: ...

    def has_approval(self, plan_id: str) -> bool: ...

    def save_execution(self, execution: Execution) -> None: ...

    def clear(self) -> None: ...


class MemoryStore:
    """MVP repository. Replace with PostgreSQL repository behind the same port."""

    def __init__(self) -> None:
        self.scans: dict[str, ScanResult] = {}
        self.findings: dict[str, Finding] = {}
        self.plans: dict[str, RemediationPlan] = {}
        self.approvals: dict[str, Approval] = {}
        self.executions: dict[str, Execution] = {}

    def save_scan(self, scan: ScanResult) -> None:
        self.scans[scan.id] = scan
        self.findings.update({finding.id: finding for finding in scan.findings})

    def list_findings(self) -> list[Finding]:
        return list(self.findings.values())

    def get_finding(self, finding_id: str) -> Finding | None:
        return self.findings.get(finding_id)

    def save_finding(self, finding: Finding) -> None:
        self.findings[finding.id] = finding

    def save_plan(self, plan: RemediationPlan) -> None:
        self.plans[plan.id] = plan

    def get_plan(self, plan_id: str) -> RemediationPlan | None:
        return self.plans.get(plan_id)

    def save_approval(self, approval: Approval) -> None:
        self.approvals[approval.plan_id] = approval

    def has_approval(self, plan_id: str) -> bool:
        return plan_id in self.approvals

    def save_execution(self, execution: Execution) -> None:
        self.executions[execution.id] = execution

    def clear(self) -> None:
        self.scans.clear()
        self.findings.clear()
        self.plans.clear()
        self.approvals.clear()
        self.executions.clear()


class SQLAlchemyStore:
    """Repository backed by SQLAlchemy.

    Use PostgreSQL in production via SOLOOPS_DATABASE_URL. SQLite is supported
    for local development and tests.
    """

    def __init__(self, database_url: str) -> None:
        self.session_factory: sessionmaker = create_session_factory(database_url)

    def save_scan(self, scan: ScanResult) -> None:
        with self.session_factory.begin() as session:
            session.merge(ScanRecord(
                id=scan.id,
                provider=scan.provider,
                started_at=scan.started_at,
                completed_at=scan.completed_at,
            ))
            for finding in scan.findings:
                session.merge(self._finding_to_record(finding, scan.id))

    def list_findings(self) -> list[Finding]:
        with self.session_factory() as session:
            records = session.scalars(select(FindingRecord).order_by(FindingRecord.created_at.desc())).all()
            return [self._record_to_finding(record) for record in records]

    def get_finding(self, finding_id: str) -> Finding | None:
        with self.session_factory() as session:
            record = session.get(FindingRecord, finding_id)
            return self._record_to_finding(record) if record else None

    def save_finding(self, finding: Finding) -> None:
        with self.session_factory.begin() as session:
            existing = session.get(FindingRecord, finding.id)
            scan_id = existing.scan_id if existing else "manual"
            session.merge(self._finding_to_record(finding, scan_id))

    def save_plan(self, plan: RemediationPlan) -> None:
        with self.session_factory.begin() as session:
            session.merge(RemediationPlanRecord(
                id=plan.id,
                finding_id=plan.finding_id,
                action=plan.action,
                target=plan.target,
                rationale=plan.rationale,
                expected_impact=plan.expected_impact,
                rollback=plan.rollback,
                requires_approval=plan.requires_approval,
                created_at=plan.created_at,
            ))

    def get_plan(self, plan_id: str) -> RemediationPlan | None:
        with self.session_factory() as session:
            record = session.get(RemediationPlanRecord, plan_id)
            if not record:
                return None
            return RemediationPlan(
                id=record.id,
                finding_id=record.finding_id,
                action=record.action,
                target=record.target,
                rationale=record.rationale,
                expected_impact=record.expected_impact,
                rollback=record.rollback,
                requires_approval=record.requires_approval,
                created_at=record.created_at,
            )

    def save_approval(self, approval: Approval) -> None:
        with self.session_factory.begin() as session:
            session.merge(ApprovalRecord(
                id=approval.id,
                plan_id=approval.plan_id,
                approver=approval.approver,
                comment=approval.comment,
                approved_at=approval.approved_at,
            ))

    def has_approval(self, plan_id: str) -> bool:
        with self.session_factory() as session:
            return session.scalar(select(ApprovalRecord.id).where(ApprovalRecord.plan_id == plan_id)) is not None

    def save_execution(self, execution: Execution) -> None:
        with self.session_factory.begin() as session:
            session.merge(ExecutionRecord(
                id=execution.id,
                plan_id=execution.plan_id,
                status=execution.status.value,
                verification=execution.verification,
                audit=execution.audit,
                created_at=execution.created_at,
            ))

    def clear(self) -> None:
        with self.session_factory.begin() as session:
            for record in (ExecutionRecord, ApprovalRecord, RemediationPlanRecord, FindingRecord, ScanRecord):
                session.query(record).delete()

    @staticmethod
    def _finding_to_record(finding: Finding, scan_id: str) -> FindingRecord:
        return FindingRecord(
            id=finding.id,
            scan_id=scan_id,
            rule_id=finding.rule_id,
            title=finding.title,
            severity=finding.severity.value,
            resource_id=finding.resource_id,
            description=finding.description,
            evidence=[evidence.model_dump(mode="json") for evidence in finding.evidence],
            remediation_action=finding.remediation_action,
            rollback_action=finding.rollback_action,
            status=finding.status.value,
            created_at=finding.created_at,
        )

    @staticmethod
    def _record_to_finding(record: FindingRecord) -> Finding:
        return Finding(
            id=record.id,
            rule_id=record.rule_id,
            title=record.title,
            severity=record.severity,
            resource_id=record.resource_id,
            description=record.description,
            evidence=record.evidence,
            remediation_action=record.remediation_action,
            rollback_action=record.rollback_action,
            status=record.status,
            created_at=record.created_at,
        )
