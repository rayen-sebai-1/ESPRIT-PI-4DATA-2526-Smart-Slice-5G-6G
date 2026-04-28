import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Loader2, RefreshCcw } from "lucide-react";

import { getNetworkLogs, type LogsQueryParams, type NetworkLogEvent } from "@/api/logsApi";
import { LogDetailDrawer } from "@/components/logs/log-detail-drawer";
import { LogFiltersBar } from "@/components/logs/log-filters-bar";
import { LogRow } from "@/components/logs/log-row";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/cn";

interface NetworkLogsFeedProps {
  scope: "national" | "regional";
  regionId?: number;
  defaultFilters?: Partial<LogsQueryParams>;
  compact?: boolean;
}

export function NetworkLogsFeed({ scope, regionId, defaultFilters, compact }: NetworkLogsFeedProps) {
  const [filters, setFilters] = useState<LogsQueryParams>({
    start: "-15m",
    min_severity: 0,
    limit: compact ? 100 : 200,
    ...defaultFilters,
  });
  const [olderEvents, setOlderEvents] = useState<NetworkLogEvent[]>([]);
  const [olderCursor, setOlderCursor] = useState<string | null | undefined>(undefined);
  const [isLoadingOlder, setIsLoadingOlder] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<NetworkLogEvent | null>(null);

  const baseParams = useMemo<LogsQueryParams>(
    () => ({
      ...filters,
      scope,
      region_id: scope === "regional" ? regionId : undefined,
      limit: compact ? 100 : filters.limit ?? 200,
    }),
    [compact, filters, regionId, scope],
  );

  const filterSignature = JSON.stringify(baseParams);

  useEffect(() => {
    setOlderEvents([]);
    setOlderCursor(undefined);
  }, [filterSignature]);

  const logsQuery = useQuery({
    queryKey: ["network-logs", baseParams],
    queryFn: () => getNetworkLogs(baseParams),
    enabled: scope === "national" || Boolean(regionId),
    refetchInterval: 5000,
  });

  const events = useMemo(() => {
    const seen = new Set<string>();
    return [...(logsQuery.data?.events ?? []), ...olderEvents].filter((event) => {
      if (seen.has(event.id)) return false;
      seen.add(event.id);
      return true;
    });
  }, [logsQuery.data?.events, olderEvents]);

  const nextCursor = olderCursor === undefined ? logsQuery.data?.next_cursor ?? null : olderCursor;

  async function loadOlder() {
    if (!nextCursor || isLoadingOlder) return;
    setIsLoadingOlder(true);
    try {
      const response = await getNetworkLogs({ ...baseParams, cursor: nextCursor });
      setOlderEvents((current) => [...current, ...response.events]);
      setOlderCursor(response.next_cursor);
    } finally {
      setIsLoadingOlder(false);
    }
  }

  return (
    <>
      <Card className={cn("p-0", compact ? "min-h-[420px]" : "min-h-[520px]")}>
        <div className="border-b border-border p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">
                {scope === "regional" ? "Logs reseau regional" : "Logs reseau national"}
              </h3>
              <p className="mt-1 text-sm text-mutedText">
                Evenements live derives des mesures InfluxDB faults, telemetry et AIOps.
              </p>
            </div>
            <Button
              size="sm"
              variant="secondary"
              type="button"
              onClick={() => void logsQuery.refetch()}
              disabled={logsQuery.isFetching}
            >
              {logsQuery.isFetching ? <Loader2 className="animate-spin" size={15} /> : <RefreshCcw size={15} />}
              Refresh
            </Button>
          </div>
          <div className="mt-4">
            <LogFiltersBar filters={filters} compact={compact} onChange={setFilters} />
          </div>
        </div>

        {logsQuery.isLoading ? (
          <div className="space-y-3 p-5">
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="h-20 animate-pulse rounded-2xl border border-border bg-cardAlt/60" />
            ))}
          </div>
        ) : logsQuery.isError ? (
          <div className="p-5">
            <EmptyState
              title="Logs reseau indisponibles"
              description="Le BFF n'a pas pu lire les mesures InfluxDB pour le moment."
            />
          </div>
        ) : events.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="Aucun evenement reseau"
              description="Aucun fault, breach KPI ou signal AIOps ne correspond aux filtres actifs."
            />
          </div>
        ) : (
          <div>
            <div className="flex items-center justify-between px-5 py-3 text-xs text-mutedText">
              <span>{events.length} evenements affiches</span>
              <span>{logsQuery.data?.window.start ?? filters.start} vers now()</span>
            </div>
            <div>
              {events.map((event) => (
                <LogRow key={event.id} event={event} onOpen={setSelectedEvent} />
              ))}
            </div>
            <div className="flex items-center justify-between border-t border-border p-4">
              <div className="inline-flex items-center gap-2 text-xs text-mutedText">
                <AlertCircle size={14} />
                Production path: InfluxDB via BFF
              </div>
              <Button
                size="sm"
                variant="secondary"
                type="button"
                onClick={() => void loadOlder()}
                disabled={!nextCursor || isLoadingOlder}
              >
                {isLoadingOlder ? <Loader2 className="animate-spin" size={15} /> : null}
                Load older
              </Button>
            </div>
          </div>
        )}
      </Card>

      <LogDetailDrawer event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </>
  );
}
