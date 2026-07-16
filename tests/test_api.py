from fastapi.testclient import TestClient

from app.api import app, service


def reset_store() -> None:
    service.cache_clear()


def test_scan_detects_expected_findings() -> None:
    reset_store()
    client = TestClient(app)
    response = client.post("/api/v1/scans", json={"provider": "mock"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["findings"]) == 3
    assert any(f["rule_id"] == "SG-001" for f in payload["findings"])


def test_execution_requires_approval_then_dry_runs() -> None:
    reset_store()
    client = TestClient(app)
    scan = client.post("/api/v1/scans", json={"provider": "mock"}).json()
    critical = next(item for item in scan["findings"] if item["rule_id"] == "SG-001")
    plan = client.post(f"/api/v1/findings/{critical['id']}/plans").json()

    denied = client.post(f"/api/v1/plans/{plan['id']}/execute")
    assert denied.status_code == 409

    approved = client.post(f"/api/v1/plans/{plan['id']}/approve", json={"approver": "owner"})
    assert approved.status_code == 200
    execution = client.post(f"/api/v1/plans/{plan['id']}/execute")
    assert execution.status_code == 200
    assert execution.json()["status"] == "succeeded"
    assert "no cloud resource was changed" in execution.json()["verification"].lower()
