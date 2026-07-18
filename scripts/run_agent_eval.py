from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agent import AgentEngine
from app.domain import Evidence, Finding
from app.playbooks import PlaybookRegistry
from app.settings import Settings


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finding_from_case(case: dict) -> Finding:
    return Finding(
        rule_id=case["rule_id"],
        title=case.get("title") or case["rule_id"],
        severity=case["severity"],
        resource_id=case["resource_id"],
        description=case["description"],
        evidence=[Evidence(**item) for item in case.get("evidence", [])],
        remediation_action=case["remediation_action"],
    )


def engine() -> AgentEngine:
    os.environ["SOLOOPS_MODEL_PROVIDER"] = "mock"
    playbooks = PlaybookRegistry()
    return AgentEngine(
        Settings(model_provider="mock", model_name="deterministic-agent"),
        {playbook.action: playbook for playbook in playbooks.list()},
    )


def assert_forbidden_absent(output: dict, forbidden: list[str]) -> None:
    encoded = json.dumps(output, ensure_ascii=False).lower()
    for token in forbidden:
        assert token.lower() not in encoded, f"forbidden token leaked: {token}"


def run_golden() -> int:
    failures = 0
    agent = engine()
    for case in load_jsonl(ROOT / "evals" / "agent_golden.jsonl"):
        run = agent.triage_finding(finding_from_case(case))
        expected = case["expected"]
        try:
            assert run.output["recommended_playbook"] == expected["recommended_playbook"]
            assert run.output["needs_more_evidence"] is expected["needs_more_evidence"]
            encoded = json.dumps(run.output, ensure_ascii=False).lower()
            for token in expected.get("must_mention", []):
                assert token.lower() in encoded, f"missing expected token: {token}"
            assert_forbidden_absent(run.output, expected.get("forbidden", []))
        except AssertionError as exc:
            failures += 1
            print(f"FAIL golden {case['case_id']}: {exc}")
    return failures


def run_red_team() -> int:
    failures = 0
    agent = engine()
    for case in load_jsonl(ROOT / "evals" / "red_team_agent.jsonl"):
        run = agent.triage_finding(finding_from_case(case))
        try:
            for flag in case.get("expected_flags", []):
                assert flag in run.safety_flags, f"missing expected safety flag: {flag}"
            assert_forbidden_absent(run.output, case.get("forbidden", []))
        except AssertionError as exc:
            failures += 1
            print(f"FAIL redteam {case['case_id']}: {exc}")
    return failures


def main() -> None:
    failures = run_golden() + run_red_team()
    if failures:
        raise SystemExit(f"agent eval failed: {failures} failures")
    print("agent eval passed")


if __name__ == "__main__":
    main()
