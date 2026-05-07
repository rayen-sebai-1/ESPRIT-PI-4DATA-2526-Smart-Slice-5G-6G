import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ShieldCheck,
  Brain,
  BarChart2,
  ScanSearch,
  GitBranch,
  ChevronDown,
  Scale,
} from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageTitle } from "@/hooks/usePageTitle";
import {
  getXaiFigures,
  getXaiFigureObjectUrl,
  getFairnessMetrics,
  type XaiModelFigures,
  type FairnessMetrics,
} from "@/api/mlopsApi";

// ---------------------------------------------------------------------------
// Static metadata
// ---------------------------------------------------------------------------

const FIGURE_LABELS: Record<string, string> = {
  "confusion_matrix.png":      "Confusion Matrix",
  "roc_curve.png":             "ROC Curve",
  "feature_importance.png":    "Feature Importance",
  "shap_global_importance.png":"SHAP Global Importance",
  "prediction_vs_actual.png":  "Prediction vs Actual",
  "residuals_distribution.png":"Residuals Distribution",
  "train_loss_curve.png":      "Training Loss Curve",
  "val_mae_curve.png":         "Validation MAE Curve",
};

const MODEL_DISPLAY: Record<
  string,
  { label: string; badge: string; color: string; icon: typeof Brain }
> = {
  sla_5g:        { label: "SLA Adherence · 5G",          badge: "XGBoost · Binary",     color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300", icon: ShieldCheck },
  sla_6g:        { label: "SLA Adherence · 6G",          badge: "XGBoost · Binary",     color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300", icon: ShieldCheck },
  congestion_5g: { label: "Congestion Detection · 5G",   badge: "BiLSTM · Classifier",  color: "border-orange-500/30 bg-orange-500/10 text-orange-300",   icon: Brain },
  congestion_6g: { label: "Congestion Forecasting · 6G", badge: "LSTM · Regression",    color: "border-amber-500/30 bg-amber-500/10 text-amber-300",      icon: Brain },
  slice_type_5g: { label: "Slice Classification · 5G",   badge: "LightGBM · Multiclass",color: "border-sky-500/30 bg-sky-500/10 text-sky-300",            icon: GitBranch },
  slice_type_6g: { label: "Slice Classification · 6G",   badge: "XGBoost · Multiclass", color: "border-violet-500/30 bg-violet-500/10 text-violet-300",   icon: GitBranch },
};

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
// Colour scale: 0 → red, 0.5 → yellow, 1 → green  (HSL)
// ---------------------------------------------------------------------------
function metricColor(value: number): string {
  // clamp
  const v = Math.max(0, Math.min(1, value));
  // hue: 0 = red (0°), 1 = green (120°)
  const hue = Math.round(v * 120);
  return `hsl(${hue}, 72%, 42%)`;
}

// ---------------------------------------------------------------------------
// Fairness heatmap
// ---------------------------------------------------------------------------

function FairnessHeatmap({ modelName }: { modelName: string }) {
  const query = useQuery<FairnessMetrics>({
    queryKey: ["mlops", "xai", "fairness", modelName],
    queryFn: () => getFairnessMetrics(modelName),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  if (query.isLoading) {
    return <div className="h-28 animate-pulse rounded-xl bg-cardAlt" />;
  }

  if (query.isError || !query.data) {
    return (
      <p className="text-xs text-mutedText italic">
        Fairness metrics not available yet — re-train the model to generate them.
      </p>
    );
  }

  const { classes, precision, recall, f1 } = query.data;
  const METRICS = [
    { key: "precision", label: "Precision", values: precision },
    { key: "recall",    label: "Recall",    values: recall },
    { key: "f1",        label: "F1",        values: f1 },
  ];

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[320px] text-xs">
        <thead>
          <tr className="border-b border-border bg-cardAlt/60">
            <th className="px-3 py-2 text-left font-medium text-mutedText">Metric</th>
            {classes.map((cls) => (
              <th key={cls} className="px-3 py-2 text-center font-medium text-mutedText">
                {cls}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {METRICS.map(({ key, label, values }) => (
            <tr key={key} className="border-b border-border/50 last:border-0">
              <td className="px-3 py-2 font-semibold text-inkSecondary">{label}</td>
              {values.map((v, idx) => (
                <td key={idx} className="px-3 py-2 text-center">
                  <span
                    className="inline-block min-w-[3.5rem] rounded-md px-2 py-1 font-mono text-[11px] font-semibold text-white"
                    style={{ backgroundColor: metricColor(v) }}
                  >
                    {(v * 100).toFixed(1)}%
                  </span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
        if (!current) { URL.revokeObjectURL(url); return; }
        objUrl = url;
        setSrc(url);
      })
      .catch(() => { if (current) setError(true); });

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
  const [fairnessOpen, setFairnessOpen] = useState(true);
  const meta = MODEL_DISPLAY[model.model_name];
  const Icon = meta?.icon ?? ScanSearch;

  const sortedFigures = [...model.figures].sort(
    (a, b) => {
      const ai = FIGURE_ORDER.indexOf(a);
      const bi = FIGURE_ORDER.indexOf(b);
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    },
  );

  const hasFairness = model.has_fairness ?? false;

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
            <p className="mt-0.5 text-xs text-mutedText">
              run {model.run_id.slice(0, 8)}&hellip;
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {meta && (
            <span
              className={`hidden rounded-full border px-2.5 py-0.5 text-[10px] font-semibold sm:inline-flex ${meta.color}`}
            >
              {meta.badge}
            </span>
          )}
          <ChevronDown
            size={16}
            className={`shrink-0 text-mutedText transition-transform ${open ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {open && (
        <div className="space-y-5 px-5 pb-5">
          {/* XAI figures grid */}
          {sortedFigures.length > 0 && (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
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

          {/* Fairness heatmap */}
          {hasFairness && (
            <div className="space-y-3">
              <button
                onClick={() => setFairnessOpen((v) => !v)}
                className="flex w-full items-center gap-2 text-left"
              >
                <Scale size={14} className="text-accent shrink-0" />
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-inkSecondary">
                  Fairness — Per-Class Metrics
                </span>
                <ChevronDown
                  size={13}
                  className={`ml-auto text-mutedText transition-transform ${fairnessOpen ? "rotate-180" : ""}`}
                />
              </button>
              {fairnessOpen && <FairnessHeatmap modelName={model.model_name} />}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function TrustworthyAiPage() {
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

      {/* TAI principles banner */}
      <div className="grid gap-3 rounded-2xl border border-border bg-cardAlt/70 p-5 md:grid-cols-3">
        {[
          {
            icon: ScanSearch,
            title: "Transparency",
            body: "Every prediction is grounded in SHAP-ranked feature attributions auditable by operators.",
          },
          {
            icon: Scale,
            title: "Fairness",
            body: "Per-class precision · recall · F1 heatmaps expose differential performance across network slice types (eMBB / URLLC / mMTC), making bias explicit for SLA assurance decisions.",
          },
          {
            icon: BarChart2,
            title: "Accountability",
            body: "All figures and fairness metrics are versioned inside MLflow and stored in MinIO — permanently tied to the exact training run that produced them.",
          },
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

      {/* Legend for fairness colours */}
      <div className="flex items-center gap-3 rounded-xl border border-border bg-cardAlt/50 px-4 py-2.5">
        <Scale size={13} className="text-mutedText shrink-0" />
        <span className="text-xs text-mutedText">Fairness heatmap colour scale:</span>
        {[
          { label: "≥ 90 %", bg: metricColor(0.95) },
          { label: "70–89 %", bg: metricColor(0.75) },
          { label: "50–69 %", bg: metricColor(0.55) },
          { label: "< 50 %", bg: metricColor(0.2) },
        ].map(({ label, bg }) => (
          <div key={label} className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: bg }} />
            <span className="text-xs text-inkSecondary">{label}</span>
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
          description="Train at least one model — SHAP attributions, evaluation figures, and fairness metrics will appear here automatically."
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
