import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Filter, Radar, ShieldAlert, Waves } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { getNationalDashboard } from "@/api/dashboardApi";
import { getSessions } from "@/api/sessionApi";
import { SearchInput } from "@/components/filters/search-input";
import { PageHeader } from "@/components/layout/page-header";
import { SessionDetailDrawer } from "@/components/layout/session-detail-drawer";
import { SessionsTable } from "@/components/tables/sessions-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { Select } from "@/components/ui/select";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatNumber } from "@/lib/format";
import type { RiskLevel, SliceType } from "@/types/shared";

export function SessionsMonitorPage() {
  usePageTitle("Sessions Monitor");

  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [region, setRegion] = useState(searchParams.get("region") ?? "");
  const [risk, setRisk] = useState<"" | RiskLevel>("");
  const [slice, setSlice] = useState<"" | SliceType>("");
  const [inspectedSessionId, setInspectedSessionId] = useState<number | null>(null);

  const regionsQuery = useQuery({
    queryKey: ["dashboard", "national", "region-list"],
    queryFn: getNationalDashboard,
  });

  const sessionsQuery = useQuery({
    queryKey: ["sessions", { page, region, risk, slice }],
    queryFn: () =>
      getSessions({
        page,
        pageSize: 20,
        region: region || undefined,
        risk: risk || undefined,
        slice: slice || undefined,
      }),
  });

  useEffect(() => {
    setPage(1);
  }, [region, risk, slice]);

  const filteredSessions = useMemo(() => {
    const items = sessionsQuery.data?.items ?? [];
    const normalized = search.trim().toLowerCase();
    if (!normalized) return items;

    return items.filter((item) => {
      return (
        item.session_code.toLowerCase().includes(normalized) ||
        item.region.name.toLowerCase().includes(normalized) ||
        item.region.code.toLowerCase().includes(normalized)
      );
    });
  }, [sessionsQuery.data?.items, search]);

  const stats = useMemo(() => {
    const items = filteredSessions;
    const highRisk = items.filter((item) => {
      return item.prediction?.risk_level === "HIGH" || item.prediction?.risk_level === "CRITICAL";
    }).length;
    const avgLatency =
      items.reduce((sum, item) => sum + item.latency_ms, 0) / (items.length || 1);
    const coveredRegions = new Set(items.map((item) => item.region.code)).size;

    return {
      itemsCount: items.length,
      highRisk,
      avgLatency,
      coveredRegions,
    };
  }, [filteredSessions]);

  if (sessionsQuery.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Loading sessions...</div>;
  }

  if (sessionsQuery.isError) {
    return (
      <EmptyState
        title="Sessions unavailable"
        description="Unable to retrieve the sessions list from session-service."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operational sessions"
        title="Sessions Monitor"
        description="Operational monitoring of network sessions, with filters by region, slice, and risk level, plus on-demand operator details."
        actions={
          <>
            <SearchInput
              placeholder="Search for a session or region..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <Select value={region} onChange={(event) => setRegion(event.target.value)}>
              <option value="">All regions</option>
              {regionsQuery.data?.regions.map((item) => (
                <option key={item.region_id} value={item.code}>
                  {item.name}
                </option>
              ))}
            </Select>
            <Select value={risk} onChange={(event) => setRisk(event.target.value as "" | RiskLevel)}>
              <option value="">All risks</option>
              <option value="LOW">LOW</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="HIGH">HIGH</option>
              <option value="CRITICAL">CRITICAL</option>
            </Select>
            <Select value={slice} onChange={(event) => setSlice(event.target.value as "" | SliceType)}>
              <option value="">All slices</option>
              <option value="eMBB">eMBB</option>
              <option value="URLLC">URLLC</option>
              <option value="mMTC">mMTC</option>
              <option value="ERLLC">ERLLC</option>
              <option value="feMBB">feMBB</option>
              <option value="umMTC">umMTC</option>
              <option value="MBRLLC">MBRLLC</option>
              <option value="mURLLC">mURLLC</option>
            </Select>
          </>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Displayed sessions"
          value={formatNumber(stats.itemsCount)}
          subtitle="Current result after filters"
          icon={<Radar size={20} />}
          tone="accent"
        />
        <KpiCard
          title="High risk"
          value={formatNumber(stats.highRisk)}
          subtitle="Sessions to escalate quickly"
          icon={<ShieldAlert size={20} />}
          tone={stats.highRisk > 0 ? "danger" : "neutral"}
        />
        <KpiCard
          title="Average latency"
          value={`${stats.avgLatency.toFixed(1)} ms`}
          subtitle="On the current page"
          icon={<Waves size={20} />}
          tone="neutral"
        />
        <KpiCard
          title="Covered regions"
          value={formatNumber(stats.coveredRegions)}
          subtitle="Presence in the filtered snapshot"
          icon={<Filter size={20} />}
          tone="accent"
        />
      </section>

      {filteredSessions.length ? (
        <>
          <SessionsTable sessions={filteredSessions} onInspect={(sessionId) => setInspectedSessionId(sessionId)} />

          <Card className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
            <div className="text-sm text-mutedText">
              Page {sessionsQuery.data?.pagination.page} / {sessionsQuery.data?.pagination.total_pages} ·
              {" "}
              {formatNumber(sessionsQuery.data?.pagination.total ?? 0)} total sessions
            </div>
            <div className="flex gap-3">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={page >= (sessionsQuery.data?.pagination.total_pages ?? 1)}
                onClick={() => setPage((value) => value + 1)}
              >
                Next
              </Button>
            </div>
          </Card>
        </>
      ) : (
        <EmptyState
          title="No session"
          description="No session matches the selected filters or the current local search."
        />
      )}

      <SessionDetailDrawer
        sessionId={inspectedSessionId}
        open={inspectedSessionId !== null}
        onClose={() => setInspectedSessionId(null)}
      />
    </div>
  );
}
