"use client";

/**
 * AlertsBanner — high-risk pending alerts list.
 *
 * Each alert links to /advisor/[cardId] when a card_id is supplied (so the
 * operator can open the AdvisorCard detail). When no card_id is attached we
 * render the alert as a non-link informational row (still visible, no nav).
 */

import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, ShieldAlert } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/lib/api/advisor";

export interface AlertItem {
  id: string;
  severity: RiskLevel;
  title: string;
  card_id?: string;
}

interface Props {
  alerts: AlertItem[];
}

const SEVERITY_STYLES: Record<RiskLevel, { box: string; pill: string; icon: string }> = {
  low: {
    box: "border-sylion-blue/20 bg-sylion-blue/5 hover:border-sylion-blue/40",
    pill: "border-sylion-blue/30 text-sylion-blue",
    icon: "text-sylion-blue",
  },
  medium: {
    box: "border-sylion-amber/20 bg-sylion-amber/5 hover:border-sylion-amber/40",
    pill: "border-sylion-amber/30 text-sylion-amber",
    icon: "text-sylion-amber",
  },
  high: {
    box: "border-orange-400/30 bg-orange-400/5 hover:border-orange-400/50",
    pill: "border-orange-400/30 text-orange-400",
    icon: "text-orange-400",
  },
  critical: {
    box: "border-sylion-red/30 bg-sylion-red/5 hover:border-sylion-red/50 animate-pulse",
    pill: "border-sylion-red/30 text-sylion-red",
    icon: "text-sylion-red",
  },
};

const SEVERITY_RANK: Record<RiskLevel, number> = { low: 0, medium: 1, high: 2, critical: 3 };

export function AlertsBanner({ alerts }: Props) {
  const sorted = [...alerts].sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity]);

  return (
    <Card className="bg-[#0f1629] ring-1 ring-[rgba(148,163,184,0.08)]" data-testid="alerts-banner">
      <header className="flex items-center justify-between px-4 pt-1 pb-2">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-orange-400" />
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Active alerts</h2>
            <p className="text-[10px] text-muted-foreground">High-risk pending items across all projects</p>
          </div>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px]",
            sorted.some((a) => a.severity === "critical")
              ? "border-sylion-red/30 text-sylion-red"
              : "border-sylion-amber/30 text-sylion-amber",
          )}
        >
          {sorted.length} alert{sorted.length === 1 ? "" : "s"}
        </Badge>
      </header>

      <div className="space-y-2 px-4 pb-3">
        {sorted.length === 0 ? (
          <div className="rounded-md border border-sylion-green/15 bg-sylion-green/5 px-3 py-3 text-center text-[11px] text-sylion-green">
            All clear · no high-risk pending items
          </div>
        ) : (
          sorted.map((alert, i) => {
            const styles = SEVERITY_STYLES[alert.severity];
            const linkable = Boolean(alert.card_id);
            const inner = (
              <div className="flex items-center gap-3">
                <AlertTriangle className={cn("h-3.5 w-3.5 shrink-0", styles.icon)} />
                <div className="min-w-0 flex-1">
                  <div className="mb-0.5 flex flex-wrap items-center gap-1.5">
                    <Badge variant="outline" className={cn("uppercase text-[9px]", styles.pill)}>
                      {alert.severity}
                    </Badge>
                  </div>
                  <p className="truncate text-sm font-medium text-foreground">{alert.title}</p>
                </div>
                {linkable ? (
                  <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1" />
                ) : null}
              </div>
            );
            return (
              <motion.div
                key={alert.id}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                {linkable ? (
                  <a
                    href={`/advisor/${encodeURIComponent(alert.card_id!)}`}
                    className={cn(
                      "group block rounded-lg border px-3 py-2 transition-colors",
                      styles.box,
                    )}
                    data-testid={`alert-row-${alert.id}`}
                  >
                    {inner}
                  </a>
                ) : (
                  <div
                    className={cn("rounded-lg border px-3 py-2", styles.box)}
                    data-testid={`alert-row-${alert.id}`}
                  >
                    {inner}
                  </div>
                )}
              </motion.div>
            );
          })
        )}
      </div>
    </Card>
  );
}
