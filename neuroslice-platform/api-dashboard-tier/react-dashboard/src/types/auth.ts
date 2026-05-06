export type UserRole =
  | "ADMIN"
  | "NETWORK_OPERATOR"
  // Legacy role kept for backward compatibility; mapped to Manager/Admin privileges.
  | "NETWORK_MANAGER"
  | "DATA_MLOPS_ENGINEER";

export type AssignableRole = Exclude<UserRole, "ADMIN">;

export interface User {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface AdminCreateUserPayload {
  full_name: string;
  email: string;
  password: string;
  role: AssignableRole;
}

export interface AdminUpdateUserPayload {
  full_name?: string;
  role?: AssignableRole;
  is_active?: boolean;
  password?: string;
}
