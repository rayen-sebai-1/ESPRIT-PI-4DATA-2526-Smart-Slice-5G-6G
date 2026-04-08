import type { PaginationMeta } from "@/types/session";
import type { RiskLevel, RICStatus, SliceType } from "@/types/shared";

export interface RegionLite {
  id: number;
  code: string;
  name: string;
  ric_status: RICStatus;
  network_load: number;
}

export interface PredictionResponse {
  id: number;
  session_id: number;
  session_code: string;
  region: RegionLite;
  sla_score: number;
  congestion_score: number;
  anomaly_score: number;
  risk_level: RiskLevel;
  predicted_slice_type: SliceType;
  slice_confidence: number;
  recommended_action: string;
  model_source: string;
  predicted_at: string;
}

export interface PredictionListResponse {
  items: PredictionResponse[];
  pagination: PaginationMeta;
}

export interface ModelInfoResponse {
  name: string;
  purpose: string;
  implementation: string;
  status: string;
  source_notebook: string;
  artifact_path: string | null;
}

export interface RunBatchRequest {
  region_id?: number;
  limit: number;
}
