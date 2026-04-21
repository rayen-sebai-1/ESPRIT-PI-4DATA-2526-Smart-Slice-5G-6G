import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { appSections } from "@/lib/constants";
import { formatNumber } from "@/lib/format";

const COLORS = ["#4ec3ff", "#34d399", "#f59e0b", "#f97316", "#ef4444", "#a78bfa", "#14b8a6"];

export function SliceDistributionChart({
  data,
  title,
  description,
}: {
  data: { slice_type: string; sessions_count: number }[];
  title: string;
  description: string;
}) {
  if (!data.length) {
    return <EmptyState title={title} description={description || appSections.fallbackInsight} />;
  }

  return (
    <Card className="p-5">
      <div className="mb-5">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="text-sm text-mutedText">{description}</p>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_220px]">
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="sessions_count"
                nameKey="slice_type"
                innerRadius={78}
                outerRadius={116}
                paddingAngle={3}
              >
                {data.map((entry, index) => (
                  <Cell key={entry.slice_type} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#101d31",
                  border: "1px solid #223653",
                  borderRadius: 18,
                  color: "#fff",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="space-y-3">
          {data.map((item, index) => (
            <div
              key={item.slice_type}
              className="flex items-center justify-between rounded-2xl border border-border bg-cardAlt/70 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <span
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: COLORS[index % COLORS.length] }}
                />
                <span className="text-sm text-white">{item.slice_type}</span>
              </div>
              <span className="text-sm text-mutedText">{formatNumber(item.sessions_count)}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
