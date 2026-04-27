import {
  Activity,
  BarChart3,
  LogOut,
  Radar,
  RadioTower,
  ShieldCheck,
  Users,
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
    label: "Dashboard National",
    to: "/dashboard/national",
    icon: BarChart3,
    roles: ["ADMIN", "NETWORK_OPERATOR", "NETWORK_MANAGER"],
  },
  {
    label: "Dashboard Regional",
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
    roles: ["ADMIN", "NETWORK_OPERATOR", "DATA_MLOPS_ENGINEER"],
  },
  {
    label: "Gestion utilisateurs",
    to: "/admin/users",
    icon: Users,
    roles: ["ADMIN"],
  },
];

export const authlessNav = {
  label: "Deconnexion",
  icon: LogOut,
};

export const roleLabels: Record<UserRole, string> = {
  ADMIN: "Administrateur",
  NETWORK_OPERATOR: "Operateur reseau (NOC)",
  NETWORK_MANAGER: "Manager reseau",
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
  DATA_MLOPS_ENGINEER: "/predictions",
};

export const appSections = {
  fallbackInsight:
    "Cette visualisation sera enrichie des qu'un endpoint agrege dedie sera disponible cote backend.",
  nocSummary:
    "Plateforme de supervision reseau 5G/6G pour la Tunisie, orientee exploitation operationnelle.",
  securityIcon: ShieldCheck,
};
