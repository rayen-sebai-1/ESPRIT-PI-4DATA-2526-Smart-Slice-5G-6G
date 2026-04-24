import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { getAuthSession, subscribeAuthSession } from "@/api/axios";
import { login as loginRequest, logout as logoutRequest, refreshSession } from "@/api/authApi";
import type { LoginPayload, LoginResponse, User } from "@/types/auth";

interface AuthState {
  token: string | null;
  user: User | null;
}

interface AuthContextValue extends AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<LoginResponse>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => getAuthSession());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => subscribeAuthSession(setState), []);

  useEffect(() => {
    let cancelled = false;

    refreshSession()
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      isAuthenticated: Boolean(state.token && state.user),
      isLoading,
      login: async (payload) => {
        const response = await loginRequest(payload);
        return response;
      },
      logout: () => {
        void logoutRequest();
      },
    }),
    [state, isLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuthContext must be used within AuthProvider");
  }
  return context;
}
