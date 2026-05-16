"use client";

import { motion } from "framer-motion";
import { AlertTriangle, Bell, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCostAlerts } from "@/lib/api/hooks";

const alertBadgeStyle: Record<string, string> = {
  budget_warning: "border-sylion-amber/40 text-sylion-amber bg-sylion-amber/5",
  budget_exceeded: "border-sylion-red/40 text-sylion-red bg-sylion-red/5",
  rate_spike: "border-orange-400/40 text-orange-400 bg-orange-400/5",
};

const alertIconColor: Record<string, string> = {
  budget_warning: "text-sylion-amber",
  budget_exceeded: "text-sylion-red",
  rate_spike: "text-orange-400",
};

const alertIcon: Record<string, React.ElementType> = {
  budget_warning: AlertTriangle,
  budget_exceeded: AlertTriangle,
  rate_spike: TrendingUp,
};

function formatAlertTime(ts: any): string {
  if (!ts) return "--";
  const d = typeof ts === "number" ? new Date(ts) : new Date(ts);
  const diff = Date.now() - d.getTime();
  if (diff < 60000) return "just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return d.toLocaleDateString();
}

function formatAlertType(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function CostAlertsSection() {
  const { data: alertsData } = useCostAlerts();
  const alerts = alertsData?.alerts ?? [];

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
          <Bell className="w-3.5 h-3.5" />
          Cost Alerts
        </h2>
        <div className="flex-1 h-px bg-border" />
        <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
          {alerts.length} alert{alerts.length !== 1 ? "s" : ""}
        </span>
      </div>

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <div
          className="rounded-xl border p-4"
          style={{
            background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
            borderColor: "rgba(148,163,184,0.08)",
          }}
        >
          {alerts.length === 0 ? (
            <div className="flex items-center justify-center py-6">
              <div className="text-center">
                <Bell className="w-6 h-6 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No budget alerts</p>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map((alert: any, i: number) => {
                const type: string = alert.alert_type ?? alert.type ?? "budget_warning";
                const AIcon = alertIcon[type] ?? AlertTriangle;
                return (
                  <motion.div
                    key={alert.id ?? i}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.2 }}
                    className="flex items-start gap-3 p-3 rounded-lg bg-muted/20 border border-border/30"
                  >
                    <div className={cn("w-7 h-7 rounded-lg flex items-center justify-center shrink-0", alertIconColor[type] ? `bg-current/10` : "bg-muted/30")} style={alertIconColor[type] ? { backgroundColor: "rgba(148,163,184,0.06)" } : {}}>
                      <AIcon className={cn("w-3.5 h-3.5", alertIconColor[type] ?? "text-muted-foreground")} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span
                          className={cn(
                            "text-[9px] px-2 py-0.5 rounded-full border",
                            alertBadgeStyle[type] ?? "border-border text-muted-foreground"
                          )}
                        >
                          {formatAlertType(type)}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {formatAlertTime(alert.timestamp ?? alert.created_at)}
                        </span>
                      </div>
                      <p className="text-xs text-foreground leading-relaxed">
                        {alert.message ?? alert.msg ?? JSON.stringify(alert)}
                      </p>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
