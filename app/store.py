from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .db import (
    AgentRunRecord,
    ApprovalRecord,
    AuditEventRecord,
    ExecutionRecord,
    FindingRecord,
    RemediationPlanRecord,
    ScanRecord,
    create_session_factory,
)
from .domain import AgentRun, Approval, AuditEvent, Execution, Finding, RemediationPlan, ScanResult


class Store(Protocol):
    def save_scan(self, scan: ScanResult) -> None: ...

    def update_scan(self, scan: ScanResult) -> None: ...

    def list_scans(self) -> list[ScanResult]: ...

    def get_scan(self, scan_id: str) -> ScanResult | None: ...

    def list_findings(self) -> list[Finding]: ...

    def get_finding(self, finding_id: str) -> Finding | None: ...

    def save_finding(self, finding: Finding) -> None: ...

    def save_plan(self, plan: RemediationPlan) -> None: ...

    def get_plan(self, plan_id: str) -> RemediationPlan | None: ...

    def save_approval(self, approval: Approval) -> None: ...

    def has_approval(self, plan_id: str) -> bool: ...

    def save_execution(self, execution: Execution) -> None: ...

    def get_execution(self, execution_id: str) -> Execution | None: ...

    def save_audit_event(self, event: AuditEvent) -> None: ...

    def list_audit_events(self) -> list[AuditEvent]: ...

    def save_agent_run(self, run: AgentRun) -> None: ...

    def get_agent_run(self, run_id: str) -> AgentRun | None: ...

    def list_agent_runs(self, finding_id: str | None = None) -> list[AgentRun]: ...

    def clear(self) -> None: ...


class MemoryStore:
    """MVP repository. Replace with SQLAlchemy/MySQL repository behind the same port."""

    def __init__(self) -> None:
        self.scans: dict[str, ScanResult] = {}
        self.findings: dict[str, Finding] = {}
        self.plans: dict[str, RemediationPlan] = {}
        self.approvals: dict[str, Approval] = {}
        self.executions: dict[str, Execution] = {}
        self.audit_events: dict[str, AuditEvent] = {}
        self.agent_runs: dict[str, AgentRun] = {}

    def save_scan(self, scan: ScanResult) -> None:
        self.scans[scan.id] = scan
        self.findings.update({finding.id: finding for finding in scan.findings})

    def update_scan(self, scan: ScanResult) -> None:
        self.save_scan(scan)

    def list_scans(self) -> list[ScanResult]:
        return list(self.scans.values())

    def get_scan(self, scan_id: str) -> ScanResult | None:
        return self.scans.get(scan_id)

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

    def get_execution(self, execution_id: str) -> Execution | None:
        return self.executions.get(execution_id)

    def save_audit_event(self, event: AuditEvent) -> None:
        self.audit_events[event.id] = event

    def list_audit_events(self) -> list[AuditEvent]:
        return sorted(self.audit_events.values(), key=lambda event: event.created_at, reverse=True)

    def save_agent_run(self, run: AgentRun) -> None:
        self.agent_runs[run.id] = run

    def get_agent_run(self, run_id: str) -> AgentRun | None:
        return self.agent_runs.get(run_id)

    def list_agent_runs(self, finding_id: str | None = None) -> list[AgentRun]:
        runs = list(self.agent_runs.values())
        if finding_id:
            runs = [run for run in runs if run.finding_id == finding_id]
        return sorted(runs, key=lambda run: run.created_at, reverse=True)

    def clear(self) -> None:
        self.scans.clear()
        self.findings.clear()
        self.plans.clear()
        self.approvals.clear()
        self.executions.clear()
        self.audit_events.clear()
        self.agent_runs.clear()


class SQLAlchemyStore:
    """Repository backed by SQLAlchemy.

    Use MySQL via SOLOOPS_DATABASE_URL. Tests can use MemoryStore by setting
    SOLOOPS_STORE_BACKEND=memory.
    """

    def __init__(self, database_url: str) -> None:
        self.session_factory: sessionmaker = create_session_factory(database_url)

    def save_scan(self, scan: ScanResult) -> None:
        with self.session_factory.begin() as session:
            session.merge(ScanRecord(
                id=scan.id,
                provider=scan.provider,
                status=scan.status.value,
                started_at=scan.started_at,
                completed_at=scan.completed_at,
                error_message=scan.error_message,
            ))
            for finding in scan.findings:
                session.merge(self._finding_to_record(finding, scan.id))

    def update_scan(self, scan: ScanResult) -> None:
        self.save_scan(scan)

    def list_scans(self) -> list[ScanResult]:
        with self.session_factory() as session:
            records = session.scalars(select(ScanRecord).order_by(ScanRecord.started_at.desc())).all()
            return [self._record_to_scan(record) for record in records]

    def get_scan(self, scan_id: str) -> ScanResult | None:
        with self.session_factory() as session:
            record = session.get(ScanRecord, scan_id)
            return self._record_to_scan(record) if record else None

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
                playbook_id=plan.playbook_id,
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
                playbook_id=record.playbook_id,
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

    def get_execution(self, execution_id: str) -> Execution | None:
        with self.session_factory() as session:
            record = session.get(ExecutionRecord, execution_id)
            if not record:
                return None
            return Execution(
                id=record.id,
                plan_id=record.plan_id,
                status=record.status,
                verification=record.verification,
                audit=record.audit,
                created_at=record.created_at,
            )

    def save_audit_event(self, event: AuditEvent) -> None:
        with self.session_factory.begin() as session:
            session.merge(AuditEventRecord(
                id=event.id,
                event_type=event.event_type,
                actor=event.actor,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                message=event.message,
                payload=event.payload,
                created_at=event.created_at,
            ))

    def list_audit_events(self) -> list[AuditEvent]:
        with self.session_factory() as session:
            records = session.scalars(select(AuditEventRecord).order_by(AuditEventRecord.created_at.desc())).all()
            return [self._record_to_audit_event(record) for record in records]

    def save_agent_run(self, run: AgentRun) -> None:
        with self.session_factory.begin() as session:
            session.merge(AgentRunRecord(
                id=run.id,
                finding_id=run.finding_id,
                trace_id=run.trace_id,
                agent_type=run.agent_type,
                model=run.model,
                input_refs=run.input_refs,
                output=run.output,
                safety_flags=run.safety_flags,
                status=run.status.value,
                created_at=run.created_at,
            ))

    def get_agent_run(self, run_id: str) -> AgentRun | None:
        with self.session_factory() as session:
            record = session.get(AgentRunRecord, run_id)
            return self._record_to_agent_run(record) if record else None

    def list_agent_runs(self, finding_id: str | None = None) -> list[AgentRun]:
        with self.session_factory() as session:
            stmt = select(AgentRunRecord)
            if finding_id:
                stmt = stmt.where(AgentRunRecord.finding_id == finding_id)
            records = session.scalars(stmt.order_by(AgentRunRecord.created_at.desc())).all()
            return [self._record_to_agent_run(record) for record in records]

    def clear(self) -> None:
        with self.session_factory.begin() as session:
            for record in (
                AgentRunRecord,
                AuditEventRecord,
                ExecutionRecord,
                ApprovalRecord,
                RemediationPlanRecord,
                FindingRecord,
                ScanRecord,
            ):
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

    def _record_to_scan(self, record: ScanRecord) -> ScanResult:
        with self.session_factory() as session:
            finding_records = session.scalars(
                select(FindingRecord).where(FindingRecord.scan_id == record.id).order_by(FindingRecord.created_at)
            ).all()
            return ScanResult(
                id=record.id,
                provider=record.provider,
                status=record.status,
                started_at=record.started_at,
                completed_at=record.completed_at,
                error_message=record.error_message,
                findings=[self._record_to_finding(finding_record) for finding_record in finding_records],
            )

    @staticmethod
    def _record_to_audit_event(record: AuditEventRecord) -> AuditEvent:
        return AuditEvent(
            id=record.id,
            event_type=record.event_type,
            actor=record.actor,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            message=record.message,
            payload=record.payload,
            created_at=record.created_at,
        )

    @staticmethod
    def _record_to_agent_run(record: AgentRunRecord) -> AgentRun:
        return AgentRun(
            id=record.id,
            finding_id=record.finding_id,
            trace_id=record.trace_id,
            agent_type=record.agent_type,
            model=record.model,
            input_refs=record.input_refs,
            output=record.output,
            safety_flags=record.safety_flags,
            status=record.status,
            created_at=record.created_at,
        )
