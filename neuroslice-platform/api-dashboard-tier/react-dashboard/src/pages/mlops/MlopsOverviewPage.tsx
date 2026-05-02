import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle2, AlertTriangle, Database, Layers } from "lucide-react";

import { getMlopsOverview } from "@/api/mlopsApi";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { usePageTitle } from "@/hooks/usePageTitle";
import { healthClassName, healthLabel } from "./mlopsHelpers";

export function MlopsOverviewPage() {
  usePageTitle("MLOps - Overview");

  const overviewQuery = useQuery({ queryKey: ["mlops", "overview"], queryFn: getMlopsOverview });

  if (overviewQuery.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Loading MLOps overview...</div>;
  }

  if (overviewQuery.isError || !overviewQuery.data) {
    return (
      <EmptyState
        title="MLOps unavailable"
        description="Unable to contact the dashboard backend for MLOps data."
      />
    );
  }

  const data = overviewQuery.data;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Promoted models"
          value={String(data.promoted_models_count)}
          subtitle="Directories under models/promoted/*/current"
          icon={<Layers size={20} />}
          tone="accent"
        />
        <KpiCard
          title="Quality gate: pass"
          value={String(data.models_with_pass_gate)}
          subtitle="Runs above the threshold"
          icon={<CheckCircle2 size={20} />}
          tone="accent"
        />
        <KpiCard
          title="Quality gate: fail"
          value={String(data.models_with_fail_gate)}
          subtitle="Runs below the threshold"
          icon={<AlertTriangle size={20} />}
          tone={data.models_with_fail_gate > 0 ? "warning" : "neutral"}
        />
        <KpiCard
          title="Pending runs"
          value={String(data.pending_runs)}
          subtitle="Promotion not finalized"
          icon={<Activity size={20} />}
          tone={data.pending_runs > 0 ? "warning" : "neutral"}
        />
      </section>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Data sources</h3>
            <p className="text-sm text-mutedText">
              MLOps integration status on the dashboard-backend side.
            </p>
          </div>
          <Database size={20} className="text-accent" />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {Object.entries(data.sources).map(([key, value]) => (
            <div key={key} className="rounded-2xl border border-border bg-cardAlt/70 p-4">
              <div className="text-xs uppercase tracking-[0.22em] text-mutedText">{key}</div>
              <div className="mt-1 text-sm text-slate-100">{value}</div>
            </div>
          ))}
        </div>
        <div className="mt-4 text-xs text-mutedText">
          Last snapshot: {data.generated_at ?? "unavailable"}
        </div>
      </Card>

      <Card className="p-5">
        <h3 className="text-lg font-semibold text-white">Promoted models</h3>
        <p className="text-sm text-mutedText">
          Summary of metadata read from models/promoted/*/current/metadata.json.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.22em] text-mutedText">
              <tr>
                <th className="pb-3 pr-4">Deployment</th>
                <th className="pb-3 pr-4">Model</th>
                <th className="pb-3 pr-4">Version</th>
                <th className="pb-3 pr-4">Framework</th>
                <th className="pb-3 pr-4">Health</th>
                <th className="pb-3 pr-4">Updated</th>
              </tr>
            </thead>
            <tbody className="text-slate-100">
              {data.promoted_models.map((row) => (
                <tr key={row.deployment_name} className="border-t border-border">
                  <td className="py-3 pr-4">{row.deployment_name}</td>
                  <td className="py-3 pr-4">{row.promoted?.model_name ?? row.registry?.model_name ?? "-"}</td>
                  <td className="py-3 pr-4">{row.promoted?.version ?? row.registry?.version ?? "-"}</td>
                  <td className="py-3 pr-4">{row.promoted?.framework ?? row.registry?.framework ?? "-"}</td>
                  <td className="py-3 pr-4">
                    <span className={healthClassName(row.health)}>{healthLabel(row.health)}</span>
                  </td>
                  <td className="py-3 pr-4 text-mutedText">{row.promoted?.updated_at ?? "-"}</td>
                </tr>
              ))}
              {data.promoted_models.length === 0 ? (
                <tr>
                  <td className="py-6 text-center text-mutedText" colSpan={6}>
                    No promoted model is currently available.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
