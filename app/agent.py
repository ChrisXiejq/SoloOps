from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Any

from .domain import AgentRun, AgentRunStatus, Finding
from .playbooks import Playbook
from .settings import Settings


OUTPUT_SCHEMA: dict[str, Any] = {
    "summary": "string",
    "impact": "string",
    "blast_radius": "string",
    "why_now": "string",
    "confidence": "high|medium|low",
    "confidence_reason": "string",
    "needs_more_evidence": "boolean",
    "evidence_used": ["string"],
    "evidence_gaps": ["string"],
    "recommended_playbook": "string|null",
    "safe_next_steps": ["string"],
    "human_questions": ["string"],
    "rollback_considerations": ["string"],
    "prohibited_actions_checked": ["string"],
    "residual_risk": "string",
}

DESTRUCTIVE_TOKENS = (
    "rm -rf",
    "drop database",
    "delete instance",
    "delete security group",
    "disable audit",
    "disable actiontrail",
    "turn off monitoring",
    "aliyun ecs Delete",
    "grant *",
)

PROMPT_INJECTION_TOKENS = (
    "ignore approval",
    "bypass approval",
    "ignore previous",
    "直接执行",
    "绕过审批",
    "关闭审计",
    "扩大权限",
)


class AgentEngine:
    """Evidence-grounded read-only Agent runner."""

    def __init__(self, settings: Settings, playbooks: dict[str, Playbook]) -> None:
        self.settings = settings
        self.playbooks = playbooks

    def triage_finding(self, finding: Finding) -> AgentRun:
        playbook = self.playbooks.get(finding.remediation_action)
        input_refs = self._input_refs(finding, playbook)
        safety_flags = self._input_safety_flags(finding)
        model = self._selected_model()

        try:
            output = self._call_model(finding, playbook, input_refs)
            output, validation_flags = self._validate_output(output, finding, playbook)
            safety_flags.extend(validation_flags)
            status = AgentRunStatus.SUCCEEDED if not validation_flags else AgentRunStatus.FALLBACK
            if validation_flags:
                output = self._fallback_output(finding, playbook, validation_flags)
        except Exception as exc:
            safety_flags.append(f"model_fallback:{type(exc).__name__}")
            output = self._fallback_output(finding, playbook, [str(exc)])
            status = AgentRunStatus.FALLBACK

        return AgentRun(
            finding_id=finding.id,
            agent_type="triage",
            model=model,
            input_refs=input_refs,
            output=output,
            safety_flags=sorted(set(safety_flags)),
            status=status,
        )

    def _selected_model(self) -> str:
        if self.settings.model_provider == "aliyun_bailian":
            return self.settings.model_name or "qwen-plus"
        return self.settings.model_name or "deterministic-agent"

    def _call_model(
        self,
        finding: Finding,
        playbook: Playbook | None,
        input_refs: dict[str, Any],
    ) -> dict[str, Any]:
        if self.settings.model_provider != "aliyun_bailian" or not self.settings.bailian_api_key:
            raise RuntimeError("aliyun_bailian model is not configured")

        payload = {
            "model": self.settings.model_name or "qwen-plus",
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the SoloOps Triage Agent. You are read-only. "
                        "Explain evidence, impact, uncertainty, and the allowlisted playbook. "
                        "Do not invent evidence. Do not generate shell commands. "
                        "Do not suggest bypassing approval, widening permissions, disabling audit, "
                        "or changing the target/action outside the provided playbook."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "Return one JSON object matching output_schema.",
                            "output_schema": OUTPUT_SCHEMA,
                            "finding": input_refs["finding"],
                            "playbook": input_refs.get("playbook"),
                            "safety_constraints": [
                                "Use only supplied evidence.",
                                "If evidence is incomplete, set needs_more_evidence=true.",
                                "recommended_playbook must equal the supplied playbook action or null.",
                                "No shell commands or destructive cloud actions.",
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        request = urllib.request.Request(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.bailian_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"bailian request failed: {exc.code} {detail[:300]}") from exc

        content = body["choices"][0]["message"]["content"]
        return json.loads(content)

    def _validate_output(
        self,
        output: dict[str, Any],
        finding: Finding,
        playbook: Playbook | None,
    ) -> tuple[dict[str, Any], list[str]]:
        flags: list[str] = []
        required_keys = set(OUTPUT_SCHEMA)
        missing = sorted(required_keys - set(output))
        if missing:
            flags.append(f"missing_output_keys:{','.join(missing)}")
        output = self._normalize_playbook_reference(output, playbook)
        if output.get("recommended_playbook") not in {None, finding.remediation_action}:
            flags.append("recommended_playbook_not_allowlisted")
        if playbook and output.get("recommended_playbook") not in {None, playbook.action}:
            flags.append("recommended_playbook_mismatch")
        encoded = json.dumps(output, ensure_ascii=False).lower()
        if any(token.lower() in encoded for token in DESTRUCTIVE_TOKENS):
            flags.append("destructive_content_detected")
        if output.get("confidence") not in {"high", "medium", "low"}:
            flags.append("invalid_confidence")
        return output, flags

    @staticmethod
    def _normalize_playbook_reference(
        output: dict[str, Any],
        playbook: Playbook | None,
    ) -> dict[str, Any]:
        if not playbook:
            return output
        recommended = output.get("recommended_playbook")
        if isinstance(recommended, dict):
            recommended = recommended.get("action") or recommended.get("id") or recommended.get("title")
        if isinstance(recommended, str):
            normalized = recommended.strip()
            if normalized in {playbook.action, playbook.id, playbook.title}:
                output["recommended_playbook"] = playbook.action
            else:
                output["recommended_playbook"] = normalized
        return output

    def _input_refs(self, finding: Finding, playbook: Playbook | None) -> dict[str, Any]:
        return {
            "finding": finding.model_dump(mode="json"),
            "playbook": asdict(playbook) if playbook else None,
            "evidence_count": len(finding.evidence),
            "evidence_sources": sorted({evidence.source for evidence in finding.evidence}),
        }

    def _input_safety_flags(self, finding: Finding) -> list[str]:
        encoded = json.dumps(finding.model_dump(mode="json"), ensure_ascii=False).lower()
        flags: list[str] = []
        if any(token.lower() in encoded for token in PROMPT_INJECTION_TOKENS):
            flags.append("prompt_injection_like_evidence")
        if not finding.evidence:
            flags.append("missing_evidence")
        if finding.remediation_action not in self.playbooks:
            flags.append("unknown_remediation_action")
        return flags

    def _fallback_output(
        self,
        finding: Finding,
        playbook: Playbook | None,
        reasons: list[str],
    ) -> dict[str, Any]:
        evidence_summaries = [self._safe_text(evidence.summary) for evidence in finding.evidence]
        evidence_gaps = []
        if not finding.evidence:
            evidence_gaps.append("No structured evidence is attached to this finding.")
        if not playbook:
            evidence_gaps.append("No allowlisted playbook is registered for the remediation action.")

        rule_guidance = self._rule_guidance(finding)
        return {
            "summary": rule_guidance["summary"],
            "impact": rule_guidance["impact"],
            "blast_radius": f"Resource {finding.resource_id}; scope should not be expanded without new evidence.",
            "why_now": finding.description,
            "confidence": "high" if finding.evidence and playbook else "medium",
            "confidence_reason": (
                "The explanation is grounded in deterministic rule output and attached evidence. "
                f"Fallback reasons: {', '.join(reasons) or 'none'}."
            ),
            "needs_more_evidence": bool(evidence_gaps),
            "evidence_used": evidence_summaries,
            "evidence_gaps": evidence_gaps,
            "recommended_playbook": playbook.action if playbook else None,
            "safe_next_steps": self._safe_next_steps(finding, playbook),
            "human_questions": rule_guidance["questions"],
            "rollback_considerations": self._rollback_considerations(playbook),
            "prohibited_actions_checked": [
                "No shell command was generated.",
                "No non-allowlisted playbook was recommended.",
                "No approval bypass was suggested.",
                "No broader cloud permission was requested.",
            ],
            "residual_risk": rule_guidance["residual_risk"],
        }

    def _rule_guidance(self, finding: Finding) -> dict[str, Any]:
        guidance = {
            "SG-001": {
                "summary": "PostgreSQL is reachable from the public internet.",
                "impact": "Attackers can attempt brute force, exploit database vulnerabilities, or enumerate exposed service metadata.",
                "questions": ["Is any legitimate external client expected to connect directly to PostgreSQL?"],
                "residual_risk": "Application-level database credentials and database audit posture still need separate review.",
            },
            "ECS-001": {
                "summary": "The ECS instance is under disk capacity pressure.",
                "impact": "High disk usage can cause failed writes, service crashes, log loss, or failed deployments.",
                "questions": ["Which mount point or workload owns the growth?"],
                "residual_risk": "Disk cleanup or expansion still requires operator validation after diagnosis.",
            },
            "ECS-002": {
                "summary": "Container restart behavior indicates a possible application or runtime instability.",
                "impact": "Repeated restarts can reduce availability, hide startup errors, and amplify downstream retries.",
                "questions": ["Was there a recent deployment, config change, or dependency outage?"],
                "residual_risk": "Root cause remains unconfirmed until logs, exit codes, and deployment context are reviewed.",
            },
            "RDS-001": {
                "summary": "The RDS network whitelist allows broad public access.",
                "impact": "Public database exposure increases brute-force and exploitation risk.",
                "questions": ["Which client CIDRs actually require database access?"],
                "residual_risk": "Credential, audit, and SQL permission posture still need independent checks.",
            },
            "RDS-002": {
                "summary": "RDS backup retention is disabled or effectively absent.",
                "impact": "Data recovery may be impossible after accidental deletion, corruption, or failed migration.",
                "questions": ["What recovery point objective is required for this database?"],
                "residual_risk": "A backup policy still needs restore testing to be trustworthy.",
            },
            "RDS-003": {
                "summary": "RDS storage usage is high.",
                "impact": "Database writes, replication, and maintenance operations may fail under storage pressure.",
                "questions": ["Is the growth caused by tables, binlogs, indexes, or temporary data?"],
                "residual_risk": "Capacity changes may affect cost and need workload-aware validation.",
            },
            "OSS-001": {
                "summary": "OSS bucket public access settings are risky.",
                "impact": "Public bucket access can expose sensitive objects or allow unintended writes.",
                "questions": ["Is this bucket intentionally public, and are object prefixes scoped?"],
                "residual_risk": "Object-level ACLs and bucket policy still need separate review.",
            },
            "OSS-002": {
                "summary": "OSS server-side encryption is not enabled.",
                "impact": "Stored objects lack the expected at-rest encryption control from OSS configuration.",
                "questions": ["Does this bucket store sensitive or regulated data?"],
                "residual_risk": "Encryption does not replace access control or data classification.",
            },
        }
        return guidance.get(finding.rule_id, {
            "summary": finding.title,
            "impact": "Impact depends on the attached evidence and affected resource.",
            "questions": ["What additional evidence confirms this risk?"],
            "residual_risk": "Residual risk is unknown until more evidence is collected.",
        })

    @staticmethod
    def _safe_next_steps(finding: Finding, playbook: Playbook | None) -> list[str]:
        steps = [
            "Review the evidence attached to the finding.",
            "Confirm the affected resource and business owner.",
        ]
        if playbook:
            steps.append(f"Create a plan using the allowlisted playbook: {playbook.action}.")
            steps.append("Require human approval before any real execution.")
        else:
            steps.append("Do not execute remediation until a playbook is registered.")
        if finding.severity.value in {"critical", "high"}:
            steps.append("Prioritize this finding in the next operational review.")
        return steps

    @staticmethod
    def _rollback_considerations(playbook: Playbook | None) -> list[str]:
        if not playbook:
            return ["No rollback can be described because no playbook is registered."]
        if playbook.rollback:
            return [f"Rollback path: {playbook.rollback}.", "Rollback should require explicit approval."]
        return ["This playbook is read-only or diagnostic; rollback is not required for cloud state."]

    @staticmethod
    def _safe_text(value: str) -> str:
        sanitized = value
        for token in DESTRUCTIVE_TOKENS:
            sanitized = sanitized.replace(token, "[redacted unsafe instruction]")
            sanitized = sanitized.replace(token.upper(), "[redacted unsafe instruction]")
        return sanitized
