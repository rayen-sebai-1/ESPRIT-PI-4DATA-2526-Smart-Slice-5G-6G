import { dashboardClient } from "@/api/axios";

export type RuntimeServiceMode = "auto" | "manual" | "disabled";

export interface RuntimeServiceState {
  service_name: string;
  enabled: boolean;
  mode: RuntimeServiceMode;
  updated_at: string | null;
  updated_by: string;
  reason: string;
}

export interface RuntimeServicesResponse {
  count: number;
  items: RuntimeServiceState[];
}

export interface RuntimeServicePatchRequest {
  enabled?: boolean;
  mode?: RuntimeServiceMode;
  reason?: string;
}

export async function listRuntimeServices(): Promise<RuntimeServicesResponse> {
  const { data } = await dashboardClient.get<RuntimeServicesResponse>("/runtime/services");
  return data;
}

export async function getRuntimeService(serviceName: string): Promise<RuntimeServiceState> {
  const { data } = await dashboardClient.get<RuntimeServiceState>(
    `/runtime/services/${encodeURIComponent(serviceName)}`,
  );
  return data;
}

export async function patchRuntimeService(
  serviceName: string,
  payload: RuntimeServicePatchRequest,
): Promise<RuntimeServiceState> {
  const { data } = await dashboardClient.patch<RuntimeServiceState>(
    `/runtime/services/${encodeURIComponent(serviceName)}`,
    payload,
  );
  return data;
}
