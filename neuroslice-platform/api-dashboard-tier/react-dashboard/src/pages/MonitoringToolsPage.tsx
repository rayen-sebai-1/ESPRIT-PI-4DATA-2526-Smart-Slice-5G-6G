import { ExternalLink } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { usePageTitle } from "@/hooks/usePageTitle";

// Resolve a tool URL: prefer the explicit VITE_* env var, fall back to
// window.location.hostname with the default port so the page works in any
// deployment without requiring a .env override.
function toolUrl(envVar: string | undefined, defaultPort: number): string {
  if (envVar && envVar.trim() !== "") return envVar.trim();
  return `http://${window.location.hostname}:${defaultPort}`;
}

interface ToolLink {
  name: string;
  description: string;
  url: string;
  category: string;
  color: string;
}

const TOOLS: ToolLink[] = [
  {
    name: "Grafana",
    description: "Dashboards for InfluxDB and Prometheus metrics — network KPIs, AIOps signals, slice health.",
    url: toolUrl(import.meta.env.VITE_GRAFANA_URL, 3000),
    category: "Observability",
    color: "border-orange-500/30 bg-orange-500/10 text-orange-300",
  },
  {
    name: "Kibana",
    description: "Elasticsearch log explorer — prediction events, fault traces, and AIOps output index.",
    url: toolUrl(import.meta.env.VITE_KIBANA_URL, 5601),
    category: "Log Management",
    color: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  },
  {
    name: "MLflow",
    description: "Experiment tracking, run comparison, model registry and artifact browser.",
    url: toolUrl(import.meta.env.VITE_MLFLOW_URL, 5000),
    category: "MLOps",
    color: "border-blue-500/30 bg-blue-500/10 text-blue-300",
  },
  {
    name: "MinIO Console",
    description: "Object storage browser for model artifacts, ONNX exports, and training datasets.",
    url: toolUrl(import.meta.env.VITE_MINIO_URL, 9001),
    category: "Artifact Storage",
    color: "border-red-500/30 bg-red-500/10 text-red-300",
  },
  {
    name: "InfluxDB UI",
    description: "Time-series data explorer — raw telemetry, KPI buckets, and Flux query editor.",
    url: toolUrl(import.meta.env.VITE_INFLUXDB_URL, 8086),
    category: "Time-Series DB",
    color: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  },
  {
    name: "Prometheus",
    description: "Metrics scraper — service health, container stats, and alerting rule status.",
    url: toolUrl(import.meta.env.VITE_PROMETHEUS_URL, 9090),
    category: "Metrics",
    color: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  },
];

const CATEGORIES = [...new Set(TOOLS.map((t) => t.category))];

export function MonitoringToolsPage() {
  usePageTitle("Monitoring Tools");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Infrastructure"
        title="Monitoring Tools"
        description="Direct access to all observability, storage, and MLOps integrations used by the NeuroSlice platform."
      />

      <div className="rounded-2xl border border-border bg-cardAlt/70 px-5 py-4 text-sm text-slate-300">
        These links open the native UIs of each integrated service running in the Docker stack.
        Ports shown are the defaults — check your <code className="font-mono text-accent">.env</code> overrides
        if a service is not reachable.
      </div>

      {CATEGORIES.map((category) => (
        <section key={category}>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-mutedText">
            {category}
          </h3>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {TOOLS.filter((t) => t.category === category).map((tool) => (
              <Card key={tool.name} className="p-5 transition hover:border-accent/30">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-semibold text-white">{tool.name}</p>
                      <span
                        className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${tool.color}`}
                      >
                        {tool.category}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-inkSecondary">{tool.description}</p>
                    <code className="mt-2 inline-block text-xs text-mutedText">{tool.url}</code>
                  </div>
                </div>
                <a
                  href={tool.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl border border-border bg-cardAlt/70 px-4 py-2.5 text-sm text-slate-200 transition hover:border-accent/40 hover:bg-card hover:text-accent"
                >
                  <ExternalLink size={15} />
                  Open {tool.name}
                </a>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
