import { dashboardClient } from "@/api/axios";

export interface MlopsActionDefinition {
  action_key: string;
  label: string;
  description: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  requires_confirmation: boolean;
  allowed_roles: string[];
}

export interface MlopsOrchestrationRunRequest {
  action: string;
  parameters?: Record<string, any>;
}

export interface MlopsOrchestrationRunResponse {
  run_id: string;
  action_key: string;
  command_label: string;
  parameters: Record<string, any>;
  triggered_by_user_id: number | null;
  triggered_by_email: string | null;
  status: "QUEUED" | "RUNNING" | "SUCCESS" | "FAILED" | "TIMEOUT" | "DISABLED" | "CANCELLED";
  started_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  duration_seconds: number | null;
  created_at: string;
}

export interface MlopsOrchestrationRunLogsResponse {
  run_id: string;
  status: string;
  stdout: string;
  stderr: string;
}

export async function getMlopsOrchestrationActions() {
  const { data } = await dashboardClient.get<MlopsActionDefinition[]>("/mlops/orchestration/actions");
  return data;
}

export async function triggerMlopsOrchestrationRun(payload: MlopsOrchestrationRunRequest) {
  const { data } = await dashboardClient.post<MlopsOrchestrationRunResponse>("/mlops/orchestration/run", payload);
  return data;
}

export async function getMlopsOrchestrationRuns(limit = 50) {
  const { data } = await dashboardClient.get<MlopsOrchestrationRunResponse[]>("/mlops/orchestration/runs", {
    params: { limit },
  });
  return data;
}

export async function getMlopsOrchestrationRun(runId: string) {
  const { data } = await dashboardClient.get<MlopsOrchestrationRunResponse>(
    `/mlops/orchestration/runs/${encodeURIComponent(runId)}`
  );
  return data;
}

export async function getMlopsOrchestrationRunLogs(runId: string) {
  const { data } = await dashboardClient.get<MlopsOrchestrationRunLogsResponse>(
    `/mlops/orchestration/runs/${encodeURIComponent(runId)}/logs`
  );
  return data;
}
