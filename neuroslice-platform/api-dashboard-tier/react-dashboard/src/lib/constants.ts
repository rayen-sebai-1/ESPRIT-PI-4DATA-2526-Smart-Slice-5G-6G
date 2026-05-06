import {
  Activity,
  BarChart3,
  Bot,
  Cpu,
  LogOut,
  Radar,
  RadioTower,
  ScanSearch,
  ShieldCheck,
  Users,
  ShieldAlert,
  TrendingUp,
  LayoutDashboard,
  Info,
} from "lucide-react";

import type { AssignableRole, UserRole } from "@/types/auth";

export interface NavItem {
  label: string;
  to: string;
  icon: typeof Activity;
  roles: UserRole[];
}

const adminActorRoles: UserRole[] = ["ADMIN", "NETWORK_MANAGER"];
const nocActorRoles: UserRole[] = ["NETWORK_OPERATOR"];
const mlopsActorRoles: UserRole[] = ["DATA_MLOPS_ENGINEER"];
const allActorRoles: UserRole[] = [...adminActorRoles, ...nocActorRoles, ...mlopsActorRoles];

export const navItems: NavItem[] = [
  {
    label: "National Dashboard",
    to: "/dashboard/national",
    icon: BarChart3,
    roles: [...adminActorRoles, ...nocActorRoles],
  },
  {
    label: "Entity Dashboard",
    to: "/dashboard/region",
    icon: RadioTower,
    roles: [...adminActorRoles, ...nocActorRoles],
  },
  {
    label: "Sessions Monitor",
    to: "/sessions",
    icon: Activity,
    roles: [...adminActorRoles, ...nocActorRoles],
  },
  {
    label: "Live State",
    to: "/live-state",
    icon: Radar,
    roles: [...adminActorRoles, ...nocActorRoles],
  },
  {
    label: "Predictions & Models",
    to: "/predictions",
    icon: TrendingUp,
    roles: [...adminActorRoles, ...nocActorRoles],
  },
  {
    label: "MLOps Control Center",
    to: "/mlops",
    icon: Cpu,
    roles: [...adminActorRoles, ...mlopsActorRoles],
  },
  {
    label: "Monitoring Tools",
    to: "/monitoring-tools",
    icon: LayoutDashboard,
    roles: [...adminActorRoles, ...mlopsActorRoles],
  },
  {
    label: "Drift Monitor",
    to: "/control/actions/drift-monitor",
    icon: ShieldAlert,
    roles: [...adminActorRoles, ...mlopsActorRoles],
  },
  {
    label: "Control Actions",
    to: "/control/actions",
    icon: ShieldAlert,
    roles: [...adminActorRoles, ...mlopsActorRoles],
  },
  {
    label: "Root Cause Agent",
    to: "/agentic/root-cause",
    icon: ScanSearch,
    roles: [...adminActorRoles, ...nocActorRoles],
  },
  {
    label: "Copilot Agent",
    to: "/agentic/copilot",
    icon: Bot,
    roles: [...allActorRoles],
  },
  {
    label: "User Management",
    to: "/admin/users",
    icon: Users,
    roles: [...adminActorRoles],
  },
  {
    label: "About ORION",
    to: "/about",
    icon: Info,
    roles: [...allActorRoles],
  },
];

export const authlessNav = {
  label: "Sign Out",
  icon: LogOut,
};

export const roleLabels: Record<UserRole, string> = {
  ADMIN: "Manager (Admin)",
  NETWORK_OPERATOR: "Network Operator (NOC)",
  NETWORK_MANAGER: "Manager (Admin)",
  DATA_MLOPS_ENGINEER: "MLOps Engineer",
};

export const assignableRoleOptions: { value: AssignableRole; label: string }[] = [
  { value: "NETWORK_OPERATOR", label: roleLabels.NETWORK_OPERATOR },
  { value: "NETWORK_MANAGER", label: roleLabels.NETWORK_MANAGER },
  { value: "DATA_MLOPS_ENGINEER", label: roleLabels.DATA_MLOPS_ENGINEER },
];

export const roleDefaultRoute: Record<UserRole, string> = {
  ADMIN: "/dashboard/national",
  NETWORK_OPERATOR: "/dashboard/national",
  NETWORK_MANAGER: "/dashboard/national",
  DATA_MLOPS_ENGINEER: "/mlops",
};

export const appSections = {
  fallbackInsight:
    "This visualization will be enriched once a dedicated aggregated endpoint is available on the backend.",
  nocSummary:
    "5G/6G network supervision platform for Tunisia, focused on operational management.",
  securityIcon: ShieldCheck,
};
