import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Activity, Gauge, Network, Signal, TowerControl, TriangleAlert } from "lucide-react";

import { getNationalDashboard, getRegionalDashboard } from "@/api/dashboardApi";
import { SliceDistributionChart } from "@/components/charts/slice-distribution-chart";
import { SlaTrendChart } from "@/components/charts/sla-trend-chart";
import { PageHeader } from "@/components/layout/page-header";
import { ServiceBadge } from "@/components/status/service-badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatNumber, formatPacketLoss, formatPercent } from "@/lib/format";

function buildRecommendations(load: number, packetLoss: number, highRiskSessions: number) {
  const actions: string[] = [];

  if (load >= 80) {
    actions.push("Reequilibrer la charge inter-gNodeB sur les cellules les plus sollicitees.");
  }
  if (packetLoss >= 1) {
    actions.push("Verifier le transport et la qualite radio sur les sessions sensibles.");
  }
  if (highRiskSessions > 0) {
    actions.push("Prioriser les sessions a haut risque pour investigation operateur.");
  }
  if (!actions.length) {
    actions.push("Maintenir une surveillance standard avec verification du trend sur 7 jours.");
  }

  return actions;
}

export function RegionalDashboardPage() {
  usePageTitle("Dashboard Regional");

  const { user } = useAuth();
  const navigate = useNavigate();
  const params = useParams();

  const nationalQuery = useQuery({
    queryKey: ["dashboard", "national", "regions"],
    queryFn: getNationalDashboard,
  });

  const regionId = useMemo(() => {
    const fromParams = Number(params.regionId);
    if (Number.isFinite(fromParams) && fromParams > 0) {
      return fromParams;
    }

    return nationalQuery.data?.regions[0]?.region_id;
  }, [params.regionId, nationalQuery.data]);

  const regionalQuery = useQuery({
    queryKey: ["dashboard", "region", regionId],
    queryFn: () => getRegionalDashboard(regionId as number),
    enabled: Boolean(regionId),
  });

  if (nationalQuery.isLoading || regionalQuery.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Chargement du dashboard regional...</div>;
  }

  if (nationalQuery.isError || regionalQuery.isError || !regionalQuery.data) {
    return (
      <EmptyState
        title="Region indisponible"
        description="Impossible de charger la vue regionale pour le moment. Tu peux reessayer dans quelques instants."
      />
    );
  }

  const selectedRegion = regionalQuery.data.region;
  const recommendations = buildRecommendations(
    selectedRegion.network_load,
    regionalQuery.data.packet_loss_avg,
    selectedRegion.high_risk_sessions_count,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Regional supervision"
        title={`Dashboard Regional · ${selectedRegion.name}`}
        description="Suivi detaille de la performance locale: charge reseau, SLA, pertes paquet, congestion et aide predictive."
        actions={
          <>
            <div className="rounded-full border border-border px-3 py-2 text-xs text-slate-200">
              <ServiceBadge value={selectedRegion.ric_status} />
            </div>
            <Select
              className="min-w-64"
              value={String(regionId)}
              onChange={(event) => navigate(`/dashboard/region/${event.target.value}`)}
            >
              {nationalQuery.data?.regions.map((region) => (
                <option key={region.region_id} value={region.region_id}>
                  {region.name}
                </option>
              ))}
            </Select>
          </>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          title="SLA regional"
          value={formatPercent(selectedRegion.sla_percent)}
          subtitle="Conformite qualite de service"
          icon={<Gauge size={20} />}
          tone={selectedRegion.sla_percent < 60 ? "danger" : "accent"}
        />
        <KpiCard
          title="Latency moyenne"
          value={`${selectedRegion.avg_latency_ms.toFixed(1)} ms`}
          subtitle="Latence moyenne observee"
          icon={<Signal size={20} />}
          tone="neutral"
        />
        <KpiCard
          title="Packet loss"
          value={formatPacketLoss(regionalQuery.data.packet_loss_avg)}
          subtitle="Moyenne regionale"
          icon={<Activity size={20} />}
          tone={regionalQuery.data.packet_loss_avg >= 1 ? "warning" : "neutral"}
        />
        <KpiCard
          title="Charge reseau"
          value={formatPercent(selectedRegion.network_load)}
          subtitle="Volume actuel de la region"
          icon={<Network size={20} />}
          tone={selectedRegion.network_load >= 80 ? "danger" : "warning"}
        />
        <KpiCard
          title="gNodeB"
          value={formatNumber(regionalQuery.data.gnodeb_count)}
          subtitle="Sites radio suivis"
          icon={<TowerControl size={20} />}
          tone="accent"
        />
        <KpiCard
          title="Sessions high risk"
          value={formatNumber(selectedRegion.high_risk_sessions_count)}
          subtitle="Sessions a traiter rapidement"
          icon={<TriangleAlert size={20} />}
          tone={selectedRegion.high_risk_sessions_count > 0 ? "danger" : "neutral"}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <SlaTrendChart
          data={regionalQuery.data.trend}
          title="Tendance regionale"
          description="Evolution combinee du SLA et de la congestion sur les derniers snapshots."
          lines={[
            { dataKey: "sla_percent", color: "#4ec3ff", label: "SLA" },
            { dataKey: "congestion_rate", color: "#f97316", label: "Congestion" },
          ]}
        />
        <SliceDistributionChart
          data={regionalQuery.data.slice_distribution}
          title="Distribution des slices"
          description="Repartition locale des sessions par type de slice reseau."
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_0.95fr]">
        <Card className="p-5">
          <div className="mb-5">
            <h3 className="text-lg font-semibold text-white">Activite IA et recommandations</h3>
            <p className="text-sm text-mutedText">
              Suggestions derivées des KPI actuellement exposes par les services existants.
            </p>
          </div>
          <div className="space-y-3">
            {recommendations.map((item) => (
              <div key={item} className="rounded-2xl border border-border bg-cardAlt/70 px-4 py-4 text-sm text-slate-200">
                {item}
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <div className="mb-5">
            <h3 className="text-lg font-semibold text-white">Snapshot exploitation</h3>
            <p className="text-sm text-mutedText">Lecture metier rapide pour la coordination terrain.</p>
          </div>
          <div className="space-y-4 text-sm text-slate-200">
            <div className="flex items-center justify-between rounded-2xl border border-border bg-cardAlt/70 px-4 py-3">
              <span>Sessions surveillees</span>
              <span>{formatNumber(selectedRegion.sessions_count)}</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border border-border bg-cardAlt/70 px-4 py-3">
              <span>Congestion rate</span>
              <span>{formatPercent(selectedRegion.congestion_rate)}</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border border-border bg-cardAlt/70 px-4 py-3">
              <span>Anomalies</span>
              <span>{formatNumber(selectedRegion.anomalies_count)}</span>
            </div>
            {user?.role !== "NETWORK_MANAGER" ? (
              <button
                className="w-full rounded-2xl border border-accent/30 bg-accentSoft px-4 py-3 text-sm font-medium text-accent transition hover:bg-accent hover:text-slate-950"
                onClick={() => navigate(`/sessions?region=${selectedRegion.code}`)}
                type="button"
              >
                Ouvrir les sessions de la region
              </button>
            ) : null}
          </div>
        </Card>
      </section>
    </div>
  );
}
