import { liveClient } from "@/api/axios";

export type LogCategory =
  | "FAULT_OPENED"
  | "FAULT_CLEARED"
  | "KPI_BREACH"
  | "AIOPS_CONGESTION"
  | "AIOPS_SLA_RISK"
  | "AIOPS_SLICE_MISMATCH";

export type LogSeverity = 0 | 1 | 2 | 3;

export interface NetworkLogEvent {
  id: string;
  ts: string;
  category: LogCategory;
  severity: LogSeverity;
  domain: string | null;
  slice_id: string | null;
  entity_id: string | null;
  entity_type: string | null;
  slice_type: string | null;
  message: string;
  evidence: Record<string, unknown>;
}

export interface NetworkLogsResponse {
  count: number;
  window: {
    start: string;
    stop: "now()";
  };
  next_cursor: string | null;
  events: NetworkLogEvent[];
}

export interface LogsQueryParams {
  scope?: "national" | "regional";
  region_id?: string | number;
  start?: "-5m" | "-15m" | "-1h" | "-6h" | "-24h";
  categories?: LogCategory[];
  min_severity?: LogSeverity;
  entity_id?: string;
  slice_id?: string;
  domain?: string;
  slice_type?: string;
  limit?: number;
  cursor?: string;
}

export const LOG_CATEGORIES: LogCategory[] = [
  "FAULT_OPENED",
  "FAULT_CLEARED",
  "KPI_BREACH",
  "AIOPS_CONGESTION",
  "AIOPS_SLA_RISK",
  "AIOPS_SLICE_MISMATCH",
];

export async function getNetworkLogs(params: LogsQueryParams = {}) {
  const query = {
    ...params,
    categories: params.categories?.length ? params.categories.join(",") : undefined,
  };
  const { data } = await liveClient.get<NetworkLogsResponse>("/logs", { params: query });
  return data;
}
