import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  getMlopsDrift,
  getMlopsEvaluation,
  getMlopsPredictionMonitoring,
  type DriftModelState,
  type EvaluationModelState,
} from "@/api/mlopsApi";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatMetric } from "./mlopsHelpers";

// ---------------------------------------------------------------------------
// Drift severity colours
// ---------------------------------------------------------------------------

function severityClass(severity?: string): string {
  switch (severity?.toUpperCase()) {
    case "CRITICAL":
      return "text-red-400 font-bold";
    case "HIGH":
      return "text-orange-400 font-bold";
    case "MEDIUM":
      return "text-amber-400";
    case "LOW":
      return "text-yellow-300";
    default:
      return "text-green-400";
  }
}

function statusBadge(status?: string, isDrift?: boolean): JSX.Element {
  if (isDrift) {
    return (
      <span className="rounded bg-red-900/60 px-2 py-0.5 text-xs font-semibold text-red-300">
        DRIFT DETECTED
      </span>
    );
  }
  switch (status) {
    case "no_drift":
      return (
        <span className="rounded bg-green-900/50 px-2 py-0.5 text-xs text-green-400">
          No Drift
        </span>
      );
    case "insufficient_data":
      return (
        <span className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-300">
          Collecting data
        </span>
      );
    case "reference_missing":
      return (
        <span className="rounded bg-amber-900/60 px-2 py-0.5 text-xs text-amber-300">
          Reference missing
        </span>
      );
    case "alibi_unavailable":
      return (
        <span className="rounded bg-amber-900/60 px-2 py-0.5 text-xs text-amber-300">
          Alibi unavailable
        </span>
      );
    case "no_data":
    default:
      return (
        <span className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-400">
          No data
        </span>
      );
  }
}

// ---------------------------------------------------------------------------
// Drift card for one model
// ---------------------------------------------------------------------------

function DriftModelCard({ state }: { state: DriftModelState }) {
  const isDrift = Boolean(state.is_drift);
  return (
    <div
      className={`rounded-lg border p-4 ${
        isDrift ? "border-red-700 bg-red-950/30" : "border-border bg-surface"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-white">{state.model_name}</p>
          <p className="text-xs text-mutedText">v{state.deployment_version ?? "unknown"}</p>
        </div>
        {statusBadge(state.status, isDrift)}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <span className="text-mutedText">p-value</span>
        <span className="font-mono text-slate-200">
          {state.p_value != null ? state.p_value.toFixed(4) : "—"}
        </span>

        <span className="text-mutedText">Threshold</span>
        <span className="font-mono text-slate-200">{state.threshold ?? 0.01}</span>

        <span className="text-mutedText">Window</span>
        <span className="font-mono text-slate-200">
          {state.window_size ?? 0} / {state.window_capacity ?? 500}
        </span>

        <span className="text-mutedText">Reference samples</span>
        <span className="font-mono text-slate-200">{state.reference_sample_count ?? 0}</span>

        {state.severity && state.severity !== "NONE" ? (
          <>
            <span className="text-mutedText">Severity</span>
            <span className={severityClass(state.severity)}>{state.severity}</span>
          </>
        ) : null}

        {state.last_checked_at ? (
          <>
            <span className="text-mutedText">Last checked</span>
            <span className="text-slate-300">
              {new Date(state.last_checked_at).toLocaleTimeString()}
            </span>
          </>
        ) : null}

        {isDrift && state.last_drift_at ? (
          <>
            <span className="text-mutedText">Last drift</span>
            <span className="text-red-300">
              {new Date(state.last_drift_at).toLocaleTimeString()}
            </span>
          </>
        ) : null}
      </div>

      {isDrift && state.recommendation ? (
        <p className="mt-3 rounded bg-red-900/30 px-3 py-2 text-xs text-red-200">
          {state.recommendation}
        </p>
      ) : null}

      {state.status === "reference_missing" ? (
        <p className="mt-3 text-xs text-amber-400">
          Run the MLOps pipeline to generate drift reference artifacts, then restart
          drift-monitor.
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Drift section
// ---------------------------------------------------------------------------

function DriftSection() {
  const driftQuery = useQuery({
    queryKey: ["mlops", "drift"],
    queryFn: getMlopsDrift,
    refetchInterval: 60_000,
  });

  if (driftQuery.isLoading) {
    return (
      <Card className="p-5">
        <h3 className="mb-3 text-lg font-semibold text-white">Drift Detection</h3>
        <p className="text-sm text-mutedText">Loading...</p>
      </Card>
    );
  }

  const driftData = driftQuery.data;
  const models = driftData?.models ?? {};
  const anyDrift = Object.values(models).some((m) => m.is_drift);

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Drift Detection</h3>
          <p className="text-xs text-mutedText">
            Alibi Detect MMD — window 500 — p &lt; 0.01 — auto-trigger OFF by default
          </p>
          {driftData?.note ? (
            <p className="mt-1 text-xs text-amber-300">{driftData.note}</p>
          ) : null}
        </div>
        <Button variant="secondary" size="sm" onClick={() => void driftQuery.refetch()}>
          Refresh
        </Button>
      </div>

      {anyDrift ? (
        <div className="mb-4 rounded border border-red-700 bg-red-950/40 px-4 py-2 text-sm text-red-300">
          Distribution drift detected on one or more models. Review the MLOps Operations
          page before promoting any candidate model.
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {Object.entries(models).map(([name, state]) => (
          <DriftModelCard key={name} state={state} />
        ))}
        {Object.keys(models).length === 0 ? (
          <p className="col-span-3 py-4 text-center text-sm text-mutedText">
            drift-monitor not reachable or no data collected yet.
          </p>
        ) : null}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Online evaluation section
// ---------------------------------------------------------------------------

function EvalModelCard({ state }: { state: EvaluationModelState }) {
  const hasTruth = Boolean(state.pseudo_ground_truth_available);

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-white">{state.model_name}</p>
        <span
          className={`rounded px-2 py-0.5 text-xs ${
            hasTruth ? "bg-emerald-900/50 text-emerald-300" : "bg-amber-900/50 text-amber-300"
          }`}
        >
          {hasTruth ? "Ground truth: available" : "Ground truth: pending"}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <span className="text-mutedText">Samples</span>
        <span className="font-mono text-slate-200">{state.samples_total ?? 0}</span>

        <span className="text-mutedText">Accuracy</span>
        <span className="font-mono text-slate-200">
          {state.accuracy != null ? `${(state.accuracy * 100).toFixed(1)}%` : "—"}
        </span>

        <span className="text-mutedText">Precision</span>
        <span className="font-mono text-slate-200">
          {state.precision != null ? `${(state.precision * 100).toFixed(1)}%` : "—"}
        </span>

        <span className="text-mutedText">Recall</span>
        <span className="font-mono text-slate-200">
          {state.recall != null ? `${(state.recall * 100).toFixed(1)}%` : "—"}
        </span>

        <span className="text-mutedText">F1</span>
        <span className="font-mono text-slate-200">
          {state.f1 != null ? `${(state.f1 * 100).toFixed(1)}%` : "—"}
        </span>

        <span className="text-mutedText">FP / FN</span>
        <span className="font-mono text-slate-200">
          {state.false_positive_count ?? 0} / {state.false_negative_count ?? 0}
        </span>
      </div>
    </div>
  );
}

function EvaluationSection() {
  const evalQuery = useQuery({
    queryKey: ["mlops", "evaluation"],
    queryFn: getMlopsEvaluation,
    refetchInterval: 30_000,
  });

  if (evalQuery.isLoading) {
    return (
      <Card className="p-5">
        <h3 className="mb-3 text-lg font-semibold text-white">Online Evaluation</h3>
        <p className="text-sm text-mutedText">Loading...</p>
      </Card>
    );
  }

  const evalData = evalQuery.data;
  const models = evalData?.models ?? {};

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Online Model Evaluation</h3>
          <p className="text-xs text-mutedText">
            Rolling metrics against Scenario B pseudo-ground-truth.
          </p>
          {evalData?.note ? <p className="mt-1 text-xs text-amber-300">{evalData.note}</p> : null}
        </div>
        <Button variant="secondary" size="sm" onClick={() => void evalQuery.refetch()}>
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {Object.entries(models).map(([name, state]) => (
          <EvalModelCard key={name} state={state} />
        ))}
        {Object.keys(models).length === 0 ? (
          <p className="col-span-3 py-4 text-center text-sm text-mutedText">
            online-evaluator not reachable or no data collected yet.
          </p>
        ) : null}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function MlopsMonitoringPage() {
  usePageTitle("MLOps - Monitoring");
  const [model, setModel] = useState("");

  const query = useQuery({
    queryKey: ["mlops", "monitoring", model],
    queryFn: () => getMlopsPredictionMonitoring({ model: model || undefined, limit: 80 }),
  });

  if (query.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Loading monitoring...</div>;
  }
  if (query.isError || !query.data) {
    return (
      <EmptyState title="Monitoring unavailable" description="Elasticsearch query failed." />
    );
  }

  const data = query.data;

  return (
    <div className="space-y-6">
      {/* Drift Detection section */}
      <DriftSection />
      <EvaluationSection />

      {/* Prediction monitoring section */}
      <Card className="p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Prediction monitoring</h3>
            <p className="text-sm text-mutedText">
              Source: {data.source} - {data.available ? "available" : "unavailable"}
            </p>
            {data.note ? <p className="mt-1 text-xs text-amber-300">{data.note}</p> : null}
          </div>
          <div className="flex items-end gap-2">
            <div>
              <label className="text-xs uppercase tracking-[0.22em] text-mutedText">
                Filter by model
              </label>
              <Input
                value={model}
                onChange={(event) => setModel(event.target.value)}
                placeholder="sla_5g, slice_type_5g..."
              />
            </div>
            <Button variant="secondary" onClick={() => void query.refetch()}>
              Refresh
            </Button>
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-white">
            Latest predictions ({data.total})
          </h4>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.22em] text-mutedText">
              <tr>
                <th className="pb-3 pr-4">Timestamp</th>
                <th className="pb-3 pr-4">Model</th>
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
                    No events available.
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
