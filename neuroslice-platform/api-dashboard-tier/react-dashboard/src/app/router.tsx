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
import { RootCauseAgentPage } from "@/pages/RootCauseAgentPage";
import { CopilotAgentPage } from "@/pages/CopilotAgentPage";
import { MlopsLayout } from "@/pages/mlops/MlopsLayout";
import { MlopsOverviewPage } from "@/pages/mlops/MlopsOverviewPage";
import { MlopsModelsPage } from "@/pages/mlops/MlopsModelsPage";
import { MlopsRunsPage } from "@/pages/mlops/MlopsRunsPage";
import { MlopsArtifactsPage } from "@/pages/mlops/MlopsArtifactsPage";
import { MlopsPromotionsPage } from "@/pages/mlops/MlopsPromotionsPage";
import { MlopsMonitoringPage } from "@/pages/mlops/MlopsMonitoringPage";
import { MlopsOperationsPage } from "@/pages/mlops/MlopsOperationsPage";
import { MlopsOrchestrationPage } from "@/pages/mlops/MlopsOrchestrationPage";

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
                allowedRoles={["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"]}
              />
            ),
            children: [{ path: "/predictions", element: <PredictionsCenterPage /> }],
          },
          { path: "/agentic/root-cause", element: <RootCauseAgentPage /> },
          { path: "/agentic/copilot", element: <CopilotAgentPage /> },
          {
            element: (
              <ProtectedRoute
                allowedRoles={["ADMIN", "DATA_MLOPS_ENGINEER", "NETWORK_MANAGER"]}
              />
            ),
            children: [
              {
                path: "/mlops",
                element: <MlopsLayout />,
                children: [
                  { index: true, element: <MlopsOverviewPage /> },
                  { path: "models", element: <MlopsModelsPage /> },
                  { path: "runs", element: <MlopsRunsPage /> },
                  { path: "artifacts", element: <MlopsArtifactsPage /> },
                  { path: "promotions", element: <MlopsPromotionsPage /> },
                  { path: "monitoring", element: <MlopsMonitoringPage /> },
                  { path: "operations", element: <MlopsOperationsPage /> },
                  { path: "orchestration", element: <MlopsOrchestrationPage /> },
                ],
              },
            ],
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
