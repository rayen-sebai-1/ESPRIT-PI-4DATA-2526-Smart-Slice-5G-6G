import { Bell, Clock3, LogOut, Moon, ShieldCheck, Sun, Radio } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { listControlActions } from "@/api/controlApi";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { roleLabels } from "@/lib/constants";
import { formatDate } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import type { User } from "@/types/auth";

// Roles that have access to the Control Actions page and should see the badge.
const CONTROL_ROLES: User["role"][] = ["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER"];

export function Topbar({
  user,
  onLogout,
}: {
  user: User;
  onLogout: () => void;
}) {
  const { theme, toggleTheme } = useTheme();

  const canSeeActions = CONTROL_ROLES.includes(user.role);
  const { data: actionsData } = useQuery({
    queryKey: ["controls", "actions"],
    queryFn: listControlActions,
    refetchInterval: 15_000,
    enabled: canSeeActions,
    staleTime: 10_000,
  });
  const pendingCount = canSeeActions
    ? (actionsData?.items ?? []).filter((a) => a.status === "PENDING_APPROVAL").length
    : 0;

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/80 px-4 py-4 backdrop-blur-xl md:px-8">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-mutedText">Network supervision</p>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-inkSecondary">
            <span className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1.5">
              <Clock3 size={14} />
              Last sync {formatDate(new Date().toISOString())}
            </span>
            <span className="inline-flex items-center gap-2 rounded-full border border-green-500/20 bg-green-500/10 px-3 py-1.5 text-green-600 dark:text-emerald-300">
              <ShieldCheck size={14} />
              Central service active
            </span>
            <span className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1.5 text-accent font-semibold tracking-wide text-xs">
              <Radio size={13} className="animate-pulse" />
              DATA SOURCE: LIVE
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Card className="hidden rounded-2xl px-4 py-3 md:block">
            <p className="text-sm font-medium text-ink">{user.full_name}</p>
            <p className="text-xs text-mutedText">{roleLabels[user.role]}</p>
          </Card>

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-border bg-card text-mutedText transition-all hover:border-accent/50 hover:text-accent"
          >
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </button>

          <Button
            variant="ghost"
            size="icon"
            className="relative rounded-full border border-border"
            title={pendingCount > 0 ? `${pendingCount} action(s) pending approval` : "No pending actions"}
          >
            <Bell size={18} />
            {pendingCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-[10px] font-bold text-slate-950">
                {pendingCount > 9 ? "9+" : pendingCount}
              </span>
            )}
          </Button>
          <Button variant="secondary" className="gap-2" onClick={onLogout}>
            <LogOut size={16} />
            Sign out
          </Button>
        </div>
      </div>
    </header>
  );
}
