import type { MlopsHealth } from "@/types/mlops";

export function healthLabel(health: MlopsHealth): string {
  switch (health) {
    case "healthy":
      return "Sain";
    case "degraded":
      return "Degrade";
    default:
      return "Inconnu";
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
