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
