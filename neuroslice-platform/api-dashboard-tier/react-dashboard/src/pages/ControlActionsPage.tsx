import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle,
  XCircle,
  Play,
  AlertTriangle,
  ShieldCheck,
  RefreshCw,
  Activity,
  Zap,
  Clock,
  ChevronRight,
} from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import {
  listControlActions,
  approveControlAction,
  rejectControlAction,
  executeControlAction,
  listControlActuations,
  getDriftStatus,
  getDriftEvents,
  triggerDriftCheck,
  type ControlAction,
  type ControlActuation,
  type ActionStatus,
} from "@/api/controlApi";

// ─── helpers ─────────────────────────────────────────────────────────────────

const ACTION_TYPE_LABELS: Record<string, string> = {
  RECOMMEND_PCF_QOS_UPDATE: "PCF QoS Update",
  RECOMMEND_REROUTE_SLICE: "Reroute Slice",
  RECOMMEND_SCALE_EDGE_RESOURCE: "Scale Edge Resource",
  RECOMMEND_INSPECT_SLICE_POLICY: "Inspect Slice Policy",
  INVESTIGATE_CONTEXT: "Investigate Context",
  NO_ACTION: "No Action",
};

function StatusBadge({ status }: { status: ActionStatus }) {
  const cfg: Record<ActionStatus, { cls: string; label: string }> = {
    PENDING_APPROVAL: { cls: "bg-amber-500/15 text-amber-400 border-amber-500/30", label: "Pending Approval" },
    APPROVED: { cls: "bg-blue-500/15 text-blue-400 border-blue-500/30", label: "Approved" },
    REJECTED: { cls: "bg-red-500/15 text-red-400 border-red-500/30", label: "Rejected" },
    EXECUTED_SIMULATED: { cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30", label: "Executed (Simulated)" },
    FAILED: { cls: "bg-red-800/15 text-red-300 border-red-800/30", label: "Failed" },
  };
  const { cls, label } = cfg[status] ?? { cls: "bg-slate-500/10 text-slate-400", label: status };
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", cls)}>
      {label}
    </span>
  );
}

function RiskBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    LOW: "bg-slate-500/10 text-slate-400 border-slate-500/20",
    MEDIUM: "bg-amber-500/10 text-amber-500 border-amber-500/20",
    HIGH: "bg-red-500/10 text-red-500 border-red-500/20",
  };
  return (
    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase", styles[level] ?? styles.LOW)}>
      {level}
    </span>
  );
}

function PipelineViz({ action }: { action: ControlAction }) {
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

function ActionRow({
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
    <div className="rounded-xl border border-white/5 bg-card p-5 space-y-3">
      {/* Header row */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-200">
              {ACTION_TYPE_LABELS[action.action_type] ?? action.action_type}
            </span>
            <RiskBadge level={action.risk_level} />
          </div>
          <p className="mt-0.5 text-xs text-slate-500 font-mono">
            alert: {action.alert_id.slice(0, 8)}… · entity: {action.entity_id}
          </p>
        </div>
        <StatusBadge status={action.status} />
      </div>

      {/* Pipeline visualization */}
      <PipelineViz action={action} />

      {/* Reason */}
      <p className="text-xs text-slate-400 leading-relaxed">{action.reason}</p>

      {/* Execution note (shown after execution) */}
      {action.execution_note && (
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400">
          <ShieldCheck className="inline size-3 mr-1" />
          {action.execution_note}
        </div>
      )}

      {/* Meta */}
      <div className="flex flex-wrap gap-4 text-xs text-slate-500">
        <span>Policy: <code className="text-slate-400">{action.policy_id}</code></span>
        {action.domain && <span>Domain: <span className="text-slate-400">{action.domain}</span></span>}
        <span>Updated: {new Date(action.updated_at).toLocaleString()}</span>
      </div>

      {/* Actions */}
      {canControl && action.status === "PENDING_APPROVAL" && (
        <div className="flex gap-2">
          <button
            disabled={loading}
            onClick={() => onApprove(action.action_id)}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600/20 px-3 py-1.5 text-xs font-medium text-blue-400 hover:bg-blue-600/30 transition disabled:opacity-50"
          >
            <CheckCircle className="size-3.5" /> Approve
          </button>
          <button
            disabled={loading}
            onClick={() => onReject(action.action_id)}
            className="flex items-center gap-1.5 rounded-lg bg-red-600/20 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-600/30 transition disabled:opacity-50"
          >
            <XCircle className="size-3.5" /> Reject
          </button>
        </div>
      )}
      {canControl && action.status === "APPROVED" && (
        <button
          disabled={loading}
          onClick={() => onExecute(action.action_id)}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-600/20 px-3 py-1.5 text-xs font-medium text-emerald-400 hover:bg-emerald-600/30 transition disabled:opacity-50"
        >
          <Play className="size-3.5" /> Execute (Simulated)
        </button>
      )}
    </div>
  );
}

// ─── main page ────────────────────────────────────────────────────────────────

export function ControlActionsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [actionErr, setActionErr] = useState<string | null>(null);

  const canControl = user?.role === "ADMIN" || user?.role === "NETWORK_OPERATOR";
  const canViewDrift =
    user?.role === "ADMIN" ||
    user?.role === "NETWORK_MANAGER" ||
    user?.role === "DATA_MLOPS_ENGINEER";
  const canTriggerDrift = user?.role === "ADMIN" || user?.role === "DATA_MLOPS_ENGINEER";

  const { data: actionsData, isLoading: actionsLoading, error: actionsError } = useQuery({
    queryKey: ["controls", "actions"],
    queryFn: listControlActions,
    refetchInterval: 8000,
  });

  const { data: driftStatus } = useQuery({
    queryKey: ["controls", "drift", "status"],
    queryFn: getDriftStatus,
    refetchInterval: 15000,
    enabled: canViewDrift,
  });

  const { data: driftEvents } = useQuery({
    queryKey: ["controls", "drift", "events"],
    queryFn: () => getDriftEvents(10),
    refetchInterval: 15000,
    enabled: canViewDrift,
  });
  const { data: actuationsData } = useQuery({
    queryKey: ["controls", "actuations"],
    queryFn: listControlActuations,
    refetchInterval: 8000,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["controls"] });

  const approveMut = useMutation({
    mutationFn: approveControlAction,
    onSuccess: invalidate,
    onError: (e: any) => setActionErr(e.response?.data?.detail ?? String(e)),
  });
  const rejectMut = useMutation({
    mutationFn: rejectControlAction,
    onSuccess: invalidate,
    onError: (e: any) => setActionErr(e.response?.data?.detail ?? String(e)),
  });
  const executeMut = useMutation({
    mutationFn: executeControlAction,
    onSuccess: invalidate,
    onError: (e: any) => setActionErr(e.response?.data?.detail ?? String(e)),
  });
  const driftTriggerMut = useMutation({
    mutationFn: triggerDriftCheck,
    onSuccess: invalidate,
    onError: (e: any) => setActionErr(e.response?.data?.detail ?? String(e)),
  });

  const mutLoading =
    approveMut.isPending || rejectMut.isPending || executeMut.isPending;

  const actions = actionsData?.items ?? [];
  const actuations = actuationsData?.items ?? [];
  const pending = actions.filter((a) => a.status === "PENDING_APPROVAL");
  const others = actions.filter((a) => a.status !== "PENDING_APPROVAL");

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <PageHeader
        title="Control Actions"
        description="Alert → Action → Approval → Execution pipeline (Scenario B simulated)"
      />

      {/* Error banner */}
      {actionErr && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400 flex items-center justify-between">
          <span><AlertTriangle className="inline size-4 mr-1" />{actionErr}</span>
          <button onClick={() => setActionErr(null)} className="text-red-300 hover:text-red-200">✕</button>
        </div>
      )}

      {/* Drift status card */}
      <section>
        <h2 className="mb-4 flex items-center gap-2 text-base font-medium text-slate-200">
          <Activity className="size-4 text-accent" /> Drift Monitor
        </h2>
        {!canViewDrift && (
          <div className="rounded-xl border border-white/5 bg-cardAlt/40 p-4 text-sm text-slate-400">
            Drift monitor status is restricted to MLOps read roles.
          </div>
        )}
        {canViewDrift && (
          <>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className={cn(
            "rounded-xl border p-4",
            driftStatus?.drift_detected
              ? "border-red-500/30 bg-red-500/10"
              : "border-white/5 bg-cardAlt/50",
          )}>
            <p className="text-xs text-slate-500 mb-1">Drift Status</p>
            <p className={cn("text-lg font-semibold", driftStatus?.drift_detected ? "text-red-400" : "text-emerald-400")}>
              {driftStatus?.drift_detected ? "DRIFT DETECTED" : "NOMINAL"}
            </p>
          </div>
          <div className="rounded-xl border border-white/5 bg-cardAlt/50 p-4">
            <p className="text-xs text-slate-500 mb-1">Anomalies ({driftStatus?.window_seconds}s window)</p>
            <p className="text-lg font-semibold text-slate-200">
              {driftStatus?.anomaly_count ?? "—"} / {driftStatus?.threshold ?? "—"}
            </p>
          </div>
          <div className="rounded-xl border border-white/5 bg-cardAlt/50 p-4">
            <p className="text-xs text-slate-500 mb-1">Last Drift Trigger</p>
            <p className="text-sm text-slate-300">
              {driftStatus?.last_trigger_time
                ? new Date(driftStatus.last_trigger_time).toLocaleString()
                : "Never"}
            </p>
          </div>
          <div className="rounded-xl border border-white/5 bg-cardAlt/50 p-4">
            <p className="text-xs text-slate-500 mb-1">Auto MLOps Pipeline</p>
            <div className="flex items-center justify-between">
              <p className={cn("text-sm font-semibold", driftStatus?.pipeline_enabled ? "text-emerald-400" : "text-slate-500")}>
                {driftStatus?.pipeline_enabled ? "ENABLED" : "DISABLED"}
              </p>
              {canTriggerDrift && (
                <button
                  onClick={() => driftTriggerMut.mutate()}
                  disabled={driftTriggerMut.isPending || driftStatus?.cooldown_active}
                  className="flex items-center gap-1 rounded-lg bg-white/5 px-2 py-1 text-xs text-slate-400 hover:bg-accent hover:text-slate-950 transition disabled:opacity-40"
                  title={driftStatus?.cooldown_active ? "Cooldown active" : "Trigger drift check now"}
                >
                  <Zap className="size-3" /> Trigger
                </button>
              )}
            </div>
            {driftStatus?.cooldown_active && (
              <p className="mt-1 text-xs text-amber-400"><Clock className="inline size-3 mr-0.5" />Cooldown active</p>
            )}
          </div>
        </div>

        {/* Recent drift events */}
        {(driftEvents?.items?.length ?? 0) > 0 && (
          <div className="mt-4 overflow-x-auto rounded-xl border border-white/5 bg-card">
            <table className="w-full text-left text-xs text-slate-400">
              <thead className="border-b border-white/5 bg-black/20 text-[11px] font-medium uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">Time</th>
                  <th className="px-4 py-2">Anomalies</th>
                  <th className="px-4 py-2">Pipeline Triggered</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {driftEvents!.items.map((ev, i) => (
                  <tr key={i}>
                    <td className="px-4 py-2 font-mono">{new Date(ev.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-2">{ev.anomaly_count}</td>
                    <td className="px-4 py-2">
                      {ev.pipeline_triggered ? (
                        <span className="text-emerald-400">Yes</span>
                      ) : (
                        <span className="text-slate-600">No</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
          </>
        )}
      </section>

      {/* Pending actions */}
      <section>
        <h2 className="mb-4 flex items-center gap-2 text-base font-medium text-slate-200">
          <AlertTriangle className="size-4 text-amber-400" />
          Pending Approval
          {pending.length > 0 && (
            <span className="ml-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-400">
              {pending.length}
            </span>
          )}
        </h2>

        {actionsLoading && (
          <div className="flex h-24 items-center justify-center rounded-xl border border-white/5 bg-card">
            <RefreshCw className="size-5 animate-spin text-slate-500" />
          </div>
        )}

        {!actionsLoading && actionsError && (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400">
            Failed to load actions. Is policy-control running?
          </div>
        )}

        {!actionsLoading && !actionsError && pending.length === 0 && (
          <div className="rounded-xl border border-white/5 bg-card p-8 text-center text-sm text-slate-500">
            <ShieldCheck className="mx-auto mb-2 size-8 text-slate-600" />
            No actions pending approval.
          </div>
        )}

        <div className="space-y-3">
          {pending.map((a) => (
            <ActionRow
              key={a.action_id}
              action={a}
              canControl={canControl}
              onApprove={(id) => approveMut.mutate(id)}
              onReject={(id) => rejectMut.mutate(id)}
              onExecute={(id) => executeMut.mutate(id)}
              loading={mutLoading}
            />
          ))}
        </div>
      </section>

      {/* History */}
      <section>
        <h2 className="mb-4 flex items-center gap-2 text-base font-medium text-slate-200">
          <Clock className="size-4 text-accent" /> Action History
        </h2>
        <div className="space-y-3">
          {others.map((a) => (
            <ActionRow
              key={a.action_id}
              action={a}
              canControl={canControl}
              onApprove={(id) => approveMut.mutate(id)}
              onReject={(id) => rejectMut.mutate(id)}
              onExecute={(id) => executeMut.mutate(id)}
              loading={mutLoading}
            />
          ))}
          {others.length === 0 && !actionsLoading && (
            <p className="py-4 text-center text-sm text-slate-600">No historical actions.</p>
          )}
        </div>
      </section>

      {/* Simulated actuations */}
      <section>
        <h2 className="mb-4 flex items-center gap-2 text-base font-medium text-slate-200">
          <Zap className="size-4 text-emerald-400" /> Simulated Actuations
        </h2>
        <div className="overflow-x-auto rounded-xl border border-white/5 bg-card">
          <table className="w-full text-left text-xs text-slate-400">
            <thead className="border-b border-white/5 bg-black/20 text-[11px] font-medium uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2">Time</th>
                <th className="px-4 py-2">Action</th>
                <th className="px-4 py-2">Entity</th>
                <th className="px-4 py-2">Keys</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {actuations.map((item: ControlActuation) => (
                <tr key={item.action_id}>
                  <td className="px-4 py-2 font-mono">{new Date(item.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-2">{ACTION_TYPE_LABELS[item.action_type] ?? item.action_type}</td>
                  <td className="px-4 py-2">{item.entity_id}</td>
                  <td className="px-4 py-2 font-mono">
                    {(item.keys_written ?? []).join(", ") || "—"}
                  </td>
                </tr>
              ))}
              {actuations.length === 0 && (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-600" colSpan={4}>
                    No simulated actuations recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
