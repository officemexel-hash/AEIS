"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth, useBundles } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import {
  Package,
  RefreshCw,
  WifiOff,
  CheckCircle2,
  Layers,
  ArrowUpRight,
  Server,
  BarChart3,
  GitBranch,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Bundle {
  bundle_id: string;
  name: string;
  description?: string;
  component_count: number;
  status: "draft" | "active" | "deployed" | "archived";
  latest_version?: string;
  created_at?: number;
  updated_at?: number;
}

/* ============================================================
   Helpers
   ============================================================ */

function statusStyles(status: string): { badge: string; dot: string; text: string; iconBg: string } {
  switch (status) {
    case "draft":
      return {
        dot: "bg-muted-foreground",
        badge: "border-muted-foreground/30 text-muted-foreground bg-muted-foreground/5",
        text: "text-muted-foreground",
        iconBg: "bg-muted-foreground/10",
      };
    case "active":
      return {
        dot: "bg-sylion-blue",
        badge: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
        text: "text-sylion-blue",
        iconBg: "bg-sylion-blue/10",
      };
    case "deployed":
      return {
        dot: "bg-sylion-green",
        badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
        text: "text-sylion-green",
        iconBg: "bg-sylion-green/10",
      };
    case "archived":
      return {
        dot: "bg-sylion-amber",
        badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
        text: "text-sylion-amber",
        iconBg: "bg-sylion-amber/10",
      };
    default:
      return {
        dot: "bg-muted-foreground",
        badge: "border-muted-foreground/30 text-muted-foreground bg-muted-foreground/5",
        text: "text-muted-foreground",
        iconBg: "bg-muted-foreground/10",
      };
  }
}

/* ============================================================
   Page Component
   ============================================================ */

export default function BundlesPage() {
  const { data: healthRaw, refresh: refreshHealth } = useHealth();
  const { data: bundlesData, refresh: refreshBundles } = useBundles();

  const healthData = healthRaw as { status: string; version?: string; modules?: number; endpoints?: number; db_mode?: string };
  const backendLive = healthData.status === "ok";

  const bundles: Bundle[] = bundlesData.bundles ?? [];

  const refreshAll = () => {
    refreshHealth();
    refreshBundles();
  };

  /* ---------- Derived: summary stats ---------- */
  const totalBundles = bundles.length;
  const activeCount = useMemo(() => bundles.filter((b) => b.status === "active").length, [bundles]);
  const deployedCount = useMemo(() => bundles.filter((b) => b.status === "deployed").length, [bundles]);
  const versionCount = useMemo(() => {
    const versions = new Set(bundles.map((b) => b.latest_version).filter(Boolean));
    return versions.size;
  }, [bundles]);

  /* ---------- Loading skeleton ---------- */
  const loading = healthRaw.status === "unknown";

  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
          <div>
            <div className="h-6 w-36 bg-muted animate-pulse rounded" />
            <div className="h-4 w-52 bg-muted animate-pulse rounded mt-1" />
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
            <Package className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Pakiety</h1>
            <p className="text-sm text-muted-foreground">Component packaging and deployment management</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend Not Reachable</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            The SYLION backend is not responding. Bundle data requires a running backend.
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
      label: "Liczba pakietów",
      value: totalBundles,
      icon: Package,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Active",
      value: activeCount,
      icon: ArrowUpRight,
      color: "text-sylion-blue",
      bgColor: "bg-sylion-blue/10",
    },
    {
      label: "Deployed",
      value: deployedCount,
      icon: CheckCircle2,
      color: "text-sylion-green",
      bgColor: "bg-sylion-green/10",
    },
    {
      label: "Versions",
      value: versionCount,
      icon: GitBranch,
      color: "text-purple-400",
      bgColor: "bg-purple-400/10",
    },
  ];

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Package className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Pakiety</h1>
            <p className="text-sm text-muted-foreground">Component packaging and deployment management</p>
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

      {/* ====== BUNDLES TABLE ====== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.2 }}
      >
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-xs font-semibold">Pakiety</h3>
              <Badge variant="outline" className="text-[9px] border-border/50 text-muted-foreground">
                {totalBundles} pakietów
              </Badge>
            </div>
          </div>

          {bundles.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Package className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">Brak zarejestrowanych pakietów</p>
              <p className="text-[10px] mt-1 opacity-60">Utwórz pakiety przez Core API</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border/20">
                    <th className="text-left font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Name</th>
                    <th className="text-left font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Description</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Components</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Status</th>
                    <th className="text-center font-medium text-muted-foreground px-4 py-2.5 uppercase tracking-wider text-[10px]">Version</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/10">
                  {bundles
                    .sort((a, b) => {
                      const order = { deployed: 0, active: 1, draft: 2, archived: 3 };
                      return (order[a.status] ?? 4) - (order[b.status] ?? 4);
                    })
                    .map((bundle, idx) => {
                      const styles = statusStyles(bundle.status);

                      return (
                        <motion.tr
                          key={bundle.bundle_id ?? idx}
                          initial={{ opacity: 0, x: -4 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.2, delay: 0.25 + idx * 0.03 }}
                          className="hover:bg-muted/10 transition-colors"
                        >
                          {/* Name */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className={cn("w-6 h-6 rounded-md flex items-center justify-center", styles.iconBg)}>
                                <Package className={cn("w-3 h-3", styles.text)} />
                              </div>
                              <span className="text-xs font-medium text-foreground">{bundle.name ?? bundle.bundle_id}</span>
                            </div>
                          </td>

                          {/* Description */}
                          <td className="px-4 py-3">
                            <span className="text-muted-foreground truncate max-w-[250px] block">
                              {bundle.description || "---"}
                            </span>
                          </td>

                          {/* Component count */}
                          <td className="px-4 py-3 text-center">
                            <div className="flex items-center justify-center gap-1">
                              <Layers className="w-3 h-3 text-muted-foreground" />
                              <span className="font-mono text-foreground">{bundle.component_count ?? 0}</span>
                            </div>
                          </td>

                          {/* Status badge */}
                          <td className="px-4 py-3 text-center">
                            <Badge variant="outline" className={cn("text-[9px] uppercase font-semibold", styles.badge)}>
                              <span className={cn("w-1.5 h-1.5 rounded-full mr-1.5", styles.dot)} />
                              {bundle.status}
                            </Badge>
                          </td>

                          {/* Latest version */}
                          <td className="px-4 py-3 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              <GitBranch className="w-3 h-3 text-muted-foreground" />
                              <span className="font-mono text-muted-foreground">
                                {bundle.latest_version || "---"}
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
    </div>
  );
}
