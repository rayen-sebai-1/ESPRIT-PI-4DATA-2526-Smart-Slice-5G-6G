import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { appSections } from "@/lib/constants";
import type { TrendPoint } from "@/types/dashboard";

interface TrendLineConfig {
  dataKey: keyof TrendPoint;
  color: string;
  label: string;
}

export function SlaTrendChart({
  data,
  title,
  description,
  lines,
}: {
  data: TrendPoint[];
  title: string;
  description?: string;
  lines?: TrendLineConfig[];
}) {
  const series = lines ?? [{ dataKey: "sla_percent", color: "#4ec3ff", label: "SLA" }];

  if (!data.length) {
    return <EmptyState title={title} description={description ?? appSections.fallbackInsight} />;
  }

  return (
    <Card className="p-5">
      <div className="mb-5">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="text-sm text-mutedText">
          {description ?? "Trend of indicators exposed by dashboard-service."}
        </p>
      </div>
      <div className="mb-5 flex flex-wrap gap-3">
        {series.map((item) => (
          <div
            key={item.label}
            className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs text-slate-300"
          >
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
            {item.label}
          </div>
        ))}
      </div>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
            <XAxis dataKey="label" stroke="#96a4ba" tickLine={false} axisLine={false} />
            <YAxis stroke="#96a4ba" tickLine={false} axisLine={false} domain={[0, 100]} />
            <Tooltip
              contentStyle={{
                background: "#101d31",
                border: "1px solid #223653",
                borderRadius: 18,
                color: "#fff",
              }}
            />
            {series.map((item) => (
              <Line
                key={item.label}
                type="monotone"
                dataKey={item.dataKey}
                stroke={item.color}
                strokeWidth={3}
                dot={false}
                name={item.label}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
