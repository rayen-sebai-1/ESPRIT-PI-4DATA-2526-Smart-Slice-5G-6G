import { useQuery } from "@tanstack/react-query";

import { getMlopsPromotions } from "@/api/mlopsApi";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageTitle } from "@/hooks/usePageTitle";

export function MlopsPromotionsPage() {
  usePageTitle("MLOps - Promotions");
  const query = useQuery({ queryKey: ["mlops", "promotions"], queryFn: () => getMlopsPromotions(80) });

  if (query.isLoading) {
    return <div className="py-10 text-sm text-mutedText">Chargement des promotions...</div>;
  }
  if (query.isError || !query.data) {
    return <EmptyState title="Promotions indisponibles" description="Echec de la lecture du registre." />;
  }

  return (
    <Card className="p-5">
      <h3 className="text-lg font-semibold text-white">Historique des promotions</h3>
      <p className="text-sm text-mutedText">
        Lignes promoted=true ou promotion_status=rejected.
      </p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-[0.22em] text-mutedText">
            <tr>
              <th className="pb-3 pr-4">Modele</th>
              <th className="pb-3 pr-4">Version</th>
              <th className="pb-3 pr-4">Stage</th>
              <th className="pb-3 pr-4">Statut</th>
              <th className="pb-3 pr-4">Run id</th>
              <th className="pb-3 pr-4">Date</th>
              <th className="pb-3 pr-4">Raison</th>
            </tr>
          </thead>
          <tbody className="text-slate-100">
            {query.data.map((event) => (
              <tr key={`${event.model_name}-${event.version}-${event.run_id}`} className="border-t border-border">
                <td className="py-3 pr-4">{event.model_name}</td>
                <td className="py-3 pr-4">{event.version ?? "-"}</td>
                <td className="py-3 pr-4">{event.stage ?? "-"}</td>
                <td className="py-3 pr-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      event.promotion_status === "promoted"
                        ? "bg-emerald-500/15 text-emerald-300"
                        : "bg-amber-500/15 text-amber-300"
                    }`}
                  >
                    {event.promotion_status ?? "-"}
                  </span>
                </td>
                <td className="py-3 pr-4 font-mono text-xs">{event.run_id ?? "-"}</td>
                <td className="py-3 pr-4 text-mutedText">{event.created_at ?? "-"}</td>
                <td className="max-w-md py-3 pr-4 text-mutedText">{event.reason ?? "-"}</td>
              </tr>
            ))}
            {query.data.length === 0 ? (
              <tr>
                <td className="py-6 text-center text-mutedText" colSpan={7}>
                  Aucun evenement de promotion.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
