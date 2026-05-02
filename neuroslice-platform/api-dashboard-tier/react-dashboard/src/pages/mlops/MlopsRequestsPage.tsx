import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Play, RefreshCcw, X } from "lucide-react";

import {
  approveMlopsRequest,
  executeMlopsRequest,
  getMlopsRequests,
  rejectMlopsRequest,
} from "@/api/mlopsApi";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmModal } from "@/components/ui/confirm-modal";
import { EmptyState } from "@/components/ui/empty-state";
import { useAuth } from "@/hooks/useAuth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { cn } from "@/lib/cn";
import type { MlopsRetrainingRequest, MlopsRetrainingRequestStatus } from "@/types/mlops";

type PendingAction = {
  requestId: string;
  operation: "approve" | "reject" | "execute";
};

const statusOrder: MlopsRetrainingRequestStatus[] = [
  "pending_approval",
  "approved",
  "running",
  "completed",
  "failed",
  "skipped",
  "rejected",
];

function statusBadgeClass(status: MlopsRetrainingRequestStatus): string {
  switch (status) {
    case "pending_approval":
      return "bg-amber-500/15 text-amber-300";
    case "approved":
      return "bg-blue-500/15 text-blue-300";
    case "running":
      return "bg-indigo-500/15 text-indigo-300";
    case "completed":
      return "bg-emerald-500/15 text-emerald-300";
    case "failed":
      return "bg-red-500/15 text-red-300";
    case "rejected":
      return "bg-slate-500/15 text-slate-300";
    case "skipped":
      return "bg-orange-500/15 text-orange-300";
    default:
      return "bg-slate-500/15 text-slate-300";
  }
}

function statusLabel(status: MlopsRetrainingRequestStatus): string {
  return status.replace(/_/g, " ");
}

function fmtDateTime(value?: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function sortByCreatedDesc(items: MlopsRetrainingRequest[]): MlopsRetrainingRequest[] {
  return [...items].sort((a, b) => {
    const aTs = Date.parse(a.created_at || "");
    const bTs = Date.parse(b.created_at || "");
    return bTs - aTs;
  });
}

export function MlopsRequestsPage() {
  usePageTitle("MLOps - Retraining Requests");
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const isAdmin = user?.role === "ADMIN";

  const requestsQuery = useQuery({
    queryKey: ["mlops", "requests"],
    queryFn: () => getMlopsRequests({ limit: 300 }),
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasActive = data?.items?.some((item) => item.status === "running");
      return hasActive ? 5_000 : 20_000;
    },
  });

  const approveMutation = useMutation({
    mutationFn: approveMlopsRequest,
    onSuccess: async () => {
      setMessage("Request approved.");
      await queryClient.invalidateQueries({ queryKey: ["mlops", "requests"] });
    },
    onError: (error) => {
      const detail =
        (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
        ?? "Unable to approve request.";
      setMessage(detail);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: rejectMlopsRequest,
    onSuccess: async () => {
      setMessage("Request rejected.");
      await queryClient.invalidateQueries({ queryKey: ["mlops", "requests"] });
    },
    onError: (error) => {
      const detail =
        (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
        ?? "Unable to reject request.";
      setMessage(detail);
    },
  });

  const executeMutation = useMutation({
    mutationFn: executeMlopsRequest,
    onSuccess: async () => {
      setMessage("Execution accepted. Training is now running in background.");
      await queryClient.invalidateQueries({ queryKey: ["mlops", "requests"] });
    },
    onError: (error) => {
      const detail =
        (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
        ?? "Unable to execute request.";
      setMessage(detail);
    },
  });

  const items = useMemo(() => {
    const rows = requestsQuery.data?.items ?? [];
    return sortByCreatedDesc(rows);
  }, [requestsQuery.data?.items]);

  const grouped = useMemo(() => {
    const bucket = new Map<MlopsRetrainingRequestStatus, MlopsRetrainingRequest[]>();
    for (const status of statusOrder) bucket.set(status, []);
    for (const item of items) {
      bucket.get(item.status)?.push(item);
    }
    return bucket;
  }, [items]);

  const busy = approveMutation.isPending || rejectMutation.isPending || executeMutation.isPending;

  return (
    <div className="space-y-6">
      {message ? <Card className="px-4 py-3 text-sm text-slate-200">{message}</Card> : null}

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Human-in-the-Loop Retraining</h3>
            <p className="text-sm text-mutedText">
              Drift creates requests only. Approval and execution are controlled here.
            </p>
          </div>
          <Button variant="secondary" onClick={() => void requestsQuery.refetch()}>
            <RefreshCcw size={16} />
            Refresh
          </Button>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-xs uppercase tracking-widest text-mutedText">Pending</p>
          <p className="mt-1 text-2xl font-bold text-amber-300">{grouped.get("pending_approval")?.length ?? 0}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs uppercase tracking-widest text-mutedText">Approved</p>
          <p className="mt-1 text-2xl font-bold text-blue-300">{grouped.get("approved")?.length ?? 0}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs uppercase tracking-widest text-mutedText">Running</p>
          <p className="mt-1 text-2xl font-bold text-indigo-300">{grouped.get("running")?.length ?? 0}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs uppercase tracking-widest text-mutedText">Failed / Skipped</p>
          <p className="mt-1 text-2xl font-bold text-red-300">
            {(grouped.get("failed")?.length ?? 0) + (grouped.get("skipped")?.length ?? 0)}
          </p>
        </Card>
      </div>

      <Card className="p-5">
        <h3 className="text-base font-semibold text-white">Retraining Requests</h3>
        <p className="text-xs text-mutedText">Newest first. Pending requests are highlighted.</p>

        {requestsQuery.isLoading ? (
          <p className="mt-4 text-sm text-mutedText">Loading requests...</p>
        ) : requestsQuery.isError ? (
          <EmptyState
            title="Requests unavailable"
            description="The backend did not return retraining requests."
          />
        ) : items.length === 0 ? (
          <p className="mt-4 text-sm text-mutedText">No retraining requests found.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-[0.22em] text-mutedText">
                <tr>
                  <th className="pb-3 pr-4">Request</th>
                  <th className="pb-3 pr-4">Model</th>
                  <th className="pb-3 pr-4">Drift</th>
                  <th className="pb-3 pr-4">Created</th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3 pr-4">Approved By</th>
                  <th className="pb-3 pr-4">Detail</th>
                  <th className="pb-3">Actions</th>
                </tr>
              </thead>
              <tbody className="text-slate-100">
                {items.map((item) => {
                  const rowHighlight = item.status === "pending_approval";
                  return (
                    <tr key={item.id} className={cn("border-t border-border", rowHighlight && "bg-amber-500/5")}>
                      <td className="py-3 pr-4 font-mono text-xs">{item.id.slice(0, 8)}</td>
                      <td className="py-3 pr-4">{item.model}</td>
                      <td className="py-3 pr-4 font-mono text-xs">
                        {item.anomaly_count} / {item.threshold}
                      </td>
                      <td className="py-3 pr-4 text-xs text-mutedText">{fmtDateTime(item.created_at)}</td>
                      <td className="py-3 pr-4">
                        <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium capitalize", statusBadgeClass(item.status))}>
                          {statusLabel(item.status)}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-xs text-mutedText">{item.approved_by ?? "-"}</td>
                      <td className="max-w-sm py-3 pr-4 text-xs text-mutedText">{item.execution_detail ?? "-"}</td>
                      <td className="py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={!isAdmin || busy || item.status !== "pending_approval"}
                            onClick={() => setPendingAction({ requestId: item.id, operation: "approve" })}
                            title={!isAdmin ? "Admin role required" : undefined}
                          >
                            <Check size={14} />
                            Approve
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={!isAdmin || busy || (item.status !== "pending_approval" && item.status !== "approved")}
                            onClick={() => setPendingAction({ requestId: item.id, operation: "reject" })}
                            title={!isAdmin ? "Admin role required" : undefined}
                          >
                            <X size={14} />
                            Reject
                          </Button>
                          <Button
                            size="sm"
                            disabled={!isAdmin || busy || item.status !== "approved"}
                            onClick={() => setPendingAction({ requestId: item.id, operation: "execute" })}
                            title={!isAdmin ? "Admin role required" : undefined}
                          >
                            <Play size={14} />
                            Execute
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ConfirmModal
        open={pendingAction !== null}
        title={
          pendingAction?.operation === "approve"
            ? "Approve retraining request?"
            : pendingAction?.operation === "reject"
              ? "Reject retraining request?"
              : "Execute retraining request?"
        }
        description={
          pendingAction?.operation === "execute"
            ? "Are you sure you want to retrain this model?"
            : "Confirm this action on the selected retraining request."
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
          if (!pendingAction) return;
          const { requestId, operation } = pendingAction;
          setPendingAction(null);
          if (operation === "approve") {
            approveMutation.mutate(requestId);
            return;
          }
          if (operation === "reject") {
            rejectMutation.mutate(requestId);
            return;
          }
          executeMutation.mutate(requestId);
        }}
      >
        {pendingAction?.operation === "execute" ? (
          <div className="rounded border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
            <div className="flex items-center gap-2">
              <AlertTriangle size={14} />
              Execution is restricted to one model training at a time.
            </div>
          </div>
        ) : null}
      </ConfirmModal>
    </div>
  );
}
