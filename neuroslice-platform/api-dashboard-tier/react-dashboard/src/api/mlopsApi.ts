import { dashboardClient } from "@/api/axios";
import type {
  MlopsActionResponse,
  MlopsArtifactStatus,
  MlopsModelHealth,
  MlopsOverview,
  MlopsPipelineRunLogsResponse,
  MlopsPipelineRunResponse,
  MlopsPredictionMonitoringResponse,
  MlopsPromotePayload,
  MlopsPromotionEvent,
  MlopsRollbackPayload,
  MlopsRunSummary,
  MlopsToolsHealthResponse,
  MlopsToolsResponse,
} from "@/types/mlops";

export async function getMlopsOverview() {
  const { data } = await dashboardClient.get<MlopsOverview>("/mlops/overview");
  return data;
}

export async function getMlopsModels() {
  const { data } = await dashboardClient.get<MlopsModelHealth[]>("/mlops/models");
  return data;
}

export async function getMlopsModel(modelName: string) {
  const { data } = await dashboardClient.get<MlopsModelHealth>(
    `/mlops/models/${encodeURIComponent(modelName)}`,
  );
  return data;
}

export async function getMlopsRuns(limit = 50) {
  const { data } = await dashboardClient.get<MlopsRunSummary[]>("/mlops/runs", {
    params: { limit },
  });
  return data;
}

export async function getMlopsArtifacts() {
  const { data } = await dashboardClient.get<MlopsArtifactStatus[]>("/mlops/artifacts");
  return data;
}

export async function getMlopsPromotions(limit = 50) {
  const { data } = await dashboardClient.get<MlopsPromotionEvent[]>("/mlops/promotions", {
    params: { limit },
  });
  return data;
}

export async function getMlopsPredictionMonitoring(params: { model?: string; limit?: number } = {}) {
  const { data } = await dashboardClient.get<MlopsPredictionMonitoringResponse>(
    "/mlops/monitoring/predictions",
    {
      params: { model: params.model || undefined, limit: params.limit ?? 50 },
    },
  );
  return data;
}

export async function promoteMlopsModel(payload: MlopsPromotePayload) {
  const { data } = await dashboardClient.post<MlopsActionResponse>("/mlops/promote", payload);
  return data;
}

export async function rollbackMlopsModel(payload: MlopsRollbackPayload) {
  const { data } = await dashboardClient.post<MlopsActionResponse>("/mlops/rollback", payload);
  return data;
}

export async function getMlopsTools() {
  const { data } = await dashboardClient.get<MlopsToolsResponse>("/mlops/tools");
  return data;
}

export async function getMlopsToolsHealth() {
  const { data } = await dashboardClient.get<MlopsToolsHealthResponse>("/mlops/tools/health");
  return data;
}

export async function triggerMlopsPipeline() {
  const { data } = await dashboardClient.post<MlopsPipelineRunResponse>("/mlops/pipeline/run");
  return data;
}

export async function getMlopsPipelineRuns(limit = 50) {
  const { data } = await dashboardClient.get<MlopsPipelineRunResponse[]>("/mlops/pipeline/runs", {
    params: { limit },
  });
  return data;
}

export async function getMlopsPipelineRun(runId: string) {
  const { data } = await dashboardClient.get<MlopsPipelineRunResponse>(
    `/mlops/pipeline/runs/${encodeURIComponent(runId)}`,
  );
  return data;
}

export async function getMlopsPipelineRunLogs(runId: string) {
  const { data } = await dashboardClient.get<MlopsPipelineRunLogsResponse>(
    `/mlops/pipeline/runs/${encodeURIComponent(runId)}/logs`,
  );
  return data;
}

export interface MlopsPipelineConfig {
  pipeline_enabled: boolean;
  message: string;
}

export async function getMlopsPipelineConfig(): Promise<MlopsPipelineConfig> {
  const { data } = await dashboardClient.get<MlopsPipelineConfig>("/mlops/pipeline/config");
  return data;
}

// ---------------------------------------------------------------------------
// Drift Detection
// ---------------------------------------------------------------------------

export interface DriftModelState {
  model_name: string;
  status: string;
  deployment_version?: string;
  window_size?: number;
  window_capacity?: number;
  reference_sample_count?: number;
  reference_loaded?: boolean;
  p_value?: number | null;
  threshold?: number;
  is_drift?: boolean;
  drift_score?: number | null;
  feature_names?: string[];
  severity?: string;
  recommendation?: string;
  last_checked_at?: string | null;
  last_drift_at?: string | null;
  auto_trigger_enabled?: boolean;
  scenario_b_live_mode?: boolean;
}

export interface DriftLatestResponse {
  models: Record<string, DriftModelState>;
  timestamp?: string | null;
  note?: string;
}

export interface DriftEvent {
  event_type: string;
  drift_id: string;
  model_name: string;
  timestamp: string;
  p_value: number;
  threshold: number;
  is_drift: boolean;
  severity: string;
  recommendation: string;
  window_size: number;
}

export interface DriftEventsResponse {
  events: DriftEvent[];
  count: number;
}

export async function getMlopsDrift(): Promise<DriftLatestResponse> {
  const { data } = await dashboardClient.get<DriftLatestResponse>("/mlops/drift");
  return data;
}

export async function getMlopsDriftModel(modelName: string): Promise<DriftModelState> {
  const { data } = await dashboardClient.get<DriftModelState>(
    `/mlops/drift/${encodeURIComponent(modelName)}`,
  );
  return data;
}

export async function getMlopsDriftEvents(limit = 50): Promise<DriftEventsResponse> {
  const { data } = await dashboardClient.get<DriftEventsResponse>("/mlops/drift-events", {
    params: { limit },
  });
  return data;
}

// ---------------------------------------------------------------------------
// Online evaluation
// ---------------------------------------------------------------------------

export interface EvaluationModelState {
  model_name: string;
  status?: string;
  timestamp?: string;
  window_size?: number;
  window_capacity?: number;
  samples_total?: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  false_positive_count?: number;
  false_negative_count?: number;
  pseudo_ground_truth_available?: boolean;
}

export interface EvaluationLatestResponse {
  models: Record<string, EvaluationModelState>;
  timestamp?: string | null;
  note?: string | null;
}

export async function getMlopsEvaluation(): Promise<EvaluationLatestResponse> {
  const { data } = await dashboardClient.get<EvaluationLatestResponse>("/mlops/evaluation");
  return data;
}

export async function getMlopsEvaluationModel(modelName: string): Promise<EvaluationModelState> {
  const { data } = await dashboardClient.get<EvaluationModelState>(
    `/mlops/evaluation/${encodeURIComponent(modelName)}`,
  );
  return data;
}
