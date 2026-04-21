import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { getCurrentUser, login as loginRequest } from "@/api/authApi";
import { authStorageKey } from "@/lib/constants";
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

function readStoredAuth(): AuthState {
  const raw = localStorage.getItem(authStorageKey);
  if (!raw) return { token: null, user: null };
  try {
    const parsed = JSON.parse(raw) as AuthState;
    return { token: parsed.token ?? null, user: parsed.user ?? null };
  } catch {
    return { token: null, user: null };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => readStoredAuth());

  const meQuery = useQuery({
    queryKey: ["auth", "me", state.token],
    queryFn: getCurrentUser,
    enabled: Boolean(state.token),
    retry: false,
  });

  useEffect(() => {
    if (meQuery.data) {
      const nextState = { token: state.token, user: meQuery.data };
      setState(nextState);
      localStorage.setItem(authStorageKey, JSON.stringify(nextState));
    }
  }, [meQuery.data, state.token]);

  useEffect(() => {
    if (meQuery.isError && state.token) {
      localStorage.removeItem(authStorageKey);
      setState({ token: null, user: null });
    }
  }, [meQuery.isError, state.token]);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      isAuthenticated: Boolean(state.token && state.user),
      isLoading: meQuery.isLoading,
      login: async (payload) => {
        const response = await loginRequest(payload);
        const nextState = { token: response.access_token, user: response.user };
        setState(nextState);
        localStorage.setItem(authStorageKey, JSON.stringify(nextState));
        return response;
      },
      logout: () => {
        localStorage.removeItem(authStorageKey);
        setState({ token: null, user: null });
      },
    }),
    [state, meQuery.isLoading],
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
