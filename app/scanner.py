from __future__ import annotations

from .domain import Evidence, Finding, ScanResult, Severity
from .providers import CloudProvider, NativeSignal, NativeSignalProvider


class Scanner:
    def scan(
        self,
        provider_name: str,
        provider: CloudProvider,
        signal_provider: NativeSignalProvider | None = None,
    ) -> ScanResult:
        findings: list[Finding] = []
        signals = signal_provider.list_signals() if signal_provider else []
        signals_by_resource = self._group_signals(signals)
        for rule in self._safe_list(provider.list_security_group_rules):
            if (
                rule.direction == "ingress"
                and rule.protocol.lower() == "tcp"
                and rule.port_range == "5432/5432"
                and rule.source_cidr in {"0.0.0.0/0", "::/0"}
            ):
                signal_evidence = self._evidence_for_resource(
                    signals_by_resource.get(rule.security_group_id, []),
                    signal_types={"change_event", "execution_record", "provider_error"},
                )
                findings.append(Finding(
                    rule_id="SG-001", title="PostgreSQL is publicly reachable",
                    severity=Severity.CRITICAL, resource_id=rule.security_group_id,
                    description="An ingress rule exposes PostgreSQL to every internet address.",
                    evidence=[
                        *signal_evidence,
                        Evidence(
                            source="resource_config",
                            summary="Security group config exposes public TCP/5432 ingress",
                            payload=rule.__dict__,
                        )
                    ],
                    remediation_action="revoke_public_postgres_rule",
                    rollback_action="restore_exact_security_group_rule",
                ))

        for instance in self._safe_list(provider.list_instances):
            if instance.disk_used_percent >= 85:
                signal_evidence = self._evidence_for_resource(
                    signals_by_resource.get(instance.instance_id, []),
                    signal_types={"metric_alarm", "change_event", "execution_record", "provider_error"},
                )
                findings.append(Finding(
                    rule_id="ECS-001", title="Instance disk space is low", severity=Severity.HIGH,
                    resource_id=instance.instance_id,
                    description=f"Disk usage is {instance.disk_used_percent:.1f}%.",
                    evidence=[
                        *signal_evidence,
                        Evidence(
                            source="resource_snapshot",
                            summary="Instance snapshot confirms disk threshold exceeded",
                            payload=instance.__dict__,
                        ),
                    ],
                    remediation_action="collect_disk_diagnosis",
                    rollback_action=None,
                ))
            restart_count = max(
                instance.container_restart_count,
                self._restart_count_from_signals(signals_by_resource.get(instance.instance_id, [])),
            )
            if restart_count >= 5:
                signal_evidence = self._evidence_for_resource(
                    signals_by_resource.get(instance.instance_id, []),
                    signal_types={"log_pattern", "change_event", "execution_record", "provider_error"},
                )
                findings.append(Finding(
                    rule_id="ECS-002", title="Container restart loop suspected", severity=Severity.HIGH,
                    resource_id=instance.instance_id,
                    description=f"Observed {restart_count} restarts.",
                    evidence=[
                        *signal_evidence,
                        Evidence(
                            source="resource_snapshot",
                            summary="Instance snapshot confirms restart threshold exceeded",
                            payload=instance.__dict__ | {"effective_restart_count": restart_count},
                        ),
                    ],
                    remediation_action="collect_container_diagnosis",
                    rollback_action=None,
                ))

        for rds in self._safe_list(provider.list_rds_instances):
            signal_evidence = self._evidence_for_resource(
                signals_by_resource.get(rds.instance_id, []),
                signal_types={"change_event", "execution_record", "provider_error"},
            )
            public_cidrs = [cidr for cidr in rds.whitelist_cidrs if cidr in {"0.0.0.0/0", "::/0"}]
            if public_cidrs:
                findings.append(Finding(
                    rule_id="RDS-001",
                    title="RDS instance allows public network access",
                    severity=Severity.CRITICAL,
                    resource_id=rds.instance_id,
                    description="The RDS whitelist contains an internet-wide CIDR.",
                    evidence=[
                        *signal_evidence,
                        Evidence(
                            source="resource_config",
                            summary="RDS whitelist contains public CIDR entries",
                            payload=rds.__dict__ | {"public_cidrs": public_cidrs},
                        ),
                    ],
                    remediation_action="review_rds_network_acl",
                    rollback_action=None,
                ))
            if rds.backup_retention_days == 0:
                findings.append(Finding(
                    rule_id="RDS-002",
                    title="RDS backup retention is disabled",
                    severity=Severity.HIGH,
                    resource_id=rds.instance_id,
                    description="The RDS instance reports zero backup retention days.",
                    evidence=[
                        *signal_evidence,
                        Evidence(
                            source="resource_config",
                            summary="RDS backup retention is zero days",
                            payload=rds.__dict__,
                        ),
                    ],
                    remediation_action="review_rds_backup_policy",
                    rollback_action=None,
                ))
            if rds.storage_used_percent >= 85:
                metric_evidence = self._evidence_for_resource(
                    signals_by_resource.get(rds.instance_id, []),
                    signal_types={"metric_alarm", "change_event", "execution_record", "provider_error"},
                )
                findings.append(Finding(
                    rule_id="RDS-003",
                    title="RDS storage usage is high",
                    severity=Severity.HIGH,
                    resource_id=rds.instance_id,
                    description=f"RDS storage usage is {rds.storage_used_percent:.1f}%.",
                    evidence=[
                        *metric_evidence,
                        Evidence(
                            source="resource_snapshot",
                            summary="RDS snapshot confirms storage threshold exceeded",
                            payload=rds.__dict__,
                        ),
                    ],
                    remediation_action="review_rds_storage_capacity",
                    rollback_action=None,
                ))

        for bucket in self._safe_list(provider.list_oss_buckets):
            signal_evidence = self._evidence_for_resource(
                signals_by_resource.get(bucket.bucket_name, []),
                signal_types={"change_event", "execution_record", "provider_error"},
            )
            if bucket.acl in {"public-read", "public-read-write"} and not bucket.public_access_block_enabled:
                findings.append(Finding(
                    rule_id="OSS-001",
                    title="OSS bucket allows public access",
                    severity=Severity.CRITICAL if bucket.acl == "public-read-write" else Severity.HIGH,
                    resource_id=bucket.bucket_name,
                    description=f"OSS bucket ACL is {bucket.acl} and public access block is not enabled.",
                    evidence=[
                        *signal_evidence,
                        Evidence(
                            source="resource_config",
                            summary="OSS ACL permits public access",
                            payload=bucket.__dict__,
                        ),
                    ],
                    remediation_action="review_oss_public_access",
                    rollback_action=None,
                ))
            if bucket.server_side_encryption_enabled is False:
                findings.append(Finding(
                    rule_id="OSS-002",
                    title="OSS server-side encryption is disabled",
                    severity=Severity.MEDIUM,
                    resource_id=bucket.bucket_name,
                    description="The OSS bucket does not report a server-side encryption rule.",
                    evidence=[
                        *signal_evidence,
                        Evidence(
                            source="resource_config",
                            summary="OSS server-side encryption rule is absent",
                            payload=bucket.__dict__,
                        ),
                    ],
                    remediation_action="review_oss_encryption_policy",
                    rollback_action=None,
                ))
        return ScanResult(provider=provider_name, findings=findings)

    @staticmethod
    def _safe_list(getter):
        try:
            return getter()
        except Exception:
            return []

    @staticmethod
    def _group_signals(signals: list[NativeSignal]) -> dict[str, list[NativeSignal]]:
        grouped: dict[str, list[NativeSignal]] = {}
        for signal in signals:
            grouped.setdefault(signal.resource_id, []).append(signal)
        return grouped

    @staticmethod
    def _evidence_for_resource(signals: list[NativeSignal], signal_types: set[str]) -> list[Evidence]:
        return [
            Evidence(
                source=signal.source,
                observed_at=signal.observed_at,
                summary=signal.summary,
                payload={
                    "signal_id": signal.id,
                    "signal_type": signal.signal_type,
                    "severity": signal.severity,
                    "title": signal.title,
                    **signal.payload,
                },
            )
            for signal in signals
            if signal.signal_type in signal_types
        ]

    @staticmethod
    def _restart_count_from_signals(signals: list[NativeSignal]) -> int:
        counts: list[int] = []
        for signal in signals:
            if signal.signal_type != "log_pattern":
                continue
            if signal.payload.get("pattern") != "container_restart":
                continue
            value = signal.payload.get("restart_count") or signal.payload.get("count")
            try:
                counts.append(int(value))
            except (TypeError, ValueError):
                continue
        return max(counts) if counts else 0
