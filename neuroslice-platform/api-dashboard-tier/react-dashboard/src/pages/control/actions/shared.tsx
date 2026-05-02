import { ChevronRight, CheckCircle, Play, XCircle } from "lucide-react";

import { cn } from "@/lib/cn";
import type { ActionStatus, ControlAction } from "@/api/controlApi";

export const ACTION_TYPE_LABELS: Record<string, string> = {
  RECOMMEND_PCF_QOS_UPDATE: "PCF QoS Update",
  RECOMMEND_REROUTE_SLICE: "Reroute Slice",
  RECOMMEND_SCALE_EDGE_RESOURCE: "Scale Edge Resource",
  RECOMMEND_INSPECT_SLICE_POLICY: "Inspect Slice Policy",
  INVESTIGATE_CONTEXT: "Investigate Context",
  NO_ACTION: "No Action",
};

export function StatusBadge({ status }: { status: ActionStatus }) {
  const cfg: Record<ActionStatus, { cls: string; label: string }> = {
    PENDING_APPROVAL: {
      cls: "bg-amber-500/15 text-amber-400 border-amber-500/30",
      label: "Pending Approval",
    },
    APPROVED: { cls: "bg-blue-500/15 text-blue-400 border-blue-500/30", label: "Approved" },
    REJECTED: { cls: "bg-red-500/15 text-red-400 border-red-500/30", label: "Rejected" },
    EXECUTED_SIMULATED: {
      cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
      label: "Executed (Simulated)",
    },
    FAILED: { cls: "bg-red-800/15 text-red-300 border-red-800/30", label: "Failed" },
  };
  const { cls, label } = cfg[status] ?? { cls: "bg-slate-500/10 text-slate-400", label: status };
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", cls)}>
      {label}
    </span>
  );
}

export function RiskBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    LOW: "bg-slate-500/10 text-slate-400 border-slate-500/20",
    MEDIUM: "bg-amber-500/10 text-amber-500 border-amber-500/20",
    HIGH: "bg-red-500/10 text-red-500 border-red-500/20",
  };
  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase",
        styles[level] ?? styles.LOW,
      )}
    >
      {level}
    </span>
  );
}

export function PipelineViz({ action }: { action: ControlAction }) {
  const steps = [
    { id: "alert", label: "Alert", done: true },
    { id: "action", label: "Action", done: true },
    { id: "approval", label: "Approval", done: action.status !== "PENDING_APPROVAL" },
    { id: "execution", label: "Execution", done: action.status === "EXECUTED_SIMULATED" },
  ];

  return (
    <div className="flex items-center gap-1 text-xs">
      {steps.map((step, i) => (
        <div key={step.id} className="flex items-center gap-1">
          <span
            className={cn(
              "rounded px-2 py-0.5 font-medium",
              step.done ? "bg-accent/20 text-accent" : "bg-white/5 text-slate-500",
            )}
          >
            {step.label}
          </span>
          {i < steps.length - 1 && <ChevronRight className="size-3 text-slate-600" />}
        </div>
      ))}
    </div>
  );
}

export function ActionRow({
  action,
  canControl,
  onApprove,
  onReject,
  onExecute,
  loading,
}: {
  action: ControlAction;
  canControl: boolean;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onExecute: (id: string) => void;
  loading: boolean;
}) {
  return (
    <div className="space-y-3 rounded-xl border border-white/5 bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-200">
              {ACTION_TYPE_LABELS[action.action_type] ?? action.action_type}
            </span>
            <RiskBadge level={action.risk_level} />
          </div>
          <p className="mt-0.5 font-mono text-xs text-slate-500">
            alert: {action.alert_id.slice(0, 8)}... · entity: {action.entity_id}
          </p>
        </div>
        <StatusBadge status={action.status} />
      </div>

      <PipelineViz action={action} />

      <p className="text-xs leading-relaxed text-slate-400">{action.reason}</p>

      {action.execution_note && (
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400">
          {action.execution_note}
        </div>
      )}

      <div className="flex flex-wrap gap-4 text-xs text-slate-500">
        <span>
          Policy: <code className="text-slate-400">{action.policy_id}</code>
        </span>
        {action.domain && (
          <span>
            Domain: <span className="text-slate-400">{action.domain}</span>
          </span>
        )}
        <span>Updated: {new Date(action.updated_at).toLocaleString()}</span>
      </div>

      {canControl && action.status === "PENDING_APPROVAL" && (
        <div className="flex gap-2">
          <button
            disabled={loading}
            onClick={() => onApprove(action.action_id)}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600/20 px-3 py-1.5 text-xs font-medium text-blue-400 transition hover:bg-blue-600/30 disabled:opacity-50"
          >
            <CheckCircle className="size-3.5" /> Approve
          </button>
          <button
            disabled={loading}
            onClick={() => onReject(action.action_id)}
            className="flex items-center gap-1.5 rounded-lg bg-red-600/20 px-3 py-1.5 text-xs font-medium text-red-400 transition hover:bg-red-600/30 disabled:opacity-50"
          >
            <XCircle className="size-3.5" /> Reject
          </button>
        </div>
      )}

      {canControl && action.status === "APPROVED" && (
        <button
          disabled={loading}
          onClick={() => onExecute(action.action_id)}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-600/20 px-3 py-1.5 text-xs font-medium text-emerald-400 transition hover:bg-emerald-600/30 disabled:opacity-50"
        >
          <Play className="size-3.5" /> Execute (Simulated)
        </button>
      )}
    </div>
  );
}
