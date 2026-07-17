from __future__ import annotations

from fastapi import HTTPException, status

from .domain import Approval, Execution, ExecutionStatus, FindingStatus, RemediationPlan
from .providers import CloudProvider
from .scanner import Scanner
from .store import Store


ALLOWED_ACTIONS = {
    "revoke_public_postgres_rule": "Remove only the exact public TCP/5432 ingress rule after approval.",
    "collect_disk_diagnosis": "Collect disk usage evidence; this action is read-only.",
    "collect_container_diagnosis": "Collect container status and logs metadata; this action is read-only.",
}


class SoloOpsService:
    def __init__(self, store: Store, scanner: Scanner) -> None:
        self.store = store
        self.scanner = scanner

    def scan(self, provider_name: str, provider: CloudProvider):
        scan = self.scanner.scan(provider_name, provider)
        self.store.save_scan(scan)
        return scan

    def create_plan(self, finding_id: str) -> RemediationPlan:
        finding = self.store.get_finding(finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")
        if finding.remediation_action not in ALLOWED_ACTIONS:
            raise HTTPException(status_code=400, detail="Finding action is not allowlisted")
        plan = RemediationPlan(
            finding_id=finding.id, action=finding.remediation_action, target=finding.resource_id,
            rationale=finding.description,
            expected_impact=ALLOWED_ACTIONS[finding.remediation_action],
            rollback=finding.rollback_action,
        )
        self.store.save_plan(plan)
        finding.status = FindingStatus.PLANNED
        self.store.save_finding(finding)
        return plan

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
        return approval

    def execute(self, plan_id: str, enabled: bool) -> Execution:
        plan = self.store.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if not self.store.has_approval(plan_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Human approval is required")
        execution = Execution(plan_id=plan_id, status=ExecutionStatus.APPROVED)
        execution.audit.append("approval verified")
        if not enabled:
            execution.audit.append("execution disabled by SOLOOPS_EXECUTION_ENABLED")
            execution.verification = "Dry run completed; no cloud resource was changed."
            execution.status = ExecutionStatus.SUCCEEDED
        else:
            # Real execution must call an adapter that receives an STS write role
            # scoped to this exact action and resource. Never pass shell input here.
            execution.status = ExecutionStatus.FAILED
            execution.verification = "No real cloud executor is configured. Refusing to mutate resources."
            execution.audit.append("mutation refused: no configured write adapter")
        self.store.save_execution(execution)
        return execution
