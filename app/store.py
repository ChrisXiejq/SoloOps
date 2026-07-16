from __future__ import annotations

from .domain import Approval, Execution, Finding, RemediationPlan, ScanResult


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
