import { authClient } from "@/api/axios";
import type {
  AdminCreateUserPayload,
  AdminUpdateUserPayload,
  LoginPayload,
  LoginResponse,
  User,
} from "@/types/auth";

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

export async function createUser(payload: AdminCreateUserPayload) {
  const { data } = await authClient.post<User>("/users", payload);
  return data;
}

export async function updateUser(userId: number, payload: AdminUpdateUserPayload) {
  const { data } = await authClient.patch<User>(`/users/${userId}`, payload);
  return data;
}

export async function deleteUser(userId: number) {
  await authClient.delete(`/users/${userId}`);
}
