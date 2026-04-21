import type { RiskLevel, RICStatus, SliceType } from "@/types/shared";

export interface RegionSummary {
  id: number;
  code: string;
  name: string;
  ric_status: RICStatus;
  network_load: number;
  gnodeb_count: number;
}

export interface PredictionSummary {
  id: number;
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

export interface SessionSummary {
  id: number;
  session_code: string;
  region: RegionSummary;
  slice_type: SliceType;
  latency_ms: number;
  packet_loss: number;
  throughput_mbps: number;
  timestamp: string;
  prediction?: PredictionSummary | null;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface SessionListResponse {
  items: SessionSummary[];
  pagination: PaginationMeta;
}
