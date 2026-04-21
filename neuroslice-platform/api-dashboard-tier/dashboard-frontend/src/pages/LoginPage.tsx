import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { LockKeyhole, Moon, Sparkles, ShieldCheck, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { OrionLogo } from "@/components/layout/orion-logo";
import { useAuth } from "@/hooks/useAuth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useTheme } from "@/lib/theme";
import { appSections, roleDefaultRoute } from "@/lib/constants";

type LocationState = {
  from?: {
    pathname?: string;
  };
};

export function LoginPage() {
  usePageTitle("Sign in");

  const { login, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated && user) {
      navigate(roleDefaultRoute[user.role], { replace: true });
    }
  }, [isAuthenticated, user, navigate]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await login({ email, password });
      const state = location.state as LocationState | null;
      const target = state?.from?.pathname || roleDefaultRoute[response.user.role];
      navigate(target, { replace: true });
    } catch (caught) {
      const message = axios.isAxiosError(caught)
        ? String(caught.response?.data?.detail ?? caught.message)
        : caught instanceof Error
          ? caught.message
          : "Request failed. Please try again.";
      setError(
        message.toLowerCase().includes("invalide") || message.toLowerCase().includes("invalid")
          ? "Invalid credentials. Please check your email and password."
          : "Cannot connect. Please contact your administrator.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="relative min-h-screen bg-background px-4 py-6 text-ink theme-transition md:px-8">
      {/* Theme toggle */}
      <button
        onClick={toggleTheme}
        title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        className="absolute right-6 top-6 inline-flex h-10 w-10 items-center justify-center rounded-full border border-border bg-card text-mutedText transition-all hover:border-accent/50 hover:text-accent"
      >
        {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
      </button>

      <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-7xl gap-6 xl:grid-cols-[1.15fr_0.85fr]">

        {/* Left panel — brand + features */}
        <Card className="panel-grid relative overflow-hidden p-8 md:p-12">
          <div className="relative flex h-full flex-col justify-between gap-10">
            {/* Logo + name */}
            <div>
              <div className="mb-8 flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-accentSoft ring-1 ring-accent/30">
                  <OrionLogo size={34} />
                </div>
                <div>
                  <p className="text-2xl font-semibold tracking-[0.22em] text-ink">ORION</p>
                  <p className="text-xs uppercase tracking-[0.3em] text-mutedText">
                    Telecom AI supervision
                  </p>
                </div>
              </div>

              <h1 className="max-w-xl text-4xl font-semibold leading-tight tracking-tight text-ink md:text-5xl">
                Network Intelligence{" "}
                <span className="text-accent">Platform</span>
              </h1>
              <p className="mt-5 max-w-xl text-base leading-7 text-mutedText">
                {appSections.nocSummary}
              </p>
            </div>

            {/* Feature cards */}
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-[20px] border border-border bg-cardAlt p-5">
                <div className="mb-4 inline-flex rounded-2xl bg-accentSoft p-3 text-accent">
                  <ShieldCheck size={18} />
                </div>
                <p className="text-sm font-semibold text-ink">Provisioned access</p>
                <p className="mt-2 text-sm leading-6 text-mutedText">
                  Accounts are created exclusively by the platform administrator.
                </p>
              </div>
              <div className="rounded-[20px] border border-border bg-cardAlt p-5">
                <div className="mb-4 inline-flex rounded-2xl bg-accentBlueSoft p-3 text-accentBlue">
                  <Sparkles size={18} />
                </div>
                <p className="text-sm font-semibold text-ink">AI Predictions</p>
                <p className="mt-2 text-sm leading-6 text-mutedText">
                  SLA, congestion, and anomaly scores powered by ML backend.
                </p>
              </div>
              <div className="rounded-[20px] border border-border bg-cardAlt p-5">
                <div className="mb-4 inline-flex rounded-2xl bg-accentSoft p-3 text-accent">
                  <LockKeyhole size={18} />
                </div>
                <p className="text-sm font-semibold text-ink">Role-based access</p>
                <p className="mt-2 text-sm leading-6 text-mutedText">
                  NOC, Manager, Data/MLOps and Admin each see their scope.
                </p>
              </div>
            </div>
          </div>
        </Card>

        {/* Right panel — login form */}
        <Card className="mx-auto flex w-full max-w-xl flex-col justify-center p-6 md:p-10">
          <div className="mb-8">
            <p className="text-xs uppercase tracking-[0.28em] text-mutedText">Access control</p>
            <h2 className="mt-3 text-3xl font-semibold text-ink">Sign in</h2>
            <p className="mt-3 text-sm leading-6 text-mutedText">
              Sign in with the account your administrator provisioned for you.
            </p>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm font-medium text-inkSecondary" htmlFor="email">
                Email
              </label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@neuroslice.tn"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-inkSecondary" htmlFor="password">
                Password
              </label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>

            {error ? (
              <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
                {error}
              </div>
            ) : null}

            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
              {isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <div className="mt-6 rounded-2xl border border-border bg-cardAlt px-4 py-4 text-sm leading-6 text-mutedText">
            No account yet? Contact your platform administrator to provision access with the appropriate role (NOC, Manager, Data/MLOps).
          </div>
        </Card>
      </div>
    </div>
  );
}
