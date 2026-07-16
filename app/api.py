from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException

from .domain import ApprovalRequest, ScanRequest
from .providers import MockCloudProvider
from .scanner import Scanner
from .service import SoloOpsService
from .store import MemoryStore


@lru_cache
def service() -> SoloOpsService:
    return SoloOpsService(MemoryStore(), Scanner())


app = FastAPI(title="SoloOps", version="0.1.0", description="Approval-gated cloud operations MVP")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/scans")
def run_scan(request: ScanRequest):
    if request.provider != "mock":
        raise HTTPException(status_code=501, detail="Only the offline mock provider is enabled in this build")
    return service().scan("mock", MockCloudProvider())


@app.get("/api/v1/findings")
def list_findings():
    return list(service().store.findings.values())


@app.post("/api/v1/findings/{finding_id}/plans")
def create_plan(finding_id: str):
    return service().create_plan(finding_id)


@app.post("/api/v1/plans/{plan_id}/approve")
def approve_plan(plan_id: str, request: ApprovalRequest):
    return service().approve(plan_id, request.approver, request.comment)


@app.post("/api/v1/plans/{plan_id}/execute")
def execute_plan(plan_id: str):
    enabled = os.getenv("SOLOOPS_EXECUTION_ENABLED", "false").lower() == "true"
    return service().execute(plan_id, enabled=enabled)
