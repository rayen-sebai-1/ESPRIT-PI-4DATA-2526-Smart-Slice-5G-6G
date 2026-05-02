import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw, ShieldCheck } from "lucide-react";

import {
  approveControlAction,
  executeControlAction,
  listControlActions,
  rejectControlAction,
} from "@/api/controlApi";
import { useAuth } from "@/hooks/useAuth";
import { ActionRow } from "@/pages/control/actions/shared";

export default function PendingApprovalPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [actionErr, setActionErr] = useState<string | null>(null);

  const canControl = user?.role === "ADMIN" || user?.role === "NETWORK_OPERATOR";

  const { data, isLoading, error } = useQuery({
    queryKey: ["controls", "actions"],
    queryFn: listControlActions,
    refetchInterval: 8000,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["controls"] });

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

  const mutLoading = approveMut.isPending || rejectMut.isPending || executeMut.isPending;
  const pending = (data?.items ?? []).filter((a) => a.status === "PENDING_APPROVAL");

  return (
    <section className="rounded-2xl border border-amber-500/20 bg-card shadow-sm">
      <div className="flex items-center gap-2 border-b border-amber-500/20 px-6 py-4">
        <AlertTriangle className="size-4 text-amber-400" />
        <h2 className="text-base font-semibold text-slate-200">Pending Approval</h2>
        {pending.length > 0 && (
          <span className="ml-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-400">
            {pending.length}
          </span>
        )}
      </div>

      <div className="space-y-3 p-6">
        {actionErr && (
          <div className="flex items-center justify-between rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            <span>
              <AlertTriangle className="mr-1 inline size-4" />
              {actionErr}
            </span>
            <button onClick={() => setActionErr(null)} className="text-red-300 hover:text-red-200">
              x
            </button>
          </div>
        )}

        {isLoading && (
          <div className="flex h-24 items-center justify-center rounded-xl border border-white/5 bg-card">
            <RefreshCw className="size-5 animate-spin text-slate-500" />
          </div>
        )}

        {!isLoading && error && (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400">
            Failed to load actions. Is policy-control running?
          </div>
        )}

        {!isLoading && !error && pending.length === 0 && (
          <div className="rounded-xl border border-white/5 bg-card p-8 text-center text-sm text-slate-500">
            <ShieldCheck className="mx-auto mb-2 size-8 text-slate-600" />
            No actions pending approval.
          </div>
        )}

        {pending.map((action) => (
          <ActionRow
            key={action.action_id}
            action={action}
            canControl={canControl}
            onApprove={(id) => approveMut.mutate(id)}
            onReject={(id) => rejectMut.mutate(id)}
            onExecute={(id) => executeMut.mutate(id)}
            loading={mutLoading}
          />
        ))}
      </div>
    </section>
  );
}
