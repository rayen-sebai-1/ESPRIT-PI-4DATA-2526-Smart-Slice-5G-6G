import type { MlopsHealth } from "@/types/mlops";

export function healthLabel(health: MlopsHealth): string {
  switch (health) {
    case "healthy":
      return "Healthy";
    case "degraded":
      return "Degraded";
    default:
      return "Unknown";
  }
}

export function healthClassName(health: MlopsHealth): string {
  switch (health) {
    case "healthy":
      return "inline-flex items-center rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-300";
    case "degraded":
      return "inline-flex items-center rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-300";
    default:
      return "inline-flex items-center rounded-full bg-slate-500/15 px-2 py-0.5 text-xs font-medium text-slate-300";
  }
}

export function formatMetric(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toFixed(4);
}

// ---------------------------------------------------------------------------
// Shared drift helpers — used by MlopsMonitoringPage and MlopsDriftPage
// ---------------------------------------------------------------------------

export function driftSeverityClass(severity?: string): string {
  switch (severity?.toUpperCase()) {
    case "CRITICAL": return "text-red-400 font-bold";
    case "HIGH":     return "text-orange-400 font-bold";
    case "MEDIUM":   return "text-amber-400";
    case "LOW":      return "text-yellow-300";
    default:         return "text-green-400";
  }
}

export function driftSeverityBg(severity?: string): string {
  switch (severity?.toUpperCase()) {
    case "CRITICAL": return "bg-red-900/60 text-red-300";
    case "HIGH":     return "bg-orange-900/60 text-orange-300";
    case "MEDIUM":   return "bg-amber-900/50 text-amber-300";
    case "LOW":      return "bg-yellow-900/40 text-yellow-300";
    default:         return "bg-green-900/40 text-green-400";
  }
}

export function driftStatusBadge(status?: string, isDrift?: boolean): string {
  if (isDrift) return "drift";
  return status ?? "no_data";
}
