import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle2, AlertTriangle, Database, Layers } from "lucide-react";

import { getMlopsOverview } from "@/api/mlopsApi";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { usePageTitle } from "@/hooks/usePageTitle";
import { healthClassName, healthLabel } from "./mlopsHelpers";

export function MlopsOverviewPage() {
  usePageTitle("MLOps - Vue globale");

  const overviewQuery = useQuery({ queryKey: ["mlops", "overview"], queryFn: getMlopsOverview });

  if (overviewQuery.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Chargement de la vue MLOps...</div>;
  }

  if (overviewQuery.isError || !overviewQuery.data) {
    return (
      <EmptyState
        title="MLOps indisponible"
        description="Impossible de contacter le backend dashboard pour les donnees MLOps."
      />
    );
  }

  const data = overviewQuery.data;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Modeles promus"
          value={String(data.promoted_models_count)}
          subtitle="Repertoires sous models/promoted/*/current"
          icon={<Layers size={20} />}
          tone="accent"
        />
        <KpiCard
          title="Quality gate: pass"
          value={String(data.models_with_pass_gate)}
          subtitle="Runs au-dessus du seuil"
          icon={<CheckCircle2 size={20} />}
          tone="accent"
        />
        <KpiCard
          title="Quality gate: fail"
          value={String(data.models_with_fail_gate)}
          subtitle="Runs sous le seuil"
          icon={<AlertTriangle size={20} />}
          tone={data.models_with_fail_gate > 0 ? "warning" : "neutral"}
        />
        <KpiCard
          title="Runs en attente"
          value={String(data.pending_runs)}
          subtitle="Promotion non finalisee"
          icon={<Activity size={20} />}
          tone={data.pending_runs > 0 ? "warning" : "neutral"}
        />
      </section>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Sources de donnees</h3>
            <p className="text-sm text-mutedText">
              Etat des integrations MLOps cote dashboard-backend.
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
          Dernier snapshot: {data.generated_at ?? "non disponible"}
        </div>
      </Card>

      <Card className="p-5">
        <h3 className="text-lg font-semibold text-white">Modeles promus</h3>
        <p className="text-sm text-mutedText">
          Synthese des metadonnees lues sous models/promoted/*/current/metadata.json.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.22em] text-mutedText">
              <tr>
                <th className="pb-3 pr-4">Deployment</th>
                <th className="pb-3 pr-4">Modele</th>
                <th className="pb-3 pr-4">Version</th>
                <th className="pb-3 pr-4">Framework</th>
                <th className="pb-3 pr-4">Sante</th>
                <th className="pb-3 pr-4">Mis a jour</th>
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
                    Aucun modele promu n'est actuellement disponible.
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
