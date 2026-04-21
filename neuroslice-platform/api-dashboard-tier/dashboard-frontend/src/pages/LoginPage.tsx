import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { LockKeyhole, RadioTower, ShieldCheck, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { usePageTitle } from "@/hooks/usePageTitle";
import { appSections, roleDefaultRoute } from "@/lib/constants";

type LocationState = {
  from?: {
    pathname?: string;
  };
};

export function LoginPage() {
  usePageTitle("Connexion");

  const { login, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
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
          : "La requete a echoue. Merci de reessayer.";
      setError(
        message.toLowerCase().includes("invalide")
          ? "Identifiants invalides. Verifiez email et mot de passe."
          : "Connexion impossible. Merci de contacter votre administrateur.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-background px-4 py-6 text-white md:px-8">
      <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-7xl gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="panel-grid relative overflow-hidden p-8 md:p-10">
          <div className="absolute inset-0 bg-network-glow opacity-70" />
          <div className="relative flex h-full flex-col justify-between gap-10">
            <div>
              <div className="inline-flex items-center gap-3 rounded-full border border-border bg-cardAlt/70 px-4 py-2 text-sm text-slate-200">
                <RadioTower size={16} className="text-accent" />
                Telecom AI supervision platform
              </div>
              <h1 className="mt-6 max-w-2xl text-4xl font-semibold tracking-tight text-white md:text-5xl">
                NeuroSlice Tunisia
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">{appSections.nocSummary}</p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <Card className="bg-cardAlt/75 p-5">
                <div className="rounded-2xl bg-accentSoft p-3 text-accent">
                  <ShieldCheck size={18} />
                </div>
                <div className="mt-4 text-sm font-medium text-white">Acces provisionne</div>
                <p className="mt-2 text-sm leading-6 text-mutedText">
                  Les comptes sont crees exclusivement par l'administrateur de la plateforme.
                </p>
              </Card>
              <Card className="bg-cardAlt/75 p-5">
                <div className="rounded-2xl bg-accentSoft p-3 text-accent">
                  <Sparkles size={18} />
                </div>
                <div className="mt-4 text-sm font-medium text-white">Predictions IA</div>
                <p className="mt-2 text-sm leading-6 text-mutedText">
                  Scores SLA, congestion et anomalies deja exposes via backend.
                </p>
              </Card>
              <Card className="bg-cardAlt/75 p-5">
                <div className="rounded-2xl bg-accentSoft p-3 text-accent">
                  <LockKeyhole size={18} />
                </div>
                <div className="mt-4 text-sm font-medium text-white">Acces par role</div>
                <p className="mt-2 text-sm leading-6 text-mutedText">
                  NOC, Manager, Data/MLOps et Admin voient chacun uniquement leur perimetre.
                </p>
              </Card>
            </div>
          </div>
        </Card>

        <Card className="mx-auto flex w-full max-w-xl flex-col justify-center p-6 md:p-8">
          <div className="mb-6">
            <p className="text-xs uppercase tracking-[0.28em] text-mutedText">Access control</p>
            <h2 className="mt-3 text-3xl font-semibold text-white">Connexion plateforme</h2>
            <p className="mt-3 text-sm leading-6 text-mutedText">
              Connecte-toi avec le compte que l'administrateur t'a fourni. La creation de compte
              est reservee a la console d'administration.
            </p>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm text-slate-200" htmlFor="email">
                Email
              </label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>

            <div>
              <label className="mb-2 block text-sm text-slate-200" htmlFor="password">
                Mot de passe
              </label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>

            {error ? (
              <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                {error}
              </div>
            ) : null}

            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
              {isSubmitting ? "Connexion..." : "Se connecter"}
            </Button>
          </form>

          <div className="mt-6 rounded-2xl border border-border bg-cardAlt/70 px-4 py-4 text-sm leading-6 text-mutedText">
            Pas encore de compte ? Contacte l'administrateur de la plateforme pour qu'il te
            provisionne un acces avec le role adapte (NOC, Manager, Data/MLOps).
          </div>
        </Card>
      </div>
    </div>
  );
}
