import type { RiskLevel, RICStatus } from "@/types/shared";

export function riskTone(level: RiskLevel) {
  switch (level) {
    case "LOW":
      return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
    case "MEDIUM":
      return "bg-amber-500/15 text-amber-300 border-amber-500/30";
    case "HIGH":
      return "bg-rose-500/15 text-rose-300 border-rose-500/30";
    case "CRITICAL":
      return "bg-red-950/80 text-red-200 border-red-700/50";
  }
}

export function statusTone(status: RICStatus) {
  switch (status) {
    case "HEALTHY":
      return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
    case "DEGRADED":
      return "bg-amber-500/15 text-amber-300 border-amber-500/30";
    case "CRITICAL":
      return "bg-rose-500/15 text-rose-300 border-rose-500/30";
    case "MAINTENANCE":
      return "bg-slate-500/15 text-slate-300 border-slate-500/30";
  }
}
