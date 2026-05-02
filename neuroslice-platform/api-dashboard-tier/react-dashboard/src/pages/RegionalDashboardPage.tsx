import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  Gauge,
  HeartPulse,
  Network,
  Search,
  ShieldAlert,
} from "lucide-react";

import { liveApi } from "@/api/liveApi";
import { NetworkLogsFeed } from "@/components/logs/network-logs-feed";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
import { Select } from "@/components/ui/select";
import { usePageTitle } from "@/hooks/usePageTitle";
import { cn } from "@/lib/cn";
import { formatDate, formatNumber, formatPacketLoss, formatPercent } from "@/lib/format";

interface LiveEntity {
  entityId?: string;
  entityType?: string;
  domain?: string;
  siteId?: string;
  sliceId?: string;
  sliceType?: string;
  healthScore?: number;
  congestionScore?: number;
  misroutingScore?: number;
  severity?: string | number;
  kpis?: Record<string, unknown> | string;
  lastUpdated?: string;
  timestamp?: string;
  [key: string]: unknown;
}

const domainLabels: Record<string, string> = {
  core: "Core",
  edge: "Edge",
  ran: "RAN",
};

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

function percentFromScore(value: unknown) {
  return Math.round(asNumber(value, 0) * 1000) / 10;
}

function entityLabel(entity?: LiveEntity | null) {
  if (!entity) return "Entity dashboard";
  return `${entity.entityId ?? "unknown"}${entity.entityType ? ` - ${entity.entityType}` : ""}`;
}

function healthTone(value: number) {
  if (value < 60) return "danger";
  if (value < 80) return "warning";
  return "accent";
}

function riskTone(value: number) {
  if (value >= 80) return "danger";
  if (value >= 60) return "warning";
  return "neutral";
}

export function RegionalDashboardPage() {
  usePageTitle("Entity Dashboard");

  const navigate = useNavigate();
  const params = useParams();
  const routeEntityId = params.regionId ? decodeURIComponent(params.regionId) : "";
  const [selectedEntityId, setSelectedEntityId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [domainFilter, setDomainFilter] = useState("");

  const entitiesQuery = useQuery({
    queryKey: ["live", "entities", "entity-dashboard"],
    queryFn: () => liveApi.getEntities(500),
    refetchInterval: 3000,
  });

  const entities = useMemo<LiveEntity[]>(() => {
    return (entitiesQuery.data?.items ?? []).filter((item: LiveEntity) => Boolean(item.entityId));
  }, [entitiesQuery.data?.items]);

  useEffect(() => {
    if (!entities.length) return;
    const routeMatch = entities.find((item) => item.entityId === routeEntityId);
    const currentStillExists = entities.some((item) => item.entityId === selectedEntityId);
    if (routeMatch && selectedEntityId !== routeMatch.entityId) {
      setSelectedEntityId(routeMatch.entityId ?? "");
      return;
    }
    if (!selectedEntityId || !currentStillExists) {
      setSelectedEntityId(entities[0].entityId ?? "");
    }
  }, [entities, routeEntityId, selectedEntityId]);

  const entityQuery = useQuery({
    queryKey: ["live", "entity-dashboard", selectedEntityId],
    queryFn: () => liveApi.getEntity(selectedEntityId),
    enabled: Boolean(selectedEntityId),
    refetchInterval: 3000,
  });

  const aiopsQuery = useQuery({
    queryKey: ["live", "entity-dashboard", "aiops", selectedEntityId],
    queryFn: () => liveApi.getEntityAiops(selectedEntityId),
    enabled: Boolean(selectedEntityId),
    refetchInterval: 3000,
  });

  const selectedEntity = (entityQuery.data as LiveEntity | undefined)
    ?? entities.find((item) => item.entityId === selectedEntityId)
    ?? null;

  const kpis = parseKpis(selectedEntity?.kpis);
  const filteredEntities = entities.filter((item) => {
    const term = search.trim().toLowerCase();
    const matchesSearch = !term
      || String(item.entityId ?? "").toLowerCase().includes(term)
      || String(item.entityType ?? "").toLowerCase().includes(term)
      || String(item.sliceId ?? "").toLowerCase().includes(term);
    const matchesDomain = !domainFilter || item.domain === domainFilter;
    return matchesSearch && matchesDomain;
  });

  const healthPercent = percentFromScore(selectedEntity?.healthScore);
  const congestionPercent = percentFromScore(selectedEntity?.congestionScore);
  const packetLoss = asNumber(kpis.packetLossPct);
  const latency = asNumber(kpis.latencyMs ?? kpis.forwardingLatencyMs);
  const throughput = asNumber(kpis.dlThroughputMbps ?? kpis.throughputMbps);
  const utilization = asNumber(kpis.rbUtilizationPct ?? kpis.cpuUtilPct ?? kpis.queueDepthPct);

  if (entitiesQuery.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Loading entity dashboard...</div>;
  }

  if (entitiesQuery.isError) {
    return (
      <EmptyState
        title="Live entities unavailable"
        description="The live state BFF is not accessible at the moment. Check api-bff-service and Redis."
      />
    );
  }

  if (!entities.length) {
    return (
      <EmptyState
        title="No live entity"
        description="No entity is currently exposed in live state. Start the simulators, then reload this page."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Entity supervision"
        title={`Entity Dashboard - ${entityLabel(selectedEntity)}`}
        description="Operational view by network entity: live KPIs, AIOps states, and filtered InfluxDB logs."
        actions={
          <Select
            className="min-w-72"
            value={selectedEntityId}
            onChange={(event) => {
              const nextEntityId = event.target.value;
              setSelectedEntityId(nextEntityId);
              navigate(`/dashboard/region/${encodeURIComponent(nextEntityId)}`);
            }}
          >
            {entities.map((entity) => (
              <option key={entity.entityId} value={entity.entityId}>
                {entity.entityId} - {domainLabels[String(entity.domain)] ?? entity.domain ?? "unknown"}
              </option>
            ))}
          </Select>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Health score"
          value={formatPercent(healthPercent)}
          subtitle="State derived from the normalizer"
          icon={<HeartPulse size={20} />}
          tone={healthTone(healthPercent)}
        />
        <KpiCard
          title="Congestion"
          value={formatPercent(congestionPercent)}
          subtitle="Live-derived score"
          icon={<Network size={20} />}
          tone={riskTone(congestionPercent)}
        />
        <KpiCard
          title="Packet loss"
          value={formatPacketLoss(packetLoss)}
          subtitle="Telemetry KPI"
          icon={<AlertTriangle size={20} />}
          tone={packetLoss >= 1 ? "warning" : "neutral"}
        />
        <KpiCard
          title="Latency"
          value={`${latency.toFixed(1)} ms`}
          subtitle="latencyMs / forwardingLatencyMs"
          icon={<Gauge size={20} />}
          tone={latency >= 30 ? "danger" : latency >= 15 ? "warning" : "neutral"}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="overflow-hidden">
          <div className="border-b border-border p-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Network entities</h3>
                <p className="text-sm text-mutedText">{formatNumber(filteredEntities.length)} displayed entities</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-[1fr_150px]">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-mutedText" />
                  <Input
                    className="pl-9"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search entity"
                  />
                </div>
                <Select value={domainFilter} onChange={(event) => setDomainFilter(event.target.value)}>
                  <option value="">All domains</option>
                  <option value="core">Core</option>
                  <option value="edge">Edge</option>
                  <option value="ran">RAN</option>
                </Select>
              </div>
            </div>
          </div>
          <div className="max-h-[520px] overflow-auto">
            {filteredEntities.map((entity) => {
              const active = entity.entityId === selectedEntityId;
              return (
                <button
                  key={entity.entityId}
                  className={cn(
                    "grid w-full gap-3 border-t border-border/70 px-5 py-4 text-left transition hover:bg-white/[0.03] md:grid-cols-[1fr_auto]",
                    active && "bg-accentSoft/50",
                  )}
                  type="button"
                  onClick={() => {
                    const nextEntityId = entity.entityId ?? "";
                    setSelectedEntityId(nextEntityId);
                    navigate(`/dashboard/region/${encodeURIComponent(nextEntityId)}`);
                  }}
                >
                  <div>
                    <div className="font-medium text-white">{entity.entityId}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-mutedText">
                      <span>{entity.entityType ?? "unknown"}</span>
                      <span>{domainLabels[String(entity.domain)] ?? entity.domain ?? "unknown"}</span>
                      {entity.sliceType ? <span>{entity.sliceType}</span> : null}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="rounded-full border border-border px-2 py-1 text-mutedText">
                      H {formatPercent(percentFromScore(entity.healthScore), 0)}
                    </span>
                    <span className="rounded-full border border-border px-2 py-1 text-mutedText">
                      C {formatPercent(percentFromScore(entity.congestionScore), 0)}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </Card>

        <Card className="p-5">
          <div className="mb-5">
            <h3 className="text-lg font-semibold text-white">Snapshot live</h3>
            <p className="text-sm text-mutedText">
              Latest update {formatDate(selectedEntity?.lastUpdated ?? selectedEntity?.timestamp ?? null)}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Detail label="Entity ID" value={selectedEntity?.entityId ?? "N/A"} />
            <Detail label="Entity type" value={selectedEntity?.entityType ?? "N/A"} />
            <Detail label="Domain" value={domainLabels[String(selectedEntity?.domain)] ?? selectedEntity?.domain ?? "N/A"} />
            <Detail label="Site" value={selectedEntity?.siteId ?? "N/A"} />
            <Detail label="Slice ID" value={selectedEntity?.sliceId ?? "N/A"} />
            <Detail label="Slice type" value={selectedEntity?.sliceType ?? "N/A"} />
            <Detail label="Throughput" value={`${throughput.toFixed(1)} Mbps`} />
            <Detail label="Utilization" value={formatPercent(utilization)} />
          </div>

          <div className="mt-5 grid gap-3 lg:grid-cols-3">
            <AiopsPanel
              title="Congestion"
              icon={<Activity size={18} />}
              data={aiopsQuery.data?.congestion}
              scoreKey="score"
            />
            <AiopsPanel
              title="SLA assurance"
              icon={<ShieldAlert size={18} />}
              data={aiopsQuery.data?.sla}
              scoreKey="score"
            />
            <AiopsPanel
              title="Slice classifier"
              icon={<BrainCircuit size={18} />}
              data={aiopsQuery.data?.slice_classification}
              scoreKey="confidence"
            />
          </div>
        </Card>
      </section>

      <section className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Network logs - {selectedEntity?.entityId}</h3>
          <p className="text-sm text-mutedText">
            Live feed filtered server-side on the selected entity.
          </p>
        </div>
        <NetworkLogsFeed
          key={selectedEntityId}
          scope="national"
          defaultFilters={{ entity_id: selectedEntityId, start: "-15m" }}
        />
      </section>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-cardAlt/70 px-4 py-3">
      <div className="text-xs text-mutedText">{label}</div>
      <div className="mt-1 break-words text-sm font-medium text-white">{value}</div>
    </div>
  );
}

function AiopsPanel({
  title,
  icon,
  data,
  scoreKey,
}: {
  title: string;
  icon: ReactNode;
  data: any;
  scoreKey: "score" | "confidence";
}) {
  const severity = asNumber(data?.severity, 0);
  return (
    <div className="rounded-2xl border border-border bg-cardAlt/70 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
        {icon}
        {title}
      </div>
      {data ? (
        <div className="space-y-2 text-sm text-mutedText">
          <div className="flex items-center justify-between gap-3">
            <span>Prediction</span>
            <span className="text-right text-white">{data.prediction ?? "unknown"}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span>Score</span>
            <span className="text-white">{asNumber(data?.[scoreKey], 0).toFixed(4)}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span>Severity</span>
            <span className={cn("rounded-full px-2 py-1 text-xs", severity >= 2 ? "bg-red-500/15 text-red-200" : "bg-emerald-500/15 text-emerald-200")}>
              S{severity}
            </span>
          </div>
        </div>
      ) : (
        <div className="text-sm text-mutedText">No live output yet</div>
      )}
    </div>
  );
}
