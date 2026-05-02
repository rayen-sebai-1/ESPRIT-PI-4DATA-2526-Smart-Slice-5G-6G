import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, RefreshCw, AlertTriangle } from "lucide-react";

import {
  approveControlAction,
  executeControlAction,
  listControlActions,
  rejectControlAction,
} from "@/api/controlApi";
import { useAuth } from "@/hooks/useAuth";
import { ActionRow } from "@/pages/control/actions/shared";

export default function ActionHistoryPage() {
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
  const history = (data?.items ?? []).filter((a) => a.status !== "PENDING_APPROVAL");

  return (
    <section className="rounded-2xl border border-white/8 bg-card shadow-sm">
      <div className="flex items-center gap-2 border-b border-white/8 px-6 py-4">
        <Clock className="size-4 text-accent" />
        <h2 className="text-base font-semibold text-slate-200">Action History</h2>
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

        {!isLoading && !error && history.length === 0 && (
          <p className="py-4 text-center text-sm text-slate-600">No historical actions.</p>
        )}

        {history.map((action) => (
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
