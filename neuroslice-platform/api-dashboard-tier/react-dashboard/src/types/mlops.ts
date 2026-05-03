export type MlopsHealth = "healthy" | "degraded" | "unknown";

export interface MlopsPromotedModel {
  deployment_name: string;
  model_name: string | null;
  version: string | null;
  framework: string | null;
  run_id: string | null;
  updated_at: string | null;
  created_at: string | null;
  metrics: Record<string, number>;
  artifact_available: boolean;
  artifact_files: string[];
}

export interface MlopsRegistryEntry {
  model_name: string;
  version: number | string | null;
  stage: string | null;
  promoted: boolean;
  framework: string | null;
  model_family: string | null;
  quality_gate_status: string | null;
  promotion_status: string | null;
  onnx_export_status: string | null;
  created_at: string | null;
  run_id: string | null;
  metrics: Record<string, number>;
  reason: string | null;
}

export interface MlopsModelHealth {
  deployment_name: string;
  promoted: MlopsPromotedModel | null;
  registry: MlopsRegistryEntry | null;
  health: MlopsHealth;
  notes: string[];
}

export interface MlopsRunSummary {
  model_name: string;
  version: number | string | null;
  run_id: string | null;
  stage: string | null;
  quality_gate_status: string | null;
  promotion_status: string | null;
  created_at: string | null;
  metrics: Record<string, number>;
}

export interface MlopsArtifactStatus {
  deployment_name: string;
  has_metadata: boolean;
  has_onnx: boolean;
  has_onnx_fp16: boolean;
  files: string[];
}

export interface MlopsPromotionEvent {
  model_name: string;
  version: number | string | null;
  run_id: string | null;
  stage: string | null;
  promotion_status: string | null;
  promoted: boolean;
  reason: string | null;
  created_at: string | null;
}

export interface MlopsOverview {
  generated_at: string | null;
  registry_available: boolean;
  promoted_models_count: number;
  models_with_pass_gate: number;
  models_with_fail_gate: number;
  pending_runs: number;
  promoted_models: MlopsModelHealth[];
  sources: Record<string, string>;
}

export interface MlopsPredictionMonitoringPoint {
  timestamp: string;
  model: string | null;
  region: string | null;
  risk_level: string | null;
  sla_score: number | null;
}

export interface MlopsPredictionMonitoringResponse {
  available: boolean;
  source: string;
  total: number;
  items: MlopsPredictionMonitoringPoint[];
  note: string | null;
}

export interface MlopsPromotePayload {
  model_name: string;
  version?: number | string;
  run_id?: string;
}

export interface MlopsRollbackPayload {
  model_name: string;
  target_version?: number | string;
}

export interface MlopsActionResponse {
  accepted: boolean;
  action: string;
  model_name: string;
  detail: string;
  delegated_to: string | null;
}

export type MlopsServiceHealth = "UP" | "DOWN" | "UNKNOWN";

export interface MlopsToolLink {
  key: string;
  name: string;
  url: string;
  description: string;
}

export interface MlopsToolsResponse {
  tools: MlopsToolLink[];
}

export interface MlopsToolHealth {
  name: string;
  url: string;
  status: MlopsServiceHealth;
  latency_ms: number | null;
  detail: string | null;
}

export interface MlopsToolsHealthResponse {
  services: MlopsToolHealth[];
}

export type PipelineRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCESS"
  | "FAILED"
  | "TIMEOUT"
  | "DISABLED";

export interface MlopsPipelineRunResponse {
  run_id: string;
  triggered_by_user_id: number | null;
  triggered_by_email: string | null;
  status: PipelineRunStatus;
  command_label: string;
  started_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  duration_seconds: number | null;
  created_at: string;
}

export interface MlopsPipelineRunLogsResponse {
  run_id: string;
  status: PipelineRunStatus;
  stdout: string;
  stderr: string;
}

export type MlopsRetrainingRequestStatus =
  | "pending_approval"
  | "approved"
  | "rejected"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

export type MlopsRetrainingTriggerType = "DRIFT" | "SCHEDULED" | "MANUAL";
export type MlopsRetrainingScheduleFrequency = "DAILY" | "WEEKLY" | "MONTHLY" | "CUSTOM_CRON";
export type MlopsRetrainingScheduleStatus = "ACTIVE" | "DISABLED" | "ERROR";

export interface MlopsRetrainingRequest {
  id: string;
  model: string;
  model_internal: string | null;
  pipeline_action: string | null;
  trigger_type: MlopsRetrainingTriggerType | null;
  reason: string;
  anomaly_count: number;
  threshold: number;
  severity: string | null;
  drift_score: number | null;
  p_value: number | null;
  request_source: string | null;
  source_schedule_id: string | null;
  status: MlopsRetrainingRequestStatus;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
  executed_by: string | null;
  executed_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
  execution_run_id: string | null;
  execution_detail: string | null;
}

export interface MlopsRetrainingRequestListResponse {
  count: number;
  items: MlopsRetrainingRequest[];
}

export interface MlopsRetrainingSchedule {
  id: string;
  model_name: string;
  enabled: boolean;
  frequency: MlopsRetrainingScheduleFrequency;
  cron_expr: string;
  timezone: string;
  require_approval: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  last_run_at: string | null;
  next_run_at: string | null;
  status: MlopsRetrainingScheduleStatus;
}

export interface MlopsRetrainingScheduleListResponse {
  count: number;
  items: MlopsRetrainingSchedule[];
}

export interface MlopsRetrainingScheduleUpsertPayload {
  model_name: string;
  enabled: boolean;
  frequency: MlopsRetrainingScheduleFrequency;
  cron_expr: string;
  timezone: string;
  require_approval: boolean;
  allow_duplicate_enabled?: boolean;
}
