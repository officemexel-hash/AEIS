"use client";

import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/lib/api/advisor";

const RISK_OPTIONS: Array<{ value: RiskLevel | "all"; label: string; cls: string }> = [
  { value: "all", label: "Wszystkie ryzyka", cls: "border-border text-muted-foreground" },
  { value: "low", label: "Niskie", cls: "border-sylion-blue/30 text-sylion-blue" },
  { value: "medium", label: "Średnie", cls: "border-sylion-amber/30 text-sylion-amber" },
  { value: "high", label: "Wysokie", cls: "border-orange-400/30 text-orange-400" },
  { value: "critical", label: "Krytyczne", cls: "border-sylion-red/30 text-sylion-red" },
];

interface Props {
  risk: RiskLevel | "all";
  onRiskChange: (value: RiskLevel | "all") => void;
  domain: string;
  onDomainChange: (value: string) => void;
  domains: string[];
  historyOnly: boolean;
  onHistoryOnlyChange: (value: boolean) => void;
}

export function FilterBar({
  risk,
  onRiskChange,
  domain,
  onDomainChange,
  domains,
  historyOnly,
  onHistoryOnlyChange,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card/60 px-3 py-2">
      <div className="flex items-center gap-1.5" data-testid="filter-risk-group">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Ryzyko</span>
        {RISK_OPTIONS.map((opt) => {
          const active = risk === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onRiskChange(opt.value)}
              data-testid={`filter-risk-${opt.value}`}
              data-active={active ? "true" : "false"}
              className={cn(
                "rounded-md border px-2 py-0.5 text-[11px] transition-colors",
                opt.cls,
                active ? "bg-foreground/5" : "opacity-60 hover:opacity-100",
              )}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      <div className="h-5 w-px bg-border/60" aria-hidden />

      <div className="flex items-center gap-1.5" data-testid="filter-domain-group">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Domena</span>
        <Badge
          variant="outline"
          onClick={() => onDomainChange("all")}
          className={cn(
            "cursor-pointer text-[11px]",
            domain === "all" ? "border-sylion-blue/40 text-sylion-blue" : "text-muted-foreground",
          )}
        >
          wszystkie
        </Badge>
        {domains.map((d) => {
          const active = domain === d;
          return (
            <Badge
              key={d}
              variant="outline"
              onClick={() => onDomainChange(d)}
              className={cn(
                "cursor-pointer text-[11px]",
                active ? "border-sylion-blue/40 text-sylion-blue" : "text-muted-foreground",
              )}
            >
              {d}
            </Badge>
          );
        })}
      </div>

      <div className="h-5 w-px bg-border/60" aria-hidden />

      <label
        className="flex items-center gap-2 text-[11px] text-muted-foreground"
        data-testid="filter-history-only"
      >
        <Switch checked={historyOnly} onCheckedChange={(value) => onHistoryOnlyChange(value)} />
        Tylko zgodne z historią
      </label>
    </div>
  );
}
