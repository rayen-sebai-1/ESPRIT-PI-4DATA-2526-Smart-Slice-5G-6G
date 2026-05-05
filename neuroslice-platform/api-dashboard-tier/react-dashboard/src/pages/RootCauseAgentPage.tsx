import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, ScanSearch, ShieldAlert } from "lucide-react";
import axios from "axios";

import { agentApi, type AgentDomain, type RcaScanResponse } from "@/api/agentApi";
import { liveApi } from "@/api/liveApi";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { usePageTitle } from "@/hooks/usePageTitle";

const DEFAULT_TIME_RANGE = { start: "-30m", stop: "now()" };
const DOMAIN_LABELS: Record<string, string> = {
  core: "Core",
  edge: "Edge",
  ran: "RAN",
};

interface LiveSliceOption {
  sliceId?: string;
  entityId?: string;
  domain?: string;
}

function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data;
    if (detail && typeof detail === "object") {
      const maybeMessage = (detail as { message?: string; detail?: unknown }).message;
      if (typeof maybeMessage === "string" && maybeMessage.trim()) {
        return maybeMessage;
      }
      const maybeDetail = (detail as { detail?: unknown }).detail;
      if (typeof maybeDetail === "string" && maybeDetail.trim()) {
        return maybeDetail;
      }
    }
    if (error.message) {
      return error.message;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error while running the RCA scan.";
}

export function RootCauseAgentPage() {
  usePageTitle("Root Cause Agent");

  const [selectedSliceId, setSelectedSliceId] = useState("");
  const [domain, setDomain] = useState<"" | AgentDomain>("");

  const entitiesQuery = useQuery({
    queryKey: ["live", "entities", "root-cause-selector"],
    queryFn: () => liveApi.getEntities(500),
    refetchInterval: 3000,
  });

  const availableSlices = useMemo(() => {
    const collected = new Map<string, LiveSliceOption>();
    for (const rawEntity of entitiesQuery.data?.items ?? []) {
      const entity = rawEntity as LiveSliceOption;
      const normalizedSliceId = String(entity.sliceId ?? "").trim();
      if (!normalizedSliceId || collected.has(normalizedSliceId)) {
        continue;
      }
      collected.set(normalizedSliceId, {
        sliceId: normalizedSliceId,
        entityId: String(entity.entityId ?? ""),
        domain: String(entity.domain ?? ""),
      });
    }

    return Array.from(collected.values()).sort((a, b) =>
      String(a.sliceId ?? "").localeCompare(String(b.sliceId ?? "")),
    );
  }, [entitiesQuery.data?.items]);

  useEffect(() => {
    if (!availableSlices.length) return;
    const currentStillExists = availableSlices.some((item) => item.sliceId === selectedSliceId);
    if (!selectedSliceId || !currentStillExists) {
      setSelectedSliceId(availableSlices[0].sliceId ?? "");
    }
  }, [availableSlices, selectedSliceId]);

  const mutation = useMutation<RcaScanResponse, unknown, { sliceId: string; domain: "" | AgentDomain }>({
    mutationFn: async ({ sliceId: id, domain: dom }) => {
      return agentApi.runRcaScan({
        slice_id: id,
        domain: dom === "" ? undefined : dom,
        time_range: DEFAULT_TIME_RANGE,
      });
    },
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = selectedSliceId.trim();
    if (!trimmed) {
      return;
    }
    mutation.mutate({ sliceId: trimmed, domain });
  };

  const result = mutation.data;
  const errorMessage = mutation.isError ? extractErrorMessage(mutation.error) : null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Agentic AI"
        title="Root Cause Agent"
        description="Run a manual RCA scan for a slice. The agent queries InfluxDB telemetry and Redis live state, then uses a local model to propose a root cause and corrective actions."
      />

      <Card className="p-6">
        <form className="grid gap-4 md:grid-cols-[2fr_1fr_auto]" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-[0.22em] text-mutedText" htmlFor="rca-entity">
              Slice ID to scan
            </label>
            <Select
              id="rca-entity"
              value={selectedSliceId}
              onChange={(event) => setSelectedSliceId(event.target.value)}
              disabled={entitiesQuery.isLoading || availableSlices.length === 0}
              required
            >
              {availableSlices.length === 0 ? (
                <option value="">
                  {entitiesQuery.isLoading ? "Loading live slice IDs..." : "No live slice ID available"}
                </option>
              ) : null}
              {availableSlices.map((item) => {
                const normalizedSliceId = item.sliceId ?? "";
                const domainLabel = DOMAIN_LABELS[item.domain ?? ""] ?? item.domain ?? "unknown";
                const entitySuffix = item.entityId && item.entityId !== normalizedSliceId
                  ? ` - ${item.entityId}`
                  : "";
                return (
                  <option key={normalizedSliceId} value={normalizedSliceId}>
                    {normalizedSliceId} - {domainLabel}
                    {entitySuffix}
                  </option>
                );
              })}
            </Select>
            <p className="text-xs text-mutedText">Selected scan target: {selectedSliceId || "N/A"}</p>
          </div>
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-[0.22em] text-mutedText" htmlFor="rca-domain">
              Domain (optional)
            </label>
            <Select
              id="rca-domain"
              value={domain}
              onChange={(event) => setDomain(event.target.value as "" | AgentDomain)}
            >
              <option value="">All</option>
              <option value="core">core</option>
              <option value="edge">edge</option>
              <option value="ran">ran</option>
            </Select>
          </div>
          <div className="flex items-end">
            <Button
              type="submit"
              disabled={mutation.isPending || selectedSliceId.trim().length === 0 || availableSlices.length === 0}
            >
              <ScanSearch size={16} />
              {mutation.isPending ? "Scan in progress..." : "Run scan"}
            </Button>
          </div>
        </form>
        {entitiesQuery.isError ? (
          <p className="mt-3 text-xs text-red-300">
            Live entity list is unavailable. Verify `api-bff-service` and Redis connectivity.
          </p>
        ) : null}
        <p className="mt-3 text-xs text-mutedText">
          Analysis window: last 30 minutes. The agent may take up to one minute depending on local Ollama model load.
        </p>
      </Card>

      {errorMessage ? (
        <Card className="border border-red-500/30 p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="text-red-400" size={20} />
            <div>
              <h3 className="text-sm font-semibold text-red-300">Scan failed</h3>
              <p className="mt-1 text-sm text-mutedText">{errorMessage}</p>
            </div>
          </div>
        </Card>
      ) : null}

      {result ? (
        <section className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-mutedText">
              <ShieldAlert size={14} className="text-accent" />
              Operational summary
            </div>
            <p className="mt-3 text-base leading-7 text-white">{result.summary}</p>
          </Card>

          <Card className="p-6">
            <h3 className="text-sm uppercase tracking-[0.22em] text-mutedText">Root cause</h3>
            <p className="mt-3 text-sm leading-7 text-slate-200">{result.rootCause}</p>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="p-6">
              <h3 className="text-sm uppercase tracking-[0.22em] text-mutedText">
                Affected entities ({result.affectedEntities.length})
              </h3>
              {result.affectedEntities.length === 0 ? (
                <p className="mt-3 text-sm text-mutedText">No explicitly affected entity.</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {result.affectedEntities.map((entity) => (
                    <li
                      key={entity}
                      className="rounded-xl border border-border bg-cardAlt px-3 py-2 text-sm text-slate-200"
                    >
                      {entity}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card className="p-6">
              <h3 className="text-sm uppercase tracking-[0.22em] text-mutedText">
                Recommended actions ({result.recommendedAction.length})
              </h3>
              {result.recommendedAction.length === 0 ? (
                <p className="mt-3 text-sm text-mutedText">No recommended action.</p>
              ) : (
                <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-200">
                  {result.recommendedAction.map((action, index) => (
                    <li key={`${index}-${action.slice(0, 16)}`}>{action}</li>
                  ))}
                </ol>
              )}
            </Card>
          </div>

          <Card className="p-6">
            <h3 className="text-sm uppercase tracking-[0.22em] text-mutedText">Evidence KPI</h3>
            <pre className="mt-3 max-h-[420px] overflow-auto rounded-2xl border border-border bg-cardAlt p-4 text-xs leading-5 text-slate-200">
              {JSON.stringify(result.evidenceKpis, null, 2)}
            </pre>
          </Card>
        </section>
      ) : null}
    </div>
  );
}
