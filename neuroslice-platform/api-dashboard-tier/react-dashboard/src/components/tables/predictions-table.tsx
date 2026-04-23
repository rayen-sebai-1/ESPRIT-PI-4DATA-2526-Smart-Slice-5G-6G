import { Play, Zap } from "lucide-react";

import { RiskBadge } from "@/components/status/risk-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatDate, formatPercent, truncateText } from "@/lib/format";
import type { PredictionResponse } from "@/types/prediction";

export function PredictionsTable({
  predictions,
  onRun,
  isRunning,
}: {
  predictions: PredictionResponse[];
  onRun: (sessionId: number) => void;
  isRunning?: boolean;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-white/5 px-5 py-4">
        <h3 className="text-lg font-semibold text-white">Predictions automatiques</h3>
        <p className="text-sm text-mutedText">
          Lecture simple des scores SLA, congestion et anomalie pour aider l'operateur.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/5 text-sm">
          <thead className="bg-slate-950/45 text-left text-xs uppercase tracking-[0.24em] text-mutedText">
            <tr>
              <th className="px-5 py-4">Session</th>
              <th className="px-5 py-4">Region</th>
              <th className="px-5 py-4">SLA</th>
              <th className="px-5 py-4">Congestion</th>
              <th className="px-5 py-4">Anomalie</th>
              <th className="px-5 py-4">Risque</th>
              <th className="px-5 py-4">Action recommandee</th>
              <th className="px-5 py-4">Run</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {predictions.map((prediction) => (
              <tr key={prediction.id} className="hover:bg-white/[0.03]">
                <td className="px-5 py-4">
                  <div className="font-medium text-white">{prediction.session_code}</div>
                  <div className="text-xs text-mutedText">{formatDate(prediction.predicted_at)}</div>
                </td>
                <td className="px-5 py-4">
                  <div className="font-medium text-white">{prediction.region.name}</div>
                  <div className="text-xs text-mutedText">{prediction.region.code}</div>
                </td>
                <td className="px-5 py-4 text-slate-300">{formatPercent(prediction.sla_score * 100)}</td>
                <td className="px-5 py-4 text-slate-300">{formatPercent(prediction.congestion_score * 100)}</td>
                <td className="px-5 py-4 text-slate-300">{formatPercent(prediction.anomaly_score * 100)}</td>
                <td className="px-5 py-4">
                  <RiskBadge value={prediction.risk_level} />
                </td>
                <td className="px-5 py-4">
                  <div className="max-w-xs text-slate-300">
                    {truncateText(prediction.recommended_action, 88)}
                  </div>
                </td>
                <td className="px-5 py-4">
                  <Button
                    variant="secondary"
                    className="gap-2"
                    disabled={isRunning}
                    onClick={() => onRun(prediction.session_id)}
                  >
                    {isRunning ? <Zap size={16} className="animate-pulse" /> : <Play size={16} />}
                    Relancer
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
