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
} from "lucide-react";

import type { AssignableRole, UserRole } from "@/types/auth";

export interface NavItem {
  label: string;
  to: string;
  icon: typeof Activity;
  roles: UserRole[];
}

export const navItems: NavItem[] = [
  {
    label: "National Dashboard",
    to: "/dashboard/national",
    icon: BarChart3,
    roles: ["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER"],
  },
  {
    label: "Entity Dashboard",
    to: "/dashboard/region",
    icon: RadioTower,
    roles: ["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER"],
  },
  {
    label: "Sessions Monitor",
    to: "/sessions",
    icon: Activity,
    roles: ["ADMIN", "NETWORK_OPERATOR"],
  },
  {
    label: "Live State",
    to: "/live-state",
    icon: Radar,
    roles: ["ADMIN", "NETWORK_OPERATOR"],
  },
  {
    label: "Predictions & Models",
    to: "/predictions",
    icon: Radar,
    roles: ["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"],
  },
  {
    label: "MLOps Control Center",
    to: "/mlops",
    icon: Cpu,
    roles: ["ADMIN", "DATA_MLOPS_ENGINEER", "NETWORK_MANAGER"],
  },
  {
    label: "Control Actions",
    to: "/control/actions",
    icon: ShieldAlert,
    roles: ["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER"],
  },
  {
    label: "Root Cause Agent",
    to: "/agentic/root-cause",
    icon: ScanSearch,
    roles: ["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"],
  },
  {
    label: "Copilot Agent",
    to: "/agentic/copilot",
    icon: Bot,
    roles: ["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER", "DATA_MLOPS_ENGINEER"],
  },
  {
    label: "User Management",
    to: "/admin/users",
    icon: Users,
    roles: ["ADMIN"],
  },
];

export const authlessNav = {
  label: "Sign Out",
  icon: LogOut,
};

export const roleLabels: Record<UserRole, string> = {
  ADMIN: "Administrator",
  NETWORK_OPERATOR: "Network Operator (NOC)",
  NETWORK_MANAGER: "Network Manager",
  DATA_MLOPS_ENGINEER: "Data / MLOps Engineer",
};

export const assignableRoleOptions: { value: AssignableRole; label: string }[] = [
  { value: "NETWORK_OPERATOR", label: roleLabels.NETWORK_OPERATOR },
  { value: "NETWORK_MANAGER", label: roleLabels.NETWORK_MANAGER },
  { value: "DATA_MLOPS_ENGINEER", label: roleLabels.DATA_MLOPS_ENGINEER },
];

export const roleDefaultRoute: Record<UserRole, string> = {
  ADMIN: "/admin/users",
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
