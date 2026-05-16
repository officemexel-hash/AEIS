"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { DLevel } from "@/lib/api/advisor";

const STYLES: Record<DLevel, string> = {
  D0: "border-muted-foreground/30 text-muted-foreground",
  D1: "border-sylion-blue/30 text-sylion-blue",
  D2: "border-sylion-amber/30 text-sylion-amber",
  D3: "border-orange-400/30 text-orange-400",
  D4: "border-orange-500/40 text-orange-500",
  D5: "border-sylion-red/40 text-sylion-red bg-sylion-red/5",
};

const LABEL: Record<DLevel, string> = {
  D0: "trivial",
  D1: "minor",
  D2: "moderate",
  D3: "significant",
  D4: "high-impact",
  D5: "critical",
};

export function DLevelBadge({ level, withLabel = false, className }: { level: DLevel; withLabel?: boolean; className?: string }) {
  return (
    <Badge variant="outline" className={cn("font-mono text-[10px]", STYLES[level], className)}>
      {level}
      {withLabel ? ` · ${LABEL[level]}` : ""}
    </Badge>
  );
}
