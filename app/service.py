from __future__ import annotations

from .domain import (
    Approval,
    AuditEvent,
    Execution,
    ExecutionStatus,
    Finding,
    FindingStatus,
    RemediationPlan,
    ScanResult,
    ScanStatus,
    utcnow,
)
from fastapi import HTTPException, status

from .playbooks import AliyunControlledExecutor, AliyunVerifier, DryRunExecutor, PlaybookRegistry, Verifier
from .providers import CloudProvider, NativeSignalProvider
from .providers import AliyunNativeSignalProvider, AliyunReadOnlyProvider, MockCloudProvider, MockNativeSignalProvider
from .scanner import Scanner
from .settings import Settings, get_settings
from .store import Store
from .worker import InProcessScanQueue, ScanJob


class SoloOpsService:
    def __init__(
        self,
        store: Store,
        scanner: Scanner,
        playbooks: PlaybookRegistry | None = None,
        executor: DryRunExecutor | None = None,
        verifier: Verifier | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.store = store
        self.scanner = scanner
        self.settings = settings or get_settings()
        self.playbooks = playbooks or PlaybookRegistry()
        self.executor = executor or AliyunControlledExecutor(self.settings)
        self.verifier = verifier or AliyunVerifier(self.settings)
        self.scan_queue = InProcessScanQueue(self.run_scan_job)

    def scan(
        self,
        provider_name: str,
        provider: CloudProvider,
        signal_provider: NativeSignalProvider | None = None,
    ) -> ScanResult:
        return self.request_scan(provider_name)

    def request_scan(self, provider_name: str) -> ScanResult:
        scan = ScanResult(provider=provider_name, status=ScanStatus.PENDING)
        self.store.save_scan(scan)
        self._audit(
            "ScanRequested",
            entity_type="scan",
            entity_id=scan.id,
            message=f"Scan requested for provider {provider_name}.",
            payload={"provider": provider_name},
        )
        response = scan.model_copy(deep=True)
        self.scan_queue.enqueue(ScanJob(scan_id=scan.id, provider=provider_name))
        return response

    def run_scan_job(self, job: ScanJob) -> None:
        scan = self.store.get_scan(job.scan_id)
        if not scan:
            return
        scan.status = ScanStatus.RUNNING
        scan.started_at = utcnow()
        scan.completed_at = scan.started_at
        self.store.update_scan(scan)
        self._audit(
            "ScanRunning",
            entity_type="scan",
            entity_id=scan.id,
            message="Scan task is running.",
        )

        try:
            provider, signal_provider = self._providers_for(job.provider)
            result = self.scanner.scan(job.provider, provider, signal_provider)
            scan.findings = result.findings
            scan.status = ScanStatus.SUCCEEDED
            scan.completed_at = utcnow()
            scan.error_message = None
            self.store.update_scan(scan)
            self._audit(
                "ScanSucceeded",
                entity_type="scan",
                entity_id=scan.id,
                message=f"Scan completed with {len(scan.findings)} findings.",
                payload={"finding_count": len(scan.findings)},
            )
            return scan
        except Exception as exc:
            scan.status = ScanStatus.FAILED
            scan.completed_at = utcnow()
            scan.error_message = str(exc)
            self.store.update_scan(scan)
            self._audit(
                "ScanFailed",
                entity_type="scan",
                entity_id=scan.id,
                message="Scan task failed.",
                payload={"error": scan.error_message},
            )

    def list_scans(self) -> list[ScanResult]:
        return self.store.list_scans()

    def get_scan(self, scan_id: str) -> ScanResult:
        scan = self.store.get_scan(scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        return scan

    def get_finding(self, finding_id: str) -> Finding:
        finding = self.store.get_finding(finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")
        return finding

    def create_plan(self, finding_id: str) -> RemediationPlan:
        finding = self.store.get_finding(finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")
        playbook = self.playbooks.get_by_action(finding.remediation_action)
        if not playbook:
            raise HTTPException(status_code=400, detail="Finding action is not allowlisted")
        plan = RemediationPlan(
            finding_id=finding.id,
            playbook_id=playbook.id,
            action=finding.remediation_action,
            target=finding.resource_id,
            rationale=finding.description,
            expected_impact=playbook.expected_impact,
            rollback=playbook.rollback or finding.rollback_action,
        )
        self.store.save_plan(plan)
        finding.status = FindingStatus.PLANNED
        self.store.save_finding(finding)
        self._audit(
            "PlanCreated",
            entity_type="plan",
            entity_id=plan.id,
            message=f"Plan created for finding {finding.id}.",
            payload={"finding_id": finding.id, "action": plan.action, "target": plan.target},
        )
        return plan

    def get_plan(self, plan_id: str) -> RemediationPlan:
        plan = self.store.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        return plan

    def get_execution(self, execution_id: str) -> Execution:
        execution = self.store.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        return execution

    def list_playbooks(self):
        return self.playbooks.list()

    def list_native_signals(self, provider_name: str):
        _, signal_provider = self._providers_for(provider_name)
        if not signal_provider:
            return []
        return signal_provider.list_signals()

    def approve(self, plan_id: str, approver: str, comment: str | None) -> Approval:
        plan = self.store.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        approval = Approval(plan_id=plan_id, approver=approver, comment=comment)
        self.store.save_approval(approval)
        finding = self.store.get_finding(plan.finding_id)
        if finding:
            finding.status = FindingStatus.APPROVED
            self.store.save_finding(finding)
        self._audit(
            "PlanApproved",
            actor=approver,
            entity_type="plan",
            entity_id=plan_id,
            message=f"Plan approved by {approver}.",
            payload={"comment": comment},
        )
        return approval

    def execute(self, plan_id: str, enabled: bool) -> Execution:
        plan = self.store.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if not self.store.has_approval(plan_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Human approval is required")
        playbook = self.playbooks.get_by_action(plan.action)
        if not playbook or playbook.id != plan.playbook_id:
            raise HTTPException(status_code=400, detail="Plan playbook is not registered")
        finding = self.store.get_finding(plan.finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")
        execution = Execution(plan_id=plan_id, status=ExecutionStatus.APPROVED)
        execution.audit.append("approval verified")
        self.store.save_execution(execution)
        self._audit(
            "ExecutionStarted",
            entity_type="execution",
            entity_id=execution.id,
            message=f"Execution started for plan {plan_id}.",
            payload={"plan_id": plan_id, "playbook_id": playbook.id},
        )
        execution = self.executor.execute(execution, plan, playbook, enabled, finding)
        execution = self.verifier.verify(execution, plan, playbook, finding)
        self.store.save_execution(execution)
        self._audit(
            "ExecutionFinished",
            entity_type="execution",
            entity_id=execution.id,
            message=f"Execution finished with status {execution.status.value}.",
            payload={"plan_id": plan_id, "audit": execution.audit, "verification": execution.verification},
        )
        return execution

    def list_audit_events(self) -> list[AuditEvent]:
        return self.store.list_audit_events()

    def _providers_for(self, provider_name: str) -> tuple[CloudProvider, NativeSignalProvider | None]:
        if provider_name == "mock":
            return MockCloudProvider(), MockNativeSignalProvider()
        if provider_name == "aliyun":
            provider = AliyunReadOnlyProvider(self.settings)
            return provider, AliyunNativeSignalProvider(provider)
        raise ValueError(f"Unsupported provider: {provider_name}")

    def _audit(
        self,
        event_type: str,
        *,
        entity_type: str,
        entity_id: str,
        message: str,
        actor: str = "system",
        payload: dict | None = None,
    ) -> None:
        self.store.save_audit_event(AuditEvent(
            event_type=event_type,
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            message=message,
            payload=payload or {},
        ))
