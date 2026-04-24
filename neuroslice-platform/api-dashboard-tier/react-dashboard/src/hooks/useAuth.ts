import { useAuthContext } from "@/features/auth/auth-context";

export function useAuth() {
  return useAuthContext();
}
