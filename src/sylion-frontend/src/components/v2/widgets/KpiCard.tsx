"use client";

/**
 * SYLION AEIS v2 — W16 G1 widget: KpiCard.
 *
 * Mała karta KPI: label, big value, optional unit + trend, variant kolor.
 * Renderuje skeleton, gdy `value === undefined` (loading).
 */

import { ArrowDown, ArrowRight, ArrowUp } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { HelpTip } from "@/components/common/HelpTip";
import { cn } from "@/lib/utils";

export interface KpiTrend {
  direction: "up" | "down" | "flat";
  pct: number;
}

export interface KpiCardProps {
  label: string;
  value: string | number | undefined;
  unit?: string;
  trend?: KpiTrend;
  helpText?: string;
  icon?: ReactNode;
  variant?: "default" | "success" | "warning" | "danger";
}

const VARIANT_CLASSES: Record<NonNullable<KpiCardProps["variant"]>, string> = {
  default: "ring-foreground/10",
  success: "ring-emerald-500/40 bg-emerald-500/5",
  warning: "ring-amber-500/40 bg-amber-500/5",
  danger: "ring-destructive/40 bg-destructive/5",
};

const TREND_COLOR: Record<KpiTrend["direction"], string> = {
  up: "text-emerald-500",
  down: "text-destructive",
  flat: "text-muted-foreground",
};

function TrendIcon({ direction }: { direction: KpiTrend["direction"] }) {
  if (direction === "up") return <ArrowUp className="h-3 w-3" />;
  if (direction === "down") return <ArrowDown className="h-3 w-3" />;
  return <ArrowRight className="h-3 w-3" />;
}

function formatValue(value: string | number): string {
  if (typeof value === "number") {
    if (Number.isInteger(value)) return value.toLocaleString("pl-PL");
    return value.toLocaleString("pl-PL", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    });
  }
  return value;
}

export function KpiCard({
  label,
  value,
  unit,
  trend,
  helpText,
  icon,
  variant = "default",
}: KpiCardProps) {
  const isLoading = value === undefined;

  return (
    <Card
      size="sm"
      className={cn("flex flex-col gap-2 px-3 py-3 ring-1", VARIANT_CLASSES[variant])}
      data-slot="kpi-card"
    >
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-muted-foreground">
        <span className="flex items-center gap-1">
          {icon && <span className="text-muted-foreground/80">{icon}</span>}
          {label}
          {helpText && <HelpTip text={helpText} />}
        </span>
        {trend && (
          <span
            className={cn("inline-flex items-center gap-0.5 text-[10px]", TREND_COLOR[trend.direction])}
          >
            <TrendIcon direction={trend.direction} />
            {trend.direction === "flat" ? "0%" : `${trend.pct.toFixed(1)}%`}
          </span>
        )}
      </div>

      {isLoading ? (
        <Skeleton className="h-8 w-24" />
      ) : (
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold leading-none tracking-tight">
            {formatValue(value)}
          </span>
          {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
        </div>
      )}
    </Card>
  );
}
