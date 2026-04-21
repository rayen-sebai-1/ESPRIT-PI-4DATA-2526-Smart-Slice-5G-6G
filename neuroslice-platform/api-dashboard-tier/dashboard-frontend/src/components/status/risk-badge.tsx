import { cn } from "@/lib/cn";
import { riskTone } from "@/lib/risk";
import type { RiskLevel } from "@/types/shared";

export function RiskBadge({ value }: { value: RiskLevel }) {
  return <span className={cn("rounded-full border px-2.5 py-1 text-xs font-semibold", riskTone(value))}>{value}</span>;
}
