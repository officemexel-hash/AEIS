"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/lib/api/advisor";

const RISK_STYLES: Record<RiskLevel, string> = {
  low: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
  medium: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
  high: "border-orange-400/30 text-orange-400 bg-orange-400/5",
  critical: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
};

export function RiskBadge({ level, className }: { level: RiskLevel; className?: string }) {
  return (
    <Badge variant="outline" className={cn("uppercase tracking-wide text-[10px]", RISK_STYLES[level], className)}>
      {riskLabel(level)}
    </Badge>
  );
}

function riskLabel(level: RiskLevel): string {
  if (level === "low") return "niskie";
  if (level === "medium") return "srednie";
  if (level === "high") return "wysokie";
  return "krytyczne";
}
