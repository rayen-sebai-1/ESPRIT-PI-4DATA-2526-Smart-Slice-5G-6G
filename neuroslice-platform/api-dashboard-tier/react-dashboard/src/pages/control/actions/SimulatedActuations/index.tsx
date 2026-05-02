import { useQuery } from "@tanstack/react-query";
import { Zap } from "lucide-react";

import { listControlActuations, type ControlActuation } from "@/api/controlApi";
import { ACTION_TYPE_LABELS } from "@/pages/control/actions/shared";

export default function SimulatedActuationsPage() {
  const { data } = useQuery({
    queryKey: ["controls", "actuations"],
    queryFn: listControlActuations,
    refetchInterval: 8000,
  });

  const actuations = data?.items ?? [];

  return (
    <section className="rounded-2xl border border-emerald-500/20 bg-card shadow-sm">
      <div className="flex items-center gap-2 border-b border-emerald-500/20 px-6 py-4">
        <Zap className="size-4 text-emerald-400" />
        <h2 className="text-base font-semibold text-slate-200">Simulated Actuations</h2>
      </div>

      <div className="p-6">
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
                  <td className="px-4 py-2 font-mono">{(item.keys_written ?? []).join(", ") || "-"}</td>
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
      </div>
    </section>
  );
}
