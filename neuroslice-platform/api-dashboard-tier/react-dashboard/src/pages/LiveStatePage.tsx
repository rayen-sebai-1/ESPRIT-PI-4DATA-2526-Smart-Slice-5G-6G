import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, RadioTower, ShieldAlert, Cpu, HeartPulse } from "lucide-react";

import { liveApi } from "@/api/liveApi";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { usePageTitle } from "@/hooks/usePageTitle";

export function LiveStatePage() {
  usePageTitle("Live State Store");

  // Fetch live overview every 3 seconds
  const { data: overview, isLoading: isOverviewLoading, isError: isOverviewError } = useQuery({
    queryKey: ["live", "overview"],
    queryFn: liveApi.getOverview,
    refetchInterval: 3000,
  });

  // Fetch entities list every 3 seconds
  const { data: entitiesData, isLoading: isEntitiesLoading } = useQuery({
    queryKey: ["live", "entities"],
    queryFn: () => liveApi.getEntities(100),
    refetchInterval: 3000,
  });

  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);

  // Fetch specific entity AiOps details
  const { data: aiopsData, isLoading: isAiopsLoading } = useQuery({
    queryKey: ["live", "aiops", selectedEntityId],
    queryFn: () => liveApi.getEntityAiops(selectedEntityId!),
    enabled: !!selectedEntityId,
    refetchInterval: 3000,
  });

  if (isOverviewLoading) {
    return <div className="py-10 text-sm text-mutedText">Loading Live State...</div>;
  }

  if (isOverviewError || !overview) {
    return (
      <EmptyState
        title="Live State unavailable"
        description="The Redis Live State Store is not accessible. Check the BFF API logs."
      />
    );
  }

  const entities = entitiesData?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Network Live State"
        title="Live State Store"
        description="Real-time tracking of all active entities connected via Redis Streams, normalizer and AIOps."
      />

      {/* Summary Cards */}
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          title="Total Entities"
          value={String(overview.total_entities)}
          subtitle="Active entities in the Live State"
          icon={<RadioTower size={20} />}
          tone="accent"
        />
        <KpiCard
          title="Unhealthy Entities"
          value={String(overview.unhealthy_entities_count)}
          subtitle="Entities with Health Score < 0.6"
          icon={<HeartPulse size={20} />}
          tone={overview.unhealthy_entities_count > 0 ? "danger" : "neutral"}
        />
        <KpiCard
          title="Active Faults"
          value={String(overview.active_faults_count)}
          subtitle="Currently injected alarms"
          icon={<AlertTriangle size={20} />}
          tone={overview.active_faults_count > 0 ? "warning" : "neutral"}
        />
        <KpiCard
          title="Congestion Risks"
          value={String(overview.congestion_alerts_count)}
          subtitle="AIOps congestion anomalies"
          icon={<Activity size={20} />}
          tone={overview.congestion_alerts_count > 0 ? "danger" : "neutral"}
        />
        <KpiCard
          title="SLA at Risk"
          value={String(overview.sla_risk_count)}
          subtitle="Predictions de degradation SLA"
          icon={<ShieldAlert size={20} />}
          tone={overview.sla_risk_count > 0 ? "warning" : "neutral"}
        />
        <KpiCard
          title="Mismatch Slices"
          value={String(overview.slice_mismatch_count)}
          subtitle="Violations type de Slices"
          icon={<Cpu size={20} />}
          tone={overview.slice_mismatch_count > 0 ? "danger" : "neutral"}
        />
      </section>

      {/* Recent AIOps Summary */}
      {overview.latest_aiops_events.length > 0 && (
          <section>
              <Card className="p-5">
                  <h3 className="text-lg font-semibold text-white mb-4">Latest AIOps Events</h3>
                  <div className="space-y-3">
                      {overview.latest_aiops_events.slice(0,3).map((ev: any, idx: number) => (
                          <div key={idx} className="flex justify-between items-center text-sm p-3 bg-cardAlt rounded-xl">
                              <span className="text-slate-200 font-medium">{ev.entityId} ({ev.entityType})</span>
                              <span className="text-slate-400">Prediction: {ev.prediction}</span>
                              <span className={`px-2 py-1 rounded text-xs ${ev.severity > 2 ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'}`}>Severity: {ev.severity}</span>
                          </div>
                      ))}
                  </div>
              </Card>
          </section>
      )}

      {/* Entities Table */}
      <section className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Card className="flex flex-col h-[500px]">
          <div className="p-4 border-b border-border">
            <h3 className="text-lg font-semibold text-white">Network Entities (Live)</h3>
          </div>
          <div className="flex-1 overflow-auto p-4">
            {isEntitiesLoading ? (
              <div className="text-sm text-mutedText">Loading entities...</div>
            ) : (
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="sticky top-0 bg-surfce/95 backdrop-blur z-10 text-xs uppercase text-mutedText border-b border-border">
                  <tr>
                    <th className="pb-3 font-medium">Entity ID</th>
                    <th className="pb-3 font-medium">Type</th>
                    <th className="pb-3 font-medium">Domain</th>
                    <th className="pb-3 font-medium">Health</th>
                    <th className="pb-3 font-medium">Congestion</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {entities.map((item: any) => (
                    <tr 
                      key={item.entityId} 
                      className={`cursor-pointer hover:bg-cardAlt transition-colors ${selectedEntityId === item.entityId ? 'bg-accent/10 border-l-2 border-accent' : ''}`}
                      onClick={() => setSelectedEntityId(item.entityId)}
                    >
                      <td className="py-3 font-medium text-white">{item.entityId}</td>
                      <td className="py-3">{item.entityType}</td>
                      <td className="py-3">{item.domain}</td>
                      <td className="py-3">{item.healthScore?.toFixed(2)}</td>
                      <td className="py-3">{item.congestionScore?.toFixed(2)}</td>
                    </tr>
                  ))}
                  {entities.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-mutedText">No data available.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </Card>

        {/* Entity Details Drawer Area */}
        <Card className="h-[500px] overflow-auto p-5">
          {selectedEntityId ? (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-white mb-1">Details: {selectedEntityId}</h3>
                <p className="text-sm text-mutedText">Live AIOps states</p>
              </div>
              
              {isAiopsLoading ? (
                <div className="text-sm text-mutedText">Retrieving metrics...</div>
              ) : (
                <div className="space-y-4">
                  {/* Congestion */}
                  <div className="p-4 bg-cardAlt rounded-xl">
                    <h4 className="text-sm font-medium text-slate-200 mb-2">Congestion Detector</h4>
                    {aiopsData?.congestion ? (
                      <div className="text-sm text-slate-400 space-y-1">
                        <div>Prediction: <span className="text-white">{aiopsData.congestion.prediction}</span></div>
                        <div>Score: {aiopsData.congestion.score?.toFixed(4)}</div>
                        <div>Model: {aiopsData.congestion.modelName} (v{aiopsData.congestion.modelVersion})</div>
                      </div>
                    ) : (
                      <div className="text-sm text-mutedText">No data yet</div>
                    )}
                  </div>
                  
                  {/* SLA */}
                  <div className="p-4 bg-cardAlt rounded-xl">
                    <h4 className="text-sm font-medium text-slate-200 mb-2">SLA Assurance</h4>
                    {aiopsData?.sla ? (
                      <div className="text-sm text-slate-400 space-y-1">
                        <div>Prediction: <span className="text-white">{aiopsData.sla.prediction}</span></div>
                        <div>Score (Risk): {aiopsData.sla.score?.toFixed(4)}</div>
                        <div>Model: {aiopsData.sla.modelName}</div>
                      </div>
                    ) : (
                      <div className="text-sm text-mutedText">No data yet</div>
                    )}
                  </div>

                  {/* Slice Classification */}
                  <div className="p-4 bg-cardAlt rounded-xl">
                    <h4 className="text-sm font-medium text-slate-200 mb-2">Slice Classifier</h4>
                    {aiopsData?.slice_classification ? (
                      <div className="text-sm text-slate-400 space-y-1">
                        <div>Predicted Type: <span className="text-white">{aiopsData.slice_classification.prediction}</span></div>
                        <div>Confidence: {aiopsData.slice_classification.confidence?.toFixed(4)}</div>
                        <div>Mismatch: {aiopsData.slice_classification.details?.mismatch ? <span className="text-red-400">Yes</span> : "No"}</div>
                      </div>
                    ) : (
                      <div className="text-sm text-mutedText">No data yet</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <Activity className="mx-auto mb-4 h-10 w-10 text-mutedText" />
              <h3 className="text-lg font-medium text-slate-200 mb-2">Select an entity</h3>
              <p className="text-sm text-mutedText max-w-[200px]">Click on a table row to view AIOps data.</p>
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
