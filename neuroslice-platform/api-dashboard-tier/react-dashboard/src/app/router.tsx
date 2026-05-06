import { Suspense, lazy } from "react";
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
import { MonitoringToolsPage } from "@/pages/MonitoringToolsPage";
import { AboutOrionPage } from "@/pages/AboutOrionPage";

// MLOps pages are code-split: each sub-page is only loaded when the user
// navigates to /mlops for the first time, keeping the initial bundle small.
const MlopsLayout = lazy(() =>
  import("@/pages/mlops/MlopsLayout").then((m) => ({ default: m.MlopsLayout })),
);
const MlopsOverviewPage = lazy(() =>
  import("@/pages/mlops/MlopsOverviewPage").then((m) => ({ default: m.MlopsOverviewPage })),
);
const MlopsModelsPage = lazy(() =>
  import("@/pages/mlops/MlopsModelsPage").then((m) => ({ default: m.MlopsModelsPage })),
);
const MlopsRunsPage = lazy(() =>
  import("@/pages/mlops/MlopsRunsPage").then((m) => ({ default: m.MlopsRunsPage })),
);
const MlopsArtifactsPage = lazy(() =>
  import("@/pages/mlops/MlopsArtifactsPage").then((m) => ({ default: m.MlopsArtifactsPage })),
);
const MlopsPromotionsPage = lazy(() =>
  import("@/pages/mlops/MlopsPromotionsPage").then((m) => ({ default: m.MlopsPromotionsPage })),
);
const MlopsMonitoringPage = lazy(() =>
  import("@/pages/mlops/MlopsMonitoringPage").then((m) => ({ default: m.MlopsMonitoringPage })),
);
const MlopsOperationsPage = lazy(() =>
  import("@/pages/mlops/MlopsOperationsPage").then((m) => ({ default: m.MlopsOperationsPage })),
);
const MlopsOrchestrationPage = lazy(() =>
  import("@/pages/mlops/MlopsOrchestrationPage").then((m) => ({ default: m.MlopsOrchestrationPage })),
);
const MlopsDriftPage = lazy(() =>
  import("@/pages/mlops/MlopsDriftPage").then((m) => ({ default: m.MlopsDriftPage })),
);
const MlopsRequestsPage = lazy(() =>
  import("@/pages/mlops/MlopsRequestsPage").then((m) => ({ default: m.MlopsRequestsPage })),
);
const MlopsRetrainingSchedulePage = lazy(() =>
  import("@/pages/mlops/MlopsRetrainingSchedulePage").then((m) => ({ default: m.MlopsRetrainingSchedulePage })),
);

const ControlActionsLayout = lazy(() =>
  import("@/pages/control/actions/ControlActionsLayout").then((module) => ({
    default: module.ControlActionsLayout,
  })),
);
const SimulatedActuationsPage = lazy(() => import("@/pages/control/actions/SimulatedActuations"));
const ActionHistoryPage = lazy(() => import("@/pages/control/actions/ActionHistory"));
const PendingApprovalPage = lazy(() => import("@/pages/control/actions/PendingApproval"));
const DriftMonitorPage = lazy(() => import("@/pages/control/actions/DriftMonitor"));

const admin_actor_roles = ["ADMIN", "NETWORK_MANAGER"] as const;
const noc_actor_roles = ["NETWORK_OPERATOR"] as const;
const mlops_actor_roles = ["DATA_MLOPS_ENGINEER"] as const;
const all_actor_roles = [...admin_actor_roles, ...noc_actor_roles, ...mlops_actor_roles] as const;

const dashboard_reader_roles = [...admin_actor_roles, ...noc_actor_roles] as const;
const sessions_live_reader_roles = [...admin_actor_roles, ...noc_actor_roles] as const;
const prediction_reader_roles = [...admin_actor_roles, ...noc_actor_roles] as const;
const monitoring_tools_reader_roles = [...admin_actor_roles, ...mlops_actor_roles] as const;
const drift_monitor_reader_roles = [...admin_actor_roles, ...mlops_actor_roles] as const;
const control_actions_roles = [...admin_actor_roles, ...mlops_actor_roles] as const;
const mlops_reader_roles = [...admin_actor_roles, ...mlops_actor_roles] as const;
const root_cause_reader_roles = [...admin_actor_roles, ...noc_actor_roles] as const;
const copilot_reader_roles = [...all_actor_roles] as const;

function RouteLoadingFallback() {
  return (
    <div className="rounded-xl border border-white/5 bg-card px-4 py-5 text-sm text-slate-400">
      Loading...
    </div>
  );
}

function withSuspense(element: JSX.Element) {
  return <Suspense fallback={<RouteLoadingFallback />}>{element}</Suspense>;
}

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
          {
            element: <ProtectedRoute allowedRoles={[...dashboard_reader_roles]} />,
            children: [
              { path: "/dashboard/national", element: <NationalDashboardPage /> },
              { path: "/dashboard/region", element: <RegionalDashboardPage /> },
              { path: "/dashboard/region/:regionId", element: <RegionalDashboardPage /> },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={[...sessions_live_reader_roles]} />,
            children: [
              { path: "/sessions", element: <SessionsMonitorPage /> },
              { path: "/live-state", element: <LiveStatePage /> },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={[...prediction_reader_roles]} />,
            children: [{ path: "/predictions", element: <PredictionsCenterPage /> }],
          },
          {
            element: <ProtectedRoute allowedRoles={[...monitoring_tools_reader_roles]} />,
            children: [{ path: "/monitoring-tools", element: <MonitoringToolsPage /> }],
          },
          {
            element: <ProtectedRoute allowedRoles={[...drift_monitor_reader_roles]} />,
            children: [{ path: "/control/actions/drift-monitor", element: withSuspense(<DriftMonitorPage />) }],
          },
          {
            element: <ProtectedRoute allowedRoles={[...root_cause_reader_roles]} />,
            children: [{ path: "/agentic/root-cause", element: <RootCauseAgentPage /> }],
          },
          {
            element: <ProtectedRoute allowedRoles={[...copilot_reader_roles]} />,
            children: [
              { path: "/agentic/copilot", element: <CopilotAgentPage /> },
              { path: "/about", element: <AboutOrionPage /> },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={[...control_actions_roles]} />,
            children: [
              {
                path: "/control/actions",
                element: withSuspense(<ControlActionsLayout />),
                children: [
                  { index: true, element: <Navigate to="/control/actions/simulated-actuations" replace /> },
                  {
                    path: "simulated-actuations",
                    element: withSuspense(<SimulatedActuationsPage />),
                  },
                  {
                    path: "action-history",
                    element: withSuspense(<ActionHistoryPage />),
                  },
                  {
                    path: "pending-approval",
                    element: withSuspense(<PendingApprovalPage />),
                  },
                ],
              },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={[...mlops_reader_roles]} />,
            children: [
              {
                path: "/mlops",
                element: withSuspense(<MlopsLayout />),
                children: [
                  { index: true, element: withSuspense(<MlopsOverviewPage />) },
                  { path: "models", element: withSuspense(<MlopsModelsPage />) },
                  { path: "runs", element: withSuspense(<MlopsRunsPage />) },
                  { path: "artifacts", element: withSuspense(<MlopsArtifactsPage />) },
                  { path: "promotions", element: withSuspense(<MlopsPromotionsPage />) },
                  { path: "monitoring", element: withSuspense(<MlopsMonitoringPage />) },
                  { path: "drift", element: withSuspense(<MlopsDriftPage />) },
                  { path: "requests", element: withSuspense(<MlopsRequestsPage />) },
                  { path: "retraining-schedule", element: withSuspense(<MlopsRetrainingSchedulePage />) },
                  { path: "operations", element: withSuspense(<MlopsOperationsPage />) },
                  { path: "orchestration", element: withSuspense(<MlopsOrchestrationPage />) },
                ],
              },
            ],
          },
          {
            element: <ProtectedRoute allowedRoles={[...admin_actor_roles]} />,
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
