from __future__ import annotations

from .domain import Evidence, Finding, ScanResult, Severity
from .providers import CloudProvider


class Scanner:
    def scan(self, provider_name: str, provider: CloudProvider) -> ScanResult:
        findings: list[Finding] = []
        for rule in provider.list_security_group_rules():
            if (
                rule.direction == "ingress"
                and rule.protocol.lower() == "tcp"
                and rule.port_range == "5432/5432"
                and rule.source_cidr in {"0.0.0.0/0", "::/0"}
            ):
                findings.append(Finding(
                    rule_id="SG-001", title="PostgreSQL is publicly reachable",
                    severity=Severity.CRITICAL, resource_id=rule.security_group_id,
                    description="An ingress rule exposes PostgreSQL to every internet address.",
                    evidence=[Evidence(source="security_group", summary="Public TCP/5432 ingress", payload=rule.__dict__)],
                    remediation_action="revoke_public_postgres_rule",
                    rollback_action="restore_exact_security_group_rule",
                ))

        for instance in provider.list_instances():
            if instance.disk_used_percent >= 85:
                findings.append(Finding(
                    rule_id="ECS-001", title="Instance disk space is low", severity=Severity.HIGH,
                    resource_id=instance.instance_id,
                    description=f"Disk usage is {instance.disk_used_percent:.1f}%.",
                    evidence=[Evidence(source="cloud_monitor", summary="Disk usage threshold exceeded", payload=instance.__dict__)],
                    remediation_action="collect_disk_diagnosis",
                    rollback_action=None,
                ))
            if instance.container_restart_count >= 5:
                findings.append(Finding(
                    rule_id="ECS-002", title="Container restart loop suspected", severity=Severity.HIGH,
                    resource_id=instance.instance_id,
                    description=f"Observed {instance.container_restart_count} restarts.",
                    evidence=[Evidence(source="docker_metrics", summary="Restart threshold exceeded", payload=instance.__dict__)],
                    remediation_action="collect_container_diagnosis",
                    rollback_action=None,
                ))
        return ScanResult(provider=provider_name, findings=findings)
