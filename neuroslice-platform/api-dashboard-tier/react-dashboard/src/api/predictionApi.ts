import { predictionClient } from "@/api/axios";
import type { PredictionListResponse, PredictionResponse, ModelInfoResponse, RunBatchRequest } from "@/types/prediction";
import type { RiskLevel } from "@/types/shared";

export interface PredictionQueryParams {
  page?: number;
  pageSize?: number;
  region?: string;
  risk?: RiskLevel;
}

export async function getPredictions(params: PredictionQueryParams) {
  const { data } = await predictionClient.get<PredictionListResponse>("/predictions", {
    params: {
      page: params.page,
      page_size: params.pageSize,
      region: params.region || undefined,
      risk: params.risk || undefined,
    },
  });
  return data;
}

export async function getPrediction(sessionId: number) {
  const { data } = await predictionClient.get<PredictionResponse>(`/predictions/${sessionId}`);
  return data;
}

export async function runPrediction(sessionId: number) {
  const { data } = await predictionClient.post<PredictionResponse>(`/predictions/run/${sessionId}`);
  return data;
}

export async function runBatchPrediction(payload: RunBatchRequest) {
  const { data } = await predictionClient.post<PredictionResponse[]>("/predictions/run-batch", payload);
  return data;
}

export async function getModelsCatalog() {
  const { data } = await predictionClient.get<ModelInfoResponse[]>("/models");
  return data;
}
