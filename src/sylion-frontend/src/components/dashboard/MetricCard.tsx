"use client";

import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import {
  Lightbulb, Wrench, FolderKanban, Shield, Play, Activity,
  TrendingUp, TrendingDown, Minus,
} from "lucide-react";
import type { KPI } from "@/lib/types";
import { motion } from "framer-motion";

const iconMap: Record<string, React.ElementType> = {
  Lightbulb, Wrench, FolderKanban, Shield, Play, Activity,
};

const accentMap: Record<string, { icon: string; glow: string; bg: string; bar: string }> = {
  Lightbulb: {
    icon: "text-amber-400",
    glow: "0 0 16px rgba(245,158,11,0.35)",
    bg: "rgba(245,158,11,0.10)",
    bar: "from-amber-500/60 to-amber-500/10",
  },
  Wrench: {
    icon: "text-sylion-blue",
    glow: "0 0 16px rgba(47,107,255,0.35)",
    bg: "rgba(47,107,255,0.10)",
    bar: "from-blue-500/60 to-blue-500/10",
  },
  FolderKanban: {
    icon: "text-sylion-blue",
    glow: "0 0 16px rgba(47,107,255,0.35)",
    bg: "rgba(47,107,255,0.10)",
    bar: "from-blue-500/60 to-blue-500/10",
  },
  Shield: {
    icon: "text-amber-400",
    glow: "0 0 16px rgba(245,158,11,0.35)",
    bg: "rgba(245,158,11,0.10)",
    bar: "from-amber-500/60 to-amber-500/10",
  },
  Play: {
    icon: "text-emerald-400",
    glow: "0 0 16px rgba(23,201,100,0.35)",
    bg: "rgba(23,201,100,0.10)",
    bar: "from-emerald-500/60 to-emerald-500/10",
  },
  Activity: {
    icon: "text-emerald-400",
    glow: "0 0 16px rgba(23,201,100,0.35)",
    bg: "rgba(23,201,100,0.10)",
    bar: "from-emerald-500/60 to-emerald-500/10",
  },
};

function seededSparkline(seed: number): number[] {
  let s = seed;
  const rand = () => { s = (s * 16807 + 0) % 2147483647; return s / 2147483647; };
  const pts: number[] = [];
  let v = 50;
  for (let i = 0; i < 12; i++) {
    v = Math.max(10, Math.min(90, v + (rand() - 0.45) * 20));
    pts.push(v);
  }
  return pts;
}

function MiniSparkline({ color, seed = 1 }: { color: string; seed?: number }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const data = useMemo(() => seededSparkline(seed), [seed]);
  const w = 56;
  const h = 20;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`).join(" ");

  if (!mounted) {
    return <svg width={w} height={h} className="opacity-40" />;
  }

  return (
    <svg width={w} height={h} className="opacity-40">
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={color}
      />
    </svg>
  );
}

export function MetricCard({ kpi, index = 0 }: { kpi: KPI; index?: number }) {
  const Icon = iconMap[kpi.icon] || Activity;
  const trendIcon = kpi.trend === "up" ? TrendingUp : kpi.trend === "down" ? TrendingDown : Minus;
  const trendColor = kpi.trend === "up" ? "text-emerald-400" : kpi.trend === "down" ? "text-amber-400" : "text-muted-foreground";
  const accent = accentMap[kpi.icon] || accentMap.Activity;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06 }}
      className="group relative overflow-hidden rounded-xl border transition-all duration-300 hover:scale-[1.015]"
      style={{
        background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
        borderColor: "rgba(148,163,184,0.08)",
        backdropFilter: "blur(12px)",
      }}
    >
      {/* Top accent glow line */}
      <div
        className="absolute top-0 left-[10%] right-[10%] h-px opacity-60"
        style={{
          background: `linear-gradient(90deg, transparent, ${accent.bg.replace("0.10", "0.5")}, transparent)`,
        }}
      />

      <div className="p-4 pb-3">
        {/* Icon + Label row */}
        <div className="flex items-center justify-between mb-3">
          <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{kpi.label}</p>
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-300 group-hover:scale-110"
            style={{
              background: accent.bg,
              boxShadow: `inset 0 1px 0 rgba(255,255,255,0.05), ${accent.glow}`,
            }}
          >
            <Icon className={cn("w-4 h-4", accent.icon)} />
          </div>
        </div>

        {/* Big number */}
        <p className="text-3xl font-bold tracking-tight text-foreground mb-1">{kpi.value}</p>

        {/* Sparkline + Trend */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            {(() => {
              const TrendIcon = trendIcon;
              return <TrendIcon className={cn("w-3 h-3", trendColor)} />;
            })()}
            <span className={cn("text-xs font-medium", trendColor)}>
              {kpi.change > 0 ? "+" : ""}{kpi.change}%
            </span>
            <span className="text-[10px] text-muted-foreground">vs last period</span>
          </div>
          <MiniSparkline color={accent.icon} seed={index + 1} />
        </div>
      </div>

      {/* Bottom gradient bar */}
      <div
        className="h-[2px] mx-3 rounded-full opacity-50"
        style={{
          background: `linear-gradient(90deg, transparent, currentColor, transparent)`,
        }}
      />
    </motion.div>
  );
}
