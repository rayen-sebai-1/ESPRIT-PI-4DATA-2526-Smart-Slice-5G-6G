import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, CircleAlert, CircleCheck, CircleHelp, RefreshCcw } from "lucide-react";

import { getMlopsTools, getMlopsToolsHealth } from "@/api/mlopsApi";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { usePageTitle } from "@/hooks/usePageTitle";
import type { MlopsServiceHealth } from "@/types/mlops";

function statusBadgeClass(status: MlopsServiceHealth): string {
  switch (status) {
    case "UP":
      return "bg-emerald-500/15 text-emerald-300";
    case "DOWN":
      return "bg-red-500/15 text-red-300";
    default:
      return "bg-slate-500/15 text-slate-300";
  }
}

function ServiceIcon({ status }: { status: MlopsServiceHealth }) {
  if (status === "UP") return <CircleCheck size={16} className="text-emerald-400" />;
  if (status === "DOWN") return <CircleAlert size={16} className="text-red-400" />;
  return <CircleHelp size={16} className="text-slate-400" />;
}

export function MonitoringToolsPage() {
  usePageTitle("Monitoring Tools");

  const toolsQuery = useQuery({
    queryKey: ["mlops", "tools"],
    queryFn: getMlopsTools,
    staleTime: 60_000,
  });
  const healthQuery = useQuery({
    queryKey: ["mlops", "tools", "health"],
    queryFn: getMlopsToolsHealth,
    refetchInterval: 30_000,
  });

  function refreshAll() {
    void toolsQuery.refetch();
    void healthQuery.refetch();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Monitoring Tools"
        title="Observability Tooling"
        description="Direct access to Grafana, Kibana, Prometheus, MLflow, MinIO, and other operational consoles exposed through the Kong gateway."
        actions={
          <Button variant="secondary" onClick={refreshAll}>
            <RefreshCcw size={16} />
            Refresh
          </Button>
        }
      />

      <Card className="p-5">
        <div className="flex flex-col gap-1">
          <h3 className="text-lg font-semibold text-white">Tool links</h3>
          <p className="text-sm text-mutedText">
            Open the external monitoring and platform consoles without mixing them with XAI model explanations.
          </p>
        </div>

        {toolsQuery.isLoading ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {[...Array(6)].map((_, index) => (
              <div key={index} className="h-28 animate-pulse rounded-2xl border border-border bg-cardAlt" />
            ))}
          </div>
        ) : null}

        {toolsQuery.isError ? (
          <div className="mt-4 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-200">
            Tool links unavailable. The dashboard backend could not load monitoring tool URLs.
          </div>
        ) : null}

        {toolsQuery.isSuccess ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {toolsQuery.data.tools.map((tool) => (
              <a
                key={tool.key}
                href={tool.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex min-h-32 items-start justify-between gap-3 rounded-2xl border border-border bg-cardAlt/70 p-4 transition hover:border-accent/40 hover:bg-cardAlt"
              >
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-white">{tool.name}</div>
                  <div className="mt-1 text-xs leading-5 text-mutedText">{tool.description}</div>
                  <div className="mt-3 break-all font-mono text-xs text-slate-400">{tool.url}</div>
                </div>
                <ArrowUpRight size={18} className="shrink-0 text-mutedText transition group-hover:text-accent" />
              </a>
            ))}
          </div>
        ) : null}
      </Card>

      <Card className="p-5">
        <div className="flex flex-col gap-1">
          <h3 className="text-lg font-semibold text-white">Service health</h3>
          <p className="text-sm text-mutedText">
            Live checks for tool endpoints, refreshed automatically every 30 seconds.
          </p>
        </div>

        {healthQuery.isLoading ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {[...Array(6)].map((_, index) => (
              <div key={index} className="h-24 animate-pulse rounded-2xl border border-border bg-cardAlt" />
            ))}
          </div>
        ) : null}

        {healthQuery.isError ? (
          <div className="mt-4 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-200">
            Service health unavailable. The dashboard backend could not check the monitoring services.
          </div>
        ) : null}

        {healthQuery.isSuccess ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {healthQuery.data.services.map((service) => (
              <div
                key={service.name}
                className="flex items-start justify-between gap-3 rounded-2xl border border-border bg-cardAlt/70 p-4"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <ServiceIcon status={service.status} />
                    {service.name}
                  </div>
                  <div className="mt-2 break-all font-mono text-xs text-slate-400">{service.url}</div>
                  {service.detail ? (
                    <div className="mt-2 text-xs leading-5 text-mutedText">{service.detail}</div>
                  ) : null}
                </div>
                <div className="shrink-0 text-right">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(service.status)}`}>
                    {service.status}
                  </span>
                  {service.latency_ms !== null ? (
                    <div className="mt-1 text-xs text-mutedText">{service.latency_ms} ms</div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
