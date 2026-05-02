import { NavLink, Outlet } from "react-router-dom";

import { PageHeader } from "@/components/layout/page-header";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";

const tabs = [
  { to: "/mlops", label: "Overview", end: true },
  { to: "/mlops/models", label: "Models" },
  { to: "/mlops/runs", label: "Runs" },
  { to: "/mlops/artifacts", label: "Artifacts" },
  { to: "/mlops/promotions", label: "Promotions" },
  { to: "/mlops/monitoring", label: "Monitoring" },
  { to: "/mlops/drift", label: "Drift" },
  { to: "/mlops/requests", label: "Requests" },
  { to: "/mlops/operations", label: "Operations" },
  { to: "/mlops/orchestration", label: "Orchestration" },
];

export function MlopsLayout() {
  const { user } = useAuth();
  const readOnly = user?.role === "NETWORK_MANAGER";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="MLOps Control Center"
        title="MLOps Control Center"
        description={
          readOnly
            ? "Read-only view of the MLOps lifecycle: promoted models, runs, artifacts and monitoring."
            : "Supervision and control of the MLOps lifecycle: promoted models, runs, artifacts, promotions and monitoring."
        }
      />

      <nav className="flex flex-wrap gap-2 border-b border-white/5 pb-2">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              cn(
                "rounded-2xl border px-4 py-2 text-sm transition",
                isActive
                  ? "border-accent bg-accent text-slate-950"
                  : "border-border bg-cardAlt/70 text-slate-200 hover:border-accent/30 hover:bg-card",
              )
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>

      <Outlet context={{ readOnly }} />
    </div>
  );
}
