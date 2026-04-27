import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getMlopsPredictionMonitoring } from "@/api/mlopsApi";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatMetric } from "./mlopsHelpers";

export function MlopsMonitoringPage() {
  usePageTitle("MLOps - Monitoring");
  const [model, setModel] = useState("");

  const query = useQuery({
    queryKey: ["mlops", "monitoring", model],
    queryFn: () => getMlopsPredictionMonitoring({ model: model || undefined, limit: 80 }),
  });

  if (query.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Chargement du monitoring...</div>;
  }
  if (query.isError || !query.data) {
    return <EmptyState title="Monitoring indisponible" description="Echec de la requete Elasticsearch." />;
  }

  const data = query.data;

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Monitoring des predictions</h3>
            <p className="text-sm text-mutedText">
              Source: {data.source} - {data.available ? "disponible" : "indisponible"}
            </p>
            {data.note ? <p className="mt-1 text-xs text-amber-300">{data.note}</p> : null}
          </div>
          <div className="flex items-end gap-2">
            <div>
              <label className="text-xs uppercase tracking-[0.22em] text-mutedText">
                Filtrer par modele
              </label>
              <Input
                value={model}
                onChange={(event) => setModel(event.target.value)}
                placeholder="sla_5g, slice_type_5g..."
              />
            </div>
            <Button variant="secondary" onClick={() => void query.refetch()}>
              Rafraichir
            </Button>
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-white">Dernieres predictions ({data.total})</h4>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.22em] text-mutedText">
              <tr>
                <th className="pb-3 pr-4">Timestamp</th>
                <th className="pb-3 pr-4">Modele</th>
                <th className="pb-3 pr-4">Region</th>
                <th className="pb-3 pr-4">Risk</th>
                <th className="pb-3 pr-4">SLA</th>
              </tr>
            </thead>
            <tbody className="text-slate-100">
              {data.items.map((point, index) => (
                <tr key={`${point.timestamp}-${index}`} className="border-t border-border">
                  <td className="py-3 pr-4 text-mutedText">{point.timestamp}</td>
                  <td className="py-3 pr-4">{point.model ?? "-"}</td>
                  <td className="py-3 pr-4">{point.region ?? "-"}</td>
                  <td className="py-3 pr-4">{point.risk_level ?? "-"}</td>
                  <td className="py-3 pr-4">{formatMetric(point.sla_score)}</td>
                </tr>
              ))}
              {data.items.length === 0 ? (
                <tr>
                  <td className="py-6 text-center text-mutedText" colSpan={5}>
                    Aucun evenement disponible.
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
