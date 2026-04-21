import type { ReactNode } from "react";
import { ArrowUpRight, Minus } from "lucide-react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

export function KpiCard({
  title,
  value,
  subtitle,
  icon,
  eyebrow,
  tone = "neutral",
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: ReactNode;
  eyebrow?: string;
  tone?: "neutral" | "accent" | "warning" | "danger";
}) {
  return (
    <Card className="panel-grid p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-3">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-mutedText">
              {eyebrow ?? "Live telemetry"}
            </p>
            <p className="mt-2 text-sm text-mutedText">{title}</p>
          </div>
          <p className="text-3xl font-semibold text-white">{value}</p>
          <p className="text-sm text-slate-300">{subtitle}</p>
        </div>
        <div
          className={cn(
            "rounded-3xl p-3",
            tone === "neutral" && "bg-white/5 text-slate-100",
            tone === "accent" && "bg-accentSoft text-accent",
            tone === "warning" && "bg-amber-500/12 text-amber-300",
            tone === "danger" && "bg-red-500/12 text-red-300",
          )}
        >
          {icon}
        </div>
      </div>
      <div className="mt-5 flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-mutedText">
        {tone === "danger" ? <Minus size={14} /> : <ArrowUpRight size={14} />}
        Operations ready
      </div>
    </Card>
  );
}
