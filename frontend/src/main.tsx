import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api";
import type { AgentRun, AuditEvent, Finding, NativeSignal, RemediationPlan, ScanResult } from "./types";
import "./styles.css";

function severityClass(severity: string): string {
  return `badge ${severity}`;
}

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function App() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [selected, setSelected] = useState<Finding | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [nativeSignals, setNativeSignals] = useState<NativeSignal[]>([]);
  const [lastScan, setLastScan] = useState<ScanResult | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);
  const [plan, setPlan] = useState<RemediationPlan | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const severityCounts = useMemo(() => {
    return findings.reduce<Record<string, number>>((acc, finding) => {
      acc[finding.severity] = (acc[finding.severity] ?? 0) + 1;
      return acc;
    }, {});
  }, [findings]);

  async function refresh() {
    const [nextFindings, nextAudit] = await Promise.all([
      api.listFindings(),
      api.listAuditEvents()
    ]);
    setFindings(nextFindings);
    setAuditEvents(nextAudit);
  }

  async function loadFinding(findingId: string) {
    setError(null);
    const finding = await api.getFinding(findingId);
    setSelected(finding);
    setAgentRun(null);
    setPlan(null);
  }

  async function runScan(provider: "mock" | "aliyun") {
    setBusy(`scan-${provider}`);
    setError(null);
    try {
      const requested = await api.requestScan(provider);
      setLastScan(requested);
      let scan = requested;
      for (let attempt = 0; attempt < 60; attempt += 1) {
        scan = await api.getScan(requested.id);
        setLastScan(scan);
        if (scan.status === "succeeded" || scan.status === "failed") {
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function explainSelected() {
    if (!selected) {
      return;
    }
    setBusy("agent");
    setError(null);
    try {
      const run = await api.createAgentRun(selected.id);
      setAgentRun(run);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function createPlan() {
    if (!selected) {
      return;
    }
    setBusy("plan");
    setError(null);
    try {
      const nextPlan = await api.createPlan(selected.id);
      setPlan(nextPlan);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function loadSignals() {
    setBusy("signals");
    setError(null);
    try {
      setNativeSignals(await api.listNativeSignals("aliyun"));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    refresh().catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)));
  }, []);

  return (
    <div>
      <header className="hero">
        <div>
          <p className="eyebrow">SoloOps W8 Console</p>
          <h1>Cloud Governance Copilot</h1>
          <p>
            Evidence-first operations for Aliyun resources: scan, correlate, explain,
            approve, audit, and safely execute allowlisted playbooks.
          </p>
        </div>
        <div className="hero-card">
          <strong>Readiness</strong>
          <span>W1-W7 core complete</span>
          <span>W8 focus: deployment, demo data, production console</span>
        </div>
      </header>

      <main className="layout">
        {error && <section className="alert">{error}</section>}

        <section className="panel span-2 metrics">
          <Metric label="Findings" value={findings.length} />
          <Metric label="Critical" value={severityCounts.critical ?? 0} />
          <Metric label="High" value={severityCounts.high ?? 0} />
          <Metric label="Audit Events" value={auditEvents.length} />
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Findings</h2>
              <p>Run a mock demo scan or query the real Aliyun provider.</p>
            </div>
            <button className="ghost" onClick={refresh}>Refresh</button>
          </div>
          <div className="toolbar">
            <button disabled={busy !== null} onClick={() => runScan("mock")}>
              {busy === "scan-mock" ? "Scanning..." : "Run Mock Scan"}
            </button>
            <button className="secondary" disabled={busy !== null} onClick={() => runScan("aliyun")}>
              {busy === "scan-aliyun" ? "Scanning..." : "Run Aliyun Scan"}
            </button>
            <button className="secondary" disabled={busy !== null} onClick={loadSignals}>
              {busy === "signals" ? "Loading..." : "Load Native Signals"}
            </button>
          </div>
          {lastScan && (
            <p className="meta">
              Last scan {lastScan.id}: {lastScan.status}, {lastScan.findings.length} findings.
            </p>
          )}
          <div className="list">
            {findings.length === 0 && <p className="empty">No findings yet. Start with a mock scan.</p>}
            {findings.map((finding) => (
              <button
                key={finding.id}
                className={`finding ${selected?.id === finding.id ? "selected" : ""}`}
                onClick={() => loadFinding(finding.id)}
              >
                <span className={severityClass(finding.severity)}>{finding.severity}</span>
                <strong>{finding.title}</strong>
                <small>{finding.rule_id} · {finding.resource_id}</small>
                <span>{finding.description}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Finding Detail</h2>
              <p>Inspect evidence, generate Agent explanation, then create a plan.</p>
            </div>
          </div>
          {!selected ? (
            <p className="empty">Select a finding to inspect evidence.</p>
          ) : (
            <div className="detail">
              <span className={severityClass(selected.severity)}>{selected.severity}</span>
              <h3>{selected.title}</h3>
              <p>{selected.description}</p>
              <p className="meta">{selected.rule_id} · {selected.resource_id}</p>
              <div className="toolbar">
                <button disabled={busy !== null} onClick={explainSelected}>
                  {busy === "agent" ? "Explaining..." : "Explain with Agent"}
                </button>
                <button className="secondary" disabled={busy !== null} onClick={createPlan}>
                  {busy === "plan" ? "Creating..." : "Create Plan"}
                </button>
              </div>

              {agentRun && (
                <div className="artifact">
                  <h4>Agent Explanation</h4>
                  <p className="meta">
                    trace {agentRun.trace_id} · {agentRun.model} · {agentRun.status}
                  </p>
                  <pre>{pretty(agentRun.output)}</pre>
                  <p className="meta">Safety flags: {agentRun.safety_flags.join(", ") || "none"}</p>
                </div>
              )}

              {plan && (
                <div className="artifact">
                  <h4>Plan</h4>
                  <pre>{pretty(plan)}</pre>
                </div>
              )}

              <div className="artifact">
                <h4>Evidence</h4>
                <pre>{pretty(selected.evidence)}</pre>
              </div>
            </div>
          )}
        </section>

        <section className="panel">
          <h2>Audit Trail</h2>
          <div className="timeline">
            {auditEvents.slice(0, 20).map((event) => (
              <div className="event" key={event.id}>
                <strong>{event.event_type}</strong>
                <span>{event.message}</span>
                <small>{event.entity_type}:{event.entity_id} · {new Date(event.created_at).toLocaleString()}</small>
              </div>
            ))}
            {auditEvents.length === 0 && <p className="empty">No audit events yet.</p>}
          </div>
        </section>

        <section className="panel">
          <h2>Native Signals</h2>
          <p className="meta">CloudMonitor, ECS health, OOS, ActionTrail, SLS provider errors and log patterns.</p>
          {nativeSignals.length === 0 ? (
            <p className="empty">No Aliyun signals loaded.</p>
          ) : (
            <pre>{pretty(nativeSignals)}</pre>
          )}
        </section>
      </main>
    </div>
  );
}

function Metric({label, value}: {label: string; value: number}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
