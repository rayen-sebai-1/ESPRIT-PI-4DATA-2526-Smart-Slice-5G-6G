import { authClient } from "@/api/axios";
import type { LoginPayload, LoginResponse, User } from "@/types/auth";

export async function login(payload: LoginPayload) {
  const { data } = await authClient.post<LoginResponse>("/auth/login", payload);
  return data;
}

export async function getCurrentUser() {
  const { data } = await authClient.get<User>("/auth/me");
  return data;
}

export async function getUsers() {
  const { data } = await authClient.get<User[]>("/users");
  return data;
}
