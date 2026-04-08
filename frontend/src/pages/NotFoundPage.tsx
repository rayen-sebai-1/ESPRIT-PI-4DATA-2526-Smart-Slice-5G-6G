import { Link } from "react-router-dom";
import { Radar } from "lucide-react";

import { Card } from "@/components/ui/card";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6 text-white">
      <Card className="max-w-lg p-8 text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-3xl bg-accentSoft text-accent">
          <Radar size={28} />
        </div>
        <h1 className="text-4xl font-semibold">Page introuvable</h1>
        <p className="mt-4 text-mutedText">
          L'interface demandee n'existe pas encore dans cette V1 NeuroSlice Tunisia.
        </p>
        <Link
          className="mt-8 inline-flex h-11 items-center justify-center rounded-2xl bg-accent px-5 text-sm font-medium text-slate-950 transition hover:bg-sky-300"
          to="/dashboard/national"
        >
          Retour au dashboard
        </Link>
      </Card>
    </div>
  );
}
