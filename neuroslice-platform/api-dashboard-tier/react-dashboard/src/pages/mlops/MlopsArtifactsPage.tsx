import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";

import { getMlopsArtifacts } from "@/api/mlopsApi";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageTitle } from "@/hooks/usePageTitle";

function StatusIcon({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckCircle2 size={16} className="text-emerald-400" />
  ) : (
    <XCircle size={16} className="text-amber-400" />
  );
}

export function MlopsArtifactsPage() {
  usePageTitle("MLOps - Artefacts");
  const query = useQuery({ queryKey: ["mlops", "artifacts"], queryFn: getMlopsArtifacts });

  if (query.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Chargement des artefacts...</div>;
  }
  if (query.isError || !query.data) {
    return <EmptyState title="Artefacts indisponibles" description="Echec de la lecture du dossier promoted/." />;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {query.data.map((artifact) => (
        <Card key={artifact.deployment_name} className="p-5">
          <h3 className="text-base font-semibold text-white">{artifact.deployment_name}</h3>
          <ul className="mt-4 space-y-2 text-sm text-slate-100">
            <li className="flex items-center gap-2">
              <StatusIcon ok={artifact.has_metadata} /> metadata.json
            </li>
            <li className="flex items-center gap-2">
              <StatusIcon ok={artifact.has_onnx} /> model.onnx
            </li>
            <li className="flex items-center gap-2">
              <StatusIcon ok={artifact.has_onnx_fp16} /> model_fp16.onnx
            </li>
          </ul>
          <div className="mt-3 text-xs text-mutedText">
            {artifact.files.length} fichiers detectes sous /current
          </div>
        </Card>
      ))}
      {query.data.length === 0 ? (
        <EmptyState title="Aucun artefact" description="Aucun modele promu n'a ete trouve." />
      ) : null}
    </div>
  );
}
