import { useQuery } from "@tanstack/react-query";
import { Activity, Gauge, ShieldAlert, X } from "lucide-react";

import { getSession } from "@/api/sessionApi";
import { RiskBadge } from "@/components/status/risk-badge";
import { ServiceBadge } from "@/components/status/service-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import {
  formatDate,
  formatLatency,
  formatPacketLoss,
  formatPercent,
  formatThroughput,
} from "@/lib/format";

export function SessionDetailDrawer({
  sessionId,
  open,
  onClose,
}: {
  sessionId: number | null;
  open: boolean;
  onClose: () => void;
}) {
  const sessionQuery = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId as number),
    enabled: open && Boolean(sessionId),
  });

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[60] flex justify-end bg-slate-950/60 backdrop-blur-sm">
      <button aria-label="Close session drawer" className="flex-1" onClick={onClose} />
      <div className="relative h-full w-full max-w-2xl overflow-y-auto border-l border-white/10 bg-surface p-5 shadow-panel">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-mutedText">Session detail</p>
            <h3 className="mt-2 text-2xl font-semibold text-white">Real-time inspection</h3>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X size={18} />
          </Button>
        </div>

        {sessionQuery.isLoading ? (
          <Card className="p-6 text-sm text-mutedText">Loading session details...</Card>
        ) : null}

        {sessionQuery.isError ? (
          <EmptyState
            title="Detail unavailable"
            description="The detail for this session is not available at the moment."
          />
        ) : null}

        {sessionQuery.data ? (
          <div className="space-y-5">
            <Card className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-white">{sessionQuery.data.session_code}</div>
                  <div className="mt-2 text-sm text-mutedText">
                    Last observation {formatDate(sessionQuery.data.timestamp)}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <ServiceBadge value={sessionQuery.data.region.ric_status} />
                  {sessionQuery.data.prediction ? (
                    <RiskBadge value={sessionQuery.data.prediction.risk_level} />
                  ) : null}
                </div>
              </div>
            </Card>

            <div className="grid gap-4 md:grid-cols-2">
              <Card className="p-5">
                <div className="flex items-center gap-3 text-white">
                  <Activity size={18} className="text-accent" />
                  <span className="font-medium">Radio KPI</span>
                </div>
                <div className="mt-4 space-y-3 text-sm text-slate-300">
                  <div className="flex items-center justify-between">
                    <span>Latency</span>
                    <span>{formatLatency(sessionQuery.data.latency_ms)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Packet loss</span>
                    <span>{formatPacketLoss(sessionQuery.data.packet_loss)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Throughput</span>
                    <span>{formatThroughput(sessionQuery.data.throughput_mbps)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Slice source</span>
                    <span>{sessionQuery.data.slice_type}</span>
                  </div>
                </div>
              </Card>

              <Card className="p-5">
                <div className="flex items-center gap-3 text-white">
                  <Gauge size={18} className="text-accent" />
                  <span className="font-medium">Network context</span>
                </div>
                <div className="mt-4 space-y-3 text-sm text-slate-300">
                  <div className="flex items-center justify-between">
                    <span>Region</span>
                    <span>{sessionQuery.data.region.name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Code</span>
                    <span>{sessionQuery.data.region.code}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Network load</span>
                    <span>{Math.round(sessionQuery.data.region.network_load)}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>gNodeB</span>
                    <span>{sessionQuery.data.region.gnodeb_count}</span>
                  </div>
                </div>
              </Card>
            </div>

            <Card className="p-5">
              <div className="flex items-center gap-3 text-white">
                <ShieldAlert size={18} className="text-accent" />
                <span className="font-medium">Predictive reading</span>
              </div>

              {sessionQuery.data.prediction ? (
                <div className="mt-4 space-y-4">
                  <div className="grid gap-4 md:grid-cols-3">
                    <div className="rounded-2xl border border-border bg-cardAlt/70 p-4">
                      <div className="text-xs uppercase tracking-[0.2em] text-mutedText">SLA</div>
                      <div className="mt-2 text-2xl font-semibold text-white">
                        {formatPercent(sessionQuery.data.prediction.sla_score * 100)}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-border bg-cardAlt/70 p-4">
                      <div className="text-xs uppercase tracking-[0.2em] text-mutedText">Congestion</div>
                      <div className="mt-2 text-2xl font-semibold text-white">
                        {formatPercent(sessionQuery.data.prediction.congestion_score * 100)}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-border bg-cardAlt/70 p-4">
                      <div className="text-xs uppercase tracking-[0.2em] text-mutedText">Anomaly</div>
                      <div className="mt-2 text-2xl font-semibold text-white">
                        {formatPercent(sessionQuery.data.prediction.anomaly_score * 100)}
                      </div>
                    </div>
                  </div>
                  <div className="rounded-2xl border border-border bg-cardAlt/70 p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-mutedText">Recommended action</div>
                    <p className="mt-3 text-sm leading-6 text-slate-200">
                      {sessionQuery.data.prediction.recommended_action}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="mt-4 text-sm text-mutedText">No prediction available for this session.</p>
              )}
            </Card>
          </div>
        ) : null}
      </div>
    </div>
  );
}
