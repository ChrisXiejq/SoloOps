export type Severity = "critical" | "high" | "medium" | "low";

export interface Evidence {
  source: string;
  summary: string;
  payload: Record<string, unknown>;
}

export interface Finding {
  id: string;
  rule_id: string;
  title: string;
  severity: Severity;
  resource_id: string;
  description: string;
  evidence: Evidence[];
  remediation_action: string;
  rollback_action?: string | null;
  status: string;
  created_at: string;
}

export interface ScanResult {
  id: string;
  provider: string;
  status: "pending" | "running" | "succeeded" | "failed";
  findings: Finding[];
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface AuditEvent {
  id: string;
  actor: string;
  entity_type: string;
  entity_id: string;
  event_type: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AgentRun {
  id: string;
  finding_id: string;
  trace_id: string;
  agent_type: string;
  model: string;
  output: Record<string, unknown>;
  safety_flags: string[];
  status: string;
  created_at: string;
}

export interface NativeSignal {
  id: string;
  source: string;
  signal_type: string;
  severity: string;
  resource_id: string;
  title: string;
  summary: string;
  observed_at: string;
  payload: Record<string, unknown>;
}

export interface RemediationPlan {
  id: string;
  finding_id: string;
  playbook_id: string;
  action: string;
  target: string;
  rationale: string;
  expected_impact: string;
  created_at: string;
}
