import { createBrowserRouter, Navigate } from "react-router-dom";

import { ProtectedRoute } from "@/layouts/ProtectedRoute";
import { AppShell } from "@/layouts/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { NationalDashboardPage } from "@/pages/NationalDashboardPage";
import { RegionalDashboardPage } from "@/pages/RegionalDashboardPage";
import { SessionsMonitorPage } from "@/pages/SessionsMonitorPage";
import { PredictionsCenterPage } from "@/pages/PredictionsCenterPage";
import { UsersManagementPage } from "@/pages/admin/UsersManagementPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { LiveStatePage } from "@/pages/LiveStatePage";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "/", element: <Navigate to="/dashboard/national" replace /> },
          { path: "/dashboard/national", element: <NationalDashboardPage /> },
          { path: "/dashboard/region", element: <RegionalDashboardPage /> },
          { path: "/dashboard/region/:regionId", element: <RegionalDashboardPage /> },
          {
            element: <ProtectedRoute allowedRoles={["ADMIN", "NETWORK_OPERATOR"]} />,
            children: [
              { path: "/sessions", element: <SessionsMonitorPage /> },
              { path: "/live-state", element: <LiveStatePage /> },
            ],
          },
          {
            element: (
              <ProtectedRoute
                allowedRoles={["ADMIN", "NETWORK_OPERATOR", "DATA_MLOPS_ENGINEER"]}
              />
            ),
            children: [{ path: "/predictions", element: <PredictionsCenterPage /> }],
          },
          {
            element: <ProtectedRoute allowedRoles={["ADMIN"]} />,
            children: [{ path: "/admin/users", element: <UsersManagementPage /> }],
          },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);
