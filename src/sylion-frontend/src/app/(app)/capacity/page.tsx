"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  useHealth,
  useCapacityResources,
  useCapacityRecommendations,
} from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import {
  Gauge,
  WifiOff,
  RefreshCw,
  Server,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Cpu,
  HardDrive,
  Activity,
  Layers,
  Zap,
  ArrowUpRight,
  CheckCircle2,
  CircleDot,
  BarChart3,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface CapacityResource {
  resource_id: string;
  resource_type: string;
  current_utilization: number;
  trend: "up" | "down" | "stable";
  forecasted_peak: number;
  unit?: string;
  status?: string;
}

interface CapacityRecommendation {
  recommendation_id: string;
  resource_id?: string;
  resource_type?: string;
  priority: "critical" | "high" | "medium" | "low";
  action: string;
  description?: string;
  estimated_impact?: string;
  status?: string;
}

/* ============================================================
   Helpers
   ============================================================ */

function utilizationColor(pct: number): string {
  if (pct >= 90) return "text-sylion-red";
  if (pct >= 70) return "text-sylion-amber";
  return "text-sylion-green";
}

function utilizationBarColor(pct: number): string {
  if (pct >= 90) return "bg-sylion-red";
  if (pct >= 70) return "bg-sylion-amber";
  return "bg-sylion-green";
}

function priorityStyles(priority: string): {
  badge: string;
  dot: string;
  text: string;
} {
  switch (priority) {
    case "critical":
      return {
        badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
        dot: "bg-sylion-red",
        text: "text-sylion-red",
      };
    case "high":
      return {
        badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
        dot: "bg-sylion-amber",
        text: "text-sylion-amber",
      };
    case "medium":
      return {
        badge: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
        dot: "bg-sylion-blue",
        text: "text-sylion-blue",
      };
    default:
      return {
        badge: "border-muted-foreground/30 text-muted-foreground bg-muted-foreground/5",
        dot: "bg-muted-foreground",
        text: "text-muted-foreground",
      };
  }
}

function TrendIndicator({ trend }: { trend: string }) {
  if (trend === "up") {
    return (
      <div className="flex items-center gap-1 text-sylion-amber">
        <TrendingUp className="w-3 h-3" />
        <span className="text-[10px]">Rising</span>
      </div>
    );
  }
  if (trend === "down") {
    return (
      <div className="flex items-center gap-1 text-sylion-green">
        <TrendingDown className="w-3 h-3" />
        <span className="text-[10px]">Falling</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1 text-muted-foreground">
      <Minus className="w-3 h-3" />
      <span className="text-[10px]">Stable</span>
    </div>
  );
}

function resourceTypeIcon(type: string): React.ElementType {
  const lower = type.toLowerCase();
  if (lower.includes("cpu") || lower.includes("compute")) return Cpu;
  if (lower.includes("mem") || lower.includes("ram")) return HardDrive;
  if (lower.includes("storage") || lower.includes("disk")) return Server;
  if (lower.includes("net") || lower.includes("bandwidth")) return Activity;
  if (lower.includes("gpu") || lower.includes("accelerat")) return Zap;
  return Layers;
}

/* ============================================================
   Page Component
   ============================================================ */

export default function CapacityPage() {
  const { data: healthRaw, refresh: refreshHealth } = useHealth();
  const { data: resourcesData, refresh: refreshResources } = useCapacityResources();
  const { data: recommendationsData, refresh: refreshRecommendations } = useCapacityRecommendations();

  const healthData = healthRaw as { status: string; version?: string; modules?: number; endpoints?: number; db_mode?: string };
  const backendLive = healthData.status === "ok";

  const resources: CapacityResource[] = resourcesData.resources ?? [];
  const recommendations: CapacityRecommendation[] = recommendationsData.recommendations ?? [];

  const refreshAll = () => {
    refreshHealth();
    refreshResources();
    refreshRecommendations();
  };

  /* ---------- Derived: summary stats ---------- */
  const totalResources = resources.length;

  const avgUtilization = useMemo(() => {
    if (resources.length === 0) return 0;
    const sum = resources.reduce((acc, r) => acc + (r.current_utilization ?? 0), 0);
    return Math.round(sum / resources.length);
  }, [resources]);

  const forecastedBottlenecks = useMemo(() => {
    return resources.filter((r) => (r.forecasted_peak ?? 0) >= 85).length;
  }, [resources]);

  const criticalRecommendations = useMemo(() => {
    return recommendations.filter(
      (r) => r.priority === "critical" || r.priority === "high"
    ).length;
  }, [recommendations]);

  /* ---------- Loading skeleton ---------- */
  const loading = healthRaw.status === "unknown";

  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
          <div>
            <div className="h-6 w-40 bg-muted animate-pulse rounded" />
            <div className="h-4 w-56 bg-muted animate-pulse rounded mt-1" />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-muted animate-pulse rounded-lg" />
          ))}
        </div>
        <div className="h-64 bg-muted animate-pulse rounded-lg" />
      </div>
    );
  }

  /* ---------- Backend unreachable ---------- */
  if (!backendLive) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-red/10 border border-sylion-red/20 flex items-center justify-center">
            <Gauge className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Planer pojemności</h1>
            <p className="text-sm text-muted-foreground">Resource tracking, forecasting, and scaling recommendations</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend Not Reachable</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            The SYLION backend is not responding. Capacity data, resource tracking, and recommendations require a running backend.
          </p>
          <Button variant="outline" size="sm" onClick={refreshAll}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Retry Connection
          </Button>
        </Card>
      </div>
    );
  }

  /* ---------- Stats cards ---------- */
  const statsCards = [
    {
      label: "Total Resources",
      value: totalResources,
      icon: Layers,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Avg Utilization",
      value: `${avgUtilization}%`,
      icon: Gauge,
      color: avgUtilization >= 80 ? "text-sylion-red" : avgUtilization >= 60 ? "text-sylion-amber" : "text-sylion-green",
      bgColor: avgUtilization >= 80 ? "bg-sylion-red/10" : avgUtilization >= 60 ? "bg-sylion-amber/10" : "bg-sylion-green/10",
    },
    {
      label: "Forecasted Bottlenecks",
      value: forecastedBottlenecks,
      icon: AlertTriangle,
      color: forecastedBottlenecks > 0 ? "text-sylion-red" : "text-sylion-green",
      bgColor: forecastedBottlenecks > 0 ? "bg-sylion-red/10" : "bg-sylion-green/10",
    },
    {
      label: "Scaling Recommendations",
      value: criticalRecommendations,
      icon: Zap,
      color: criticalRecommendations > 0 ? "text-sylion-amber" : "text-sylion-green",
      bgColor: criticalRecommendations > 0 ? "bg-sylion-amber/10" : "bg-sylion-green/10",
    },
  ];

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Gauge className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Planer pojemności</h1>
            <p className="text-sm text-muted-foreground">Resource tracking, forecasting, and scaling recommendations</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="outline" className="text-[10px] flex items-center gap-1.5 border-sylion-green/30 text-sylion-green bg-sylion-green/5">
            <span className="w-1.5 h-1.5 rounded-full bg-sylion-green animate-pulse" />
            LIVE
          </Badge>

          <Button variant="outline" size="sm" onClick={refreshAll}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* ====== STATS ROW (4 cards) ====== */}
      <div className="grid grid-cols-4 gap-3">
        {statsCards.map((stat, i) => {
          const SIcon = stat.icon;
          return (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.05 }}
            >
              <Card className="p-4 bg-[#0f1629] border-sylion-border card-hover">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{stat.label}</p>
                    <p className={cn("text-xl font-semibold mt-1 font-mono", stat.color)}>{stat.value}</p>
                  </div>
                  <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", stat.bgColor)}>
                    <SIcon className={cn("w-4 h-4", stat.color)} />
                  </div>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* ====== RESOURCES TABLE ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.2 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-xs font-semibold">Tracked Resources</h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {totalResources} resources
              </Badge>
            </div>
          </div>

          {resources.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Server className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">No resources tracked</p>
              <p className="text-[10px] mt-1 opacity-60">Register resources via the Capacity Planning API</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border/20">
                    <th className="text-left font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Type</th>
                    <th className="text-left font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Resource ID</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Utilization</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Trend</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Forecasted Peak</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/10">
                  {resources
                    .sort((a, b) => (b.forecasted_peak ?? 0) - (a.forecasted_peak ?? 0))
                    .map((res, idx) => {
                      const RIcon = resourceTypeIcon(res.resource_type ?? "");
                      const util = res.current_utilization ?? 0;
                      const peak = res.forecasted_peak ?? 0;
                      const trend = res.trend ?? "stable";

                      return (
                        <motion.tr
                          key={res.resource_id ?? idx}
                          initial={{ opacity: 0, x: -4 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.2, delay: 0.25 + idx * 0.03 }}
                          className="hover:bg-muted/10 transition-colors"
                        >
                          {/* Type */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className={cn(
                                "w-6 h-6 rounded-md flex items-center justify-center",
                                util >= 80 ? "bg-sylion-red/10" : util >= 60 ? "bg-sylion-amber/10" : "bg-sylion-green/10"
                              )}>
                                <RIcon className={cn(
                                  "w-3 h-3",
                                  util >= 80 ? "text-sylion-red" : util >= 60 ? "text-sylion-amber" : "text-sylion-green"
                                )} />
                              </div>
                              <span className="text-muted-foreground">{res.resource_type ?? "---"}</span>
                            </div>
                          </td>

                          {/* Resource ID */}
                          <td className="px-4 py-3">
                            <span className="font-mono text-foreground">{res.resource_id ?? "---"}</span>
                          </td>

                          {/* Utilization */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className="w-16">
                                <Progress value={util} className="h-1.5" />
                              </div>
                              <span className={cn("font-mono w-10 text-right", utilizationColor(util))}>
                                {util}%
                              </span>
                            </div>
                          </td>

                          {/* Trend */}
                          <td className="px-4 py-3 text-center">
                            <TrendIndicator trend={trend} />
                          </td>

                          {/* Forecasted Peak */}
                          <td className="px-4 py-3 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              {peak >= 85 && (
                                <AlertTriangle className="w-3 h-3 text-sylion-red" />
                              )}
                              <span className={cn("font-mono", utilizationColor(peak))}>
                                {peak}%
                              </span>
                            </div>
                          </td>
                        </motion.tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </motion.div>

      {/* ====== RECOMMENDATIONS ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.35 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-sylion-amber" />
              <h3 className="text-xs font-semibold">Scaling Recommendations</h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {recommendations.length} total
              </Badge>
            </div>
          </div>

          {recommendations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <CheckCircle2 className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">No recommendations at this time</p>
              <p className="text-[10px] mt-1 opacity-60">Resources are operating within normal parameters</p>
            </div>
          ) : (
            <div className="divide-y divide-border/10">
              {recommendations
                .sort((a, b) => {
                  const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
                  return (order[a.priority] ?? 4) - (order[b.priority] ?? 4);
                })
                .map((rec, idx) => {
                  const styles = priorityStyles(rec.priority);
                  return (
                    <motion.div
                      key={rec.recommendation_id ?? idx}
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.2, delay: 0.4 + idx * 0.04 }}
                      className={cn(
                        "flex items-start gap-3 px-4 py-3 hover:bg-muted/10 transition-colors",
                        rec.priority === "critical" && "bg-sylion-red/[0.02]"
                      )}
                    >
                      {/* Priority badge */}
                      <Badge variant="outline" className={cn("text-[9px] shrink-0 uppercase font-semibold", styles.badge)}>
                        <span className={cn("w-1.5 h-1.5 rounded-full mr-1.5", styles.dot)} />
                        {rec.priority}
                      </Badge>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-xs font-medium text-foreground truncate">{rec.action}</p>
                          {rec.resource_type && (
                            <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground shrink-0">
                              {rec.resource_type}
                            </Badge>
                          )}
                        </div>
                        {rec.description && (
                          <p className="text-[10px] text-muted-foreground mt-0.5">{rec.description}</p>
                        )}
                        {rec.estimated_impact && (
                          <div className="flex items-center gap-1 mt-1">
                            <ArrowUpRight className="w-2.5 h-2.5 text-sylion-blue" />
                            <span className="text-[10px] text-sylion-blue">{rec.estimated_impact}</span>
                          </div>
                        )}
                      </div>

                      {/* Resource ID */}
                      {rec.resource_id && (
                        <span className="text-[10px] font-mono text-muted-foreground shrink-0">{rec.resource_id}</span>
                      )}
                    </motion.div>
                  );
                })}
            </div>
          )}
        </Card>
      </motion.div>
    </div>
  );
}
