import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Gauge,
  Network,
  RadioTower,
  ShieldAlert,
} from "lucide-react";

import { getNationalDashboard, getNationalSlaTrend, getNationalSliceDistribution } from "@/api/dashboardApi";
import { liveApi } from "@/api/liveApi";
import { RegionLoadChart } from "@/components/charts/region-load-chart";
import { SlaTrendChart } from "@/components/charts/sla-trend-chart";
import { SliceDistributionChart } from "@/components/charts/slice-distribution-chart";
import { NetworkLogsFeed } from "@/components/logs/network-logs-feed";
import { PageHeader } from "@/components/layout/page-header";
import { TunisiaNetworkMap } from "@/components/layout/tunisia-network-map";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatDate, formatNumber, formatPercent, truncateText } from "@/lib/format";

interface LiveEntity {
  entityId?: string;
  entityType?: string;
  domain?: string;
  sliceId?: string;
  sliceType?: string;
  healthScore?: number;
  congestionScore?: number;
  severity?: string | number;
  kpis?: Record<string, unknown> | string;
  lastUpdated?: string;
  timestamp?: string;
  [key: string]: unknown;
}

function asNumber(value: unknown, fallback = 0) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function parseKpis(raw: LiveEntity["kpis"]) {
  if (!raw) return {};
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return typeof parsed === "object" && parsed !== null ? parsed as Record<string, unknown> : {};
    } catch {
      return {};
    }
  }
  return raw;
}

function severityWeight(value: unknown) {
  const text = String(value ?? "").toLowerCase();
  if (text === "critical") return 35;
  if (text === "high") return 28;
  if (text === "medium") return 18;
  if (text === "low") return 8;
  return asNumber(value) * 10;
}

function healthTone(value: number) {
  if (value < 60) return "danger";
  if (value < 80) return "warning";
  return "accent";
}

function riskTone(value: number) {
  if (value >= 80) return "danger";
  if (value >= 60) return "warning";
  return "accent";
}

export function NationalDashboardPage() {
  usePageTitle("National Dashboard");
  const navigate = useNavigate();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["dashboard", "national"],
    queryFn: getNationalDashboard,
    staleTime: 60_000,
  });

  const liveOverviewQuery = useQuery({
    queryKey: ["live", "overview", "national-dashboard"],
    queryFn: liveApi.getOverview,
    refetchInterval: 3000,
  });

  const liveEntitiesQuery = useQuery({
    queryKey: ["live", "entities", "national-dashboard"],
    queryFn: () => liveApi.getEntities(500),
    refetchInterval: 3000,
  });

  const liveEntities = useMemo<LiveEntity[]>(() => {
    return (liveEntitiesQuery.data?.items ?? []).filter((item: LiveEntity) => Boolean(item.entityId));
  }, [liveEntitiesQuery.data?.items]);

  const liveNetworkStats = useMemo(() => {
    const healthValues = liveEntities.map((item) => asNumber(item.healthScore, 1));
    const congestionValues = liveEntities.map((item) => asNumber(item.congestionScore, 0));
    const average = (items: number[]) => items.length
      ? items.reduce((sum, item) => sum + item, 0) / items.length
      : 0;

    return {
      healthPercent: average(healthValues) * 100,
      congestionPercent: average(congestionValues) * 100,
      degradedEntities: liveEntities.filter((item) => asNumber(item.healthScore, 1) < 0.6).length,
    };
  }, [liveEntities]);

  const topRiskEntities = useMemo(() => {
    return liveEntities
      .map((entity) => {
        const kpis = parseKpis(entity.kpis);
        const health = asNumber(entity.healthScore, 1);
        const congestion = asNumber(entity.congestionScore, 0);
        const packetLoss = asNumber(kpis.packetLossPct);
        const rbUtilization = asNumber(kpis.rbUtilizationPct);
        const latency = asNumber(kpis.latencyMs ?? kpis.forwardingLatencyMs);
        const riskScore = Math.round(
          Math.max(0, 1 - health) * 100
          + congestion * 80
          + packetLoss * 8
          + Math.max(0, rbUtilization - 80) * 1.5
          + Math.max(0, latency - 20) * 1.2
          + severityWeight(entity.severity),
        );
        const reasons = [
          health < 0.6 ? `health ${formatPercent(health * 100, 0)}` : null,
          congestion > 0.7 ? `congestion ${formatPercent(congestion * 100, 0)}` : null,
          packetLoss >= 1 ? `loss ${packetLoss.toFixed(2)}%` : null,
          rbUtilization >= 90 ? `RB ${formatPercent(rbUtilization, 0)}` : null,
          latency >= 30 ? `${latency.toFixed(1)} ms` : null,
        ].filter((item): item is string => Boolean(item));

        return { entity, health, congestion, packetLoss, rbUtilization, latency, riskScore, reasons };
      })
      .sort((left, right) => right.riskScore - left.riskScore)
      .slice(0, 5);
  }, [liveEntities]);

  const slaTrendQuery = useQuery({
    queryKey: ["dashboard", "national", "sla-trend"],
    queryFn: getNationalSlaTrend,
    staleTime: 60_000,
    retry: false,
  });

  const sliceDistributionQuery = useQuery({
    queryKey: ["dashboard", "national", "slice-distribution"],
    queryFn: getNationalSliceDistribution,
    staleTime: 60_000,
    retry: false,
  });

  if (isLoading) {
    return <div className="py-10 text-sm text-mutedText">Loading national dashboard...</div>;
  }

  if (isError || !data) {
    return (
      <EmptyState
        title="Dashboard unavailable"
        description="Dashboard data is currently unavailable. You can refresh the page."
      />
    );
  }

  const { overview, regions } = data;
  const liveOverview = liveOverviewQuery.data;
  const networkHealth = liveNetworkStats.healthPercent || overview.sla_national_percent;
  const networkCongestion = liveNetworkStats.congestionPercent || overview.congestion_rate;
  const activeFaults = liveOverview?.active_faults_count ?? overview.active_alerts_count;
  const liveAiopsAlerts = (liveOverview?.congestion_alerts_count ?? 0)
    + (liveOverview?.sla_risk_count ?? 0)
    + (liveOverview?.slice_mismatch_count ?? 0);
  const mostRiskyEntity = topRiskEntities[0];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Network operations center"
        title="National Dashboard"
        description="Real-time supervision of overall network state: degraded entities, active faults, congestion, SLA, and AIOps signals."
        actions={
          <button
            className="rounded-2xl border border-border bg-cardAlt/70 px-4 py-3 text-sm text-slate-200 transition hover:border-accent/40 hover:bg-card"
            onClick={() => void refetch()}
            type="button"
          >
            Latest generation {formatDate(overview.generated_at)}
          </button>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          title="Network health"
          value={formatPercent(networkHealth)}
          subtitle="Live average health scores"
          icon={<Gauge size={20} />}
          tone={healthTone(networkHealth)}
        />
        <KpiCard
          title="Average latency"
          value={`${overview.avg_latency_ms.toFixed(1)} ms`}
          subtitle="End-to-end performance signal"
          icon={<Activity size={20} />}
          tone="neutral"
        />
        <KpiCard
          title="Network congestion"
          value={formatPercent(networkCongestion)}
          subtitle="Live average congestion scores"
          icon={<Network size={20} />}
          tone={riskTone(networkCongestion)}
        />
        <KpiCard
          title="Active faults"
          value={formatNumber(activeFaults)}
          subtitle="Open incidents on the network"
          icon={<AlertTriangle size={20} />}
          tone={activeFaults > 0 ? "warning" : "neutral"}
        />
        <KpiCard
          title="Live entities"
          value={formatNumber(liveOverview?.total_entities ?? liveEntities.length ?? overview.sessions_count)}
          subtitle={`${formatNumber(liveNetworkStats.degradedEntities)} degraded entities`}
          icon={<RadioTower size={20} />}
          tone="accent"
        />
        <KpiCard
          title="AIOps alerts"
          value={formatNumber(liveAiopsAlerts || overview.anomalies_count)}
          subtitle="Congestion, SLA risk, and mismatch"
          icon={<ShieldAlert size={20} />}
          tone={(liveAiopsAlerts || overview.anomalies_count) > 0 ? "danger" : "neutral"}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <RegionLoadChart data={regions} />
        <TunisiaNetworkMap regions={regions} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Card className="p-5">
          <div className="mb-5">
            <h3 className="text-lg font-semibold text-white">Top at-risk entities</h3>
            <p className="text-sm text-mutedText">
              Entities with the most problematic signals: low health, congestion,
              packet loss, radio utilization, or latency.
            </p>
          </div>

          <div className="space-y-4">
            {topRiskEntities.map(({ entity, health, congestion, riskScore, reasons }) => (
              <button
                key={entity.entityId}
                className="w-full rounded-2xl border border-border bg-cardAlt/70 p-4 text-left transition hover:border-accent/40 hover:bg-card"
                type="button"
                onClick={() => navigate(`/dashboard/region/${encodeURIComponent(entity.entityId ?? "")}`)}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm font-medium text-white">{entity.entityId}</div>
                    <div className="mt-1 text-xs text-mutedText">
                      {entity.domain ?? "unknown"} - {entity.entityType ?? "unknown"}
                      {entity.sliceType ? ` - ${entity.sliceType}` : ""}
                    </div>
                  </div>
                  <div className="rounded-full border border-border px-3 py-1 text-xs text-slate-200">
                    risk {riskScore}
                  </div>
                </div>
                <div className="mt-4 space-y-2">
                  <div className="flex justify-between text-xs text-mutedText">
                    <span>Health</span>
                    <span>{formatPercent(health * 100, 0)}</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5">
                    <div
                      className="h-2 rounded-full bg-gradient-to-r from-emerald-400 to-sky-400"
                      style={{ width: `${Math.min(Math.max(health * 100, 0), 100)}%` }}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2 pt-1 text-xs text-mutedText">
                    <span>Congestion {formatPercent(congestion * 100, 0)}</span>
                    {reasons.length
                      ? reasons.map((reason) => <span key={reason}>{reason}</span>)
                      : <span>standard monitoring</span>}
                  </div>
                </div>
              </button>
            ))}
            {!topRiskEntities.length ? (
              <div className="rounded-2xl border border-border bg-cardAlt/70 p-4 text-sm text-mutedText">
                No live entity available for ranking. The dashboard remains available with
                existing national indicators.
              </div>
            ) : null}
          </div>
        </Card>

        <SlaTrendChart
          data={slaTrendQuery.data ?? []}
          title="National SLA trend"
          description="Awaiting metrics aggregation — the /metrics/sla-trend endpoint will populate this chart once the aggregation pipeline is active."
          lines={[
            { dataKey: "sla_percent", color: "#4ec3ff", label: "SLA %" },
            { dataKey: "congestion_rate", color: "#f59e0b", label: "Congestion %" },
          ]}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Card className="p-5">
          <div className="mb-5">
            <h3 className="text-lg font-semibold text-white">Operations summary</h3>
            <p className="text-sm text-mutedText">
              Quick read for national NOC coordination.
            </p>
          </div>
          <div className="space-y-4 text-sm leading-6 text-slate-200">
            <p>
              The currently highest-priority entity is{" "}
              <strong>{mostRiskyEntity?.entity.entityId ?? "N/A"}</strong>, with a risk score of{" "}
              {mostRiskyEntity?.riskScore ?? 0}.
            </p>
            <p>
              The network has {formatNumber(activeFaults)} active fault(s) and{" "}
              {formatNumber(liveNetworkStats.degradedEntities)} entity(s) under critical health score.
            </p>
            <p>
              Priority actions for the NOC are to open the most degraded entities,
              verify related KPIs, then correlate events in the national network feed.
            </p>
            <div className="rounded-2xl border border-border bg-cardAlt/70 p-4 text-mutedText">
              {truncateText(
                "This summary combines existing dashboard data with Redis live state and InfluxDB events to provide an overall operator view.",
                180,
              )}
            </div>
          </div>
        </Card>

        <SliceDistributionChart
          data={sliceDistributionQuery.data ?? []}
          title="Slice distribution"
          description="Awaiting metrics aggregation — the /metrics/slice-distribution endpoint will populate this chart once the aggregation pipeline is active."
        />
      </section>

      <section className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Network logs (national)</h3>
          <p className="text-sm text-mutedText">
            Live timeline of faults, KPI breaches, and AIOps predictions derived from InfluxDB.
          </p>
        </div>
        <NetworkLogsFeed scope="national" />
      </section>
    </div>
  );
}
