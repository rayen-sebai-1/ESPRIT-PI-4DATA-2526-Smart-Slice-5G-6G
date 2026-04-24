import {
  authClient,
  clearAuthSession,
  refreshAccessToken,
  setAuthSession,
} from "@/api/axios";
import type {
  AdminCreateUserPayload,
  AdminUpdateUserPayload,
  LoginPayload,
  LoginResponse,
  User,
} from "@/types/auth";

export async function login(payload: LoginPayload) {
  const { data } = await authClient.post<LoginResponse>("/login", payload);
  setAuthSession({ token: data.access_token, user: data.user });
  return data;
}

export async function refreshSession() {
  return refreshAccessToken();
}

export async function getCurrentUser() {
  const { data } = await authClient.get<User>("/me");
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

export async function logout() {
  try {
    await authClient.post("/logout");
  } finally {
    clearAuthSession();
  }
}
