import { BookOpenText, Bot, FileWarning, PackageSearch } from "lucide-react";

import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import type { ModelInfoResponse } from "@/types/prediction";

export function ModelsCatalog({
  models,
  isLoading,
  isError,
}: {
  models: ModelInfoResponse[] | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return <Card className="p-6 text-sm text-mutedText">Loading model catalogue...</Card>;
  }

  if (isError) {
    return (
      <EmptyState
        title="Catalogue unavailable"
        description="The backend exposes the catalogue concept, but the /models endpoint is currently returning an error."
        icon={<FileWarning size={24} />}
      />
    );
  }

  if (!models?.length) {
    return (
      <EmptyState
        title="No models available"
        description="No models are currently visible from the prediction service."
        icon={<PackageSearch size={24} />}
      />
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {models.map((model) => (
        <Card key={model.name} className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-lg font-semibold text-white">{model.name}</div>
              <p className="mt-2 text-sm leading-6 text-mutedText">{model.purpose}</p>
            </div>
            <div className="rounded-3xl bg-accentSoft p-3 text-accent">
              <Bot size={20} />
            </div>
          </div>

          <div className="mt-5 grid gap-3">
            <div className="rounded-2xl border border-border bg-cardAlt/70 px-4 py-3">
              <div className="text-xs uppercase tracking-[0.22em] text-mutedText">Implementation</div>
              <div className="mt-2 text-sm text-white">{model.implementation}</div>
            </div>
            <div className="rounded-2xl border border-border bg-cardAlt/70 px-4 py-3">
              <div className="text-xs uppercase tracking-[0.22em] text-mutedText">Status</div>
              <div className="mt-2 text-sm text-white">{model.status}</div>
            </div>
            <div className="rounded-2xl border border-border bg-cardAlt/70 px-4 py-3">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-mutedText">
                <BookOpenText size={14} />
                Notebook source
              </div>
              <div className="mt-2 text-sm text-white">{model.source_notebook}</div>
            </div>
            <div className="rounded-2xl border border-border bg-cardAlt/70 px-4 py-3">
              <div className="text-xs uppercase tracking-[0.22em] text-mutedText">Artifact</div>
              <div className="mt-2 text-sm text-white">{model.artifact_path ?? "Not yet exported"}</div>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
