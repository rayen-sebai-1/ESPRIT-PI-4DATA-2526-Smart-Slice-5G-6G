import { sessionClient } from "@/api/axios";
import type { RiskLevel, SliceType } from "@/types/shared";
import type { SessionListResponse, SessionSummary } from "@/types/session";

export interface SessionQueryParams {
  page?: number;
  pageSize?: number;
  region?: string;
  risk?: RiskLevel;
  slice?: SliceType;
}

export async function getSessions(params: SessionQueryParams) {
  const { data } = await sessionClient.get<SessionListResponse>("/sessions", {
    params: {
      page: params.page,
      page_size: params.pageSize,
      region: params.region || undefined,
      risk: params.risk || undefined,
      slice: params.slice || undefined,
    },
  });
  return data;
}

export async function getSession(sessionId: number) {
  const { data } = await sessionClient.get<SessionSummary>(`/sessions/${sessionId}`);
  return data;
}
