import { dashboardClient } from "@/api/axios";
import type {
  NationalDashboardResponse,
  RegionDashboardResponse,
  SliceDistributionPoint,
  TrendPoint,
} from "@/types/dashboard";

export async function getNationalDashboard() {
  const { data } = await dashboardClient.get<NationalDashboardResponse>("/national");
  return data;
}

export async function getRegionalDashboard(regionId: number) {
  const { data } = await dashboardClient.get<RegionDashboardResponse>(`/region/${regionId}`);
  return data;
}

export async function getNationalSlaTrend(): Promise<TrendPoint[]> {
  const { data } = await dashboardClient.get<TrendPoint[]>("/metrics/sla-trend");
  return data;
}

export async function getNationalSliceDistribution(): Promise<SliceDistributionPoint[]> {
  const { data } = await dashboardClient.get<SliceDistributionPoint[]>("/metrics/slice-distribution");
  return data;
}
