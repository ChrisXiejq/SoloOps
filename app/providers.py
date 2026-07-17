from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .settings import Settings


@dataclass(frozen=True)
class SecurityGroupRule:
    security_group_id: str
    direction: str
    protocol: str
    port_range: str
    source_cidr: str


@dataclass(frozen=True)
class InstanceSnapshot:
    instance_id: str
    name: str
    disk_used_percent: float
    container_restart_count: int


@dataclass(frozen=True)
class RdsInstanceSnapshot:
    instance_id: str
    engine: str
    network_type: str
    whitelist_cidrs: list[str]
    backup_retention_days: int | None
    storage_used_percent: float


@dataclass(frozen=True)
class OssBucketSnapshot:
    bucket_name: str
    acl: str
    server_side_encryption_enabled: bool | None
    public_access_block_enabled: bool | None
    lifecycle_rule_count: int | None


@dataclass(frozen=True)
class NativeSignal:
    id: str
    source: str
    signal_type: str
    severity: str
    resource_id: str
    title: str
    summary: str
    observed_at: datetime
    payload: dict


class CloudProvider(Protocol):
    """Read-only cloud inventory port. Implementations must not mutate resources."""

    def list_instances(self) -> list[InstanceSnapshot]: ...

    def list_security_group_rules(self) -> list[SecurityGroupRule]: ...

    def list_rds_instances(self) -> list[RdsInstanceSnapshot]: ...

    def list_oss_buckets(self) -> list[OssBucketSnapshot]: ...


class NativeSignalProvider(Protocol):
    """Read-only native observability signal port.

    Implementations read CloudMonitor, ARMS, SLS, ECS health, OOS and other
    native signals. They must not mutate resources.
    """

    def list_signals(self) -> list[NativeSignal]: ...


class MockCloudProvider:
    """Deterministic data for local demo and tests; no credentials required."""

    def list_instances(self) -> list[InstanceSnapshot]:
        return [
            InstanceSnapshot(
                instance_id="i-soloops-demo", name="redflow-prod", disk_used_percent=91.0,
                container_restart_count=7,
            ),
            InstanceSnapshot(
                instance_id="i-healthy-demo", name="side-project", disk_used_percent=42.0,
                container_restart_count=0,
            ),
        ]

    def list_security_group_rules(self) -> list[SecurityGroupRule]:
        return [
            SecurityGroupRule("sg-redflow-app", "ingress", "tcp", "443/443", "0.0.0.0/0"),
            SecurityGroupRule("sg-redflow-db", "ingress", "tcp", "5432/5432", "0.0.0.0/0"),
        ]

    def list_rds_instances(self) -> list[RdsInstanceSnapshot]:
        return [
            RdsInstanceSnapshot(
                instance_id="rm-soloops-demo",
                engine="PostgreSQL",
                network_type="VPC",
                whitelist_cidrs=["0.0.0.0/0"],
                backup_retention_days=0,
                storage_used_percent=91.0,
            )
        ]

    def list_oss_buckets(self) -> list[OssBucketSnapshot]:
        return [
            OssBucketSnapshot(
                bucket_name="soloops-public-demo",
                acl="public-read",
                server_side_encryption_enabled=False,
                public_access_block_enabled=False,
                lifecycle_rule_count=0,
            )
        ]


class MockNativeSignalProvider:
    """Deterministic CloudMonitor/SLS/OOS-like signals for local demo."""

    def list_signals(self) -> list[NativeSignal]:
        now = datetime.now(timezone.utc)
        return [
            NativeSignal(
                id="cms-disk-i-soloops-demo",
                source="cloudmonitor",
                signal_type="metric_alarm",
                severity="high",
                resource_id="i-soloops-demo",
                title="Disk usage exceeded threshold",
                summary="CloudMonitor alarm: disk usage reached 91%.",
                observed_at=now,
                payload={"metric": "disk_used_percent", "value": 91.0, "threshold": 85.0},
            ),
            NativeSignal(
                id="sls-container-restart-i-soloops-demo",
                source="sls",
                signal_type="log_pattern",
                severity="high",
                resource_id="i-soloops-demo",
                title="Container restart pattern detected",
                summary="SLS log summary detected 7 container restarts in the latest window.",
                observed_at=now,
                payload={"pattern": "container_restart", "restart_count": 7},
            ),
            NativeSignal(
                id="oos-last-diagnosis-i-soloops-demo",
                source="oos",
                signal_type="execution_record",
                severity="info",
                resource_id="i-soloops-demo",
                title="Previous disk diagnosis template completed",
                summary="OOS execution history is available for prior disk diagnosis.",
                observed_at=now,
                payload={"template": "ACS-ECS-CollectDiskDiagnosticInfo", "status": "Success"},
            ),
        ]


class AliyunReadOnlyProvider:
    """Read-only Alibaba Cloud ECS/CMS adapter.

    The first real implementation is intentionally scoped to a configured ECS
    instance and security group. It does not mutate cloud resources.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.region = settings.aliyun_region
        self.instance_id = settings.aliyun_ecs_instance_id
        self.security_group_id = settings.aliyun_security_group_id
        self._ecs_client = None
        self._cms_client = None
        self._oos_client = None
        self._actiontrail_client = None
        self._rds_client = None

    def list_instances(self) -> list[InstanceSnapshot]:
        request = self._ecs_models().DescribeInstancesRequest(
            region_id=self.region,
            instance_ids=json.dumps([self.instance_id]) if self.instance_id else None,
            vpc_id=self.settings.aliyun_vpc_id,
            page_size=10,
        )
        response = self._ecs_client_lazy().describe_instances(request)
        instances = response.body.to_map().get("Instances", {}).get("Instance", []) or []
        snapshots: list[InstanceSnapshot] = []
        for instance in instances:
            instance_id = instance.get("InstanceId")
            if not instance_id:
                continue
            snapshots.append(InstanceSnapshot(
                instance_id=instance_id,
                name=instance.get("InstanceName") or instance_id,
                disk_used_percent=self._latest_cms_metric(instance_id, "diskusage_utilization"),
                container_restart_count=0,
            ))
        return snapshots

    def list_security_group_rules(self) -> list[SecurityGroupRule]:
        if not self.security_group_id:
            return []
        request = self._ecs_models().DescribeSecurityGroupAttributeRequest(
            region_id=self.region,
            security_group_id=self.security_group_id,
            direction="all",
        )
        response = self._ecs_client_lazy().describe_security_group_attribute(request)
        permissions = response.body.to_map().get("Permissions", {}).get("Permission", []) or []
        rules: list[SecurityGroupRule] = []
        for permission in permissions:
            rules.append(SecurityGroupRule(
                security_group_id=self.security_group_id,
                direction=(permission.get("Direction") or "ingress").lower(),
                protocol=(permission.get("IpProtocol") or "").lower(),
                port_range=permission.get("PortRange") or "",
                source_cidr=permission.get("SourceCidrIp")
                or permission.get("Ipv6SourceCidrIp")
                or permission.get("SourceGroupId")
                or "",
            ))
        return rules

    def list_rds_instances(self) -> list[RdsInstanceSnapshot]:
        request = self._rds_models().DescribeDBInstancesRequest(
            region_id=self.region,
            dbinstance_id=self.settings.aliyun_rds_instance_id,
            vpc_id=self.settings.aliyun_vpc_id,
            page_size=30,
        )
        response = self._rds_client_lazy().describe_dbinstances(request)
        instances = (
            response.body.to_map()
            .get("Items", {})
            .get("DBInstance", [])
            or []
        )
        snapshots: list[RdsInstanceSnapshot] = []
        for instance in instances:
            instance_id = instance.get("DBInstanceId")
            if not instance_id:
                continue
            attrs = self._rds_instance_attributes(instance_id)
            whitelists = self._rds_whitelist_cidrs(instance_id)
            snapshots.append(RdsInstanceSnapshot(
                instance_id=instance_id,
                engine=str(attrs.get("Engine") or instance.get("Engine") or ""),
                network_type=str(
                    attrs.get("InstanceNetworkType")
                    or instance.get("InstanceNetworkType")
                    or instance.get("DBInstanceNetType")
                    or ""
                ),
                whitelist_cidrs=whitelists,
                backup_retention_days=self._int_or_none(
                    attrs.get("BackupRetentionPeriod") or attrs.get("BackupPolicy")
                ),
                storage_used_percent=self._storage_used_percent(attrs),
            ))
        return snapshots

    def list_oss_buckets(self) -> list[OssBucketSnapshot]:
        bucket_names = [self.settings.aliyun_oss_bucket] if self.settings.aliyun_oss_bucket else []
        if not bucket_names:
            bucket_names = self._list_oss_bucket_names()
        return [self._oss_bucket_snapshot(name) for name in bucket_names if name]

    def _latest_cms_metric(self, instance_id: str, metric_name: str) -> float:
        request = self._cms_models().DescribeMetricLastRequest(
            namespace="acs_ecs_dashboard",
            metric_name=metric_name,
            region_id=self.region,
            dimensions=json.dumps({"instanceId": instance_id}),
            period="60",
        )
        try:
            response = self._cms_client_lazy().describe_metric_last(request)
            datapoints = json.loads(response.body.datapoints or "[]")
        except Exception:
            return 0.0
        values = [point.get("Maximum") or point.get("Average") or point.get("Value") for point in datapoints]
        numeric_values = [float(value) for value in values if value is not None]
        return max(numeric_values) if numeric_values else 0.0

    def _ecs_client_lazy(self):
        if self._ecs_client is None:
            from alibabacloud_ecs20140526.client import Client as EcsClient

            self._ecs_client = EcsClient(self._openapi_config("ecs"))
        return self._ecs_client

    def _cms_client_lazy(self):
        if self._cms_client is None:
            from alibabacloud_cms20190101.client import Client as CmsClient

            self._cms_client = CmsClient(self._openapi_config("cms"))
        return self._cms_client

    def _oos_client_lazy(self):
        if self._oos_client is None:
            from alibabacloud_oos20190601.client import Client as OosClient

            self._oos_client = OosClient(self._openapi_config("oos"))
        return self._oos_client

    def _actiontrail_client_lazy(self):
        if self._actiontrail_client is None:
            from alibabacloud_actiontrail20200706.client import Client as ActionTrailClient

            self._actiontrail_client = ActionTrailClient(self._openapi_config("actiontrail"))
        return self._actiontrail_client

    def _rds_client_lazy(self):
        if self._rds_client is None:
            from alibabacloud_rds20140815.client import Client as RdsClient

            self._rds_client = RdsClient(self._openapi_config("rds"))
        return self._rds_client

    def _openapi_config(self, product: str):
        from alibabacloud_tea_openapi import models as openapi_models

        if not self.settings.aliyun_access_key_id or not self.settings.aliyun_access_key_secret:
            raise ValueError("Missing ALIBABA_CLOUD_ACCESS_KEY_ID or ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        endpoint = {
            "ecs": f"ecs.{self.region}.aliyuncs.com",
            "cms": "metrics.cn-shanghai.aliyuncs.com",
            "oos": f"oos.{self.region}.aliyuncs.com",
            "actiontrail": self.settings.aliyun_actiontrail_endpoint,
            "rds": f"rds.{self.region}.aliyuncs.com",
        }[product]
        return openapi_models.Config(
            access_key_id=self.settings.aliyun_access_key_id,
            access_key_secret=self.settings.aliyun_access_key_secret,
            endpoint=endpoint,
        )

    @staticmethod
    def _ecs_models():
        from alibabacloud_ecs20140526 import models as ecs_models

        return ecs_models

    @staticmethod
    def _cms_models():
        from alibabacloud_cms20190101 import models as cms_models

        return cms_models

    @staticmethod
    def _oos_models():
        from alibabacloud_oos20190601 import models as oos_models

        return oos_models

    @staticmethod
    def _actiontrail_models():
        from alibabacloud_actiontrail20200706 import models as actiontrail_models

        return actiontrail_models

    @staticmethod
    def _rds_models():
        from alibabacloud_rds20140815 import models as rds_models

        return rds_models

    def _rds_instance_attributes(self, instance_id: str) -> dict:
        request = self._rds_models().DescribeDBInstanceAttributeRequest(dbinstance_id=instance_id)
        try:
            response = self._rds_client_lazy().describe_dbinstance_attribute(request)
            attrs = response.body.to_map().get("Items", {}).get("DBInstanceAttribute", []) or []
        except Exception:
            return {}
        return attrs[0] if attrs else {}

    def _rds_whitelist_cidrs(self, instance_id: str) -> list[str]:
        request = self._rds_models().DescribeDBInstanceIPArrayListRequest(dbinstance_id=instance_id)
        try:
            response = self._rds_client_lazy().describe_dbinstance_iparray_list(request)
            arrays = response.body.to_map().get("Items", {}).get("DBInstanceIPArray", []) or []
        except Exception:
            return []
        cidrs: list[str] = []
        for item in arrays:
            raw = item.get("SecurityIPList") or ""
            cidrs.extend(value.strip() for value in str(raw).split(",") if value.strip())
        return cidrs

    @staticmethod
    def _storage_used_percent(attrs: dict) -> float:
        used = AliyunReadOnlyProvider._float_or_none(
            attrs.get("DBInstanceStorageUsed") or attrs.get("DataSize")
        )
        total = AliyunReadOnlyProvider._float_or_none(
            attrs.get("DBInstanceStorage") or attrs.get("DBInstanceStorageSize")
        )
        if used is None or total is None or total <= 0:
            return 0.0
        if used > total and total < 1_000_000:
            total = total * 1024 * 1024 * 1024
        return min(100.0, used / total * 100)

    def _list_oss_bucket_names(self) -> list[str]:
        import oss2

        service = oss2.Service(self._oss_auth(), self._oss_endpoint())
        return [bucket.name for bucket in oss2.BucketIterator(service)]

    def _oss_bucket_snapshot(self, bucket_name: str) -> OssBucketSnapshot:
        bucket = self._oss_bucket(bucket_name)
        return OssBucketSnapshot(
            bucket_name=bucket_name,
            acl=self._oss_acl(bucket),
            server_side_encryption_enabled=self._oss_encryption_enabled(bucket),
            public_access_block_enabled=self._oss_public_access_block_enabled(bucket),
            lifecycle_rule_count=self._oss_lifecycle_rule_count(bucket),
        )

    def _oss_bucket(self, bucket_name: str):
        import oss2

        return oss2.Bucket(self._oss_auth(), self._oss_endpoint(), bucket_name)

    def _oss_auth(self):
        import oss2

        if not self.settings.aliyun_access_key_id or not self.settings.aliyun_access_key_secret:
            raise ValueError("Missing ALIBABA_CLOUD_ACCESS_KEY_ID or ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        return oss2.Auth(self.settings.aliyun_access_key_id, self.settings.aliyun_access_key_secret)

    def _oss_endpoint(self) -> str:
        return f"https://oss-{self.region}.aliyuncs.com"

    @staticmethod
    def _oss_acl(bucket) -> str:
        try:
            return str(bucket.get_bucket_acl().acl)
        except Exception:
            return "unknown"

    @staticmethod
    def _oss_encryption_enabled(bucket) -> bool | None:
        try:
            bucket.get_bucket_encryption()
            return True
        except Exception as exc:
            if getattr(exc, "code", "") == "NoSuchServerSideEncryptionRule":
                return False
            return None

    @staticmethod
    def _oss_public_access_block_enabled(bucket) -> bool | None:
        try:
            result = bucket.get_bucket_public_access_block()
            value = getattr(result, "block_public_access", False)
            if isinstance(value, str):
                return value.lower() == "true"
            return bool(value)
        except Exception:
            return None

    @staticmethod
    def _oss_lifecycle_rule_count(bucket) -> int | None:
        try:
            result = bucket.get_bucket_lifecycle()
            rules = getattr(result, "rules", None)
            return len(rules or [])
        except Exception:
            return None

    @staticmethod
    def _int_or_none(value) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float_or_none(value) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class AliyunNativeSignalProvider:
    """Read CloudMonitor-like native signals for the configured ECS instance."""

    def __init__(self, provider: AliyunReadOnlyProvider) -> None:
        self.provider = provider

    def list_signals(self) -> list[NativeSignal]:
        signals: list[NativeSignal] = []
        for instance in self.provider.list_instances():
            if instance.disk_used_percent >= 85:
                signals.append(NativeSignal(
                    id=f"cms-disk-{instance.instance_id}",
                    source="cloudmonitor",
                    signal_type="metric_alarm",
                    severity="high",
                    resource_id=instance.instance_id,
                    title="Disk usage exceeded threshold",
                    summary=f"CloudMonitor metric diskusage_utilization is {instance.disk_used_percent:.1f}%.",
                    observed_at=datetime.now(timezone.utc),
                    payload={
                        "namespace": "acs_ecs_dashboard",
                        "metric": "diskusage_utilization",
                        "value": instance.disk_used_percent,
                        "threshold": 85.0,
                    },
                ))
        signals.extend(self._ecs_health_signals())
        signals.extend(self._oos_execution_signals())
        signals.extend(self._actiontrail_change_signals())
        return signals

    def _ecs_health_signals(self) -> list[NativeSignal]:
        if not self.provider.instance_id:
            return []
        request = self.provider._ecs_models().DescribeInstancesFullStatusRequest(
            region_id=self.provider.region,
            instance_id=[self.provider.instance_id],
            page_size=10,
        )
        try:
            response = self.provider._ecs_client_lazy().describe_instances_full_status(request)
            statuses = response.body.to_map().get("InstanceFullStatusSet", {}).get("InstanceFullStatusType", []) or []
        except Exception:
            return []
        signals: list[NativeSignal] = []
        now = datetime.now(timezone.utc)
        for status in statuses:
            instance_id = status.get("InstanceId") or self.provider.instance_id
            health = status.get("HealthStatus", {}).get("Status")
            if health and health.lower() != "ok":
                signals.append(NativeSignal(
                    id=f"ecs-health-{instance_id}-{int(now.timestamp())}",
                    source="ecs",
                    signal_type="health_event",
                    severity="high",
                    resource_id=instance_id,
                    title="ECS health status is not OK",
                    summary=f"ECS full status reports health status {health}.",
                    observed_at=now,
                    payload=status,
                ))
        return signals

    def _oos_execution_signals(self) -> list[NativeSignal]:
        request = self.provider._oos_models().ListExecutionsRequest(
            region_id=self.provider.region,
            max_results=self.provider.settings.aliyun_signal_max_results,
            sort_field="StartDate",
            sort_order="Descending",
        )
        try:
            response = self.provider._oos_client_lazy().list_executions(request)
            executions = response.body.to_map().get("Executions", []) or []
        except Exception as exc:
            return [self._provider_error_signal("oos", "execution_record", exc)]

        signals: list[NativeSignal] = []
        for execution in executions:
            resource_id = self._resource_id_from_payload(execution) or self.provider.instance_id or "unknown"
            if not self._is_relevant_resource(resource_id, execution):
                continue
            status = str(execution.get("Status") or "Unknown")
            template_name = str(execution.get("TemplateName") or execution.get("TemplateId") or "unknown")
            execution_id = str(execution.get("ExecutionId") or self._stable_id(execution))
            severity = "high" if status.lower() in {"failed", "cancelled", "timeout"} else "info"
            signals.append(NativeSignal(
                id=f"oos-{execution_id}",
                source="oos",
                signal_type="execution_record",
                severity=severity,
                resource_id=resource_id,
                title=f"OOS execution {status}",
                summary=f"OOS execution {execution_id} for {template_name} is {status}.",
                observed_at=self._parse_time(execution.get("StartDate")) or datetime.now(timezone.utc),
                payload=execution,
            ))
        return signals

    def _actiontrail_change_signals(self) -> list[NativeSignal]:
        resource_ids = [
            resource_id
            for resource_id in (
                self.provider.instance_id,
                self.provider.security_group_id,
                self.provider.settings.aliyun_rds_instance_id,
                self.provider.settings.aliyun_oss_bucket,
            )
            if resource_id
        ]
        if not resource_ids:
            resource_ids = [self.provider.settings.aliyun_account_id or "account"]

        seen: set[str] = set()
        signals: list[NativeSignal] = []
        errors: list[NativeSignal] = []
        for resource_id in resource_ids:
            try:
                events = self._lookup_actiontrail_events(resource_id)
            except Exception as exc:
                errors.append(self._provider_error_signal("actiontrail", "change_event", exc, resource_id))
                continue
            for event in events:
                event_id = str(event.get("EventId") or event.get("RequestId") or self._stable_id(event))
                if event_id in seen:
                    continue
                seen.add(event_id)
                event_name = str(event.get("EventName") or "UnknownEvent")
                username = str(event.get("Username") or event.get("UserIdentity") or "unknown")
                event_resource_id = self._resource_id_from_payload(event) or resource_id
                signals.append(NativeSignal(
                    id=f"actiontrail-{event_id}",
                    source="actiontrail",
                    signal_type="change_event",
                    severity=self._actiontrail_severity(event_name),
                    resource_id=event_resource_id,
                    title=f"Recent cloud API change: {event_name}",
                    summary=f"ActionTrail recorded {event_name} by {username}.",
                    observed_at=self._parse_time(event.get("EventTime")) or datetime.now(timezone.utc),
                    payload=event,
                ))
        return signals or errors

    def _lookup_actiontrail_events(self, resource_id: str) -> list[dict]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=self.provider.settings.aliyun_signal_lookback_hours)
        attr = self.provider._actiontrail_models().LookupEventsRequestLookupAttribute(
            key="ResourceName",
            value=resource_id,
        )
        request = self.provider._actiontrail_models().LookupEventsRequest(
            start_time=self._format_aliyun_time(start),
            end_time=self._format_aliyun_time(end),
            lookup_attribute=[attr],
            max_results=str(self.provider.settings.aliyun_signal_max_results),
            direction="Backwards",
        )
        response = self.provider._actiontrail_client_lazy().lookup_events(request)
        return response.body.to_map().get("Events", []) or []

    def _provider_error_signal(
        self,
        source: str,
        signal_type: str,
        exc: Exception,
        resource_id: str | None = None,
    ) -> NativeSignal:
        now = datetime.now(timezone.utc)
        return NativeSignal(
            id=f"{source}-error-{int(now.timestamp())}",
            source=source,
            signal_type="provider_error",
            severity="medium",
            resource_id=resource_id or next(iter(self._configured_resource_ids()), "account"),
            title=f"{source} signal read failed",
            summary=f"Failed to read {source} {signal_type}: {exc}",
            observed_at=now,
            payload={"error": str(exc), "requested_signal_type": signal_type},
        )

    def _is_relevant_resource(self, resource_id: str, payload: dict) -> bool:
        configured_resources = self._configured_resource_ids()
        if resource_id in configured_resources:
            return True
        encoded = json.dumps(payload, ensure_ascii=False)
        return any(configured in encoded for configured in configured_resources)

    def _resource_id_from_payload(self, payload: dict) -> str | None:
        for key in ("ResourceId", "ResourceName", "resourceId", "resourceName"):
            value = payload.get(key)
            if value:
                return str(value)
        encoded = json.dumps(payload, ensure_ascii=False)
        for configured in self._configured_resource_ids():
            if configured in encoded:
                return configured
        return None

    def _configured_resource_ids(self) -> set[str]:
        return {
            resource_id
            for resource_id in (
                self.provider.instance_id,
                self.provider.security_group_id,
                self.provider.settings.aliyun_rds_instance_id,
                self.provider.settings.aliyun_oss_bucket,
            )
            if resource_id
        }

    @staticmethod
    def _actiontrail_severity(event_name: str) -> str:
        lowered = event_name.lower()
        if any(token in lowered for token in ("delete", "revoke", "stop", "release", "detach")):
            return "high"
        if any(token in lowered for token in ("create", "authorize", "modify", "update", "start")):
            return "medium"
        return "info"

    @staticmethod
    def _stable_id(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(encoded.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _parse_time(value) -> datetime | None:
        if not value:
            return None
        text = str(value).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _format_aliyun_time(value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
