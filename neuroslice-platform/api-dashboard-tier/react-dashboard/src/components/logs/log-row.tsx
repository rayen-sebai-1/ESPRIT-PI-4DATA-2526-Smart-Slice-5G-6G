import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Gauge,
  RadioTower,
  ShieldAlert,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { LogCategory, NetworkLogEvent } from "@/api/logsApi";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/format";

interface LogRowProps {
  event: NetworkLogEvent;
  onOpen: (event: NetworkLogEvent) => void;
}

const categoryLabels: Record<LogCategory, string> = {
  FAULT_OPENED: "Fault opened",
  FAULT_CLEARED: "Fault cleared",
  KPI_BREACH: "KPI breach",
  AIOPS_CONGESTION: "AIOps congestion",
  AIOPS_SLA_RISK: "AIOps SLA risk",
  AIOPS_SLICE_MISMATCH: "AIOps mismatch",
};

const categoryIcons: Record<LogCategory, LucideIcon> = {
  FAULT_OPENED: XCircle,
  FAULT_CLEARED: CheckCircle2,
  KPI_BREACH: Gauge,
  AIOPS_CONGESTION: RadioTower,
  AIOPS_SLA_RISK: ShieldAlert,
  AIOPS_SLICE_MISMATCH: BrainCircuit,
};

function relativeTime(value: string) {
  const deltaSeconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (deltaSeconds < 60) return `${deltaSeconds}s`;
  const minutes = Math.round(deltaSeconds / 60);
  if (minutes < 60) return `${minutes}min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.round(hours / 24)}j`;
}

function severityTone(severity: number) {
  if (severity >= 3) return "border-red-400/30 bg-red-500/10 text-red-200";
  if (severity === 2) return "border-orange-300/30 bg-orange-500/10 text-orange-100";
  if (severity === 1) return "border-sky-300/30 bg-sky-500/10 text-sky-100";
  return "border-emerald-300/30 bg-emerald-500/10 text-emerald-100";
}

export function LogRow({ event, onOpen }: LogRowProps) {
  const Icon = categoryIcons[event.category] ?? AlertTriangle;

  return (
    <button
      className="grid w-full gap-3 border-t border-border/70 px-4 py-3 text-left transition hover:bg-white/[0.03] md:grid-cols-[minmax(0,1fr)_160px]"
      type="button"
      onClick={() => onOpen(event)}
    >
      <div className="flex min-w-0 items-start gap-3">
        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-border bg-slate-950/50 text-accent">
          <Icon size={17} />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-white">{categoryLabels[event.category]}</span>
            <span className={cn("rounded-full border px-2 py-0.5 text-[11px]", severityTone(event.severity))}>
              S{event.severity}
            </span>
            {event.domain ? <span className="text-xs uppercase text-mutedText">{event.domain}</span> : null}
          </div>
          <p className="mt-1 break-words text-sm leading-5 text-slate-200">{event.message}</p>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-mutedText">
            {event.entity_id ? <span>{event.entity_id}</span> : null}
            {event.slice_id ? <span>{event.slice_id}</span> : null}
            {event.slice_type ? <span>{event.slice_type}</span> : null}
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 text-xs text-mutedText md:flex-col md:items-end md:justify-center">
        <span>{formatDate(event.ts)}</span>
        <span>{relativeTime(event.ts)}</span>
      </div>
    </button>
  );
}
