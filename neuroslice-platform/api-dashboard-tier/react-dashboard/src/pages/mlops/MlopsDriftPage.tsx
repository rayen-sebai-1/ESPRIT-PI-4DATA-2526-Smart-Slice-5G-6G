import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import {
  getMlopsDrift,
  getMlopsDriftEvents,
  type DriftEvent,
  type DriftModelState,
} from "@/api/mlopsApi";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { usePageTitle } from "@/hooks/usePageTitle";
import { driftSeverityBg, driftSeverityClass } from "./mlopsHelpers";

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

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
      return <span className="rounded bg-green-900/50 px-2 py-0.5 text-xs text-green-400">Stable</span>;
    case "insufficient_data":
      return <span className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-300">Collecting data</span>;
    case "reference_missing":
      return <span className="rounded bg-amber-900/60 px-2 py-0.5 text-xs text-amber-300">Reference missing</span>;
    case "alibi_unavailable":
      return <span className="rounded bg-amber-900/60 px-2 py-0.5 text-xs text-amber-300">Alibi unavailable</span>;
    case "no_data":
    default:
      return <span className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-400">No data</span>;
  }
}

function fmtTime(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString();
}

function fmtDateTime(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

// ---------------------------------------------------------------------------
// Window fill bar
// ---------------------------------------------------------------------------

function WindowBar({ size, capacity }: { size?: number; capacity?: number }) {
  const current = size ?? 0;
  const max = capacity ?? 500;
  const pct = max > 0 ? Math.min((current / max) * 100, 100) : 0;
  const full = pct >= 100;
  return (
    <div className="mt-1">
      <div className="flex items-center justify-between text-xs text-mutedText">
        <span>Window</span>
        <span className="font-mono text-slate-200">
          {current} / {max}
        </span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-700">
        <div
          className={`h-full rounded-full transition-all ${full ? "bg-green-500" : "bg-blue-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// P-value bar
// ---------------------------------------------------------------------------

function PValueBar({ pValue, threshold }: { pValue?: number | null; threshold?: number }) {
  const p = pValue ?? null;
  const thr = threshold ?? 0.01;
  if (p === null) {
    return (
      <div className="mt-1">
        <div className="flex items-center justify-between text-xs text-mutedText">
          <span>p-value</span>
          <span className="font-mono text-slate-400">—</span>
        </div>
        <div className="mt-1 h-1.5 w-full rounded-full bg-slate-700" />
      </div>
    );
  }
  const drift = p < thr;
  const pct = Math.min(p * 100, 100);
  const thrPct = Math.min(thr * 100, 100);
  return (
    <div className="mt-1">
      <div className="flex items-center justify-between text-xs text-mutedText">
        <span>p-value</span>
        <span className={`font-mono ${drift ? "text-red-400 font-bold" : "text-green-400"}`}>
          {p.toFixed(4)}
          <span className="ml-1 text-slate-500">(thr {thr})</span>
        </span>
      </div>
      <div className="relative mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-700">
        <div
          className={`h-full rounded-full transition-all ${drift ? "bg-red-500" : "bg-green-500"}`}
          style={{ width: `${pct}%` }}
        />
        {/* threshold marker */}
        <div
          className="absolute top-0 h-full w-px bg-yellow-400 opacity-80"
          style={{ left: `${thrPct}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Feature names list
// ---------------------------------------------------------------------------

function FeatureList({ names }: { names?: string[] }) {
  const [open, setOpen] = useState(false);
  if (!names || names.length === 0) return null;
  return (
    <div className="mt-2">
      <button
        className="text-xs text-slate-400 hover:text-slate-200 underline underline-offset-2"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Hide" : "Show"} {names.length} features
      </button>
      {open && (
        <div className="mt-1 flex flex-wrap gap-1">
          {names.map((f) => (
            <span
              key={f}
              className="rounded bg-slate-700 px-1.5 py-0.5 text-xs font-mono text-slate-300"
            >
              {f}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Full model card
// ---------------------------------------------------------------------------

function ModelDriftCard({ state, onRequestRetraining }: { state: DriftModelState; onRequestRetraining: () => void }) {
  const isDrift = Boolean(state.is_drift);
  return (
    <div
      className={`flex flex-col rounded-lg border p-4 ${
        isDrift ? "border-red-700 bg-red-950/30" : "border-border bg-surface"
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-white">{state.model_name}</p>
          <p className="text-xs text-mutedText">v{state.deployment_version ?? "—"}</p>
        </div>
        {statusBadge(state.status, isDrift)}
      </div>

      {/* Bars */}
      <div className="mt-3 space-y-1">
        <PValueBar pValue={state.p_value} threshold={state.threshold} />
        <WindowBar size={state.window_size} capacity={state.window_capacity} />
      </div>

      {/* Meta grid */}
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <span className="text-mutedText">Reference</span>
        <span
          className={
            state.reference_loaded ? "text-green-400" : "text-amber-400"
          }
        >
          {state.reference_loaded ? `loaded (${state.reference_sample_count ?? 0} samples)` : "missing"}
        </span>

        {state.severity && state.severity !== "NONE" ? (
          <>
            <span className="text-mutedText">Severity</span>
            <span className={driftSeverityClass(state.severity)}>{state.severity}</span>
          </>
        ) : null}

        <span className="text-mutedText">Auto-trigger</span>
        <span className={state.auto_trigger_enabled ? "text-green-400" : "text-slate-400"}>
          {state.auto_trigger_enabled ? "ON" : "OFF"}
        </span>

        <span className="text-mutedText">Last check</span>
        <span className="text-slate-300">{fmtTime(state.last_checked_at)}</span>

        {isDrift && state.last_drift_at ? (
          <>
            <span className="text-mutedText">Last drift</span>
            <span className="text-red-300">{fmtTime(state.last_drift_at)}</span>
          </>
        ) : null}
      </div>

      {/* Feature list */}
      <FeatureList names={state.feature_names} />

      {/* Recommendation */}
      {isDrift && state.recommendation ? (
        <p className="mt-3 rounded bg-red-900/30 px-3 py-2 text-xs text-red-200">
          {state.recommendation}
        </p>
      ) : null}

      {isDrift && (
        <Button
          size="sm"
          className="mt-3 w-full"
          onClick={onRequestRetraining}
        >
          Request Retraining →
        </Button>
      )}

      {state.status === "reference_missing" ? (
        <p className="mt-3 rounded bg-amber-900/30 px-3 py-2 text-xs text-amber-300">
          Run the MLOps pipeline to generate drift reference artifacts, then restart
          drift-monitor.
        </p>
      ) : null}

      {state.status === "insufficient_data" ? (
        <p className="mt-3 text-xs text-slate-400">
          Filling window ({state.window_size ?? 0}/{state.window_capacity ?? 500} samples). First
          drift test runs when window is full.
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Summary KPI row
// ---------------------------------------------------------------------------

function SummaryRow({
  models,
  lastUpdate,
}: {
  models: Record<string, DriftModelState>;
  lastUpdate?: string | null;
}) {
  const total = Object.keys(models).length;
  const drifting = Object.values(models).filter((m) => m.is_drift).length;
  const missingRef = Object.values(models).filter((m) => m.status === "reference_missing").length;
  const collecting = Object.values(models).filter(
    (m) => m.status === "insufficient_data" || m.status === "no_data",
  ).length;

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <Card className="p-4">
        <p className="text-xs uppercase tracking-widest text-mutedText">Models monitored</p>
        <p className="mt-1 text-2xl font-bold text-white">{total}</p>
      </Card>
      <Card
        className={`p-4 ${drifting > 0 ? "border-red-700 bg-red-950/30" : ""}`}
      >
        <p className="text-xs uppercase tracking-widest text-mutedText">Drifting now</p>
        <p className={`mt-1 text-2xl font-bold ${drifting > 0 ? "text-red-400" : "text-green-400"}`}>
          {drifting}
        </p>
      </Card>
      <Card className="p-4">
        <p className="text-xs uppercase tracking-widest text-mutedText">Ref missing</p>
        <p className={`mt-1 text-2xl font-bold ${missingRef > 0 ? "text-amber-400" : "text-slate-300"}`}>
          {missingRef}
        </p>
      </Card>
      <Card className="p-4">
        <p className="text-xs uppercase tracking-widest text-mutedText">Collecting data</p>
        <p className="mt-1 text-2xl font-bold text-slate-300">{collecting}</p>
        {lastUpdate ? (
          <p className="mt-1 text-xs text-mutedText">Updated {fmtTime(lastUpdate)}</p>
        ) : null}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Events table
// ---------------------------------------------------------------------------

function EventsTable({ modelFilter }: { modelFilter: string }) {
  const query = useQuery({
    queryKey: ["mlops", "drift-events"],
    queryFn: () => getMlopsDriftEvents(100),
    refetchInterval: 60_000,
  });

  const events: DriftEvent[] = query.data?.events ?? [];
  const filtered = modelFilter
    ? events.filter((e) => e.model_name.toLowerCase().includes(modelFilter.toLowerCase()))
    : events;

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-white">Drift Event History</h3>
          <p className="text-xs text-mutedText">
            {query.data?.count ?? 0} total events — last 100 shown
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => void query.refetch()}>
          Refresh
        </Button>
      </div>

      {query.isLoading ? (
        <p className="py-4 text-sm text-mutedText">Loading events...</p>
      ) : filtered.length === 0 ? (
        <p className="py-6 text-center text-sm text-mutedText">
          No drift events recorded yet. Events appear when a drift test triggers.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.22em] text-mutedText">
              <tr>
                <th className="pb-3 pr-4">Timestamp</th>
                <th className="pb-3 pr-4">Model</th>
                <th className="pb-3 pr-4">p-value</th>
                <th className="pb-3 pr-4">Severity</th>
                <th className="pb-3 pr-4">Window</th>
                <th className="pb-3">Recommendation</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((ev) => (
                <tr key={ev.drift_id} className="border-t border-border">
                  <td className="py-2.5 pr-4 text-xs text-mutedText">{fmtDateTime(ev.timestamp)}</td>
                  <td className="py-2.5 pr-4 font-mono text-xs text-slate-200">{ev.model_name}</td>
                  <td className="py-2.5 pr-4 font-mono text-xs text-red-300">
                    {ev.p_value.toFixed(4)}
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${driftSeverityBg(ev.severity)}`}>
                      {ev.severity}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 font-mono text-xs text-slate-300">{ev.window_size}</td>
                  <td className="py-2.5 text-xs text-slate-400">{ev.recommendation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function MlopsDriftPage() {
  usePageTitle("MLOps - Drift Detection");
  const navigate = useNavigate();
  const [modelFilter, setModelFilter] = useState("");

  const driftQuery = useQuery({
    queryKey: ["mlops", "drift"],
    queryFn: getMlopsDrift,
    refetchInterval: 30_000,
  });

  const models = driftQuery.data?.models ?? {};
  const anyDrift = Object.values(models).some((m) => m.is_drift);

  return (
    <div className="space-y-6">
      {/* Page controls */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-mutedText">
            Alibi Detect MMD &middot; window 500 &middot; p &lt; 0.01 &middot; refresh every 30 s
          </p>
          {driftQuery.data?.note ? (
            <p className="mt-1 text-xs text-amber-300">{driftQuery.data.note}</p>
          ) : null}
        </div>
        <Button variant="secondary" size="sm" onClick={() => void driftQuery.refetch()}>
          {driftQuery.isFetching ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      {/* Summary KPIs */}
      {driftQuery.isLoading ? (
        <p className="text-sm text-mutedText">Loading drift status...</p>
      ) : (
        <SummaryRow models={models} lastUpdate={driftQuery.data?.timestamp} />
      )}

      {/* Global drift alert banner */}
      {anyDrift && (
        <div className="flex items-center justify-between gap-4 rounded border border-red-700 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          <span>
            <span className="font-semibold">Distribution drift detected</span> on one or more
            production models. A retraining request must be approved before training starts.
          </span>
          <Button
            size="sm"
            onClick={() => navigate("/mlops/requests")}
            className="shrink-0"
          >
            View Retraining Requests →
          </Button>
        </div>
      )}

      {/* Model cards */}
      {!driftQuery.isLoading && (
        <div>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-widest text-mutedText">
            Model Status
          </h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {Object.values(models).length > 0 ? (
              Object.values(models).map((state) => (
                <ModelDriftCard
                  key={state.model_name}
                  state={state}
                  onRequestRetraining={() => navigate("/mlops/requests")}
                />
              ))
            ) : (
              <p className="col-span-3 py-6 text-center text-sm text-mutedText">
                drift-monitor is not reachable or has not collected data yet. Make sure the stack
                was started with <code className="font-mono">--profile drift</code>.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Events table with model filter */}
      <div>
        <div className="mb-3 flex items-center gap-4">
          <h3 className="text-sm font-semibold uppercase tracking-widest text-mutedText">
            Drift Events
          </h3>
          <input
            className="rounded border border-border bg-cardAlt px-3 py-1 text-xs text-slate-200 placeholder:text-mutedText focus:outline-none focus:ring-1 focus:ring-accent"
            placeholder="Filter by model..."
            value={modelFilter}
            onChange={(e) => setModelFilter(e.target.value)}
          />
        </div>
        <EventsTable modelFilter={modelFilter} />
      </div>
    </div>
  );
}
