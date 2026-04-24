import { NavLink } from "react-router-dom";
import { Menu, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { OrionLogo } from "@/components/layout/orion-logo";
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
        className="fixed left-4 top-4 z-50 rounded-2xl border border-border bg-card p-2 text-ink shadow-panel lg:hidden"
      >
        {open ? <X size={18} /> : <Menu size={18} />}
      </button>

      {open ? (
        <button
          aria-label="Close sidebar overlay"
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={onToggle}
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-border bg-surface/95 p-6 backdrop-blur-xl transition-transform duration-300 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Brand */}
        <div className="mb-8 flex items-center gap-3">
          <OrionLogo size={40} />
        </div>

        {/* Description */}
        <div className="mb-8 rounded-[20px] border border-border bg-cardAlt p-4">
          <p className="text-xs uppercase tracking-[0.22em] text-mutedText">Platform</p>
          <p className="mt-2 text-sm leading-6 text-inkSecondary">
            5G/6G network supervision cockpit for session monitoring and AI-driven predictive insights.
          </p>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-1">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => {
                if (open) onToggle();
              }}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-accent text-[#0D0906] shadow-glow"
                    : "text-inkSecondary hover:bg-accentSoft hover:text-ink",
                )
              }
            >
              <item.icon size={17} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Footer card */}
        <div className="rounded-[20px] border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.22em] text-mutedText">Status</p>
          <p className="mt-2 text-sm leading-6 text-inkSecondary">
            Live backend connected — dashboard, monitoring and prediction active.
          </p>
          <Button className="mt-4 w-full" variant="secondary">
            Monitoring active
          </Button>
        </div>
      </aside>
    </>
  );
}
