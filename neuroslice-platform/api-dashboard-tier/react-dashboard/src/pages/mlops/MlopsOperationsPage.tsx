import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useOutletContext } from "react-router-dom";
import {
  ArrowUpRight,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  Play,
  RefreshCcw,
  Terminal,
} from "lucide-react";

import {
  getMlopsPipelineRunLogs,
  getMlopsPipelineRuns,
  getMlopsTools,
  getMlopsToolsHealth,
  triggerMlopsPipeline,
} from "@/api/mlopsApi";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmModal } from "@/components/ui/confirm-modal";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageTitle } from "@/hooks/usePageTitle";
import { cn } from "@/lib/cn";
import type { MlopsPipelineRunResponse, MlopsServiceHealth, PipelineRunStatus } from "@/types/mlops";

interface MlopsContext {
  readOnly: boolean;
}

function statusBadgeClass(status: MlopsServiceHealth | PipelineRunStatus): string {
  switch (status) {
    case "UP":
    case "SUCCESS":
      return "bg-emerald-500/15 text-emerald-300";
    case "DOWN":
    case "FAILED":
    case "TIMEOUT":
      return "bg-red-500/15 text-red-300";
    case "RUNNING":
    case "QUEUED":
      return "bg-amber-500/15 text-amber-300";
    case "DISABLED":
      return "bg-slate-500/15 text-slate-300";
    default:
      return "bg-slate-500/15 text-slate-300";
  }
}

function ServiceIcon({ status }: { status: MlopsServiceHealth }) {
  if (status === "UP") return <CircleCheck size={16} className="text-emerald-400" />;
  if (status === "DOWN") return <CircleAlert size={16} className="text-red-400" />;
  return <CircleHelp size={16} className="text-slate-400" />;
}

export function MlopsOperationsPage() {
  usePageTitle("MLOps - Operations");
  const { readOnly } = useOutletContext<MlopsContext>();
  const queryClient = useQueryClient();

  const toolsQuery = useQuery({ queryKey: ["mlops", "tools"], queryFn: getMlopsTools });
  const healthQuery = useQuery({
    queryKey: ["mlops", "tools", "health"],
    queryFn: getMlopsToolsHealth,
    refetchInterval: 30_000,
  });

  const runsQuery = useQuery({
    queryKey: ["mlops", "pipeline", "runs"],
    queryFn: () => getMlopsPipelineRuns(50),
    refetchInterval: (query) => {
      const data = query.state.data as MlopsPipelineRunResponse[] | undefined;
      const hasActive = data?.some((run) => run.status === "RUNNING" || run.status === "QUEUED");
      return hasActive ? 5_000 : 30_000;
    },
  });

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [logsRunId, setLogsRunId] = useState<string | null>(null);

  const triggerMutation = useMutation({
    mutationFn: triggerMlopsPipeline,
    onSuccess: async (response) => {
      setMessage(`Pipeline lance (run ${response.run_id.slice(0, 8)}).`);
      await queryClient.invalidateQueries({ queryKey: ["mlops", "pipeline", "runs"] });
    },
    onError: (error) => {
      const detail =
        // axios error -> response.data.detail
        (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
        ?? "Echec du lancement du pipeline.";
      setMessage(detail);
    },
  });

  return (
    <div className="space-y-6">
      {message ? (
        <Card className="px-4 py-3 text-sm text-slate-200">{message}</Card>
      ) : null}

      {/* A. Tool links */}
      <Card className="p-5">
        <h3 className="text-lg font-semibold text-white">Outils MLOps</h3>
        <p className="text-sm text-mutedText">
          Ouvre les UIs externes (lien direct, ne traverse pas le backend).
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {toolsQuery.data?.tools.map((tool) => (
            <a
              key={tool.key}
              href={tool.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start justify-between gap-3 rounded-2xl border border-border bg-cardAlt/70 p-4 transition hover:border-accent/40"
            >
              <div>
                <div className="text-sm font-semibold text-white">{tool.name}</div>
                <div className="mt-1 text-xs text-mutedText">{tool.description}</div>
                <div className="mt-2 font-mono text-xs text-slate-400">{tool.url}</div>
              </div>
              <ArrowUpRight size={18} className="text-mutedText transition group-hover:text-accent" />
            </a>
          )) ?? null}
        </div>
      </Card>

      {/* B. Service health */}
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Sante des services</h3>
            <p className="text-sm text-mutedText">
              Sondage cote dashboard-backend (auto-refresh toutes les 30 s).
            </p>
          </div>
          <Button variant="secondary" onClick={() => void healthQuery.refetch()}>
            <RefreshCcw size={16} />
            Rafraichir
          </Button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {healthQuery.data?.services.map((service) => (
            <div
              key={service.name}
              className="flex items-start justify-between rounded-2xl border border-border bg-cardAlt/70 p-4"
            >
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-white">
                  <ServiceIcon status={service.status} />
                  {service.name}
                </div>
                <div className="mt-1 font-mono text-xs text-slate-400">{service.url}</div>
                {service.detail ? (
                  <div className="mt-1 text-xs text-mutedText">{service.detail}</div>
                ) : null}
              </div>
              <div className="text-right">
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-medium",
                    statusBadgeClass(service.status),
                  )}
                >
                  {service.status}
                </span>
                {service.latency_ms !== null ? (
                  <div className="mt-1 text-xs text-mutedText">{service.latency_ms} ms</div>
                ) : null}
              </div>
            </div>
          )) ?? null}
        </div>
      </Card>

      {/* C. Pipeline control */}
      <Card className="p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Pipeline offline</h3>
            <p className="text-sm text-mutedText">
              Lance la sequence: training, MLflow, ONNX export, FP16, promotion.
            </p>
          </div>
          <Button
            onClick={() => {
              setMessage(null);
              setConfirmOpen(true);
            }}
            disabled={readOnly || triggerMutation.isPending}
          >
            <Play size={16} />
            Run Offline MLOps Pipeline
          </Button>
        </div>
      </Card>

      {/* D. Pipeline runs */}
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Historique des executions</h3>
          <Button variant="secondary" onClick={() => void runsQuery.refetch()}>
            <RefreshCcw size={16} />
            Rafraichir
          </Button>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.22em] text-mutedText">
              <tr>
                <th className="pb-3 pr-4">Run</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4">Trigger</th>
                <th className="pb-3 pr-4">Demarre</th>
                <th className="pb-3 pr-4">Duree</th>
                <th className="pb-3 pr-4">Exit</th>
                <th className="pb-3 pr-4">Actions</th>
              </tr>
            </thead>
            <tbody className="text-slate-100">
              {runsQuery.data?.map((run) => (
                <tr key={run.run_id} className="border-t border-border">
                  <td className="py-3 pr-4 font-mono text-xs">{run.run_id.slice(0, 8)}</td>
                  <td className="py-3 pr-4">
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        statusBadgeClass(run.status),
                      )}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-mutedText">{run.triggered_by_email ?? "-"}</td>
                  <td className="py-3 pr-4 text-mutedText">{run.started_at ?? "-"}</td>
                  <td className="py-3 pr-4">
                    {run.duration_seconds !== null
                      ? `${Math.round(run.duration_seconds)} s`
                      : "-"}
                  </td>
                  <td className="py-3 pr-4">{run.exit_code ?? "-"}</td>
                  <td className="py-3 pr-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setLogsRunId(run.run_id)}
                    >
                      <Terminal size={14} />
                      Logs
                    </Button>
                  </td>
                </tr>
              ))}
              {(runsQuery.data?.length ?? 0) === 0 ? (
                <tr>
                  <td className="py-6 text-center text-mutedText" colSpan={7}>
                    Aucune execution enregistree.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Card>

      {toolsQuery.isError && healthQuery.isError ? (
        <EmptyState
          title="Operations indisponibles"
          description="Le backend n'a pas pu repondre. Verifie la connexion et le token."
        />
      ) : null}

      <ConfirmModal
        open={confirmOpen}
        title="Lancer le pipeline offline ?"
        description="Cela va demarrer le training, le logging MLflow, l'export ONNX, la conversion FP16 et la promotion. L'execution peut durer plusieurs minutes."
        confirmLabel="Lancer"
        destructive
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false);
          triggerMutation.mutate();
        }}
      />

      <PipelineLogsModal runId={logsRunId} onClose={() => setLogsRunId(null)} />
    </div>
  );
}

function PipelineLogsModal({ runId, onClose }: { runId: string | null; onClose: () => void }) {
  const enabled = runId !== null;
  const logsQuery = useQuery({
    queryKey: ["mlops", "pipeline", "logs", runId],
    queryFn: () => getMlopsPipelineRunLogs(runId as string),
    enabled,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      return data.status === "RUNNING" || data.status === "QUEUED" ? 4_000 : false;
    },
  });

  useEffect(() => {
    if (!enabled) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled, onClose]);

  if (!enabled) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
      <Card className="w-full max-w-4xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Logs pipeline</h3>
            <p className="font-mono text-xs text-mutedText">{runId}</p>
          </div>
          <Button variant="secondary" onClick={onClose}>
            Fermer
          </Button>
        </div>
        {logsQuery.isLoading ? (
          <p className="mt-4 text-sm text-mutedText">Chargement...</p>
        ) : logsQuery.isError || !logsQuery.data ? (
          <p className="mt-4 text-sm text-red-300">Logs indisponibles.</p>
        ) : (
          <div className="mt-4 space-y-3">
            <div className="text-xs uppercase tracking-[0.22em] text-mutedText">
              Status: {logsQuery.data.status}
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-mutedText">stdout</div>
              <pre className="mt-1 max-h-64 overflow-auto rounded-xl border border-border bg-black/40 p-3 font-mono text-xs text-slate-200">
                {logsQuery.data.stdout || "(vide)"}
              </pre>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-mutedText">stderr</div>
              <pre className="mt-1 max-h-64 overflow-auto rounded-xl border border-border bg-black/40 p-3 font-mono text-xs text-red-200">
                {logsQuery.data.stderr || "(vide)"}
              </pre>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
