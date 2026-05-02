import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Card } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { roleDefaultRoute } from "@/lib/constants";
import type { UserRole } from "@/types/auth";

export function ProtectedRoute({ allowedRoles }: { allowedRoles?: UserRole[] }) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6 text-white">
        <Card className="w-full max-w-md p-6 text-center">
          <div className="text-xs uppercase tracking-[0.24em] text-mutedText">NeuroSlice Tunisia</div>
          <div className="mt-3 text-lg font-semibold">Loading platform...</div>
          <div className="mt-3 text-sm text-mutedText">
            Validating JWT token and synchronizing user profile.
          </div>
        </Card>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={roleDefaultRoute[user.role]} replace />;
  }

  return <Outlet />;
}
