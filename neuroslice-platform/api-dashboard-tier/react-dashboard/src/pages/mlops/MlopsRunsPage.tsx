import { useQuery } from "@tanstack/react-query";

import { getMlopsRuns } from "@/api/mlopsApi";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatMetric } from "./mlopsHelpers";

export function MlopsRunsPage() {
  usePageTitle("MLOps - Runs");

  const runsQuery = useQuery({ queryKey: ["mlops", "runs"], queryFn: () => getMlopsRuns(80) });

  if (runsQuery.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Loading runs...</div>;
  }
  if (runsQuery.isError || !runsQuery.data) {
    return <EmptyState title="Runs unavailable" description="Reading the MLOps registry failed." />;
  }

  return (
    <Card className="p-5">
      <h3 className="text-lg font-semibold text-white">Latest MLflow runs</h3>
      <p className="text-sm text-mutedText">Sorted from most recent to oldest.</p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-[0.22em] text-mutedText">
            <tr>
              <th className="pb-3 pr-4">Model</th>
              <th className="pb-3 pr-4">Version</th>
              <th className="pb-3 pr-4">Stage</th>
              <th className="pb-3 pr-4">Quality gate</th>
              <th className="pb-3 pr-4">Promotion</th>
              <th className="pb-3 pr-4">Run id</th>
              <th className="pb-3 pr-4">Created</th>
              <th className="pb-3 pr-4">F1</th>
              <th className="pb-3 pr-4">ROC AUC</th>
            </tr>
          </thead>
          <tbody className="text-slate-100">
            {runsQuery.data.map((run) => (
              <tr key={`${run.model_name}-${run.version}-${run.run_id}`} className="border-t border-border">
                <td className="py-3 pr-4">{run.model_name}</td>
                <td className="py-3 pr-4">{run.version ?? "-"}</td>
                <td className="py-3 pr-4">{run.stage ?? "-"}</td>
                <td className="py-3 pr-4">{run.quality_gate_status ?? "-"}</td>
                <td className="py-3 pr-4">{run.promotion_status ?? "-"}</td>
                <td className="py-3 pr-4 font-mono text-xs">{run.run_id ?? "-"}</td>
                <td className="py-3 pr-4 text-mutedText">{run.created_at ?? "-"}</td>
                <td className="py-3 pr-4">{formatMetric(run.metrics?.val_f1)}</td>
                <td className="py-3 pr-4">{formatMetric(run.metrics?.val_roc_auc)}</td>
              </tr>
            ))}
            {runsQuery.data.length === 0 ? (
              <tr>
                <td className="py-6 text-center text-mutedText" colSpan={9}>
                  No runs recorded.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
