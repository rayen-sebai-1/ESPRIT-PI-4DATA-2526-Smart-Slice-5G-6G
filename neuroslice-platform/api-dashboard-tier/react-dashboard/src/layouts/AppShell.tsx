import { useState } from "react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { ParticleBackground } from "@/components/layout/particle-background";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/lib/theme";

export function AppShell() {
  const { user, logout } = useAuth();
  const { theme } = useTheme();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen text-ink theme-transition">
      <ParticleBackground theme={theme} />
      <Sidebar role={user.role} open={sidebarOpen} onToggle={() => setSidebarOpen((v) => !v)} />
      <div className="relative lg:pl-72" style={{ zIndex: 1 }}>
        <Topbar user={user} onLogout={logout} />
        <main className="px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
