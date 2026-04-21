import { NavLink } from "react-router-dom";
import { Menu, RadioTower, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { navItems } from "@/lib/constants";
import { cn } from "@/lib/cn";
import type { UserRole } from "@/types/auth";

interface SidebarProps {
  role: UserRole;
  open: boolean;
  onToggle: () => void;
}

export function Sidebar({ role, open, onToggle }: SidebarProps) {
  const items = navItems.filter((item) => item.roles.includes(role));

  return (
    <>
      <button
        onClick={onToggle}
        className="fixed left-4 top-4 z-50 rounded-2xl border border-border bg-card p-2 text-white shadow-panel lg:hidden"
      >
        {open ? <X size={18} /> : <Menu size={18} />}
      </button>

      {open ? (
        <button
          aria-label="Close sidebar overlay"
          className="fixed inset-0 z-30 bg-slate-950/55 backdrop-blur-sm lg:hidden"
          onClick={onToggle}
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-white/5 bg-surface/95 p-6 backdrop-blur-xl transition-transform duration-300 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="mb-8 flex items-center gap-3">
          <div className="rounded-3xl bg-accentSoft p-3 text-accent">
            <RadioTower size={22} />
          </div>
          <div>
            <p className="text-lg font-semibold text-white">NeuroSlice Tunisia</p>
            <p className="text-xs uppercase tracking-[0.28em] text-mutedText">NOC supervision</p>
          </div>
        </div>

        <div className="mb-8 rounded-[24px] border border-border bg-cardAlt/90 p-4">
          <p className="text-xs uppercase tracking-[0.24em] text-mutedText">Plateforme</p>
          <p className="mt-2 text-sm leading-6 text-slate-200">
            Cockpit reseau 5G/6G centre sur la supervision locale, le monitoring des sessions et
            une aide predictive simple pour la demonstration.
          </p>
        </div>

        <nav className="flex-1 space-y-2">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => {
                if (open) onToggle();
              }}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-all",
                  isActive
                    ? "bg-accent text-slate-950 shadow-glow"
                    : "text-slate-300 hover:bg-white/5 hover:text-white",
                )
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="rounded-[24px] border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.24em] text-mutedText">Mode demo</p>
          <p className="mt-2 text-sm leading-6 text-slate-200">
            Un seul backend, une interface stable, et un parcours recentre sur le dashboard, le
            monitoring et la prediction simple.
          </p>
          <Button className="mt-4 w-full" variant="secondary">
            Monitoring actif
          </Button>
        </div>
      </aside>
    </>
  );
}
