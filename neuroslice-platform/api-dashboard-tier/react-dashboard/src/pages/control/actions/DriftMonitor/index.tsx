import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, Clock, Zap } from "lucide-react";

import { getDriftEvents, getDriftStatus, triggerDriftCheck } from "@/api/controlApi";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";

export default function DriftMonitorPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [actionErr, setActionErr] = useState<string | null>(null);

  const canViewDrift =
    user?.role === "ADMIN" || user?.role === "NETWORK_MANAGER" || user?.role === "DATA_MLOPS_ENGINEER";
  const canTriggerDrift = user?.role === "ADMIN" || user?.role === "DATA_MLOPS_ENGINEER";

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

  const driftTriggerMut = useMutation({
    mutationFn: triggerDriftCheck,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["controls"] }),
    onError: (e: any) => setActionErr(e.response?.data?.detail ?? String(e)),
  });

  return (
    <section className="rounded-2xl border border-white/8 bg-card shadow-sm">
      <div className="flex items-center gap-2 border-b border-white/8 px-6 py-4">
        <Activity className="size-4 text-accent" />
        <h2 className="text-base font-semibold text-slate-200">Drift Monitor</h2>
      </div>

      <div className="p-6">
        {actionErr && (
          <div className="mb-4 flex items-center justify-between rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            <span>
              <AlertTriangle className="mr-1 inline size-4" />
              {actionErr}
            </span>
            <button onClick={() => setActionErr(null)} className="text-red-300 hover:text-red-200">
              x
            </button>
          </div>
        )}

        {!canViewDrift && (
          <div className="rounded-xl border border-white/5 bg-cardAlt/40 p-4 text-sm text-slate-400">
            Drift monitor status is restricted to MLOps read roles.
          </div>
        )}

        {canViewDrift && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div
                className={cn(
                  "rounded-xl border p-4",
                  driftStatus?.drift_detected
                    ? "border-red-500/30 bg-red-500/10"
                    : "border-white/5 bg-cardAlt/50",
                )}
              >
                <p className="mb-1 text-xs text-slate-500">Drift Status</p>
                <p
                  className={cn(
                    "text-lg font-semibold",
                    driftStatus?.drift_detected ? "text-red-400" : "text-emerald-400",
                  )}
                >
                  {driftStatus?.drift_detected ? "DRIFT DETECTED" : "NOMINAL"}
                </p>
              </div>

              <div className="rounded-xl border border-white/5 bg-cardAlt/50 p-4">
                <p className="mb-1 text-xs text-slate-500">
                  Anomalies ({driftStatus?.window_seconds}s window)
                </p>
                <p className="text-lg font-semibold text-slate-200">
                  {driftStatus?.anomaly_count ?? "-"} / {driftStatus?.threshold ?? "-"}
                </p>
              </div>

              <div className="rounded-xl border border-white/5 bg-cardAlt/50 p-4">
                <p className="mb-1 text-xs text-slate-500">Last Drift Trigger</p>
                <p className="text-sm text-slate-300">
                  {driftStatus?.last_trigger_time
                    ? new Date(driftStatus.last_trigger_time).toLocaleString()
                    : "Never"}
                </p>
              </div>

              <div className="rounded-xl border border-white/5 bg-cardAlt/50 p-4">
                <p className="mb-1 text-xs text-slate-500">Auto MLOps Pipeline</p>
                <div className="flex items-center justify-between">
                  <p
                    className={cn(
                      "text-sm font-semibold",
                      driftStatus?.pipeline_enabled ? "text-emerald-400" : "text-slate-500",
                    )}
                  >
                    {driftStatus?.pipeline_enabled ? "ENABLED" : "DISABLED"}
                  </p>
                  {canTriggerDrift && (
                    <button
                      onClick={() => driftTriggerMut.mutate()}
                      disabled={driftTriggerMut.isPending || driftStatus?.cooldown_active}
                      className="flex items-center gap-1 rounded-lg bg-white/5 px-2 py-1 text-xs text-slate-400 transition hover:bg-accent hover:text-slate-950 disabled:opacity-40"
                      title={driftStatus?.cooldown_active ? "Cooldown active" : "Trigger drift check now"}
                    >
                      <Zap className="size-3" /> Trigger
                    </button>
                  )}
                </div>
                {driftStatus?.cooldown_active && (
                  <p className="mt-1 text-xs text-amber-400">
                    <Clock className="mr-0.5 inline size-3" />Cooldown active
                  </p>
                )}
              </div>
            </div>

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
                    {(driftEvents?.items ?? []).map((event, idx) => (
                      <tr key={`${event.timestamp}-${idx}`}>
                        <td className="px-4 py-2 font-mono">{new Date(event.timestamp).toLocaleString()}</td>
                        <td className="px-4 py-2">{event.anomaly_count}</td>
                        <td className="px-4 py-2">
                          {event.pipeline_triggered ? (
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
      </div>
    </section>
  );
}
