import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, Brain, BarChart2, ScanSearch, GitBranch, ChevronDown } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageTitle } from "@/hooks/usePageTitle";
import { getXaiFigures, getXaiFigureObjectUrl, type XaiModelFigures } from "@/api/mlopsApi";


// Resolve a tool URL: prefer explicit VITE_* env var, otherwise default to
// Kong-routed same-origin subpaths.
function toolUrl(envVar: string | undefined, defaultPath: string): string {
  if (envVar && envVar.trim() !== "") return envVar.trim();
  return `${window.location.origin}${defaultPath}`;
}

// ---------------------------------------------------------------------------
// Static metadata
// ---------------------------------------------------------------------------


const FIGURE_LABELS: Record<string, string> = {
  "confusion_matrix.png": "Confusion Matrix",
  "roc_curve.png": "ROC Curve",
  "feature_importance.png": "Feature Importance",
  "shap_global_importance.png": "SHAP Global Importance",
  "prediction_vs_actual.png": "Prediction vs Actual",
  "residuals_distribution.png": "Residuals Distribution",
  "train_loss_curve.png": "Training Loss Curve",
  "val_mae_curve.png": "Validation MAE Curve",
};

const MODEL_DISPLAY: Record<string, { label: string; badge: string; color: string; icon: typeof Brain }> = {
  sla_5g:         { label: "SLA Adherence · 5G",      badge: "XGBoost · Classifier",  color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300", icon: ShieldCheck },
  sla_6g:         { label: "SLA Adherence · 6G",      badge: "XGBoost · Classifier",  color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300", icon: ShieldCheck },
  congestion_5g:  { label: "Congestion Detection · 5G", badge: "LSTM · Classifier",   color: "border-orange-500/30 bg-orange-500/10 text-orange-300",   icon: Brain },
  congestion_6g:  { label: "Congestion Forecasting · 6G", badge: "LSTM · Regression", color: "border-amber-500/30 bg-amber-500/10 text-amber-300",   icon: Brain },
  slice_type_5g:  { label: "Slice Classification · 5G", badge: "LightGBM · Multiclass", color: "border-sky-500/30 bg-sky-500/10 text-sky-300",         icon: GitBranch },
  slice_type_6g:  { label: "Slice Classification · 6G", badge: "XGBoost · Multiclass",  color: "border-violet-500/30 bg-violet-500/10 text-violet-300", icon: GitBranch },
};

const TOOLS: ToolLink[] = [
  {
    name: "Grafana",
    description: "Dashboards for InfluxDB and Prometheus metrics - network KPIs, AIOps signals, slice health.",
    url: toolUrl(import.meta.env.VITE_GRAFANA_URL, "/grafana/"),
    category: "Observability",
    color: "border-orange-500/30 bg-orange-500/10 text-orange-300",
  },
  {
    name: "Kibana",
    description: "Elasticsearch log explorer - prediction events, fault traces, and AIOps output index.",
    url: toolUrl(import.meta.env.VITE_KIBANA_URL, "/kibana/"),
    category: "Log Management",
    color: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  },
  {
    name: "MLflow",
    description: "Experiment tracking, run comparison, model registry and artifact browser.",
    url: toolUrl(import.meta.env.VITE_MLFLOW_URL, "/mlflow/"),
    category: "MLOps",
    color: "border-blue-500/30 bg-blue-500/10 text-blue-300",
  },
  {
    name: "MinIO Console",
    description: "Object storage browser for model artifacts, ONNX exports, and training datasets.",
    url: toolUrl(import.meta.env.VITE_MINIO_URL, "/minio/"),
    category: "Artifact Storage",
    color: "border-red-500/30 bg-red-500/10 text-red-300",
  },
  {
    name: "InfluxDB UI",
    description: "Time-series data explorer - raw telemetry, KPI buckets, and Flux query editor.",
    url: toolUrl(import.meta.env.VITE_INFLUXDB_URL, "/influxdb/"),
    category: "Time-Series DB",
    color: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  },
  {
    name: "Prometheus",
    description: "Metrics scraper - service health, container stats, and alerting rule status.",
    url: toolUrl(import.meta.env.VITE_PROMETHEUS_URL, "/prometheus/"),
    category: "Metrics",
    color: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  },

const FIGURE_ORDER = [
  "shap_global_importance.png",
  "feature_importance.png",
  "confusion_matrix.png",
  "roc_curve.png",
  "prediction_vs_actual.png",
  "residuals_distribution.png",
  "train_loss_curve.png",
  "val_mae_curve.png",
];

// ---------------------------------------------------------------------------
// Authenticated image component (fetches via JWT then creates a blob URL)
// ---------------------------------------------------------------------------

function XaiFigure({ modelName, figure }: { modelName: string; figure: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let current = true;
    let objUrl: string | null = null;

    getXaiFigureObjectUrl(modelName, figure)
      .then((url) => {
        if (!current) {
          URL.revokeObjectURL(url);
          return;
        }
        objUrl = url;
        setSrc(url);
      })
      .catch(() => {
        if (current) setError(true);
      });

    return () => {
      current = false;
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
  }, [modelName, figure]);

  if (error) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl bg-cardAlt text-xs text-mutedText">
        Figure unavailable
      </div>
    );
  }

  if (!src) {
    return <div className="h-40 animate-pulse rounded-xl bg-cardAlt" />;
  }

  return (
    <img
      src={src}
      alt={FIGURE_LABELS[figure] ?? figure}
      className="w-full rounded-xl object-contain"
    />
  );
}

// ---------------------------------------------------------------------------
// Per-model accordion card
// ---------------------------------------------------------------------------

function ModelCard({ model }: { model: XaiModelFigures }) {
  const [open, setOpen] = useState(true);
  const meta = MODEL_DISPLAY[model.model_name];
  const Icon = meta?.icon ?? ScanSearch;

  const sortedFigures = [...model.figures].sort(
    (a, b) => FIGURE_ORDER.indexOf(a) - FIGURE_ORDER.indexOf(b),
  );

  return (
    <Card className="overflow-hidden p-0">
      {/* Header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-cardAlt/40"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accentSoft text-ink">
            <Icon size={18} />
          </div>
          <div>
            <p className="font-semibold text-white">{meta?.label ?? model.model_name}</p>
            <p className="mt-0.5 text-xs text-mutedText">run {model.run_id.slice(0, 8)}&hellip;</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {meta && (
            <span className={`hidden rounded-full border px-2.5 py-0.5 text-[10px] font-semibold sm:inline-flex ${meta.color}`}>
              {meta.badge}
            </span>
          )}
          <ChevronDown
            size={16}
            className={`shrink-0 text-mutedText transition-transform ${open ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {/* Figure grid */}
      {open && (
        <div className="grid gap-4 p-5 pt-0 md:grid-cols-2 xl:grid-cols-3">
          {sortedFigures.map((fig) => (
            <div key={fig} className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-mutedText">
                {FIGURE_LABELS[fig] ?? fig}
              </p>
              <XaiFigure modelName={model.model_name} figure={fig} />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function MonitoringToolsPage() {
  usePageTitle("Trustworthy AI");

  const query = useQuery({
    queryKey: ["mlops", "xai", "figures"],
    queryFn: getXaiFigures,
    staleTime: 5 * 60 * 1000,
  });

  const sorted = (query.data ?? []).sort((a, b) => {
    const order = Object.keys(MODEL_DISPLAY);
    const ai = order.indexOf(a.model_name);
    const bi = order.indexOf(b.model_name);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Trustworthy AI"
        title="XAI Model Explainability"
        description="SHAP attributions, feature importances, confusion matrices and performance curves — exported from the last MLflow training run for every model."
      />

      <div className="rounded-2xl border border-border bg-cardAlt/70 px-5 py-4 text-sm text-slate-300">
        These links open tool UIs through Kong gateway routes. If needed, override
        individual URLs with <code className="font-mono text-accent">VITE_*_URL</code> variables.

      {/* Trustworthy-AI principles banner */}
      <div className="grid gap-3 rounded-2xl border border-border bg-cardAlt/70 p-5 md:grid-cols-3">
        {[
          { icon: ScanSearch,  title: "Transparency",   body: "Every prediction is grounded in SHAP-ranked feature attributions auditable by operators." },
          { icon: ShieldCheck, title: "Fairness",        body: "Confusion matrices expose per-class errors so bias across network slices can be detected." },
          { icon: BarChart2,   title: "Accountability",  body: "Figures are versioned inside MLflow and stored in MinIO — tied to the exact run that produced them." },
        ].map(({ icon: Icon, title, body }) => (
          <div key={title} className="flex gap-3">
            <div className="mt-0.5 shrink-0 text-accent">
              <Icon size={16} />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">{title}</p>
              <p className="mt-1 text-xs leading-5 text-inkSecondary">{body}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Content */}
      {query.isLoading && (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-2xl border border-border bg-cardAlt" />
          ))}
        </div>
      )}

      {query.isError && (
        <EmptyState
          title="XAI figures unavailable"
          description="The backend could not retrieve figures from MLflow. Make sure MLFLOW_TRACKING_URI is set to an HTTP address and models have been trained at least once."
        />
      )}

      {query.isSuccess && sorted.length === 0 && (
        <EmptyState
          title="No XAI figures yet"
          description="Train at least one model and its SHAP / evaluation figures will appear here automatically."
        />
      )}

      {query.isSuccess && sorted.length > 0 && (
        <div className="space-y-4">
          {sorted.map((model) => (
            <ModelCard key={model.model_name} model={model} />
          ))}
        </div>
      )}
    </div>
  );
}
