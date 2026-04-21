import { dashboardClient } from "@/api/axios";
import type { NationalDashboardResponse, RegionDashboardResponse } from "@/types/dashboard";

export async function getNationalDashboard() {
  const { data } = await dashboardClient.get<NationalDashboardResponse>("/dashboard/national");
  return data;
}

export async function getRegionalDashboard(regionId: number) {
  const { data } = await dashboardClient.get<RegionDashboardResponse>(`/dashboard/region/${regionId}`);
  return data;
}
