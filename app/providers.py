from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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


class CloudProvider(Protocol):
    """Read-only cloud inventory port. Implementations must not mutate resources."""

    def list_instances(self) -> list[InstanceSnapshot]: ...

    def list_security_group_rules(self) -> list[SecurityGroupRule]: ...


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


class AliyunReadOnlyProvider:
    """Integration seam for Alibaba Cloud SDK.

    Deliberately unimplemented in the MVP: it must be instantiated only with a
    short-lived read-only RAM/STS role. See docs/iam.md before implementing it.
    """

    def __init__(self, region: str) -> None:
        self.region = region

    def list_instances(self) -> list[InstanceSnapshot]:
        raise NotImplementedError("Configure an STS read role and Alibaba SDK adapter first.")

    def list_security_group_rules(self) -> list[SecurityGroupRule]:
        raise NotImplementedError("Configure an STS read role and Alibaba SDK adapter first.")
