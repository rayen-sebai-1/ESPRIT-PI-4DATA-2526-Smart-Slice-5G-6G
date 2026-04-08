import type { RICStatus } from "@/types/shared";

export interface NationalOverview {
  sla_national_percent: number;
  avg_latency_ms: number;
  congestion_rate: number;
  active_alerts_count: number;
  sessions_count: number;
  anomalies_count: number;
  generated_at: string | null;
}

export interface RegionComparison {
  region_id: number;
  code: string;
  name: string;
  ric_status: RICStatus;
  network_load: number;
  gnodeb_count: number;
  sessions_count: number;
  sla_percent: number;
  avg_latency_ms: number;
  avg_packet_loss: number;
  congestion_rate: number;
  high_risk_sessions_count: number;
  anomalies_count: number;
}

export interface TrendPoint {
  label: string;
  generated_at: string;
  sla_percent: number;
  congestion_rate: number;
  active_alerts_count: number;
  anomalies_count: number;
  total_sessions: number;
}

export interface SliceDistributionPoint {
  slice_type: string;
  sessions_count: number;
}

export interface NationalDashboardResponse {
  overview: NationalOverview;
  regions: RegionComparison[];
}

export interface RegionDashboardResponse {
  region: RegionComparison;
  gnodeb_count: number;
  packet_loss_avg: number;
  slice_distribution: SliceDistributionPoint[];
  trend: TrendPoint[];
}
