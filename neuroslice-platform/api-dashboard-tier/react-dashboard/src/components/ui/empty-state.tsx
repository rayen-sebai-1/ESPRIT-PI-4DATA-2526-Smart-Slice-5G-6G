import { DatabaseZap } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Card className="flex min-h-64 flex-col items-center justify-center gap-5 border-dashed p-8 text-center">
      <div className="rounded-3xl bg-accentSoft p-4 text-accent">
        {icon ?? <DatabaseZap size={24} />}
      </div>
      <div className="space-y-2">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="max-w-xl text-sm leading-6 text-mutedText">{description}</p>
      </div>
      {action}
    </Card>
  );
}
