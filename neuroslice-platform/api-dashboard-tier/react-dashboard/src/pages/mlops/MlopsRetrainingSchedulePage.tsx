import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Pencil, RefreshCcw, Trash2 } from "lucide-react";
import { useOutletContext } from "react-router-dom";

import {
  createMlopsRetrainingSchedule,
  deleteMlopsRetrainingSchedule,
  getMlopsRetrainingSchedules,
  updateMlopsRetrainingSchedule,
} from "@/api/mlopsApi";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmModal } from "@/components/ui/confirm-modal";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/useAuth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { cn } from "@/lib/cn";
import type {
  MlopsRetrainingSchedule,
  MlopsRetrainingScheduleFrequency,
  MlopsRetrainingScheduleUpsertPayload,
} from "@/types/mlops";

interface MlopsContext {
  readOnly: boolean;
}

type PendingAction =
  | { kind: "delete"; schedule: MlopsRetrainingSchedule }
  | { kind: "disable"; schedule: MlopsRetrainingSchedule };

const MODEL_OPTIONS = ["congestion-5g", "sla-5g", "slice-type-5g"] as const;
const TIMEZONE_OPTIONS = ["UTC", "Africa/Tunis", "Europe/Paris", "America/New_York", "Asia/Dubai"] as const;

function statusBadgeClass(status: MlopsRetrainingSchedule["status"]): string {
  if (status === "ACTIVE") return "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30";
  if (status === "DISABLED") return "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/25";
  return "bg-red-500/15 text-red-300 ring-1 ring-red-500/30";
}

function fmtDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function cronFromForm(form: FormState): string {
  const hh = form.hour.padStart(2, "0");
  const mm = form.minute.padStart(2, "0");
  if (form.frequency === "DAILY") return `${mm} ${hh} * * *`;
  if (form.frequency === "WEEKLY") return `${mm} ${hh} * * ${form.dayOfWeek}`;
  if (form.frequency === "MONTHLY") return `${mm} ${hh} ${form.dayOfMonth} * *`;
  return form.customCron.trim();
}

type FormState = {
  id: string | null;
  model_name: string;
  enabled: boolean;
  frequency: MlopsRetrainingScheduleFrequency;
  timezone: string;
  require_approval: boolean;
  allow_duplicate_enabled: boolean;
  hour: string;
  minute: string;
  dayOfWeek: string;
  dayOfMonth: string;
  customCron: string;
};

const INITIAL_FORM: FormState = {
  id: null,
  model_name: MODEL_OPTIONS[0],
  enabled: true,
  frequency: "DAILY",
  timezone: "UTC",
  require_approval: false,
  allow_duplicate_enabled: false,
  hour: "02",
  minute: "00",
  dayOfWeek: "0",
  dayOfMonth: "1",
  customCron: "0 2 * * 0",
};

function hydrateForm(item: MlopsRetrainingSchedule): FormState {
  const next: FormState = {
    ...INITIAL_FORM,
    id: item.id,
    model_name: item.model_name,
    enabled: item.enabled,
    frequency: item.frequency,
    timezone: item.timezone,
    require_approval: item.require_approval,
    customCron: item.cron_expr,
  };
  const parts = item.cron_expr.split(/\s+/);
  if (parts.length >= 5) {
    next.minute = parts[0];
    next.hour = parts[1];
    next.dayOfMonth = parts[2];
    next.dayOfWeek = parts[4];
  }
  return next;
}

export function MlopsRetrainingSchedulePage() {
  usePageTitle("MLOps — Retraining Schedule");
  const { user } = useAuth();
  const { readOnly } = useOutletContext<MlopsContext>();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);

  const canWrite = !readOnly && (user?.role === "ADMIN" || user?.role === "DATA_MLOPS_ENGINEER");
  const query = useQuery({
    queryKey: ["mlops", "retraining-schedule"],
    queryFn: getMlopsRetrainingSchedules,
    refetchInterval: 30_000,
  });

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["mlops", "retraining-schedule"] });
  };

  const createMutation = useMutation({
    mutationFn: createMlopsRetrainingSchedule,
    onSuccess: () => {
      toast.success("Schedule created.");
      setForm(INITIAL_FORM);
      void invalidate();
    },
    onError: (err) => {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Could not create schedule.";
      toast.error(detail);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<MlopsRetrainingScheduleUpsertPayload> }) =>
      updateMlopsRetrainingSchedule(id, payload),
    onSuccess: () => {
      toast.success("Schedule saved.");
      setForm(INITIAL_FORM);
      void invalidate();
    },
    onError: (err) => {
      const statusCode = (err as { response?: { status?: number } }).response?.status;
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Could not save schedule.";
      if (statusCode === 404) {
        void invalidate();
      }
      toast.error(detail);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteMlopsRetrainingSchedule,
    onSuccess: () => {
      toast.info("Schedule deleted.");
      void invalidate();
    },
    onError: (err) => {
      const statusCode = (err as { response?: { status?: number } }).response?.status;
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Could not delete schedule.";
      if (statusCode === 404) {
        void invalidate();
      }
      toast.error(detail);
    },
  });

  const busy = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;
  const schedules = useMemo(() => query.data?.items ?? [], [query.data?.items]);

  function submitForm() {
    const payload = {
      model_name: form.model_name,
      enabled: form.enabled,
      frequency: form.frequency,
      cron_expr: cronFromForm(form),
      timezone: form.timezone,
      require_approval: form.require_approval,
      allow_duplicate_enabled: form.allow_duplicate_enabled,
    };
    if (form.id) {
      updateMutation.mutate({ id: form.id, payload });
      return;
    }
    createMutation.mutate(payload);
  }

  function onEnableToggle(item: MlopsRetrainingSchedule) {
    if (item.enabled) {
      setPendingAction({ kind: "disable", schedule: item });
      return;
    }
    updateMutation.mutate({
      id: item.id,
      payload: { enabled: true },
    });
  }

  function confirmAction() {
    if (!pendingAction) return;
    if (pendingAction.kind === "delete") {
      deleteMutation.mutate(pendingAction.schedule.id);
    } else if (pendingAction.kind === "disable") {
      updateMutation.mutate({
        id: pendingAction.schedule.id,
        payload: { enabled: false },
      });
    }
    setPendingAction(null);
  }

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-white">Retraining Schedule</h2>
            <p className="text-sm text-mutedText">
              Configure backend-managed scheduled retraining request creation.
            </p>
            {!canWrite && (
              <p className="text-xs text-amber-300">Read-only mode. Only Admin and MLOps Engineer can manage schedules.</p>
            )}
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            <RefreshCcw size={14} className={cn(query.isFetching && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </Card>

      <Card className="p-5">
        <h3 className="mb-4 text-base font-semibold text-white">{form.id ? "Edit Schedule" : "Create Schedule"}</h3>
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-mutedText">Model</label>
            <select
              className="h-9 w-full rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200"
              value={form.model_name}
              onChange={(e) => setForm((p) => ({ ...p, model_name: e.target.value }))}
              disabled={!canWrite}
            >
              {MODEL_OPTIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-mutedText">Frequency</label>
            <select
              className="h-9 w-full rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200"
              value={form.frequency}
              onChange={(e) => setForm((p) => ({ ...p, frequency: e.target.value as MlopsRetrainingScheduleFrequency }))}
              disabled={!canWrite}
            >
              <option value="DAILY">Daily</option>
              <option value="WEEKLY">Weekly</option>
              <option value="MONTHLY">Monthly</option>
              <option value="CUSTOM_CRON">Custom cron</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-mutedText">Timezone</label>
            <select
              className="h-9 w-full rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200"
              value={form.timezone}
              onChange={(e) => setForm((p) => ({ ...p, timezone: e.target.value }))}
              disabled={!canWrite}
            >
              {TIMEZONE_OPTIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>

          {form.frequency !== "CUSTOM_CRON" && (
            <>
              <div>
                <label className="mb-1 block text-xs text-mutedText">Hour (0-23)</label>
                <input
                  className="h-9 w-full rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200"
                  value={form.hour}
                  onChange={(e) => setForm((p) => ({ ...p, hour: e.target.value }))}
                  disabled={!canWrite}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-mutedText">Minute (0-59)</label>
                <input
                  className="h-9 w-full rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200"
                  value={form.minute}
                  onChange={(e) => setForm((p) => ({ ...p, minute: e.target.value }))}
                  disabled={!canWrite}
                />
              </div>
              {form.frequency === "WEEKLY" && (
                <div>
                  <label className="mb-1 block text-xs text-mutedText">Weekday (0=Sun)</label>
                  <input
                    className="h-9 w-full rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200"
                    value={form.dayOfWeek}
                    onChange={(e) => setForm((p) => ({ ...p, dayOfWeek: e.target.value }))}
                    disabled={!canWrite}
                  />
                </div>
              )}
              {form.frequency === "MONTHLY" && (
                <div>
                  <label className="mb-1 block text-xs text-mutedText">Day of month (1-31)</label>
                  <input
                    className="h-9 w-full rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200"
                    value={form.dayOfMonth}
                    onChange={(e) => setForm((p) => ({ ...p, dayOfMonth: e.target.value }))}
                    disabled={!canWrite}
                  />
                </div>
              )}
            </>
          )}

          {form.frequency === "CUSTOM_CRON" && (
            <div className="md:col-span-3">
              <label className="mb-1 block text-xs text-mutedText">Cron expression</label>
              <input
                className="h-9 w-full rounded-xl border border-border bg-cardAlt px-3 text-sm text-slate-200"
                value={form.customCron}
                onChange={(e) => setForm((p) => ({ ...p, customCron: e.target.value }))}
                disabled={!canWrite}
                placeholder="0 2 * * 0"
              />
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-wrap gap-4 text-sm text-slate-200">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm((p) => ({ ...p, enabled: e.target.checked }))}
              disabled={!canWrite}
            />
            Enabled
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.require_approval}
              onChange={(e) => setForm((p) => ({ ...p, require_approval: e.target.checked }))}
              disabled={!canWrite}
            />
            Require human approval
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.allow_duplicate_enabled}
              onChange={(e) => setForm((p) => ({ ...p, allow_duplicate_enabled: e.target.checked }))}
              disabled={!canWrite}
            />
            Allow duplicate enabled schedule for model
          </label>
        </div>
        <p className="mt-2 text-xs text-mutedText">
          If "Require human approval" is enabled, schedule firing creates a request in Pending Approval and does not start training automatically.
        </p>

        <div className="mt-4 flex gap-2">
          <Button onClick={submitForm} disabled={!canWrite || busy}>
            {form.id ? "Save" : "Create Schedule"}
          </Button>
          <Button
            variant="secondary"
            onClick={() => setForm(INITIAL_FORM)}
            disabled={busy}
          >
            Clear
          </Button>
        </div>
      </Card>

      <Card className="p-5">
        <h3 className="mb-4 text-base font-semibold text-white">Configured Schedules</h3>
        {query.isLoading ? (
          <div className="flex items-center gap-3 text-sm text-mutedText">
            <RefreshCcw size={16} className="animate-spin" />
            Loading schedules...
          </div>
        ) : query.isError ? (
          <EmptyState
            title="Schedules unavailable"
            description="Could not load schedule configuration from backend."
          />
        ) : schedules.length === 0 ? (
          <EmptyState
            icon={<CalendarClock size={24} />}
            title="No schedules configured"
            description="Create a schedule to automatically create retraining requests."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-[10px] uppercase tracking-[0.22em] text-mutedText">
                  <th className="pb-3 pr-4 font-normal">Model</th>
                  <th className="pb-3 pr-4 font-normal">Frequency</th>
                  <th className="pb-3 pr-4 font-normal">Cron</th>
                  <th className="pb-3 pr-4 font-normal">Timezone</th>
                  <th className="pb-3 pr-4 font-normal">Approval</th>
                  <th className="pb-3 pr-4 font-normal">Status</th>
                  <th className="pb-3 pr-4 font-normal">Last run</th>
                  <th className="pb-3 pr-4 font-normal">Next run</th>
                  <th className="pb-3 font-normal">Actions</th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((item) => (
                  <tr key={item.id} className="border-t border-border">
                    <td className="py-3 pr-4">{item.model_name}</td>
                    <td className="py-3 pr-4">{item.frequency}</td>
                    <td className="py-3 pr-4 font-mono text-xs">{item.cron_expr}</td>
                    <td className="py-3 pr-4">{item.timezone}</td>
                    <td className="py-3 pr-4">{item.require_approval ? "Yes" : "No"}</td>
                    <td className="py-3 pr-4">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs", statusBadgeClass(item.status))}>
                        {item.status}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-xs text-mutedText">{fmtDateTime(item.last_run_at)}</td>
                    <td className="py-3 pr-4 text-xs text-mutedText">{fmtDateTime(item.next_run_at)}</td>
                    <td className="py-3">
                      <div className="flex flex-wrap gap-1.5">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setForm(hydrateForm(item))}
                          disabled={busy}
                        >
                          <Pencil size={13} />
                          Edit
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => onEnableToggle(item)}
                          disabled={!canWrite || busy}
                        >
                          {item.enabled ? "Disable" : "Enable"}
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setPendingAction({ kind: "delete", schedule: item })}
                          disabled={!canWrite || busy}
                        >
                          <Trash2 size={13} />
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ConfirmModal
        open={pendingAction !== null}
        title={pendingAction?.kind === "delete" ? "Delete schedule?" : "Disable schedule?"}
        description={
          pendingAction?.kind === "delete"
            ? "This scheduled configuration will be permanently removed."
            : "This schedule will stop creating retraining requests until enabled again."
        }
        confirmLabel={pendingAction?.kind === "delete" ? "Delete" : "Disable"}
        destructive
        onCancel={() => setPendingAction(null)}
        onConfirm={confirmAction}
      />
    </div>
  );
}
