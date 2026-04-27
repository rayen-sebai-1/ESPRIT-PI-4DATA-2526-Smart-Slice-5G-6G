import { NavLink, Outlet } from "react-router-dom";

import { PageHeader } from "@/components/layout/page-header";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";

const tabs = [
  { to: "/mlops", label: "Vue globale", end: true },
  { to: "/mlops/models", label: "Modeles" },
  { to: "/mlops/runs", label: "Runs" },
  { to: "/mlops/artifacts", label: "Artefacts" },
  { to: "/mlops/promotions", label: "Promotions" },
  { to: "/mlops/monitoring", label: "Monitoring" },
  { to: "/mlops/operations", label: "Operations" },
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
            ? "Lecture seule du cycle de vie MLOps : modeles promus, runs, artefacts et monitoring."
            : "Supervision et controle du cycle de vie MLOps : modeles promus, runs, artefacts, promotions et monitoring."
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
