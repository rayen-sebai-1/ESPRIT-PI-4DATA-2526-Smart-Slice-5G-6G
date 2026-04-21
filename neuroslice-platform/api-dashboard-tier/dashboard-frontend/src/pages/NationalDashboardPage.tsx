import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Gauge,
  Network,
  RadioTower,
  ShieldAlert,
} from "lucide-react";

import { getNationalDashboard } from "@/api/dashboardApi";
import { RegionLoadChart } from "@/components/charts/region-load-chart";
import { PageHeader } from "@/components/layout/page-header";
import { TunisiaNetworkMap } from "@/components/layout/tunisia-network-map";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatDate, formatNumber, formatPercent, truncateText } from "@/lib/format";

export function NationalDashboardPage() {
  usePageTitle("Dashboard National");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["dashboard", "national"],
    queryFn: getNationalDashboard,
  });

  const topRiskRegions = useMemo(() => {
    return [...(data?.regions ?? [])]
      .sort((left, right) => {
        const leftScore = left.high_risk_sessions_count * 3 + left.network_load + (100 - left.sla_percent);
        const rightScore = right.high_risk_sessions_count * 3 + right.network_load + (100 - right.sla_percent);
        return rightScore - leftScore;
      })
      .slice(0, 5);
  }, [data?.regions]);

  if (isLoading) {
    return <div className="py-10 text-sm text-mutedText">Chargement du dashboard national...</div>;
  }

  if (isError || !data) {
    return (
      <EmptyState
        title="Dashboard indisponible"
        description="Les donnees du tableau de bord ne sont pas disponibles pour le moment. Tu peux relancer la page."
      />
    );
  }

  const { overview, regions } = data;
  const lowestSlaRegion = [...regions].sort((left, right) => left.sla_percent - right.sla_percent)[0];
  const highestLoadRegion = [...regions].sort((left, right) => right.network_load - left.network_load)[0];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="National command center"
        title="Dashboard National"
        description="Vision consolidee des performances reseau, des zones sous tension et de l'exposition au risque sur l'ensemble des regions tunisiennes."
        actions={
          <button
            className="rounded-2xl border border-border bg-cardAlt/70 px-4 py-3 text-sm text-slate-200 transition hover:border-accent/40 hover:bg-card"
            onClick={() => void refetch()}
            type="button"
          >
            Derniere generation {formatDate(overview.generated_at)}
          </button>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          title="SLA National"
          value={formatPercent(overview.sla_national_percent)}
          subtitle="Niveau global de conformite reseau"
          icon={<Gauge size={20} />}
          tone={overview.sla_national_percent < 60 ? "danger" : "accent"}
        />
        <KpiCard
          title="Latence moyenne"
          value={`${overview.avg_latency_ms.toFixed(1)} ms`}
          subtitle="Moyenne des sessions suivees"
          icon={<Activity size={20} />}
          tone="neutral"
        />
        <KpiCard
          title="Congestion rate"
          value={formatPercent(overview.congestion_rate)}
          subtitle="Niveau de saturation observe"
          icon={<Network size={20} />}
          tone={overview.congestion_rate >= 60 ? "warning" : "accent"}
        />
        <KpiCard
          title="Alertes actives"
          value={formatNumber(overview.active_alerts_count)}
          subtitle="Sessions a prioriser cote NOC"
          icon={<AlertTriangle size={20} />}
          tone={overview.active_alerts_count > 10 ? "danger" : "warning"}
        />
        <KpiCard
          title="Sessions"
          value={formatNumber(overview.sessions_count)}
          subtitle="Sessions reseau suivies"
          icon={<RadioTower size={20} />}
          tone="accent"
        />
        <KpiCard
          title="Anomalies"
          value={formatNumber(overview.anomalies_count)}
          subtitle="Anomalies detectees dans le snapshot courant"
          icon={<ShieldAlert size={20} />}
          tone={overview.anomalies_count > 0 ? "danger" : "neutral"}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <RegionLoadChart data={regions} />
        <TunisiaNetworkMap regions={regions} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Card className="p-5">
          <div className="mb-5">
            <h3 className="text-lg font-semibold text-white">Top regions a risque</h3>
            <p className="text-sm text-mutedText">
              Priorisation operateur combinee entre charge reseau, SLA et volume de sessions a haut
              risque.
            </p>
          </div>

          <div className="space-y-4">
            {topRiskRegions.map((region) => (
              <div key={region.region_id} className="rounded-2xl border border-border bg-cardAlt/70 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm font-medium text-white">{region.name}</div>
                    <div className="mt-1 text-xs text-mutedText">
                      {region.code} · {region.sessions_count} sessions · {region.gnodeb_count} gNodeB
                    </div>
                  </div>
                  <div className="rounded-full border border-border px-3 py-1 text-xs text-slate-200">
                    {region.high_risk_sessions_count} high risk
                  </div>
                </div>
                <div className="mt-4 space-y-2">
                  <div className="flex justify-between text-xs text-mutedText">
                    <span>Load</span>
                    <span>{Math.round(region.network_load)}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5">
                    <div
                      className="h-2 rounded-full bg-gradient-to-r from-orange-400 to-red-500"
                      style={{ width: `${Math.min(region.network_load, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <EmptyState
          title="Evolution SLA nationale en attente"
          description="Cet espace est reserve a une future courbe d'evolution nationale. La mise en page est deja prete pour l'accueillir."
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Card className="p-5">
          <div className="mb-5">
            <h3 className="text-lg font-semibold text-white">Synthese exploitation</h3>
            <p className="text-sm text-mutedText">
              Lecture rapide pour la coordination NOC nationale.
            </p>
          </div>
          <div className="space-y-4 text-sm leading-6 text-slate-200">
            <p>
              La zone actuellement la plus sous pression est <strong>{highestLoadRegion?.name}</strong>,
              avec une charge reseau de {Math.round(highestLoadRegion?.network_load ?? 0)}%.
            </p>
            <p>
              Le niveau SLA le plus bas est observe sur <strong>{lowestSlaRegion?.name}</strong>, avec
              {" "}
              {formatPercent(lowestSlaRegion?.sla_percent ?? 0)}.
            </p>
            <p>
              Les actions a prioriser en V1 consistent a surveiller les regions degradees et a
              cibler d'abord les sessions sous haute pression, en particulier sur Grand Tunis si la
              tendance actuelle se maintient.
            </p>
            <div className="rounded-2xl border border-border bg-cardAlt/70 p-4 text-mutedText">
              {truncateText(
                "Cette synthese est construite a partir des donnees de supervision actuellement disponibles. Elle pourra etre enrichie plus tard par davantage d'indicateurs operationnels.",
                180,
              )}
            </div>
          </div>
        </Card>

        <EmptyState
          title="Distribution nationale des slices en attente"
          description="Cet espace est reserve a une future vue de repartition des slices sans modifier la template actuelle."
        />
      </section>
    </div>
  );
}
