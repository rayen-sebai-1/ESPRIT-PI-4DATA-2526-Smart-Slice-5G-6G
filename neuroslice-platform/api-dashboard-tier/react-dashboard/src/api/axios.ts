import axios, { type InternalAxiosRequestConfig } from "axios";

import type { LoginResponse, User } from "@/types/auth";

interface SessionState {
  token: string | null;
  user: User | null;
}

type SessionListener = (state: SessionState) => void;

const listeners = new Set<SessionListener>();
let sessionState: SessionState = { token: null, user: null };
let refreshPromise: Promise<LoginResponse> | null = null;

const authApiBaseUrl = import.meta.env.VITE_AUTH_API_URL ?? "/api/auth";
const dashboardApiBaseUrl = import.meta.env.VITE_DASHBOARD_API_URL ?? "/api/dashboard";

const refreshClient = axios.create({
  baseURL: authApiBaseUrl,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

export function getAuthSession() {
  return sessionState;
}

export function subscribeAuthSession(listener: SessionListener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setAuthSession(nextState: SessionState) {
  sessionState = nextState;
  for (const listener of listeners) {
    listener(sessionState);
  }
}

export function clearAuthSession() {
  setAuthSession({ token: null, user: null });
}

export async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = refreshClient
      .post<LoginResponse>("/refresh")
      .then(({ data }) => {
        setAuthSession({ token: data.access_token, user: data.user });
        return data;
      })
      .catch((error) => {
        clearAuthSession();
        throw error;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

function createClient(baseURL: string) {
  const client = axios.create({
    baseURL,
    withCredentials: true,
    headers: {
      "Content-Type": "application/json",
    },
  });

  client.interceptors.request.use((config) => {
    const token = sessionState.token;
    if (token) {
      config.headers = config.headers ?? {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
      const responseStatus = error.response?.status;
      const requestUrl = String(originalRequest?.url ?? "");

      if (
        responseStatus === 401 &&
        originalRequest &&
        !originalRequest._retry &&
        !requestUrl.includes("/login") &&
        !requestUrl.includes("/refresh") &&
        !requestUrl.includes("/logout")
      ) {
        originalRequest._retry = true;
        try {
          const refreshed = await refreshAccessToken();
          originalRequest.headers = originalRequest.headers ?? {};
          originalRequest.headers.Authorization = `Bearer ${refreshed.access_token}`;
          return client(originalRequest);
        } catch (refreshError) {
          clearAuthSession();
          if (window.location.pathname !== "/login") {
            window.location.href = "/login";
          }
          return Promise.reject(refreshError);
        }
      }

      return Promise.reject(error);
    },
  );

  return client;
}

export const authClient = createClient(authApiBaseUrl);
export const dashboardClient = createClient(dashboardApiBaseUrl);
export const sessionClient = createClient(import.meta.env.VITE_SESSION_API_URL ?? dashboardApiBaseUrl);
export const predictionClient = createClient(
  import.meta.env.VITE_PREDICTION_API_URL ?? dashboardApiBaseUrl,
);
export const liveClient = createClient("/api/v1/live");
// Agentic routes go through dashboard-backend so JWT/session validation is enforced.
export const agentClient = createClient(import.meta.env.VITE_AGENTIC_API_URL ?? "/api/dashboard/agentic");
