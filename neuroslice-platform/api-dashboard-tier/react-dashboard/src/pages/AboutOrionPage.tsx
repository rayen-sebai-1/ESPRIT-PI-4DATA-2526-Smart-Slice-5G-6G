import {
  Activity,
  Building2,
  Cpu,
  HeartPulse,
  Network,
  Recycle,
  ShieldCheck,
  Zap,
} from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { usePageTitle } from "@/hooks/usePageTitle";

interface SdgCard {
  code: "SDG 3" | "SDG 9" | "SDG 11" | "SDG 12";
  title: string;
  icon: typeof HeartPulse;
  accent: string;
  summary: string;
  points: string[];
}

const sdgCards: SdgCard[] = [
  {
    code: "SDG 3",
    title: "Good Health and Well-being",
    icon: HeartPulse,
    accent: "from-emerald-500/25 to-emerald-500/5",
    summary:
      "Resilient digital network operations help keep telemedicine, emergency communications, and critical health data paths continuously available.",
    points: [
      "Early anomaly detection lowers service interruption risk for healthcare traffic.",
      "Root-cause workflows reduce mean-time-to-recovery for high-priority slices.",
      "SLA supervision supports predictable quality for latency-sensitive medical services.",
    ],
  },
  {
    code: "SDG 9",
    title: "Industry, Innovation and Infrastructure",
    icon: Cpu,
    accent: "from-sky-500/25 to-sky-500/5",
    summary:
      "ORION modernizes telecom infrastructure with AI-assisted observability, agentic operations, and continuous model governance.",
    points: [
      "Unified telemetry and live-state architecture strengthens infrastructure visibility.",
      "MLOps controls support repeatable, auditable innovation cycles.",
      "Agentic copilots assist operators in complex incident triage and action planning.",
    ],
  },
  {
    code: "SDG 11",
    title: "Sustainable Cities and Communities",
    icon: Building2,
    accent: "from-amber-500/25 to-amber-500/5",
    summary:
      "Reliable urban connectivity enables safer mobility systems, city services, and inclusive access to digital public infrastructure.",
    points: [
      "National and regional dashboards support coordinated city-scale operations.",
      "Entity-level monitoring helps isolate local degradations before they cascade.",
      "Operational transparency improves trust in connected public services.",
    ],
  },
  {
    code: "SDG 12",
    title: "Responsible Consumption and Production",
    icon: Recycle,
    accent: "from-orange-500/25 to-orange-500/5",
    summary:
      "Data-driven operations reduce wasted network resources and encourage responsible infrastructure usage through targeted interventions.",
    points: [
      "Predictive insights help avoid over-provisioning and unnecessary capacity spikes.",
      "Control actions focus remediation where impact is highest.",
      "Lifecycle governance promotes responsible model and artifact management.",
    ],
  },
];

const projectPillars = [
  {
    title: "Observe",
    description:
      "Ingest and normalize multi-domain telemetry from RAN, EDGE, and CORE into a shared operational view.",
    icon: Activity,
  },
  {
    title: "Anticipate",
    description:
      "Use AIOps prediction services to detect congestion, SLA degradation, and slice mismatch risks before incidents escalate.",
    icon: Zap,
  },
  {
    title: "Act",
    description:
      "Coordinate operators and agents through root-cause diagnosis, copilot guidance, and controlled remediation workflows.",
    icon: ShieldCheck,
  },
];

export function AboutOrionPage() {
  usePageTitle("About ORION");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Project overview"
        title="About ORION"
        description="ORION is the NeuroSlice operational intelligence layer for 5G/6G supervision in Tunisia, combining observability, AIOps prediction, and agent-assisted response in a single control cockpit."
      />

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="overflow-hidden p-6">
          <div className="relative">
            <div className="absolute -right-20 -top-20 h-52 w-52 rounded-full bg-accent/15 blur-3xl" />
            <div className="absolute -bottom-24 left-16 h-52 w-52 rounded-full bg-accent-blue/15 blur-3xl" />
            <div className="relative">
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-cardAlt/80 px-3 py-1 text-xs uppercase tracking-[0.2em] text-mutedText">
                <Network size={14} />
                Smart Slice 5G/6G
              </div>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200">
                The platform links live telemetry, AI model outputs, and actionable operations. Operators can move from
                situational awareness to validated corrective actions without leaving the dashboard ecosystem.
              </p>
              <div className="mt-6 grid gap-3 md:grid-cols-3">
                {projectPillars.map((pillar) => (
                  <div key={pillar.title} className="rounded-2xl border border-border bg-cardAlt/70 p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-white">
                      <pillar.icon size={16} />
                      {pillar.title}
                    </div>
                    <p className="mt-2 text-xs leading-6 text-mutedText">{pillar.description}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold text-white">Strategic value</h3>
          <p className="mt-2 text-sm leading-6 text-mutedText">
            ORION aligns day-to-day network operations with resilient digital infrastructure outcomes.
          </p>
          <div className="mt-5 space-y-3">
            <div className="rounded-2xl border border-border bg-cardAlt/70 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-mutedText">Operational continuity</p>
              <p className="mt-2 text-sm text-slate-200">
                Real-time dashboards and alerts minimize blind spots across the network stack.
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-cardAlt/70 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-mutedText">Data-to-decision loop</p>
              <p className="mt-2 text-sm text-slate-200">
                Prediction, explanation, and remediation are integrated to shorten incident resolution cycles.
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-cardAlt/70 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-mutedText">Responsible scaling</p>
              <p className="mt-2 text-sm text-slate-200">
                Governance workflows support sustainable expansion of AI-driven network operations.
              </p>
            </div>
          </div>
        </Card>
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-xl font-semibold text-white">ORION and the UN Sustainable Development Goals</h2>
          <p className="mt-2 text-sm text-mutedText">
            The platform directly supports SDG 3, SDG 9, SDG 11, and SDG 12 through measurable operational practices.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {sdgCards.map((sdg) => (
            <Card key={sdg.code} className="overflow-hidden p-5">
              <div className={`rounded-2xl border border-border bg-gradient-to-br ${sdg.accent} p-4`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.22em] text-mutedText">{sdg.code}</p>
                    <h3 className="mt-1 text-base font-semibold text-white">{sdg.title}</h3>
                  </div>
                  <div className="rounded-xl border border-border bg-card/60 p-2 text-white">
                    <sdg.icon size={16} />
                  </div>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-200">{sdg.summary}</p>
              </div>

              <ul className="mt-4 space-y-2">
                {sdg.points.map((point) => (
                  <li key={point} className="flex items-start gap-2 text-sm text-mutedText">
                    <span className="mt-2 h-1.5 w-1.5 rounded-full bg-accent" />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
