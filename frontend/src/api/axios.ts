import axios from "axios";

import { authStorageKey } from "@/lib/constants";

function getStoredToken() {
  const raw = localStorage.getItem(authStorageKey);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as { token?: string };
    return parsed.token ?? null;
  } catch {
    return null;
  }
}

function createClient(baseURL: string) {
  const client = axios.create({
    baseURL,
    headers: {
      "Content-Type": "application/json",
    },
  });

  client.interceptors.request.use((config) => {
    const token = getStoredToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        localStorage.removeItem(authStorageKey);
        if (window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
      }

      return Promise.reject(error);
    },
  );

  return client;
}

export const authClient = createClient(import.meta.env.VITE_AUTH_API_URL ?? "/api/auth");
export const sessionClient = createClient(import.meta.env.VITE_SESSION_API_URL ?? "/api/session");
export const predictionClient = createClient(import.meta.env.VITE_PREDICTION_API_URL ?? "/api/prediction");
export const dashboardClient = createClient(import.meta.env.VITE_DASHBOARD_API_URL ?? "/api/dashboard");
