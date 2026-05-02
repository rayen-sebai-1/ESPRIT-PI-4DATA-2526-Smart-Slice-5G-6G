import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useOutletContext } from "react-router-dom";
import { RefreshCcw, Rocket, Undo2, ShieldCheck } from "lucide-react";

import {
  getMlopsModel,
  getMlopsModels,
  promoteMlopsModel,
  rollbackMlopsModel,
} from "@/api/mlopsApi";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmModal } from "@/components/ui/confirm-modal";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageTitle } from "@/hooks/usePageTitle";
import { formatMetric, healthClassName, healthLabel } from "./mlopsHelpers";

type Action = "promote" | "rollback" | "validate" | null;

interface MlopsContext {
  readOnly: boolean;
}

export function MlopsModelsPage() {
  usePageTitle("MLOps - Models");
  const { readOnly } = useOutletContext<MlopsContext>();
  const queryClient = useQueryClient();

  const modelsQuery = useQuery({ queryKey: ["mlops", "models"], queryFn: getMlopsModels });
  const [selected, setSelected] = useState<string | null>(null);
  const [action, setAction] = useState<Action>(null);
  const [message, setMessage] = useState<string | null>(null);

  const detailQuery = useQuery({
    queryKey: ["mlops", "models", selected],
    queryFn: () => getMlopsModel(selected as string),
    enabled: Boolean(selected),
  });

  const promoteMutation = useMutation({
    mutationFn: promoteMlopsModel,
    onSuccess: async (response) => {
      setMessage(response.detail);
      await queryClient.invalidateQueries({ queryKey: ["mlops"] });
    },
    onError: () => setMessage("Promotion failed."),
  });

  const rollbackMutation = useMutation({
    mutationFn: rollbackMlopsModel,
    onSuccess: async (response) => {
      setMessage(response.detail);
      await queryClient.invalidateQueries({ queryKey: ["mlops"] });
    },
    onError: () => setMessage("Rollback failed."),
  });

  if (modelsQuery.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Loading models...</div>;
  }

  if (modelsQuery.isError || !modelsQuery.data) {
    return (
      <EmptyState title="Models unavailable" description="The backend could not read the models list." />
    );
  }

  const onConfirm = () => {
    if (!selected || !action) return;
    if (action === "promote") {
      promoteMutation.mutate({ model_name: selected });
    }
    if (action === "rollback") {
      rollbackMutation.mutate({ model_name: selected });
    }
    if (action === "validate") {
      void queryClient.invalidateQueries({ queryKey: ["mlops", "models", selected] });
      setMessage(`Validation refreshed for ${selected}.`);
    }
    setAction(null);
  };

  const detail = detailQuery.data;

  return (
    <div className="space-y-6">
      {message ? <Card className="px-4 py-3 text-sm text-slate-200">{message}</Card> : null}

      <div className="grid gap-6 xl:grid-cols-[0.6fr_1fr]">
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">Available models</h3>
              <p className="text-sm text-mutedText">Reading registry + promoted/ folder.</p>
            </div>
            <Button variant="secondary" onClick={() => void modelsQuery.refetch()}>
              <RefreshCcw size={16} />
              Refresh
            </Button>
          </div>
          <ul className="space-y-2">
            {modelsQuery.data.map((row) => (
              <li key={row.deployment_name}>
                <button
                  type="button"
                  onClick={() => setSelected(row.deployment_name)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                    selected === row.deployment_name
                      ? "border-accent bg-accent/10"
                      : "border-border bg-cardAlt/70 hover:border-accent/40"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-white">{row.deployment_name}</span>
                    <span className={healthClassName(row.health)}>{healthLabel(row.health)}</span>
                  </div>
                  <div className="mt-1 text-xs text-mutedText">
                    {row.promoted?.framework ?? row.registry?.framework ?? "unknown framework"} ·{" "}
                    v{row.promoted?.version ?? row.registry?.version ?? "?"}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-5">
          {!selected ? (
            <p className="text-sm text-mutedText">Select a model to view details.</p>
          ) : detailQuery.isLoading || !detail ? (
            <p className="text-sm text-mutedText">Loading details...</p>
          ) : (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-white">{detail.deployment_name}</h3>
                  <p className="text-sm text-mutedText">
                    Health: <span className={healthClassName(detail.health)}>{healthLabel(detail.health)}</span>
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setAction("validate");
                      setMessage(null);
                    }}
                  >
                    <ShieldCheck size={16} />
                    Validate model
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => void detailQuery.refetch()}
                  >
                    <RefreshCcw size={16} />
                    Refresh
                  </Button>
                  <Button
                    onClick={() => {
                      setAction("promote");
                      setMessage(null);
                    }}
                    disabled={readOnly || promoteMutation.isPending}
                  >
                    <Rocket size={16} />
                    Promote
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => {
                      setAction("rollback");
                      setMessage(null);
                    }}
                    disabled={readOnly || rollbackMutation.isPending}
                  >
                    <Undo2 size={16} />
                    Rollback
                  </Button>
                </div>
              </div>

              {detail.notes.length ? (
                <ul className="space-y-1 rounded-2xl border border-amber-400/30 bg-amber-500/10 p-3 text-xs text-amber-200">
                  {detail.notes.map((note) => (
                    <li key={note}>- {note}</li>
                  ))}
                </ul>
              ) : null}

              <div className="grid gap-4 md:grid-cols-2">
                <Card className="p-4">
                  <h4 className="text-sm font-semibold text-white">Promoted model</h4>
                  {detail.promoted ? (
                    <dl className="mt-3 space-y-1 text-xs text-mutedText">
                      <Row label="Model" value={detail.promoted.model_name} />
                      <Row label="Version" value={detail.promoted.version} />
                      <Row label="Framework" value={detail.promoted.framework} />
                      <Row label="Run id" value={detail.promoted.run_id} />
                      <Row label="Updated at" value={detail.promoted.updated_at} />
                      <Row
                        label="ONNX artifact"
                        value={detail.promoted.artifact_available ? "available" : "missing"}
                      />
                    </dl>
                  ) : (
                    <p className="mt-3 text-xs text-mutedText">No promoted version.</p>
                  )}
                </Card>

                <Card className="p-4">
                  <h4 className="text-sm font-semibold text-white">Dernier run (registry)</h4>
                  {detail.registry ? (
                    <dl className="mt-3 space-y-1 text-xs text-mutedText">
                      <Row label="Version" value={detail.registry.version} />
                      <Row label="Stage" value={detail.registry.stage} />
                      <Row label="Quality gate" value={detail.registry.quality_gate_status} />
                      <Row label="Promotion" value={detail.registry.promotion_status} />
                      <Row label="ONNX export" value={detail.registry.onnx_export_status} />
                      <Row label="Created at" value={detail.registry.created_at} />
                    </dl>
                  ) : (
                    <p className="mt-3 text-xs text-mutedText">No entry in registry.</p>
                  )}
                </Card>
              </div>

              <Card className="p-4">
                <h4 className="text-sm font-semibold text-white">Key metrics</h4>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  {Object.entries(detail.promoted?.metrics ?? detail.registry?.metrics ?? {}).map(
                    ([key, value]) => (
                      <div key={key} className="rounded-xl border border-border bg-cardAlt/70 p-3 text-xs">
                        <div className="text-mutedText">{key}</div>
                        <div className="mt-1 text-base font-semibold text-white">
                          {formatMetric(typeof value === "number" ? value : null)}
                        </div>
                      </div>
                    ),
                  )}
                </div>
              </Card>
            </div>
          )}
        </Card>
      </div>

      <ConfirmModal
        open={action === "promote"}
        title="Promote model?"
        description={`You are about to request promotion of model "${selected}". This action is logged.`}
        onConfirm={onConfirm}
        onCancel={() => setAction(null)}
        confirmLabel="Promote"
      />
      <ConfirmModal
        open={action === "rollback"}
        title="Rollback model?"
        description={`You are about to request rollback of model "${selected}". This action is considered risky.`}
        onConfirm={onConfirm}
        onCancel={() => setAction(null)}
        confirmLabel="Rollback"
        destructive
      />
      <ConfirmModal
        open={action === "validate"}
        title="Validate metadata?"
        description={`Re-reading metadata for "${selected}". No server-side modification.`}
        onConfirm={onConfirm}
        onCancel={() => setAction(null)}
        confirmLabel="Validate"
      />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex items-center justify-between">
      <dt>{label}</dt>
      <dd className="text-slate-100">{value === null || value === undefined ? "-" : String(value)}</dd>
    </div>
  );
}
