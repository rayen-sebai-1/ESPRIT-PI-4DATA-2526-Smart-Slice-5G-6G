import { useEffect, useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Play, FileText, AlertTriangle, CheckCircle, Clock, XCircle, Search, RefreshCw, X, Activity, Zap } from "lucide-react";
import { getDriftStatus } from "@/api/controlApi";
import {
  listRuntimeServices,
  patchRuntimeService,
  type RuntimeServiceMode,
  type RuntimeServiceState,
} from "@/api/runtimeApi";

import { PageHeader } from "@/components/layout/page-header";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import {
  getMlopsOrchestrationActions,
  getMlopsOrchestrationRuns,
  triggerMlopsOrchestrationRun,
  getMlopsOrchestrationRunLogs,
  type MlopsActionDefinition,
  type MlopsOrchestrationRunResponse
} from "@/api/mlopsOrchestrationApi";

// Helper components

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    SUCCESS: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
    FAILED: "bg-red-500/10 text-red-500 border-red-500/20",
    RUNNING: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    QUEUED: "bg-amber-500/10 text-amber-500 border-amber-500/20",
    TIMEOUT: "bg-orange-500/10 text-orange-500 border-orange-500/20",
    DISABLED: "bg-slate-500/10 text-slate-400 border-slate-500/20",
    CANCELLED: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold", styles[status] || styles.DISABLED)}>
      {status}
    </span>
  );
}

function TriggerSourceBadge({ source }: { source?: string }) {
  const cfg: Record<string, { cls: string; label: string }> = {
    manual: { cls: "bg-slate-500/10 text-slate-400 border-slate-500/20", label: "Manual" },
    drift: { cls: "bg-purple-500/10 text-purple-400 border-purple-500/20", label: "Drift" },
    scheduled: { cls: "bg-blue-500/10 text-blue-400 border-blue-500/20", label: "Scheduled" },
  };
  const { cls, label } = cfg[source ?? "manual"] ?? cfg.manual;
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase", cls)}>
      {label}
    </span>
  );
}

function RiskBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    LOW: "bg-slate-500/10 text-slate-400 border-slate-500/20",
    MEDIUM: "bg-amber-500/10 text-amber-500 border-amber-500/20",
    HIGH: "bg-red-500/10 text-red-500 border-red-500/20",
    CRITICAL: "bg-red-500/10 text-red-500 border-red-500/20",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase", styles[level] || styles.LOW)}>
      {level} RISK
    </span>
  );
}

function LogsModal({ runId, isOpen, onClose }: { runId: string | null; isOpen: boolean; onClose: () => void }) {
  const { data: logs, refetch } = useQuery({
    queryKey: ["mlops", "orchestration", "logs", runId],
    queryFn: () => getMlopsOrchestrationRunLogs(runId!),
    enabled: !!runId && isOpen,
    refetchInterval: (query) => {
      if (query.state.data?.status === "RUNNING" || query.state.data?.status === "QUEUED") return 2000;
      return false;
    },
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="flex h-[90vh] w-[90vw] max-w-6xl flex-col rounded-xl border border-white/10 bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/5 p-4">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-medium text-slate-200">Logs</h3>
            {logs && <StatusBadge status={logs.status} />}
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white transition">
            <X className="size-5" />
          </button>
        </div>
        <div className="flex-1 overflow-auto bg-[#0a0a0a] p-4 text-xs font-mono leading-relaxed text-slate-300">
          {!logs ? (
            <div className="flex h-full items-center justify-center text-slate-500">Chargement...</div>
          ) : (
            <>
              {logs.stdout && (
                <div className="mb-4 whitespace-pre-wrap">{logs.stdout}</div>
              )}
              {logs.stderr && (
                <div className="whitespace-pre-wrap text-red-400">{logs.stderr}</div>
              )}
              {!logs.stdout && !logs.stderr && (
                <div className="text-slate-500 italic">Aucun log disponible.</div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function RunFormModal({ action, isOpen, onClose, onRun }: { action: MlopsActionDefinition | null; isOpen: boolean; onClose: () => void; onRun: (params: any) => void }) {
  const [modelName, setModelName] = useState("");
  const [extraParams, setExtraParams] = useState("{}");

  if (!isOpen || !action) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const parsed = JSON.parse(extraParams);
      const params = { ...parsed };
      if (modelName) params.MODEL_NAME = modelName;
      onRun(params);
    } catch {
      alert("Invalid JSON parameters");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-white/10 bg-card p-6 shadow-2xl">
        <h3 className="mb-2 text-xl font-medium text-slate-200">Execute: {action.label}</h3>
        <p className="mb-6 text-sm text-slate-400">{action.description}</p>
        
        {action.requires_confirmation && (
          <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400 flex items-start gap-2">
            <AlertTriangle className="size-4 shrink-0 mt-0.5" />
            <p>This is a high risk action. Please confirm you want to proceed.</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Model Name (Optional)</label>
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              placeholder="e.g. sla_5g"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Additional Parameters (JSON)</label>
            <textarea
              value={extraParams}
              onChange={(e) => setExtraParams(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm font-mono text-slate-200 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              rows={3}
            />
          </div>
          
          <div className="mt-6 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/5 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              className={cn(
                "rounded-lg px-4 py-2 text-sm font-medium text-slate-950 transition",
                action.requires_confirmation ? "bg-red-500 hover:bg-red-400 text-white" : "bg-accent hover:bg-accent/90"
              )}
            >
              Run Action
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function MlopsOrchestrationPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [logsRunId, setLogsRunId] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<MlopsActionDefinition | null>(null);

  const { data: driftStatus } = useQuery({
    queryKey: ["controls", "drift", "status"],
    queryFn: getDriftStatus,
    refetchInterval: 15000,
  });

  const { data: actions = [], isLoading: isLoadingActions } = useQuery({
    queryKey: ["mlops", "orchestration", "actions"],
    queryFn: getMlopsOrchestrationActions,
  });

  const { data: runs = [], isLoading: isLoadingRuns } = useQuery({
    queryKey: ["mlops", "orchestration", "runs"],
    queryFn: () => getMlopsOrchestrationRuns(50),
    refetchInterval: 5000,
  });

  const runMutation = useMutation({
    mutationFn: triggerMlopsOrchestrationRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mlops", "orchestration", "runs"] });
      setSelectedAction(null);
    },
    onError: (error: any) => {
      const msg = error.response?.data?.detail || error.message || String(error);
      alert(`Error triggering run: ${msg}`);
    },
  });

  const { data: runtimeServicesData, isLoading: runtimeLoading } = useQuery({
    queryKey: ["runtime", "services"],
    queryFn: listRuntimeServices,
    refetchInterval: 8000,
  });

  const runtimePatchMutation = useMutation({
    mutationFn: ({
      serviceName,
      enabled,
      mode,
      reason,
    }: {
      serviceName: string;
      enabled: boolean;
      mode: RuntimeServiceMode;
      reason: string;
    }) => patchRuntimeService(serviceName, { enabled, mode, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runtime", "services"] });
    },
    onError: (error: any) => {
      const msg = error.response?.data?.detail || error.message || String(error);
      alert(`Runtime update failed: ${msg}`);
    },
  });

  const canExecute = user?.role === "ADMIN" || user?.role === "DATA_MLOPS_ENGINEER";
  const canWriteRuntime = user?.role === "ADMIN" || user?.role === "DATA_MLOPS_ENGINEER";

  const lastDriftRun = runs.find((r) => r.trigger_source === "drift");
  const runtimeServices = runtimeServicesData?.items ?? [];

  return (
    <div className="space-y-8 animate-in fade-in duration-500">

      {/* Auto MLOps status bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className={cn(
          "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold",
          driftStatus?.pipeline_enabled
            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
            : "border-slate-500/20 bg-slate-500/10 text-slate-500",
        )}>
          <Activity className="size-3" />
          Auto MLOps: {driftStatus?.pipeline_enabled ? "ON" : "OFF"}
        </div>

        {driftStatus?.drift_detected && (
          <div className="flex items-center gap-2 rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-400">
            <Zap className="size-3" />
            DRIFT DETECTED — {driftStatus.anomaly_count} anomalies
          </div>
        )}

        {lastDriftRun && (
          <div className="flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-500/10 px-3 py-1.5 text-xs text-purple-400">
            <Zap className="size-3" />
            Last drift-triggered run: {lastDriftRun.started_at ? new Date(lastDriftRun.started_at).toLocaleString() : "pending"}
          </div>
        )}
      </div>

      {/* Runtime controls */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-medium text-slate-200">
            <Activity className="size-5 text-accent" />
            Runtime Service Controls
          </h2>
          <p className="text-xs text-slate-500">
            Redis contract: <code>runtime:service:{"{name}"}:*</code>
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {runtimeServices.map((svc: RuntimeServiceState) => (
            <div key={svc.service_name} className="rounded-xl border border-white/5 bg-cardAlt/50 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-slate-200">{svc.service_name}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Updated {svc.updated_at ? new Date(svc.updated_at).toLocaleString() : "never"} by {svc.updated_by || "system"}
                  </p>
                </div>
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase",
                    svc.enabled
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                      : "border-slate-500/20 bg-slate-500/10 text-slate-400",
                  )}
                >
                  {svc.enabled ? "enabled" : "disabled"}
                </span>
              </div>

              <div className="mt-3 flex items-center gap-2 text-xs">
                <span className="text-slate-500">Mode:</span>
                <span className="rounded bg-white/5 px-2 py-0.5 font-mono text-slate-300">{svc.mode}</span>
              </div>

              <p className="mt-3 min-h-8 text-xs text-slate-400">
                {svc.reason || "No reason provided."}
              </p>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  disabled={!canWriteRuntime || runtimePatchMutation.isPending || svc.enabled}
                  onClick={() =>
                    runtimePatchMutation.mutate({
                      serviceName: svc.service_name,
                      enabled: true,
                      mode: "auto",
                      reason: `Enabled by ${user?.email ?? "operator"} from orchestration view`,
                    })
                  }
                  className="rounded-lg bg-emerald-600/20 px-3 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-600/30 disabled:opacity-40"
                >
                  Enable
                </button>
                <button
                  disabled={!canWriteRuntime || runtimePatchMutation.isPending || !svc.enabled}
                  onClick={() =>
                    runtimePatchMutation.mutate({
                      serviceName: svc.service_name,
                      enabled: false,
                      mode: "disabled",
                      reason: `Disabled by ${user?.email ?? "operator"} from orchestration view`,
                    })
                  }
                  className="rounded-lg bg-red-600/20 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-600/30 disabled:opacity-40"
                >
                  Disable
                </button>
                <button
                  disabled={!canWriteRuntime || runtimePatchMutation.isPending}
                  onClick={() =>
                    runtimePatchMutation.mutate({
                      serviceName: svc.service_name,
                      enabled: svc.enabled,
                      mode: "manual",
                      reason: `Set manual mode by ${user?.email ?? "operator"} from orchestration view`,
                    })
                  }
                  className="rounded-lg bg-blue-600/20 px-3 py-1.5 text-xs font-medium text-blue-300 hover:bg-blue-600/30 disabled:opacity-40"
                >
                  Manual Mode
                </button>
              </div>
            </div>
          ))}

          {!runtimeLoading && runtimeServices.length === 0 && (
            <div className="col-span-full rounded-xl border border-white/5 bg-card p-5 text-sm text-slate-400">
              Runtime services are unavailable from the dashboard-backend.
            </div>
          )}
        </div>
      </section>

      {/* Actions Grid */}
      <section>
        <h2 className="mb-4 flex items-center gap-2 text-lg font-medium text-slate-200">
          <Play className="size-5 text-accent" />
          Pipeline Actions
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {actions.map((action) => (
            <div key={action.action_key} className="flex flex-col rounded-xl border border-white/5 bg-cardAlt/50 p-5 transition hover:bg-card">
              <div className="mb-3 flex items-start justify-between">
                <h3 className="font-medium text-slate-200">{action.label}</h3>
                <RiskBadge level={action.risk_level} />
              </div>
              <p className="mb-6 flex-1 text-xs text-slate-400 leading-relaxed">
                {action.description}
              </p>
              <button
                disabled={!canExecute || runMutation.isPending}
                onClick={() => setSelectedAction(action)}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-white/5 py-2 text-sm font-medium text-slate-300 transition hover:bg-accent hover:text-slate-950 disabled:opacity-50"
              >
                <Play className="size-4" />
                Run
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* History Table */}
      <section>
        <h2 className="mb-4 flex items-center gap-2 text-lg font-medium text-slate-200">
          <Clock className="size-5 text-accent" />
          Execution History
        </h2>
        <div className="overflow-x-auto rounded-xl border border-white/5 bg-card">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="border-b border-white/5 bg-black/20 text-xs font-medium uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Triggered By</th>
                <th className="px-4 py-3">Started</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3">Logs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {runs.length === 0 && !isLoadingRuns && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    No runs found.
                  </td>
                </tr>
              )}
              {runs.map((run) => (
                <tr key={run.run_id} className="transition hover:bg-white/[0.02]">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-200">{run.command_label}</div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">{run.action_key}</div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3">
                    <TriggerSourceBadge source={run.trigger_source} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-slate-300">{run.triggered_by_email || "System"}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-400">
                    {run.started_at ? new Date(run.started_at).toLocaleString() : "-"}
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-400">
                    {run.duration_seconds ? `${run.duration_seconds.toFixed(1)}s` : "-"}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setLogsRunId(run.run_id)}
                      className="rounded p-1.5 text-slate-400 hover:bg-white/10 hover:text-white transition"
                    >
                      <FileText className="size-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <LogsModal
        runId={logsRunId}
        isOpen={!!logsRunId}
        onClose={() => setLogsRunId(null)}
      />

      <RunFormModal
        action={selectedAction}
        isOpen={!!selectedAction}
        onClose={() => setSelectedAction(null)}
        onRun={(params) => runMutation.mutate({ action: selectedAction!.action_key, parameters: params })}
      />
    </div>
  );
}
