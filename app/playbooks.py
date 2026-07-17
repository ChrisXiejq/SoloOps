from __future__ import annotations

from dataclasses import dataclass

from .domain import Execution, ExecutionStatus, Finding, RemediationPlan
from .providers import AliyunNativeSignalProvider, AliyunReadOnlyProvider, SecurityGroupRule
from .settings import Settings


@dataclass(frozen=True)
class Playbook:
    id: str
    action: str
    title: str
    description: str
    expected_impact: str
    required_permission: str
    dry_run_steps: tuple[str, ...]
    verifier: str
    rollback: str | None = None
    oos_template_id: str | None = None


class PlaybookRegistry:
    def __init__(self) -> None:
        self._playbooks = {
            playbook.action: playbook
            for playbook in (
                Playbook(
                    id="pb-revoke-public-postgres-rule",
                    action="revoke_public_postgres_rule",
                    title="Revoke public PostgreSQL ingress",
                    description="Remove only the exact public TCP/5432 ingress rule after approval.",
                    expected_impact="Blocks public PostgreSQL access while preserving unrelated rules.",
                    required_permission="ecs:RevokeSecurityGroup",
                    dry_run_steps=(
                        "load security group evidence",
                        "validate exact TCP/5432 public ingress match",
                        "prepare revoke rule request without sending it",
                    ),
                    verifier="security_group_rule_absent",
                    rollback="restore_exact_security_group_rule",
                    oos_template_id="ACS-ECS-RevokeSecurityGroupRule",
                ),
                Playbook(
                    id="pb-collect-disk-diagnosis",
                    action="collect_disk_diagnosis",
                    title="Collect disk diagnosis",
                    description="Collect disk usage evidence and recommended cleanup paths.",
                    expected_impact="Read-only diagnosis; no cloud resource is mutated.",
                    required_permission="cms:DescribeMetricList",
                    dry_run_steps=(
                        "read CloudMonitor disk alarm evidence",
                        "read instance snapshot",
                        "prepare diagnosis report",
                    ),
                    verifier="diagnosis_report_created",
                    oos_template_id="ACS-ECS-CollectDiskDiagnosticInfo",
                ),
                Playbook(
                    id="pb-collect-container-diagnosis",
                    action="collect_container_diagnosis",
                    title="Collect container restart diagnosis",
                    description="Collect container restart and log-pattern evidence.",
                    expected_impact="Read-only diagnosis; no cloud resource is mutated.",
                    required_permission="log:GetLogs",
                    dry_run_steps=(
                        "read SLS restart pattern evidence",
                        "read instance snapshot",
                        "prepare restart diagnosis report",
                    ),
                    verifier="diagnosis_report_created",
                    oos_template_id="ACS-ECS-CollectApplicationLogs",
                ),
                Playbook(
                    id="pb-review-rds-network-acl",
                    action="review_rds_network_acl",
                    title="Review RDS network access",
                    description="Review RDS whitelist entries and recommend least-privilege CIDR changes.",
                    expected_impact="Read-only review; no database network policy is changed automatically.",
                    required_permission="rds:DescribeDBInstanceIPArrayList",
                    dry_run_steps=(
                        "read RDS whitelist evidence",
                        "identify internet-wide CIDR entries",
                        "prepare least-privilege access recommendation",
                    ),
                    verifier="review_report_created",
                ),
                Playbook(
                    id="pb-review-rds-backup-policy",
                    action="review_rds_backup_policy",
                    title="Review RDS backup policy",
                    description="Review RDS backup retention and recommend an auditable backup policy.",
                    expected_impact="Read-only review; no backup policy is changed automatically.",
                    required_permission="rds:DescribeDBInstanceAttribute",
                    dry_run_steps=(
                        "read RDS backup policy evidence",
                        "compare retention against SoloOps baseline",
                        "prepare backup policy recommendation",
                    ),
                    verifier="review_report_created",
                ),
                Playbook(
                    id="pb-review-rds-storage-capacity",
                    action="review_rds_storage_capacity",
                    title="Review RDS storage capacity",
                    description="Review RDS storage usage and recommend capacity or cleanup actions.",
                    expected_impact="Read-only review; no storage capacity is changed automatically.",
                    required_permission="rds:DescribeDBInstanceAttribute",
                    dry_run_steps=(
                        "read RDS storage usage evidence",
                        "estimate capacity pressure",
                        "prepare expansion or cleanup recommendation",
                    ),
                    verifier="review_report_created",
                ),
                Playbook(
                    id="pb-review-oss-public-access",
                    action="review_oss_public_access",
                    title="Review OSS public access",
                    description="Review OSS ACL and public access block settings.",
                    expected_impact="Read-only review; no bucket ACL is changed automatically.",
                    required_permission="oss:GetBucketAcl",
                    dry_run_steps=(
                        "read OSS ACL evidence",
                        "check public access block status",
                        "prepare bucket access recommendation",
                    ),
                    verifier="review_report_created",
                ),
                Playbook(
                    id="pb-review-oss-encryption-policy",
                    action="review_oss_encryption_policy",
                    title="Review OSS encryption policy",
                    description="Review OSS server-side encryption configuration.",
                    expected_impact="Read-only review; no bucket encryption policy is changed automatically.",
                    required_permission="oss:GetBucketEncryption",
                    dry_run_steps=(
                        "read OSS encryption evidence",
                        "compare encryption setting against SoloOps baseline",
                        "prepare encryption policy recommendation",
                    ),
                    verifier="review_report_created",
                ),
            )
        }

    def get_by_action(self, action: str) -> Playbook | None:
        return self._playbooks.get(action)

    def list(self) -> list[Playbook]:
        return list(self._playbooks.values())


class DryRunExecutor:
    def execute(
        self,
        execution: Execution,
        plan: RemediationPlan,
        playbook: Playbook,
        enabled: bool,
        finding: Finding | None = None,
    ) -> Execution:
        execution.status = ExecutionStatus.RUNNING
        execution.audit.append(f"playbook selected: {playbook.id}")
        execution.audit.append(f"required permission: {playbook.required_permission}")
        execution.audit.extend(f"dry-run step: {step}" for step in playbook.dry_run_steps)

        if not enabled:
            execution.audit.append("execution disabled by SOLOOPS_EXECUTION_ENABLED")
            execution.verification = (
                f"Dry run completed for {playbook.action}; no cloud resource was changed."
            )
            execution.status = ExecutionStatus.SUCCEEDED
            return execution

        execution.status = ExecutionStatus.FAILED
        execution.verification = "Real executor is not configured. Refusing to mutate resources."
        execution.audit.append("mutation refused: no configured write adapter")
        return execution


class Verifier:
    def verify(
        self,
        execution: Execution,
        plan: RemediationPlan,
        playbook: Playbook,
        finding: Finding | None = None,
    ) -> Execution:
        if execution.status != ExecutionStatus.SUCCEEDED:
            execution.audit.append("verification skipped: execution did not succeed")
            return execution
        execution.audit.append(f"verifier selected: {playbook.verifier}")
        if playbook.verifier == "security_group_rule_absent":
            execution.audit.append("dry-run verifier confirmed intended rule would be removed")
        elif playbook.verifier == "diagnosis_report_created":
            execution.audit.append("dry-run verifier confirmed diagnosis report would be created")
        elif playbook.verifier == "review_report_created":
            execution.audit.append("dry-run verifier confirmed review report would be created")
        else:
            execution.audit.append("dry-run verifier completed with generic success")
        return execution


class AliyunControlledExecutor(DryRunExecutor):
    """Guarded real executor for approved Alibaba Cloud playbooks.

    Mutating operations are intentionally narrow. The executor only revokes the
    exact public PostgreSQL ingress rule captured in the Finding evidence.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(
        self,
        execution: Execution,
        plan: RemediationPlan,
        playbook: Playbook,
        enabled: bool,
        finding: Finding | None = None,
    ) -> Execution:
        if not enabled:
            return super().execute(execution, plan, playbook, enabled, finding)

        execution.status = ExecutionStatus.RUNNING
        execution.audit.append(f"playbook selected: {playbook.id}")
        execution.audit.append(f"required permission: {playbook.required_permission}")

        if playbook.action == "revoke_public_postgres_rule":
            return self._revoke_public_postgres_rule(execution, plan, finding)
        if playbook.action in {"collect_disk_diagnosis", "collect_container_diagnosis"}:
            return self._collect_read_only_diagnosis(execution, plan, playbook)
        if playbook.action.startswith("review_rds_") or playbook.action.startswith("review_oss_"):
            return self._collect_read_only_cloud_review(execution, plan, playbook)

        execution.status = ExecutionStatus.FAILED
        execution.verification = f"Unsupported real execution action: {playbook.action}"
        execution.audit.append("mutation refused: action is not implemented by the real executor")
        return execution

    def _collect_read_only_cloud_review(
        self,
        execution: Execution,
        plan: RemediationPlan,
        playbook: Playbook,
    ) -> Execution:
        try:
            provider = AliyunReadOnlyProvider(self.settings)
            rds_instances = provider.list_rds_instances()
            oss_buckets = provider.list_oss_buckets()
            execution.audit.append(f"read {len(rds_instances)} RDS snapshots")
            execution.audit.append(f"read {len(oss_buckets)} OSS bucket snapshots")
            execution.audit.append("read-only cloud review completed without mutating cloud resources")
            execution.status = ExecutionStatus.SUCCEEDED
            execution.verification = (
                f"Read-only {playbook.action} review collected for target {plan.target}."
            )
        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.verification = f"Cloud review failed: {exc}"
            execution.audit.append(f"cloud review error: {exc}")
        return execution

    def _revoke_public_postgres_rule(
        self,
        execution: Execution,
        plan: RemediationPlan,
        finding: Finding | None,
    ) -> Execution:
        try:
            rule = self._extract_public_postgres_rule(finding)
            self._validate_target(plan, rule)
            request = self._ecs_models().RevokeSecurityGroupRequest(
                region_id=self.settings.aliyun_region,
                security_group_id=rule.security_group_id,
                ip_protocol=rule.protocol,
                port_range=rule.port_range,
                source_cidr_ip=rule.source_cidr,
            )
            response = self._ecs_client().revoke_security_group(request)
            request_id = getattr(response.body, "request_id", None)
            execution.audit.append(
                "sent RevokeSecurityGroup request for exact TCP/5432 public ingress rule"
            )
            if request_id:
                execution.audit.append(f"aliyun request_id: {request_id}")
            execution.status = ExecutionStatus.SUCCEEDED
            execution.verification = "Revoke request submitted; verifier will re-read the security group."
        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.verification = f"Real execution failed: {exc}"
            execution.audit.append(f"execution error: {exc}")
        return execution

    def _collect_read_only_diagnosis(
        self,
        execution: Execution,
        plan: RemediationPlan,
        playbook: Playbook,
    ) -> Execution:
        try:
            provider = AliyunReadOnlyProvider(self.settings)
            instances = provider.list_instances()
            signals = AliyunNativeSignalProvider(provider).list_signals()
            target_instances = [item for item in instances if item.instance_id == plan.target]
            execution.audit.append(f"read {len(target_instances)} target instance snapshots")
            execution.audit.append(f"read {len(signals)} native signals")
            execution.audit.append("read-only diagnosis completed without mutating cloud resources")
            execution.status = ExecutionStatus.SUCCEEDED
            execution.verification = (
                f"Read-only {playbook.action} diagnosis collected for target {plan.target}."
            )
        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.verification = f"Diagnosis failed: {exc}"
            execution.audit.append(f"diagnosis error: {exc}")
        return execution

    def _validate_target(self, plan: RemediationPlan, rule: SecurityGroupRule) -> None:
        if not self.settings.aliyun_security_group_id:
            raise ValueError("SOLOOPS_ALIYUN_SECURITY_GROUP_ID is required for real execution")
        if plan.target != self.settings.aliyun_security_group_id:
            raise ValueError("plan target does not match configured security group")
        if rule.security_group_id != self.settings.aliyun_security_group_id:
            raise ValueError("finding evidence does not match configured security group")

    @staticmethod
    def _extract_public_postgres_rule(finding: Finding | None) -> SecurityGroupRule:
        if not finding:
            raise ValueError("finding evidence is required for real execution")
        for evidence in finding.evidence:
            if evidence.source != "resource_config":
                continue
            payload = evidence.payload
            rule = SecurityGroupRule(
                security_group_id=str(payload.get("security_group_id") or ""),
                direction=str(payload.get("direction") or ""),
                protocol=str(payload.get("protocol") or "").lower(),
                port_range=str(payload.get("port_range") or ""),
                source_cidr=str(payload.get("source_cidr") or ""),
            )
            if (
                rule.direction == "ingress"
                and rule.protocol == "tcp"
                and rule.port_range == "5432/5432"
                and rule.source_cidr == "0.0.0.0/0"
            ):
                return rule
        raise ValueError("finding does not contain an exact public TCP/5432 ingress rule")

    def _ecs_client(self):
        from alibabacloud_ecs20140526.client import Client as EcsClient
        from alibabacloud_tea_openapi import models as openapi_models

        if not self.settings.aliyun_access_key_id or not self.settings.aliyun_access_key_secret:
            raise ValueError("Missing ALIBABA_CLOUD_ACCESS_KEY_ID or ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        return EcsClient(openapi_models.Config(
            access_key_id=self.settings.aliyun_access_key_id,
            access_key_secret=self.settings.aliyun_access_key_secret,
            endpoint=f"ecs.{self.settings.aliyun_region}.aliyuncs.com",
        ))

    @staticmethod
    def _ecs_models():
        from alibabacloud_ecs20140526 import models as ecs_models

        return ecs_models


class AliyunVerifier(Verifier):
    """Verifier that re-reads Alibaba Cloud state after real execution."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify(
        self,
        execution: Execution,
        plan: RemediationPlan,
        playbook: Playbook,
        finding: Finding | None = None,
    ) -> Execution:
        if execution.status != ExecutionStatus.SUCCEEDED:
            execution.audit.append("verification skipped: execution did not succeed")
            return execution
        if any("execution disabled by SOLOOPS_EXECUTION_ENABLED" in item for item in execution.audit):
            return super().verify(execution, plan, playbook, finding)
        if playbook.action == "revoke_public_postgres_rule":
            return self._verify_public_postgres_rule_absent(execution, finding)
        if playbook.action in {"collect_disk_diagnosis", "collect_container_diagnosis"}:
            return self._verify_read_only_diagnosis(execution, plan, playbook)
        return super().verify(execution, plan, playbook, finding)

    def _verify_public_postgres_rule_absent(
        self,
        execution: Execution,
        finding: Finding | None,
    ) -> Execution:
        try:
            intended_rule = AliyunControlledExecutor._extract_public_postgres_rule(finding)
            provider = AliyunReadOnlyProvider(self.settings)
            current_rules = provider.list_security_group_rules()
            still_present = any(self._same_rule(rule, intended_rule) for rule in current_rules)
            execution.audit.append("verifier re-read Alibaba Cloud security group rules")
            if still_present:
                execution.status = ExecutionStatus.FAILED
                execution.verification = "Verification failed: public PostgreSQL ingress rule is still present."
            else:
                execution.verification = "Verified: public PostgreSQL ingress rule is absent."
        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.verification = f"Verification failed: {exc}"
            execution.audit.append(f"verification error: {exc}")
        return execution

    def _verify_read_only_diagnosis(
        self,
        execution: Execution,
        plan: RemediationPlan,
        playbook: Playbook,
    ) -> Execution:
        try:
            provider = AliyunReadOnlyProvider(self.settings)
            target_exists = any(instance.instance_id == plan.target for instance in provider.list_instances())
            execution.audit.append("verifier re-read Alibaba Cloud instance inventory")
            if not target_exists:
                execution.status = ExecutionStatus.FAILED
                execution.verification = f"Verification failed: target {plan.target} was not found."
            else:
                execution.verification = f"Verified: read-only {playbook.action} target still exists."
        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.verification = f"Verification failed: {exc}"
            execution.audit.append(f"verification error: {exc}")
        return execution

    @staticmethod
    def _same_rule(left: SecurityGroupRule, right: SecurityGroupRule) -> bool:
        return (
            left.security_group_id == right.security_group_id
            and left.direction == right.direction
            and left.protocol.lower() == right.protocol.lower()
            and left.port_range == right.port_range
            and left.source_cidr == right.source_cidr
        )
