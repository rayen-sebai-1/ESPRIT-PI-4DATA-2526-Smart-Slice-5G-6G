import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarClock,
  Check,
  ClipboardList,
  Play,
  RefreshCcw,
  TrendingDown,
  X,
  Zap,
} from "lucide-react";

import {
  approveMlopsRequest,
  executeMlopsRequest,
  getMlopsRequests,
  rejectMlopsRequest,
  triggerMlopsRetraining,
} from "@/api/mlopsApi";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmModal } from "@/components/ui/confirm-modal";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { cn } from "@/lib/cn";
import type {
  MlopsRetrainingRequest,
  MlopsRetrainingRequestStatus,
  MlopsRetrainingTriggerType,
} from "@/types/mlops";
import { driftSeverityBg } from "./mlopsHelpers";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PendingAction = {
  request: MlopsRetrainingRequest;
  operation: "approve" | "reject" | "execute";
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_ORDER: MlopsRetrainingRequestStatus[] = [
  "pending_approval",
  "approved",
  "running",
  "completed",
  "failed",
  "skipped",
  "rejected",
];

const STATUS_LABEL: Record<MlopsRetrainingRequestStatus, string> = {
  pending_approval: "Pending Approval",
  approved:         "Approved",
  running:          "Running",
  completed:        "Completed",
  failed:           "Failed",
  rejected:         "Rejected",
  skipped:          "Skipped",
};

const STATUS_CLASS: Record<MlopsRetrainingRequestStatus, string> = {
  pending_approval: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  approved:         "bg-blue-500/15 text-blue-300 ring-1 ring-blue-500/30",
  running:          "bg-indigo-500/15 text-indigo-300 ring-1 ring-indigo-500/30",
  completed:        "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  failed:           "bg-red-500/15 text-red-300 ring-1 ring-red-500/30",
  rejected:         "bg-slate-500/15 text-slate-400 ring-1 ring-slate-500/20",
  skipped:          "bg-orange-500/15 text-orange-300 ring-1 ring-orange-500/30",
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: MlopsRetrainingRequestStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        STATUS_CLASS[status] ?? "bg-slate-500/15 text-slate-400",
      )}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function TriggerBadge({ type }: { type: MlopsRetrainingTriggerType | null }) {
  if (type === "SCHEDULED") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-purple-500/15 px-2.5 py-0.5 text-xs font-medium text-purple-300 ring-1 ring-purple-500/30">
        <CalendarClock size={10} />
        Scheduled
      </span>
    );
  }
  if (type === "MANUAL") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-500/15 px-2.5 py-0.5 text-xs font-medium text-slate-300 ring-1 ring-slate-500/20">
        Manual
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-500/15 px-2.5 py-0.5 text-xs font-medium text-red-300 ring-1 ring-red-500/30">
      <TrendingDown size={10} />
      Drift
    </span>
  );
}

function RunningPulse() {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-400" />
      </span>
      <span className="text-indigo-300">Running</span>
    </span>
  );
}

function PValueCell({ value }: { value: number | null }) {
  if (value === null || value === undefined) return <span className="text-mutedText">—</span>;
  return (
    <span className={cn("font-mono", value < 0.01 ? "text-red-400" : "text-emerald-400")}>
      {value.toFixed(4)}
    </span>
  );
}

function fmtDateTime(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    year:   "numeric",
    month:  "short",
    day:    "2-digit",
    hour:   "2-digit",
    minute: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// KPI summary bar
// ---------------------------------------------------------------------------

function KpiBar({
  grouped,
}: {
  grouped: Map<MlopsRetrainingRequestStatus, MlopsRetrainingRequest[]>;
}) {
  const kpis = [
    {
      label: "Pending",
      count: grouped.get("pending_approval")?.length ?? 0,
      cls: "text-amber-300",
    },
    {
      label: "Approved",
      count: grouped.get("approved")?.length ?? 0,
      cls: "text-blue-300",
    },
    {
      label: "Running",
      count: grouped.get("running")?.length ?? 0,
      cls: "text-indigo-300",
    },
    {
      label: "Completed",
      count: grouped.get("completed")?.length ?? 0,
      cls: "text-emerald-300",
    },
    {
      label: "Failed",
      count: (grouped.get("failed")?.length ?? 0) + (grouped.get("skipped")?.length ?? 0),
      cls: "text-red-300",
    },
    {
      label: "Rejected",
      count: grouped.get("rejected")?.length ?? 0,
      cls: "text-slate-400",
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
      {kpis.map(({ label, count, cls }) => (
        <Card key={label} className="px-4 py-3">
          <p className="text-[10px] uppercase tracking-widest text-mutedText">{label}</p>
          <p className={cn("mt-1 text-2xl font-bold tabular-nums", cls)}>{count}</p>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confirm modal content per action
// ---------------------------------------------------------------------------

function ActionModalContent({
  operation,
  request,
}: {
  operation: "approve" | "reject" | "execute";
  request: MlopsRetrainingRequest;
}) {
  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-white/8 bg-cardAlt px-4 py-3 text-xs">
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
          <span className="text-mutedText">Model</span>
          <span className="font-medium text-slate-200">{request.model}</span>
          <span className="text-mutedText">Trigger</span>
          <span>
            <TriggerBadge type={request.trigger_type} />
          </span>
          {request.severity && (
            <>
              <span className="text-mutedText">Severity</span>
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-xs font-semibold w-fit",
                  driftSeverityBg(request.severity),
                )}
              >
                {request.severity}
              </span>
            </>
          )}
          {request.p_value != null && (
            <>
              <span className="text-mutedText">p-value</span>
              <PValueCell value={request.p_value} />
            </>
          )}
          {request.drift_score != null && (
            <>
              <span className="text-mutedText">Drift score</span>
              <span className="font-mono text-slate-200">
                {request.drift_score.toFixed(3)}
              </span>
            </>
          )}
          <span className="text-mutedText">Created</span>
          <span className="text-slate-300">{fmtDateTime(request.created_at)}</span>
        </div>
      </div>

      {operation === "execute" && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2.5 text-xs text-amber-200">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>
            This launches the batch training pipeline for{" "}
            <strong>{request.model}</strong>. Only one model trains at a time; a cooldown
            applies after success.
          </span>
        </div>
      )}

      {operation === "reject" && (
        <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5 text-xs text-red-200">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>Rejection is terminal — this request cannot be executed afterwards.</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function MlopsRequestsPage() {
  usePageTitle("MLOps — Retraining Requests");
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [triggerFilter, setTriggerFilter] = useState<string>("all");
  const [modelFilter, setModelFilter] = useState<string>("");

  const canWrite = user?.role === "ADMIN" || user?.role === "DATA_MLOPS_ENGINEER";

  // -------------------------------------------------------------------------
  // Query — auto-refresh 10s while running, 15s otherwise
  // -------------------------------------------------------------------------

  const requestsQuery = useQuery({
    queryKey: ["mlops", "requests"],
    queryFn: () => getMlopsRequests({ limit: 300 }),
    refetchInterval: (query) => {
      const hasRunning = query.state.data?.items?.some((r) => r.status === "running");
      return hasRunning ? 10_000 : 15_000;
    },
  });

  // -------------------------------------------------------------------------
  // Mutations
  // -------------------------------------------------------------------------

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["mlops", "requests"] });

  const approveMutation = useMutation({
    mutationFn: approveMlopsRequest,
    onSuccess: (data) => {
      toast.success(`Request approved for model "${data.model}".`);
      void invalidate();
    },
    onError: (err) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
        "Could not approve request.";
      toast.error(detail);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: rejectMlopsRequest,
    onSuccess: (data) => {
      toast.info(`Request rejected for model "${data.model}".`);
      void invalidate();
    },
    onError: (err) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
        "Could not reject request.";
      toast.error(detail);
    },
  });

  const executeMutation = useMutation({
    mutationFn: executeMlopsRequest,
    onSuccess: (data) => {
      toast.success(
        `Training pipeline accepted for "${data.model}". Status: ${data.status}.`,
      );
      void invalidate();
    },
    onError: (err) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
        "Could not execute request.";
      toast.error(detail);
    },
  });

  const simulateMutation = useMutation({
    mutationFn: triggerMlopsRetraining,
    onSuccess: (result) => {
      if (result.triggered) {
        toast.success(
          `Drift trigger fired (anomaly count: ${result.anomaly_count}). Pending requests created.`,
        );
      } else {
        toast.warning(`Trigger skipped: ${result.reason}`);
      }
      void invalidate();
    },
    onError: (err) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
        "Trigger failed.";
      toast.error(detail);
    },
  });

  // -------------------------------------------------------------------------
  // Derived data
  // -------------------------------------------------------------------------

  const busy =
    approveMutation.isPending ||
    rejectMutation.isPending ||
    executeMutation.isPending ||
    simulateMutation.isPending;

  const allItems = useMemo(() => {
    const rows = requestsQuery.data?.items ?? [];
    return [...rows].sort(
      (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
    );
  }, [requestsQuery.data?.items]);

  const grouped = useMemo(() => {
    const m = new Map<MlopsRetrainingRequestStatus, MlopsRetrainingRequest[]>();
    for (const s of STATUS_ORDER) m.set(s, []);
    for (const item of allItems) m.get(item.status)?.push(item);
    return m;
  }, [allItems]);

  const filteredItems = useMemo(() => {
    return allItems.filter((item) => {
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      if (
        triggerFilter !== "all" &&
        (item.trigger_type ?? "DRIFT") !== triggerFilter
      )
        return false;
      if (
        modelFilter &&
        !item.model.toLowerCase().includes(modelFilter.toLowerCase())
      )
        return false;
      return true;
    });
  }, [allItems, statusFilter, triggerFilter, modelFilter]);

  const hasRunning = allItems.some((r) => r.status === "running");

  // -------------------------------------------------------------------------
  // Action dispatch
  // -------------------------------------------------------------------------

  function dispatchAction(action: PendingAction) {
    setPendingAction(null);
    const { request, operation } = action;
    if (operation === "approve") approveMutation.mutate(request.id);
    else if (operation === "reject") rejectMutation.mutate(request.id);
    else executeMutation.mutate(request.id);
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="space-y-6">

      {/* ── Header card ── */}
      <Card className="p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-white">
              Human-in-the-Loop Retraining
            </h2>
            <p className="text-sm text-mutedText">
              Drift events, scheduled cycles, and manual triggers create{" "}
              <span className="text-amber-300">pending</span> requests only. Approval
              and execution are always human-controlled.
            </p>
            {!canWrite && (
              <p className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1 text-xs text-amber-300">
                <AlertTriangle size={12} />
                Read-only — Admin or MLOps Engineer role required to approve or
                execute.
              </p>
            )}
            {hasRunning && (
              <p className="inline-flex items-center gap-1.5 rounded-full bg-indigo-500/10 px-3 py-1 text-xs text-indigo-300">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-indigo-400" />
                </span>
                A training run is active — auto-refreshing every 10 s.
              </p>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {canWrite && (
              <Button
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={() => simulateMutation.mutate()}
                title="Fires POST /controls/drift/trigger — creates pending_approval requests for all models (bypasses threshold). Use to test the approval flow."
              >
                <Zap size={15} />
                {simulateMutation.isPending ? "Triggering…" : "Simulate Drift Trigger"}
              </Button>
            )}
            <Button
              variant="secondary"
              size="sm"
              disabled={requestsQuery.isFetching}
              onClick={() => void requestsQuery.refetch()}
            >
              <RefreshCcw
                size={15}
                className={cn(requestsQuery.isFetching && "animate-spin")}
              />
              Refresh
            </Button>
          </div>
        </div>
      </Card>

      {/* ── KPI bar ── */}
      <KpiBar grouped={grouped} />

      {/* ── Filters ── */}
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-4">
          {/* Status */}
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-widest text-mutedText">
              Status
            </label>
            <select
              className="h-9 rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-accent"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">All statuses</option>
              {STATUS_ORDER.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </div>

          {/* Trigger */}
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-widest text-mutedText">
              Trigger type
            </label>
            <select
              className="h-9 rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-accent"
              value={triggerFilter}
              onChange={(e) => setTriggerFilter(e.target.value)}
            >
              <option value="all">All triggers</option>
              <option value="DRIFT">Drift</option>
              <option value="SCHEDULED">Scheduled</option>
              <option value="MANUAL">Manual</option>
            </select>
          </div>

          {/* Model */}
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-widest text-mutedText">
              Model
            </label>
            <input
              className="h-9 rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200 placeholder:text-mutedText focus:outline-none focus:ring-1 focus:ring-accent"
              placeholder="e.g. congestion-5g"
              value={modelFilter}
              onChange={(e) => setModelFilter(e.target.value)}
            />
          </div>

          {(statusFilter !== "all" || triggerFilter !== "all" || modelFilter) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setStatusFilter("all");
                setTriggerFilter("all");
                setModelFilter("");
              }}
            >
              Clear filters
            </Button>
          )}

          <p className="ml-auto text-xs text-mutedText">
            {filteredItems.length} of {allItems.length} requests
          </p>
        </div>
      </Card>

      {/* ── Table ── */}
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-white">Retraining Requests</h3>
            <p className="text-xs text-mutedText">
              Newest first · last {allItems.length} stored
            </p>
          </div>
        </div>

        {requestsQuery.isLoading ? (
          <div className="flex items-center gap-3 py-10 text-sm text-mutedText">
            <RefreshCcw size={16} className="animate-spin" />
            Loading requests…
          </div>
        ) : requestsQuery.isError ? (
          <EmptyState
            title="Requests unavailable"
            description="The backend did not return retraining requests. Make sure the platform is running."
          />
        ) : filteredItems.length === 0 ? (
          <EmptyState
            icon={<ClipboardList size={24} />}
            title={
              allItems.length === 0
                ? "No retraining requests yet"
                : "No requests match current filters"
            }
            description={
              allItems.length === 0
                ? 'Drift events or cron schedules will create them automatically. You can also click "Simulate Drift Trigger" to test the flow.'
                : "Try clearing the filters to see all requests."
            }
            action={
              allItems.length === 0 && canWrite ? (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => simulateMutation.mutate()}
                >
                  <Zap size={14} />
                  Simulate Drift Trigger
                </Button>
              ) : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-[10px] uppercase tracking-[0.22em] text-mutedText">
                  <th className="pb-3 pr-4 font-normal">Request ID</th>
                  <th className="pb-3 pr-4 font-normal">Model</th>
                  <th className="pb-3 pr-4 font-normal">Trigger</th>
                  <th className="pb-3 pr-4 font-normal">Source Schedule</th>
                  <th className="pb-3 pr-4 font-normal">Status</th>
                  <th className="pb-3 pr-4 font-normal">Severity</th>
                  <th className="pb-3 pr-4 font-normal">p-value</th>
                  <th className="pb-3 pr-4 font-normal">Drift score</th>
                  <th className="pb-3 pr-4 font-normal">Anomalies</th>
                  <th className="pb-3 pr-4 font-normal">Created</th>
                  <th className="pb-3 pr-4 font-normal">Approved by</th>
                  <th className="pb-3 pr-4 font-normal">Approved at</th>
                  <th className="pb-3 pr-4 font-normal">Execution status</th>
                  <th className="pb-3 font-normal">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => {
                  const isPending = item.status === "pending_approval";
                  const isRunning = item.status === "running";

                  // Action visibility rules (spec-exact)
                  const showApprove = canWrite && isPending;
                  const showReject  = canWrite && (isPending || item.status === "approved");
                  const showExecute = canWrite && item.status === "approved";
                  const hasActions  = showApprove || showReject || showExecute;

                  return (
                    <tr
                      key={item.id}
                      className={cn(
                        "border-t border-border transition-colors",
                        isPending && "bg-amber-500/5 hover:bg-amber-500/8",
                        isRunning && "bg-indigo-500/5 hover:bg-indigo-500/8",
                        !isPending && !isRunning && "hover:bg-white/2",
                      )}
                    >
                      {/* Request ID */}
                      <td className="py-3 pr-4">
                        <span className="font-mono text-xs text-mutedText">
                          {item.id.slice(0, 8)}
                        </span>
                      </td>

                      {/* Model */}
                      <td className="py-3 pr-4">
                        <span className="font-medium text-slate-100">{item.model}</span>
                        {item.model_internal && item.model_internal !== item.model && (
                          <span className="ml-1 font-mono text-[10px] text-mutedText">
                            ({item.model_internal})
                          </span>
                        )}
                      </td>

                      {/* Trigger type */}
                      <td className="py-3 pr-4">
                        <TriggerBadge type={item.trigger_type} />
                      </td>

                      {/* Source schedule id */}
                      <td className="py-3 pr-4">
                        {item.source_schedule_id ? (
                          <span className="font-mono text-xs text-slate-300">
                            {item.source_schedule_id.slice(0, 8)}
                          </span>
                        ) : (
                          <span className="text-xs text-mutedText">—</span>
                        )}
                      </td>

                      {/* Status */}
                      <td className="py-3 pr-4">
                        {isRunning ? (
                          <RunningPulse />
                        ) : (
                          <StatusBadge status={item.status} />
                        )}
                      </td>

                      {/* Severity */}
                      <td className="py-3 pr-4">
                        {item.severity ? (
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-xs font-semibold",
                              driftSeverityBg(item.severity),
                            )}
                          >
                            {item.severity}
                          </span>
                        ) : (
                          <span className="text-xs text-mutedText">—</span>
                        )}
                      </td>

                      {/* p-value */}
                      <td className="py-3 pr-4 text-xs">
                        <PValueCell value={item.p_value} />
                      </td>

                      {/* Drift score */}
                      <td className="py-3 pr-4 font-mono text-xs text-slate-300">
                        {item.drift_score != null
                          ? item.drift_score.toFixed(3)
                          : <span className="text-mutedText">—</span>}
                      </td>

                      {/* Anomaly count */}
                      <td className="py-3 pr-4 font-mono text-xs text-slate-300">
                        {item.trigger_type !== "SCHEDULED" ? (
                          `${item.anomaly_count} / ${item.threshold}`
                        ) : (
                          <span className="text-mutedText">—</span>
                        )}
                      </td>

                      {/* Created at */}
                      <td className="py-3 pr-4 text-xs text-mutedText whitespace-nowrap">
                        {fmtDateTime(item.created_at)}
                      </td>

                      {/* Approved by */}
                      <td className="py-3 pr-4 text-xs text-slate-300">
                        {item.approved_by ?? <span className="text-mutedText">—</span>}
                      </td>

                      {/* Approved at */}
                      <td className="py-3 pr-4 text-xs text-mutedText whitespace-nowrap">
                        {item.approved_at
                          ? fmtDateTime(item.approved_at)
                          : <span>—</span>}
                      </td>

                      {/* Execution status / detail */}
                      <td className="max-w-[14rem] py-3 pr-4 text-xs text-mutedText">
                        {item.execution_detail
                          ? <span className="line-clamp-2">{item.execution_detail}</span>
                          : <span>—</span>}
                      </td>

                      {/* Actions */}
                      <td className="py-3">
                        {hasActions ? (
                          <div className="flex flex-wrap items-center gap-1.5">
                            {showApprove && (
                              <Button
                                variant="secondary"
                                size="sm"
                                disabled={busy}
                                onClick={() =>
                                  setPendingAction({ request: item, operation: "approve" })
                                }
                              >
                                <Check size={13} />
                                Approve
                              </Button>
                            )}
                            {showReject && (
                              <Button
                                variant="secondary"
                                size="sm"
                                disabled={busy}
                                onClick={() =>
                                  setPendingAction({ request: item, operation: "reject" })
                                }
                              >
                                <X size={13} />
                                Reject
                              </Button>
                            )}
                            {showExecute && (
                              <Button
                                size="sm"
                                disabled={busy}
                                onClick={() =>
                                  setPendingAction({ request: item, operation: "execute" })
                                }
                              >
                                <Play size={13} />
                                Execute
                              </Button>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-mutedText">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ── Confirm modal ── */}
      <ConfirmModal
        open={pendingAction !== null}
        title={
          pendingAction?.operation === "approve"
            ? "Approve retraining request?"
            : pendingAction?.operation === "reject"
              ? "Reject retraining request?"
              : "Execute training pipeline?"
        }
        description={
          pendingAction?.operation === "approve"
            ? "The request will move to Approved. An engineer must then click Execute to start training."
            : pendingAction?.operation === "reject"
              ? "The request will be permanently rejected and cannot be executed."
              : "The training pipeline will be launched in the background."
        }
        confirmLabel={
          pendingAction?.operation === "approve"
            ? "Approve"
            : pendingAction?.operation === "reject"
              ? "Reject"
              : "Execute"
        }
        destructive={pendingAction?.operation !== "approve"}
        onCancel={() => setPendingAction(null)}
        onConfirm={() => {
          if (pendingAction) dispatchAction(pendingAction);
        }}
      >
        {pendingAction && (
          <ActionModalContent
            operation={pendingAction.operation}
            request={pendingAction.request}
          />
        )}
      </ConfirmModal>
    </div>
  );
}
