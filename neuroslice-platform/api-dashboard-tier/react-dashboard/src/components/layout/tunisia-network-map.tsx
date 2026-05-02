import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  Gauge,
  RadioTower,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";

import tunisiaGovernoratesSvg from "@/assets/tunisia-governorates.svg?raw";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { formatLatency, formatNumber, formatPercent } from "@/lib/format";
import type { RegionComparison } from "@/types/dashboard";

const GOVERNORATE_TO_REGION_CODE: Record<string, string> = {
  "11": "GT",
  "12": "GT",
  "13": "GT",
  "14": "GT",
  "21": "CB",
  "22": "CB",
  "23": "NO",
  "31": "NO",
  "32": "NO",
  "33": "NO",
  "34": "NO",
  "41": "CO",
  "42": "CO",
  "43": "CO",
  "51": "SH",
  "52": "SH",
  "53": "SH",
  "61": "SF",
  "71": "SO",
  "72": "SO",
  "73": "SO",
  "81": "SE",
  "82": "SE",
  "83": "SE",
};

const REGION_COVERAGE: Record<string, string[]> = {
  GT: ["Tunis", "Ariana", "Ben Arous", "La Manouba"],
  CB: ["Nabeul", "Zaghouan"],
  SH: ["Sousse", "Monastir", "Mahdia"],
  SF: ["Sfax"],
  NO: ["Bizerte", "Beja", "Jendouba", "Le Kef", "Siliana"],
  CO: ["Kairouan", "Kasserine", "Sidi Bouzid"],
  SE: ["Gabes", "Medenine", "Tataouine"],
  SO: ["Gafsa", "Tozeur", "Kebili"],
};

type SeverityTone = {
  rank: number;
  label: string;
  fill: string;
  stroke: string;
  glow: string;
  dotClassName: string;
  pillClassName: string;
};

function getRegionTone(region: RegionComparison, active: boolean): SeverityTone {
  const isCritical =
    region.network_load >= 82 ||
    region.sla_percent <= 62 ||
    region.high_risk_sessions_count >= 8 ||
    region.anomalies_count >= 4;
  const isHigh =
    region.network_load >= 68 ||
    region.sla_percent <= 72 ||
    region.congestion_rate >= 58 ||
    region.high_risk_sessions_count >= 4;
  const isMedium =
    region.network_load >= 52 ||
    region.sla_percent <= 84 ||
    region.congestion_rate >= 42;

  if (isCritical) {
    return {
      rank: 4,
      label: "Critical",
      fill: active ? "#fb7185" : "#e11d48",
      stroke: active ? "#ffe4e6" : "#fecdd3",
      glow: "drop-shadow(0 0 26px rgba(244,63,94,0.33))",
      dotClassName: "bg-rose-500",
      pillClassName: "border-rose-400/25 bg-rose-500/12 text-rose-100",
    };
  }

  if (isHigh) {
    return {
      rank: 3,
      label: "Under pressure",
      fill: active ? "#fb923c" : "#f97316",
      stroke: active ? "#ffedd5" : "#fed7aa",
      glow: "drop-shadow(0 0 24px rgba(249,115,22,0.28))",
      dotClassName: "bg-orange-400",
      pillClassName: "border-orange-400/25 bg-orange-500/12 text-orange-100",
    };
  }

  if (isMedium) {
    return {
      rank: 2,
      label: "Monitored",
      fill: active ? "#fbbf24" : "#f59e0b",
      stroke: active ? "#fef3c7" : "#fde68a",
      glow: "drop-shadow(0 0 22px rgba(245,158,11,0.22))",
      dotClassName: "bg-amber-300",
      pillClassName: "border-amber-300/25 bg-amber-400/12 text-amber-50",
    };
  }

  return {
    rank: 1,
    label: "Stable",
    fill: active ? "#2dd4bf" : "#14b8a6",
    stroke: active ? "#ccfbf1" : "#99f6e4",
    glow: "drop-shadow(0 0 20px rgba(20,184,166,0.2))",
    dotClassName: "bg-teal-400",
    pillClassName: "border-teal-300/25 bg-teal-400/12 text-teal-50",
  };
}

function getFallbackRegionCode(regions: RegionComparison[]) {
  return [...regions]
    .sort((left, right) => {
      const leftTone = getRegionTone(left, false);
      const rightTone = getRegionTone(right, false);
      if (leftTone.rank !== rightTone.rank) {
        return rightTone.rank - leftTone.rank;
      }
      return right.network_load - left.network_load;
    })[0]?.code;
}

export function TunisiaNetworkMap({ regions }: { regions: RegionComparison[] }) {
  const navigate = useNavigate();
  const mapRef = useRef<HTMLDivElement | null>(null);
  const [activeRegionCode, setActiveRegionCode] = useState<string | null>(null);

  const fallbackRegionCode = getFallbackRegionCode(regions) ?? regions[0]?.code ?? null;
  const orderedRegions = [...regions].sort((left, right) => {
    const leftTone = getRegionTone(left, false);
    const rightTone = getRegionTone(right, false);
    if (leftTone.rank !== rightTone.rank) {
      return rightTone.rank - leftTone.rank;
    }
    return right.network_load - left.network_load;
  });

  const activeRegion =
    orderedRegions.find((region) => region.code === activeRegionCode) ??
    orderedRegions.find((region) => region.code === fallbackRegionCode) ??
    orderedRegions[0] ??
    null;

  useEffect(() => {
    if (!regions.length) {
      setActiveRegionCode(null);
      return;
    }

    if (!activeRegionCode || !regions.some((region) => region.code === activeRegionCode)) {
      setActiveRegionCode(fallbackRegionCode);
    }
  }, [activeRegionCode, fallbackRegionCode, regions]);

  useEffect(() => {
    const root = mapRef.current;
    if (!root) return;

    const regionLookup = new Map(regions.map((region) => [region.code, region]));
    const anchors = Array.from(root.querySelectorAll<SVGAElement>("a[id^='area-']"));
    const cleanups: Array<() => void> = [];

    anchors.forEach((anchor) => {
      const governorateId = anchor.id.replace("area-", "");
      const regionCode = GOVERNORATE_TO_REGION_CODE[governorateId];
      const region = regionLookup.get(regionCode);
      const path = anchor.querySelector("path");
      if (!regionCode || !region || !path) return;

      const tone = getRegionTone(region, regionCode === activeRegionCode);
      const coverage = REGION_COVERAGE[regionCode] ?? [region.name];

      anchor.dataset.regionCode = regionCode;
      anchor.setAttribute("role", "button");
      anchor.setAttribute("tabindex", "0");
      anchor.setAttribute(
        "aria-label",
        `${region.name}. ${tone.label}. ${coverage.join(", ")}. Load ${Math.round(region.network_load)} percent.`,
      );

      path.setAttribute("fill", tone.fill);
      path.setAttribute("stroke", tone.stroke);
      path.setAttribute("stroke-width", regionCode === activeRegionCode ? "2.1" : "1.05");
      path.style.filter = tone.glow;
      path.style.opacity = regionCode === activeRegionCode ? "1" : "0.94";

      const activate = () => setActiveRegionCode(regionCode);
      const goToRegion = (event?: Event) => {
        event?.preventDefault();
        setActiveRegionCode(regionCode);
        navigate(`/dashboard/region/${region.region_id}`);
      };
      const handleKeyDown = (event: KeyboardEvent) => {
        if (event.key === "Enter" || event.key === " ") {
          goToRegion(event);
        }
      };

      anchor.addEventListener("mouseenter", activate);
      anchor.addEventListener("focus", activate);
      anchor.addEventListener("click", goToRegion);
      anchor.addEventListener("keydown", handleKeyDown);

      cleanups.push(() => {
        anchor.removeEventListener("mouseenter", activate);
        anchor.removeEventListener("focus", activate);
        anchor.removeEventListener("click", goToRegion);
        anchor.removeEventListener("keydown", handleKeyDown);
      });
    });

    return () => {
      cleanups.forEach((cleanup) => cleanup());
    };
  }, [activeRegionCode, navigate, regions]);

  if (!activeRegion) {
    return (
      <Card className="p-5">
        <div className="text-sm text-mutedText">
          The Tunisia map will be available once the national dashboard regions are loaded.
        </div>
      </Card>
    );
  }

  const activeTone = getRegionTone(activeRegion, true);
  const activeCoverage = REGION_COVERAGE[activeRegion.code] ?? [activeRegion.name];

  return (
    <Card className="overflow-hidden p-5">
      <style>{`
        .ns-tunisia-map svg {
          display: block;
          width: 100%;
          height: auto;
          overflow: visible;
        }

        .ns-tunisia-map a {
          cursor: pointer;
          outline: none;
        }

        .ns-tunisia-map path {
          vector-effect: non-scaling-stroke;
          stroke-linejoin: round;
          stroke-linecap: round;
          transition:
            fill 220ms ease,
            stroke 220ms ease,
            filter 220ms ease,
            opacity 220ms ease,
            transform 220ms ease;
          transform-origin: center;
        }

        .ns-tunisia-map a:hover path,
        .ns-tunisia-map a:focus path {
          opacity: 1;
          transform: translateY(-1px);
        }
      `}</style>

      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Tunisia supervision map</h3>
          <p className="mt-1 max-w-2xl text-sm text-mutedText">
            National map aggregated by operational zones. Each governorate inherits the color of its
            business region, with a risk level derived from network load, SLA and high-pressure
            sessions.
          </p>
        </div>

        <div className="flex flex-wrap gap-2 text-xs">
          {[
            { label: "Stable", className: "border-teal-300/25 bg-teal-400/12 text-teal-50" },
            { label: "Monitored", className: "border-amber-300/25 bg-amber-400/12 text-amber-50" },
            { label: "Under pressure", className: "border-orange-400/25 bg-orange-500/12 text-orange-100" },
            { label: "Critical", className: "border-rose-400/25 bg-rose-500/12 text-rose-100" },
          ].map((item) => (
            <span
              key={item.label}
              className={cn("rounded-full border px-3 py-1.5 tracking-[0.16em]", item.className)}
            >
              {item.label}
            </span>
          ))}
        </div>
      </div>

      <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="rounded-[30px] border border-border bg-cardAlt/70 p-4 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="rounded-full border border-border bg-background/70 px-4 py-2 text-xs uppercase tracking-[0.2em] text-mutedText">
              Territorial aggregation across 8 regions
            </div>
            <div className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-4 py-2 text-xs text-cyan-100">
              Click on an area to open the regional dashboard
            </div>
          </div>

          <div className="relative overflow-hidden rounded-[28px] border border-border bg-[#081220] p-4 sm:p-6">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(56,189,248,0.16),transparent_28%),radial-gradient(circle_at_88%_10%,rgba(20,184,166,0.13),transparent_24%),linear-gradient(180deg,rgba(10,18,32,0.9),rgba(8,17,30,0.96))]" />
            <div className="absolute inset-0 panel-grid opacity-25" />
            <div className="absolute inset-x-6 bottom-6 h-24 rounded-full bg-cyan-500/10 blur-3xl" />

            <div className="relative z-10 mx-auto max-w-[360px] sm:max-w-[420px] xl:max-w-[470px]">
              <div
                ref={mapRef}
                className="ns-tunisia-map"
                dangerouslySetInnerHTML={{ __html: tunisiaGovernoratesSvg }}
              />
            </div>

            <div className="relative z-10 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[22px] border border-border bg-background/55 px-4 py-3 text-xs text-mutedText">
              <span>Active zone: {activeRegion.name}</span>
              <span>{activeCoverage.length} governorate(s) grouped</span>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-[30px] border border-border bg-cardAlt/80 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.24em] text-mutedText">Active zone</div>
                <h4 className="mt-2 text-2xl font-semibold text-white">{activeRegion.name}</h4>
                <p className="mt-2 text-sm leading-6 text-mutedText">
                  {activeCoverage.join(" • ")}
                </p>
              </div>
              <div className={cn("rounded-full border px-3 py-1.5 text-xs tracking-[0.18em]", activeTone.pillClassName)}>
                {activeTone.label}
              </div>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-border bg-background/70 p-4">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-mutedText">
                  <Gauge size={14} />
                  SLA
                </div>
                <div className="mt-2 text-xl font-semibold text-white">
                  {formatPercent(activeRegion.sla_percent)}
                </div>
                <div className="mt-1 text-xs text-mutedText">
                  Latency {formatLatency(activeRegion.avg_latency_ms)}
                </div>
              </div>

              <div className="rounded-2xl border border-border bg-background/70 p-4">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-mutedText">
                  <TriangleAlert size={14} />
                  Network load
                </div>
                <div className="mt-2 text-xl font-semibold text-white">
                  {Math.round(activeRegion.network_load)}%
                </div>
                <div className="mt-1 text-xs text-mutedText">
                  Congestion {formatPercent(activeRegion.congestion_rate)}
                </div>
              </div>

              <div className="rounded-2xl border border-border bg-background/70 p-4">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-mutedText">
                  <RadioTower size={14} />
                  Sessions
                </div>
                <div className="mt-2 text-xl font-semibold text-white">
                  {formatNumber(activeRegion.sessions_count)}
                </div>
                <div className="mt-1 text-xs text-mutedText">
                  {activeRegion.gnodeb_count} gNodeB supervises
                </div>
              </div>

              <div className="rounded-2xl border border-border bg-background/70 p-4">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-mutedText">
                  <ShieldAlert size={14} />
                  Risk
                </div>
                <div className="mt-2 text-xl font-semibold text-white">
                  {formatNumber(activeRegion.high_risk_sessions_count)}
                </div>
                <div className="mt-1 text-xs text-mutedText">
                  {formatNumber(activeRegion.anomalies_count)} active anomalies
                </div>
              </div>
            </div>

            <button
              className="mt-5 flex w-full items-center justify-between rounded-2xl border border-accent/35 bg-accent/10 px-4 py-3 text-sm font-medium text-cyan-100 transition hover:border-accent/55 hover:bg-accent/15"
              onClick={() => navigate(`/dashboard/region/${activeRegion.region_id}`)}
              type="button"
            >
              <span>Open regional dashboard</span>
              <ArrowUpRight size={16} />
            </button>
          </div>

          <div className="rounded-[30px] border border-border bg-cardAlt/80 p-4">
            <div className="mb-3 text-xs uppercase tracking-[0.22em] text-mutedText">
              Operational regions
            </div>

            <div className="space-y-2">
              {orderedRegions.map((region) => {
                const tone = getRegionTone(region, region.code === activeRegion.code);
                const coverage = REGION_COVERAGE[region.code] ?? [region.name];

                return (
                  <button
                    key={region.region_id}
                    className={cn(
                      "w-full rounded-2xl border px-4 py-3 text-left transition",
                      region.code === activeRegion.code
                        ? "border-accent/40 bg-background/80"
                        : "border-border bg-background/55 hover:border-accent/30 hover:bg-background/70",
                    )}
                    onClick={() => navigate(`/dashboard/region/${region.region_id}`)}
                    onFocus={() => setActiveRegionCode(region.code)}
                    onMouseEnter={() => setActiveRegionCode(region.code)}
                    type="button"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={cn("h-2.5 w-2.5 rounded-full", tone.dotClassName)} />
                          <span className="text-sm font-medium text-white">{region.name}</span>
                        </div>
                        <div className="mt-1 text-xs leading-5 text-mutedText">
                          {coverage.join(" • ")}
                        </div>
                      </div>
                      <div className="text-right text-xs text-mutedText">
                        <div className="text-sm font-medium text-white">
                          {Math.round(region.network_load)}%
                        </div>
                        <div>load</div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
