from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .domain import ApprovalRequest, ScanRequest
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


app = FastAPI(
    title="SoloOps",
    version="0.1.0",
    description="AI governance layer for cloud-native alerts, evidence, approvals, and controlled remediation.",
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def console() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/api/v1/scans")
def run_scan(request: ScanRequest):
    if request.provider not in {"mock", "aliyun"}:
        raise HTTPException(status_code=501, detail="Only mock and aliyun providers are enabled in this build")
    return service().request_scan(request.provider)


@app.get("/api/v1/scans")
def list_scans():
    return service().list_scans()


@app.get("/api/v1/scans/{scan_id}")
def get_scan(scan_id: str):
    return service().get_scan(scan_id)


@app.get("/api/v1/findings")
def list_findings():
    return service().store.list_findings()


@app.get("/api/v1/findings/{finding_id}")
def get_finding(finding_id: str):
    return service().get_finding(finding_id)


@app.post("/api/v1/findings/{finding_id}/plans")
def create_plan(finding_id: str):
    return service().create_plan(finding_id)


@app.get("/api/v1/plans/{plan_id}")
def get_plan(plan_id: str):
    return service().get_plan(plan_id)


@app.get("/api/v1/audit-events")
def list_audit_events():
    return service().list_audit_events()


@app.get("/api/v1/executions/{execution_id}")
def get_execution(execution_id: str):
    return service().get_execution(execution_id)


@app.get("/api/v1/playbooks")
def list_playbooks():
    return service().list_playbooks()


@app.get("/api/v1/native-signals")
def list_native_signals(provider: str = "mock"):
    if provider not in {"mock", "aliyun"}:
        raise HTTPException(status_code=501, detail="Only mock and aliyun providers are enabled in this build")
    return service().list_native_signals(provider)


@app.post("/api/v1/plans/{plan_id}/approve")
def approve_plan(plan_id: str, request: ApprovalRequest):
    return service().approve(plan_id, request.approver, request.comment)


@app.post("/api/v1/plans/{plan_id}/execute")
def execute_plan(plan_id: str):
    return service().execute(plan_id, enabled=get_settings().execution_enabled)
