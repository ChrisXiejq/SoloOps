import type { AgentRun, AuditEvent, Finding, NativeSignal, RemediationPlan, ScanResult } from "./types";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{status: string}>("/healthz"),
  requestScan: (provider: "mock" | "aliyun") =>
    request<ScanResult>("/api/v1/scans", {
      method: "POST",
      body: JSON.stringify({provider})
    }),
  getScan: (scanId: string) => request<ScanResult>(`/api/v1/scans/${scanId}`),
  listFindings: () => request<Finding[]>("/api/v1/findings"),
  getFinding: (findingId: string) => request<Finding>(`/api/v1/findings/${findingId}`),
  createPlan: (findingId: string) =>
    request<RemediationPlan>(`/api/v1/findings/${findingId}/plans`, {method: "POST"}),
  createAgentRun: (findingId: string) =>
    request<AgentRun>(`/api/v1/findings/${findingId}/agent-runs`, {method: "POST"}),
  listAuditEvents: () => request<AuditEvent[]>("/api/v1/audit-events"),
  listNativeSignals: (provider: "mock" | "aliyun") =>
    request<NativeSignal[]>(`/api/v1/native-signals?provider=${provider}`)
};
