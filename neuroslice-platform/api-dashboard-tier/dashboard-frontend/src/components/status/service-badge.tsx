import { cn } from "@/lib/cn";
import { statusTone } from "@/lib/risk";
import type { RICStatus } from "@/types/shared";

export function ServiceBadge({ value }: { value: RICStatus }) {
  return <span className={cn("rounded-full border px-2.5 py-1 text-xs font-semibold", statusTone(value))}>{value}</span>;
}
