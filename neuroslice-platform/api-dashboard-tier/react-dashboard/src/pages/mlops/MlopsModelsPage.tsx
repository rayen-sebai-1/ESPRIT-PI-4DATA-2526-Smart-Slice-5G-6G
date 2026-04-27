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
  usePageTitle("MLOps - Modeles");
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
    onError: () => setMessage("Echec de la promotion."),
  });

  const rollbackMutation = useMutation({
    mutationFn: rollbackMlopsModel,
    onSuccess: async (response) => {
      setMessage(response.detail);
      await queryClient.invalidateQueries({ queryKey: ["mlops"] });
    },
    onError: () => setMessage("Echec du rollback."),
  });

  if (modelsQuery.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Chargement des modeles...</div>;
  }

  if (modelsQuery.isError || !modelsQuery.data) {
    return (
      <EmptyState title="Modeles indisponibles" description="Le backend n'a pas pu lire la liste des modeles." />
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
      setMessage(`Validation rafraichie pour ${selected}.`);
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
              <h3 className="text-lg font-semibold text-white">Modeles disponibles</h3>
              <p className="text-sm text-mutedText">Lecture du registre + dossier promoted/.</p>
            </div>
            <Button variant="secondary" onClick={() => void modelsQuery.refetch()}>
              <RefreshCcw size={16} />
              Rafraichir
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
                    {row.promoted?.framework ?? row.registry?.framework ?? "framework inconnu"} ·{" "}
                    v{row.promoted?.version ?? row.registry?.version ?? "?"}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-5">
          {!selected ? (
            <p className="text-sm text-mutedText">Selectionne un modele pour voir le detail.</p>
          ) : detailQuery.isLoading || !detail ? (
            <p className="text-sm text-mutedText">Chargement du detail...</p>
          ) : (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-white">{detail.deployment_name}</h3>
                  <p className="text-sm text-mutedText">
                    Sante: <span className={healthClassName(detail.health)}>{healthLabel(detail.health)}</span>
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
                    Valider modele
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => void detailQuery.refetch()}
                  >
                    <RefreshCcw size={16} />
                    Rafraichir
                  </Button>
                  <Button
                    onClick={() => {
                      setAction("promote");
                      setMessage(null);
                    }}
                    disabled={readOnly || promoteMutation.isPending}
                  >
                    <Rocket size={16} />
                    Promouvoir
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
                  <h4 className="text-sm font-semibold text-white">Modele promu</h4>
                  {detail.promoted ? (
                    <dl className="mt-3 space-y-1 text-xs text-mutedText">
                      <Row label="Modele" value={detail.promoted.model_name} />
                      <Row label="Version" value={detail.promoted.version} />
                      <Row label="Framework" value={detail.promoted.framework} />
                      <Row label="Run id" value={detail.promoted.run_id} />
                      <Row label="Mis a jour" value={detail.promoted.updated_at} />
                      <Row
                        label="Artefact ONNX"
                        value={detail.promoted.artifact_available ? "disponible" : "absent"}
                      />
                    </dl>
                  ) : (
                    <p className="mt-3 text-xs text-mutedText">Pas de version promue.</p>
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
                      <Row label="Cree le" value={detail.registry.created_at} />
                    </dl>
                  ) : (
                    <p className="mt-3 text-xs text-mutedText">Pas d'entree dans le registry.</p>
                  )}
                </Card>
              </div>

              <Card className="p-4">
                <h4 className="text-sm font-semibold text-white">Metriques cles</h4>
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
        title="Promouvoir le modele ?"
        description={`Tu vas demander la promotion du modele "${selected}". Cette action est tracee.`}
        onConfirm={onConfirm}
        onCancel={() => setAction(null)}
        confirmLabel="Promouvoir"
      />
      <ConfirmModal
        open={action === "rollback"}
        title="Rollback du modele ?"
        description={`Tu vas demander un rollback du modele "${selected}". L'action est consideree dangereuse.`}
        onConfirm={onConfirm}
        onCancel={() => setAction(null)}
        confirmLabel="Rollback"
        destructive
      />
      <ConfirmModal
        open={action === "validate"}
        title="Valider la metadata ?"
        description={`Re-lecture des metadonnees pour "${selected}". Aucune modification cote serveur.`}
        onConfirm={onConfirm}
        onCancel={() => setAction(null)}
        confirmLabel="Valider"
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
