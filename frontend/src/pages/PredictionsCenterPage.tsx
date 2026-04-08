import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Gauge, RefreshCcw, ShieldAlert, Waves } from "lucide-react";

import { getNationalDashboard } from "@/api/dashboardApi";
import { getPredictions, runPrediction } from "@/api/predictionApi";
import { PageHeader } from "@/components/layout/page-header";
import { PredictionsTable } from "@/components/tables/predictions-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { Select } from "@/components/ui/select";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatNumber, formatPercent } from "@/lib/format";
import type { PredictionResponse } from "@/types/prediction";
import type { RiskLevel } from "@/types/shared";

type PredictionTab = "sla" | "congestion" | "anomaly";

function sortPredictions(items: PredictionResponse[], tab: PredictionTab) {
  const copied = [...items];

  if (tab === "sla") {
    return copied.sort((left, right) => left.sla_score - right.sla_score);
  }
  if (tab === "congestion") {
    return copied.sort((left, right) => right.congestion_score - left.congestion_score);
  }

  return copied.sort((left, right) => right.anomaly_score - left.anomaly_score);
}

export function PredictionsCenterPage() {
  usePageTitle("Prediction simple");

  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [region, setRegion] = useState("");
  const [risk, setRisk] = useState<"" | RiskLevel>("");
  const [activeTab, setActiveTab] = useState<PredictionTab>("sla");

  const predictionsQuery = useQuery({
    queryKey: ["predictions", { page, region, risk }],
    queryFn: () =>
      getPredictions({
        page,
        pageSize: 20,
        region: region || undefined,
        risk: risk || undefined,
      }),
  });

  const regionsQuery = useQuery({
    queryKey: ["dashboard", "national", "prediction-regions"],
    queryFn: getNationalDashboard,
  });

  const runMutation = useMutation({
    mutationFn: runPrediction,
    onSuccess: async () => {
      setMessage("Prediction relancee avec succes.");
      await queryClient.invalidateQueries({ queryKey: ["predictions"] });
      await queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
    onError: () => {
      setMessage("La relance a echoue. Verifie le service central.");
    },
  });

  const orderedPredictions = useMemo(() => {
    return sortPredictions(predictionsQuery.data?.items ?? [], activeTab);
  }, [predictionsQuery.data?.items, activeTab]);

  const stats = useMemo(() => {
    const items = predictionsQuery.data?.items ?? [];
    const average = (selector: (item: PredictionResponse) => number) =>
      items.reduce((sum, item) => sum + selector(item), 0) / (items.length || 1);

    return {
      avgSla: average((item) => item.sla_score),
      avgCongestion: average((item) => item.congestion_score),
      avgAnomaly: average((item) => item.anomaly_score),
      highRiskCount: items.filter((item) => item.risk_level === "HIGH" || item.risk_level === "CRITICAL").length,
    };
  }, [predictionsQuery.data?.items]);

  if (predictionsQuery.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Chargement des predictions...</div>;
  }

  if (predictionsQuery.isError) {
    return (
      <EmptyState
        title="Predictions indisponibles"
        description="Impossible de contacter le service central pour recuperer les scores."
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Predictive monitoring"
        title="Prediction simple"
        description="Lecture simple des scores automatiques pour aider l'operateur a prioriser les sessions a surveiller."
        actions={
          <>
            <Select value={region} onChange={(event) => setRegion(event.target.value)}>
              <option value="">Toutes les regions</option>
              {regionsQuery.data?.regions.map((item) => (
                <option key={item.region_id} value={item.code}>
                  {item.name}
                </option>
              ))}
            </Select>
            <Select value={risk} onChange={(event) => setRisk(event.target.value as "" | RiskLevel)}>
              <option value="">Tous les risques</option>
              <option value="LOW">LOW</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="HIGH">HIGH</option>
              <option value="CRITICAL">CRITICAL</option>
            </Select>
            <Button variant="secondary" onClick={() => void predictionsQuery.refetch()}>
              <RefreshCcw size={16} />
              Rafraichir
            </Button>
          </>
        }
      />

      <div className="flex flex-wrap gap-3">
        {([
          { key: "sla", label: "SLA", icon: Gauge },
          { key: "congestion", label: "Congestion", icon: Waves },
          { key: "anomaly", label: "Anomalies", icon: ShieldAlert },
        ] as const).map((tab) => (
          <button
            key={tab.key}
            className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm transition ${
              activeTab === tab.key
                ? "border-accent bg-accent text-slate-950"
                : "border-border bg-cardAlt/70 text-slate-200 hover:border-accent/30 hover:bg-card"
            }`}
            onClick={() => setActiveTab(tab.key)}
            type="button"
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {message ? <Card className="px-4 py-3 text-sm text-slate-200">{message}</Card> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="SLA moyen"
          value={formatPercent(stats.avgSla * 100)}
          subtitle="Sur la page courante"
          icon={<Gauge size={20} />}
          tone="accent"
        />
        <KpiCard
          title="Congestion moyenne"
          value={formatPercent(stats.avgCongestion * 100)}
          subtitle="Sessions chargees"
          icon={<Waves size={20} />}
          tone={stats.avgCongestion >= 0.6 ? "warning" : "neutral"}
        />
        <KpiCard
          title="Anomalie moyenne"
          value={formatPercent(stats.avgAnomaly * 100)}
          subtitle="Sessions chargees"
          icon={<ShieldAlert size={20} />}
          tone={stats.avgAnomaly >= 0.6 ? "danger" : "neutral"}
        />
        <KpiCard
          title="Sessions high risk"
          value={formatNumber(stats.highRiskCount)}
          subtitle="Scores critiques ou eleves"
          icon={<BarChart3 size={20} />}
          tone={stats.highRiskCount > 0 ? "danger" : "accent"}
        />
      </section>

      {orderedPredictions.length ? (
        <>
          <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
            <PredictionsTable
              predictions={orderedPredictions}
              onRun={(sessionId) => {
                setMessage(null);
                runMutation.mutate(sessionId);
              }}
              isRunning={runMutation.isPending}
            />

            <Card className="p-5">
              <div className="mb-5">
                <h3 className="text-lg font-semibold text-white">Focus prioritaire</h3>
                <p className="text-sm text-mutedText">
                  Sessions les plus importantes selon l'onglet actif.
                </p>
              </div>
              <div className="space-y-3">
                {orderedPredictions.slice(0, 5).map((item) => (
                  <div key={item.id} className="rounded-2xl border border-border bg-cardAlt/70 p-4">
                    <div className="text-sm font-medium text-white">{item.session_code}</div>
                    <div className="mt-1 text-xs text-mutedText">{item.region.name}</div>
                    <div className="mt-3 text-sm text-slate-200">
                      {activeTab === "sla" ? "SLA " : activeTab === "congestion" ? "Congestion " : "Anomalie "}
                      {activeTab === "sla"
                        ? formatPercent(item.sla_score * 100)
                        : activeTab === "congestion"
                          ? formatPercent(item.congestion_score * 100)
                          : formatPercent(item.anomaly_score * 100)}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </section>

          <Card className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
            <div className="text-sm text-mutedText">
              Page {predictionsQuery.data?.pagination.page} / {predictionsQuery.data?.pagination.total_pages} ·{" "}
              {formatNumber(predictionsQuery.data?.pagination.total ?? 0)} predictions au total
            </div>
            <div className="flex gap-3">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
                Precedent
              </Button>
              <Button
                variant="secondary"
                disabled={page >= (predictionsQuery.data?.pagination.total_pages ?? 1)}
                onClick={() => setPage((value) => value + 1)}
              >
                Suivant
              </Button>
            </div>
          </Card>
        </>
      ) : (
        <EmptyState
          title="Aucune prediction"
          description="Aucun enregistrement ne correspond aux filtres actifs."
        />
      )}
    </div>
  );
}
