import { X } from "lucide-react";

import type { NetworkLogEvent } from "@/api/logsApi";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";

interface LogDetailDrawerProps {
  event: NetworkLogEvent | null;
  onClose: () => void;
}

export function LogDetailDrawer({ event, onClose }: LogDetailDrawerProps) {
  if (!event) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm" role="dialog" aria-modal="true">
      <div className="absolute inset-y-0 right-0 flex w-full max-w-xl flex-col border-l border-border bg-[#101724] shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-border p-5">
          <div>
            <div className="text-xs uppercase text-mutedText">{event.category}</div>
            <h3 className="mt-1 text-lg font-semibold text-white">{event.message}</h3>
            <p className="mt-2 text-sm text-mutedText">{formatDate(event.ts)}</p>
          </div>
          <Button size="icon" variant="ghost" type="button" onClick={onClose} aria-label="Close">
            <X size={18} />
          </Button>
        </div>

        <div className="grid gap-3 border-b border-border p-5 text-sm text-slate-200 sm:grid-cols-2">
          <Detail label="Severity" value={`S${event.severity}`} />
          <Detail label="Domain" value={event.domain ?? "N/A"} />
          <Detail label="Entity" value={event.entity_id ?? "N/A"} />
          <Detail label="Slice" value={event.slice_id ?? "N/A"} />
          <Detail label="Entity type" value={event.entity_type ?? "N/A"} />
          <Detail label="Type slice" value={event.slice_type ?? "N/A"} />
        </div>

        <div className="min-h-0 flex-1 overflow-auto p-5">
          <div className="mb-3 text-sm font-medium text-white">Evidence JSON</div>
          <pre className="overflow-auto rounded-2xl border border-border bg-slate-950/70 p-4 text-xs leading-5 text-slate-200">
            {JSON.stringify(event.evidence, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-cardAlt/70 px-4 py-3">
      <div className="text-xs text-mutedText">{label}</div>
      <div className="mt-1 break-words text-sm text-white">{value}</div>
    </div>
  );
}
