import { useState } from "react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { useAuth } from "@/hooks/useAuth";

export function AppShell() {
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background text-ink theme-transition">
      <Sidebar role={user.role} open={sidebarOpen} onToggle={() => setSidebarOpen((v) => !v)} />
      <div className="relative lg:pl-72">
        <Topbar user={user} onLogout={logout} />
        <main className="px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
