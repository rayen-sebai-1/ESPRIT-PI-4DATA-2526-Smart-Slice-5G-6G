import { Activity, BarChart3, LogOut, Radar, RadioTower, ShieldCheck } from "lucide-react";

import type { UserRole } from "@/types/auth";

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
    label: "Prediction simple",
    to: "/predictions",
    icon: Radar,
    roles: ["ADMIN", "NETWORK_OPERATOR"],
  },
];

export const authStorageKey = "neuroslice-auth";

export const authlessNav = {
  label: "Deconnexion",
  icon: LogOut,
};

export const roleLabels: Record<UserRole, string> = {
  ADMIN: "Administrateur",
  NETWORK_OPERATOR: "Operateur reseau",
  NETWORK_MANAGER: "Manager reseau",
};

export const roleDefaultRoute: Record<UserRole, string> = {
  ADMIN: "/dashboard/national",
  NETWORK_OPERATOR: "/dashboard/national",
  NETWORK_MANAGER: "/dashboard/national",
};

export const appSections = {
  fallbackInsight:
    "Cette visualisation sera enrichie des qu'un endpoint agrege dedie sera disponible cote backend.",
  nocSummary:
    "Plateforme de supervision reseau 5G/6G pour la Tunisie, orientee exploitation operationnelle.",
  securityIcon: ShieldCheck,
};

export const demoAccounts = [
  {
    label: "Admin",
    email: "admin@neuroslice.tn",
    password: "admin123",
    role: "ADMIN" as const,
  },
  {
    label: "Operator",
    email: "operator@neuroslice.tn",
    password: "operator123",
    role: "NETWORK_OPERATOR" as const,
  },
  {
    label: "Manager",
    email: "manager@neuroslice.tn",
    password: "manager123",
    role: "NETWORK_MANAGER" as const,
  },
];
