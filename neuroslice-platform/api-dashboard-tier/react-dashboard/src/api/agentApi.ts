import { agentClient } from "./axios";

export type AgentDomain = "core" | "edge" | "ran";

export interface RcaTimeRange {
  start: string;
  stop: string;
}

export interface RcaScanRequest {
  slice_id: string;
  domain?: AgentDomain;
  time_range?: RcaTimeRange;
}

export interface RcaScanResponse {
  summary: string;
  rootCause: string;
  affectedEntities: string[];
  evidenceKpis: Record<string, unknown>;
  recommendedAction: string[];
}

export interface RcaErrorResponse {
  error: string;
  message: string;
  diagnostics?: Record<string, unknown>;
}

export interface CopilotQueryRequest {
  session_id: string;
  query: string;
}

export interface CopilotQueryResponse {
  session_id: string;
  answer: string;
}

export const agentApi = {
  runRcaScan: async (payload: RcaScanRequest): Promise<RcaScanResponse> => {
    const body: RcaScanRequest = {
      slice_id: payload.slice_id,
      time_range: payload.time_range ?? { start: "-30m", stop: "now()" },
    };
    if (payload.domain) {
      body.domain = payload.domain;
    }
    // Route goes through dashboard-backend proxy (/api/dashboard/agentic) for auth.
    const response = await agentClient.post<RcaScanResponse>("/root-cause/manual-scan", body);
    return response.data;
  },

  askCopilot: async (payload: CopilotQueryRequest): Promise<CopilotQueryResponse> => {
    // Route goes through dashboard-backend proxy (/api/dashboard/agentic) for auth.
    const response = await agentClient.post<CopilotQueryResponse>("/copilot/query/text", payload);
    return response.data;
  },
};
