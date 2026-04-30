import { dashboardClient } from "@/api/axios";

export type ActionStatus =
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "EXECUTED_SIMULATED"
  | "FAILED";

export type ActionType =
  | "RECOMMEND_PCF_QOS_UPDATE"
  | "RECOMMEND_REROUTE_SLICE"
  | "RECOMMEND_SCALE_EDGE_RESOURCE"
  | "RECOMMEND_INSPECT_SLICE_POLICY"
  | "INVESTIGATE_CONTEXT"
  | "NO_ACTION";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface ControlAction {
  action_id: string;
  alert_id: string;
  entity_id: string;
  slice_id: string | null;
  domain: string | null;
  action_type: ActionType;
  mode: string;
  risk_level: RiskLevel;
  requires_approval: boolean;
  status: ActionStatus;
  reason: string;
  policy_id: string;
  execution_note: string | null;
  created_at: string;
  updated_at: string;
  actuation_result?: ControlActuation | null;
}

export interface ControlActuation {
  action_id: string;
  alert_id: string;
  entity_id: string;
  slice_id: string | null;
  policy_id: string;
  action_type: ActionType;
  timestamp: string;
  simulated: boolean;
  keys_written: string[];
  note?: string;
}

export interface ControlActionsResponse {
  count: number;
  items: ControlAction[];
}

export interface ControlActuationsResponse {
  count: number;
  items: ControlActuation[];
}

export interface DriftStatus {
  drift_detected: boolean;
  p_value: number | null;
  anomaly_count: number;
  window_seconds: number;
  threshold: number;
  last_detection_time: string | null;
  last_trigger_time: string | null;
  pipeline_triggered: boolean;
  cooldown_active: boolean;
  pipeline_enabled: boolean;
}

export interface DriftEventsResponse {
  count: number;
  items: Array<{
    event_type: string;
    anomaly_count: string;
    window_seconds: string;
    threshold: string;
    timestamp: string;
    drift_detected?: boolean;
    pipeline_triggered?: boolean;
    cooldown_active?: boolean;
    pipeline_enabled?: boolean;
  }>;
}

export async function listControlActions(): Promise<ControlActionsResponse> {
  const { data } = await dashboardClient.get<ControlActionsResponse>("/controls/actions");
  return data;
}

export async function getControlAction(actionId: string): Promise<ControlAction> {
  const { data } = await dashboardClient.get<ControlAction>(`/controls/actions/${actionId}`);
  return data;
}

export async function approveControlAction(actionId: string): Promise<ControlAction> {
  const { data } = await dashboardClient.post<ControlAction>(`/controls/actions/${actionId}/approve`);
  return data;
}

export async function rejectControlAction(actionId: string): Promise<ControlAction> {
  const { data } = await dashboardClient.post<ControlAction>(`/controls/actions/${actionId}/reject`);
  return data;
}

export async function executeControlAction(actionId: string): Promise<ControlAction> {
  const { data } = await dashboardClient.post<ControlAction>(`/controls/actions/${actionId}/execute`);
  return data;
}

export async function listControlActuations(): Promise<ControlActuationsResponse> {
  const { data } = await dashboardClient.get<ControlActuationsResponse>("/controls/actuations");
  return data;
}

export async function getControlActuation(actionId: string): Promise<ControlActuation> {
  const { data } = await dashboardClient.get<ControlActuation>(`/controls/actuations/${actionId}`);
  return data;
}

export async function getDriftStatus(): Promise<DriftStatus> {
  const { data } = await dashboardClient.get<DriftStatus>("/controls/drift/status");
  return data;
}

export async function getDriftEvents(limit = 20): Promise<DriftEventsResponse> {
  const { data } = await dashboardClient.get<DriftEventsResponse>(`/controls/drift/events?limit=${limit}`);
  return data;
}

export async function triggerDriftCheck(): Promise<{ triggered: boolean; reason: string; anomaly_count: number }> {
  const { data } = await dashboardClient.post("/controls/drift/trigger");
  return data;
}
