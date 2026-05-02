import { NavLink, Outlet } from "react-router-dom";

import { PageHeader } from "@/components/layout/page-header";
import { cn } from "@/lib/cn";

const tabs = [
  { to: "/control/actions/SimulatedActuations", label: "Simulated Actuations" },
  { to: "/control/actions/ActionHistory", label: "Action History" },
  { to: "/control/actions/PendingApproval", label: "Pending Approval" },
  { to: "/control/actions/DriftMonitor", label: "Drift Monitor" },
];

export function ControlActionsLayout() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Control Actions"
        description="Alert -> Action -> Approval -> Execution pipeline (Scenario B simulated)"
      />

      <nav className="flex flex-wrap gap-2 border-b border-white/8 pb-2">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
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

      <Outlet />
    </div>
  );
}
