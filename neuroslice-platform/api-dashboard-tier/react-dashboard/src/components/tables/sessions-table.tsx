import { Eye, Sparkles } from "lucide-react";

import { RiskBadge } from "@/components/status/risk-badge";
import { ServiceBadge } from "@/components/status/service-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  formatDate,
  formatLatency,
  formatPacketLoss,
  formatThroughput,
  truncateText,
} from "@/lib/format";
import type { SessionSummary } from "@/types/session";

export function SessionsTable({
  sessions,
  onInspect,
}: {
  sessions: SessionSummary[];
  onInspect: (sessionId: number) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-white/5 px-5 py-4">
        <h3 className="text-lg font-semibold text-white">Sessions reseau</h3>
        <p className="text-sm text-mutedText">
          Vue operateur avec prediction la plus recente et action recommendee.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/5 text-sm">
          <thead className="bg-slate-950/45 text-left text-xs uppercase tracking-[0.24em] text-mutedText">
            <tr>
              <th className="px-5 py-4">Session</th>
              <th className="px-5 py-4">Region</th>
              <th className="px-5 py-4">Slice</th>
              <th className="px-5 py-4">Qualite radio</th>
              <th className="px-5 py-4">Prediction</th>
              <th className="px-5 py-4">Action IA</th>
              <th className="px-5 py-4">Detail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {sessions.map((session) => (
              <tr key={session.id} className="hover:bg-white/[0.03]">
                <td className="px-5 py-4 align-top">
                  <div className="font-medium text-white">{session.session_code}</div>
                  <div className="mt-1 text-xs text-mutedText">{formatDate(session.timestamp)}</div>
                </td>
                <td className="px-5 py-4 align-top">
                  <div className="font-medium text-white">{session.region.name}</div>
                  <div className="mt-2">
                    <ServiceBadge value={session.region.ric_status} />
                  </div>
                </td>
                <td className="px-5 py-4 align-top text-slate-200">{session.slice_type}</td>
                <td className="px-5 py-4 align-top">
                  <div className="space-y-1 text-slate-300">
                    <div>Latency: {formatLatency(session.latency_ms)}</div>
                    <div>Loss: {formatPacketLoss(session.packet_loss)}</div>
                    <div>Throughput: {formatThroughput(session.throughput_mbps)}</div>
                  </div>
                </td>
                <td className="px-5 py-4 align-top">
                  {session.prediction ? (
                    <div className="space-y-2">
                      <RiskBadge value={session.prediction.risk_level} />
                      <div className="text-xs text-mutedText">
                        SLA {Math.round(session.prediction.sla_score * 100)} / Cong.
                        {" "}
                        {Math.round(session.prediction.congestion_score * 100)} / Anom.
                        {" "}
                        {Math.round(session.prediction.anomaly_score * 100)}
                      </div>
                    </div>
                  ) : (
                    <span className="text-mutedText">Sans prediction</span>
                  )}
                </td>
                <td className="px-5 py-4 align-top">
                  {session.prediction ? (
                    <div className="flex max-w-xs items-start gap-2 text-slate-300">
                      <Sparkles size={15} className="mt-0.5 shrink-0 text-accent" />
                      <span>{truncateText(session.prediction.recommended_action, 92)}</span>
                    </div>
                  ) : (
                    <span className="text-mutedText">Aucune action</span>
                  )}
                </td>
                <td className="px-5 py-4 align-top">
                  <Button variant="secondary" className="gap-2" onClick={() => onInspect(session.id)}>
                    <Eye size={16} />
                    Ouvrir
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
