"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ConfidenceLabel } from "@/lib/api/advisor";

interface Props {
  score: number;
  label?: ConfidenceLabel;
  breakdown?: {
    council_match: number;
    history_match: number;
    pricing_quality: number;
    historical_acceptance_rate: number;
    used_local_fallback?: boolean;
  };
  compact?: boolean;
  className?: string;
}

export function ConfidenceMeter({ score, label, breakdown, compact = false, className }: Props) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  const tone =
    pct >= 90 ? "text-sylion-green" : pct >= 75 ? "text-sylion-amber" : pct >= 50 ? "text-orange-400" : "text-sylion-red";
  const bar =
    pct >= 90 ? "bg-sylion-green" : pct >= 75 ? "bg-sylion-amber" : pct >= 50 ? "bg-orange-400" : "bg-sylion-red";

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-center gap-2">
        <span className={cn("text-sm font-semibold tabular-nums", tone)}>{pct}%</span>
        {label ? (
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {confidenceLabel(label)}
          </span>
        ) : null}
        {breakdown?.used_local_fallback ? (
          <span className="text-[10px] uppercase tracking-wide text-orange-400">lokalny fallback x0.8</span>
        ) : null}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted/30">
        <motion.div
          className={cn("h-full rounded-full", bar)}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.45, ease: "easeOut" }}
        />
      </div>
      {breakdown && !compact ? (
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 pt-1.5 text-[11px] text-muted-foreground">
          <ComponentRow label="Zgodnosc Rady" value={breakdown.council_match} weight={0.4} />
          <ComponentRow label="Zgodnosc historii" value={breakdown.history_match} weight={0.4} />
          <ComponentRow label="Jakosc kosztow" value={breakdown.pricing_quality} weight={0.2} />
          <ComponentRow label="Akceptacje historyczne" value={breakdown.historical_acceptance_rate} weight={null} />
        </div>
      ) : null}
    </div>
  );
}

function ComponentRow({ label, value, weight }: { label: string; value: number; weight: number | null }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="truncate">
        {label}
        {weight !== null ? <span className="text-muted-foreground/50"> · w{weight}</span> : null}
      </span>
      <span className="font-mono tabular-nums text-foreground/80">{pct}%</span>
    </div>
  );
}

function confidenceLabel(label: ConfidenceLabel): string {
  if (label === "low") return "niska";
  if (label === "med") return "srednia";
  if (label === "high") return "wysoka";
  if (label === "very_high") return "bardzo wysoka";
  return "pewna";
}
