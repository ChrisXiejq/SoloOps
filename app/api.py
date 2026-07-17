from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException

from .domain import ApprovalRequest, ScanRequest
from .providers import MockCloudProvider
from .scanner import Scanner
from .service import SoloOpsService
from .settings import get_settings
from .store import MemoryStore, SQLAlchemyStore, Store


@lru_cache
def service() -> SoloOpsService:
    settings = get_settings()
    store: Store
    if settings.store_backend == "memory":
        store = MemoryStore()
    else:
        store = SQLAlchemyStore(settings.database_url)
    return SoloOpsService(store, Scanner())


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
    return service().store.list_findings()


@app.post("/api/v1/findings/{finding_id}/plans")
def create_plan(finding_id: str):
    return service().create_plan(finding_id)


@app.post("/api/v1/plans/{plan_id}/approve")
def approve_plan(plan_id: str, request: ApprovalRequest):
    return service().approve(plan_id, request.approver, request.comment)


@app.post("/api/v1/plans/{plan_id}/execute")
def execute_plan(plan_id: str):
    return service().execute(plan_id, enabled=get_settings().execution_enabled)
