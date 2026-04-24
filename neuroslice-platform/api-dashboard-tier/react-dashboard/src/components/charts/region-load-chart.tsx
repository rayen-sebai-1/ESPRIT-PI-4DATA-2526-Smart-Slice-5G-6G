import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import type { RegionComparison } from "@/types/dashboard";

export function RegionLoadChart({ data }: { data: RegionComparison[] }) {
  if (!data.length) {
    return (
      <EmptyState
        title="Aucune region exploitable"
        description="Le backend ne renvoie pas encore de regions avec niveau de charge."
      />
    );
  }

  return (
    <Card className="p-5">
      <div className="mb-5">
        <h3 className="text-lg font-semibold text-white">Pression reseau par region</h3>
        <p className="text-sm text-mutedText">
          Charge reseau et exposition congestion sur les zones les plus sollicitees.
        </p>
      </div>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data.slice(0, 6)} barGap={10}>
            <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
            <XAxis dataKey="code" stroke="#96a4ba" tickLine={false} axisLine={false} />
            <YAxis stroke="#96a4ba" tickLine={false} axisLine={false} domain={[0, 100]} />
            <Tooltip
              contentStyle={{
                background: "#101d31",
                border: "1px solid #223653",
                borderRadius: 18,
                color: "#fff",
              }}
            />
            <Bar dataKey="network_load" name="Charge" fill="#4ec3ff" radius={[10, 10, 0, 0]} />
            <Bar dataKey="congestion_rate" name="Congestion" fill="#f97316" radius={[10, 10, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
