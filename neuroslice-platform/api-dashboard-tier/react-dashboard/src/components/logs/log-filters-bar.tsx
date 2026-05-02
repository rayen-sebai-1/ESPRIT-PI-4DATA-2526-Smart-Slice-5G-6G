import { Filter } from "lucide-react";

import { LOG_CATEGORIES, type LogCategory, type LogSeverity, type LogsQueryParams } from "@/api/logsApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/cn";

interface LogFiltersBarProps {
  filters: LogsQueryParams;
  compact?: boolean;
  onChange: (filters: LogsQueryParams) => void;
}

const categoryLabels: Record<LogCategory, string> = {
  FAULT_OPENED: "Fault open",
  FAULT_CLEARED: "Fault clear",
  KPI_BREACH: "KPI breach",
  AIOPS_CONGESTION: "Congestion",
  AIOPS_SLA_RISK: "SLA risk",
  AIOPS_SLICE_MISMATCH: "Slice mismatch",
};

export function LogFiltersBar({ filters, compact, onChange }: LogFiltersBarProps) {
  const selectedCategories = filters.categories ?? [];

  function setPatch(patch: Partial<LogsQueryParams>) {
    onChange({ ...filters, ...patch });
  }

  function toggleCategory(category: LogCategory) {
    const next = selectedCategories.includes(category)
      ? selectedCategories.filter((item) => item !== category)
      : [...selectedCategories, category];
    setPatch({ categories: next });
  }

  return (
    <div className="space-y-3">
      <div className={cn("grid gap-3", compact ? "md:grid-cols-2" : "md:grid-cols-4")}>
        <Select
          value={filters.start ?? "-15m"}
          onChange={(event) => setPatch({ start: event.target.value as LogsQueryParams["start"] })}
        >
          <option value="-5m">5 min</option>
          <option value="-15m">15 min</option>
          <option value="-1h">1 h</option>
          <option value="-6h">6 h</option>
          <option value="-24h">24 h</option>
        </Select>
        <Select
          value={String(filters.min_severity ?? 0)}
          onChange={(event) => setPatch({ min_severity: Number(event.target.value) as LogSeverity })}
        >
          <option value="0">Severity 0+</option>
          <option value="1">Severity 1+</option>
          <option value="2">Severity 2+</option>
          <option value="3">Severity 3</option>
        </Select>
        <Input
          value={filters.entity_id ?? ""}
          onChange={(event) => setPatch({ entity_id: event.target.value || undefined })}
          placeholder="Entity ID"
        />
        <Input
          value={filters.slice_id ?? ""}
          onChange={(event) => setPatch({ slice_id: event.target.value || undefined })}
          placeholder="Slice ID"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex h-9 items-center gap-2 rounded-2xl border border-border bg-cardAlt px-3 text-xs text-mutedText">
          <Filter size={14} />
          Categories
        </div>
        {LOG_CATEGORIES.map((category) => {
          const active = selectedCategories.includes(category);
          return (
            <button
              key={category}
              className={cn(
                "rounded-2xl border px-3 py-2 text-xs transition",
                active
                  ? "border-accent/50 bg-accentSoft text-accent"
                  : "border-border bg-slate-950/40 text-mutedText hover:border-accent/30 hover:text-slate-200",
              )}
              type="button"
              onClick={() => toggleCategory(category)}
            >
              {categoryLabels[category]}
            </button>
          );
        })}
        {selectedCategories.length ? (
          <Button size="sm" variant="ghost" type="button" onClick={() => setPatch({ categories: [] })}>
            Reset
          </Button>
        ) : null}
      </div>
    </div>
  );
}
