"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { TrendingUp, Activity, Zap, BarChart3 } from "lucide-react";
import type { TelemetryPoint } from "@/lib/types";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-lg border px-3 py-2 shadow-lg"
      style={{
        background: "rgba(20,27,45,0.95)",
        borderColor: "rgba(148,163,184,0.12)",
        backdropFilter: "blur(8px)",
      }}
    >
      <p className="text-[10px] text-muted-foreground mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-muted-foreground">{entry.name}:</span>
          <span className="font-semibold text-foreground">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

export function TelemetryChart({ data }: { data: TelemetryPoint[] }) {
  const chartData = data.slice(-24);
  const latestEvents = chartData[chartData.length - 1]?.events || 0;
  const latestTasks = chartData[chartData.length - 1]?.tasks || 0;
  const latestLoad = chartData[chartData.length - 1]?.load || 0;
  const avgEvents = Math.round(chartData.reduce((a, d) => a + d.events, 0) / chartData.length);
  const throughputTrend = chartData.length >= 2
    ? Math.round(((chartData[chartData.length - 1].events - chartData[chartData.length - 2].events) / Math.max(chartData[chartData.length - 2].events, 1)) * 100)
    : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.3 }}
      className="relative overflow-hidden rounded-xl border"
      style={{
        background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
        borderColor: "rgba(148,163,184,0.08)",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 pb-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground tracking-wide">System Telemetry</h3>
          <p className="text-[10px] text-muted-foreground mt-0.5">24-hour execution throughput + event volume</p>
        </div>
        <div className="flex items-center gap-1 text-xs text-emerald-400">
          <TrendingUp className="w-3.5 h-3.5" />
          <span className="font-medium">+{Math.abs(throughputTrend)}%</span>
        </div>
      </div>

      {/* Area Chart */}
      <div className="px-2">
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="eventGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(47,107,255,0.35)" />
                <stop offset="95%" stopColor="rgba(47,107,255,0.02)" />
              </linearGradient>
              <linearGradient id="taskGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(23,201,100,0.25)" />
                <stop offset="95%" stopColor="rgba(23,201,100,0.02)" />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(148,163,184,0.06)"
              vertical={false}
            />
            <XAxis
              dataKey="time"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "rgba(148,163,184,0.35)", fontSize: 10 }}
              interval={5}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "rgba(148,163,184,0.35)", fontSize: 10 }}
              width={30}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="events"
              name="Events"
              stroke="rgba(47,107,255,0.8)"
              strokeWidth={2}
              fill="url(#eventGradient)"
              dot={false}
              activeDot={{ r: 4, fill: "#2F6BFF", stroke: "#0f1629", strokeWidth: 2 }}
            />
            <Area
              type="monotone"
              dataKey="tasks"
              name="Tasks"
              stroke="rgba(23,201,100,0.6)"
              strokeWidth={1.5}
              fill="url(#taskGradient)"
              dot={false}
              activeDot={{ r: 3, fill: "#17C964", stroke: "#0f1629", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Time labels */}
      <div className="flex justify-between px-4 -mt-1">
        <span className="text-[10px] text-muted-foreground/50">24h ago</span>
        <span className="text-[10px] text-muted-foreground/50">now</span>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-3 p-4 pt-3 mt-2 border-t" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-sylion-blue/10 flex items-center justify-center">
            <Activity className="w-3 h-3 text-sylion-blue" />
          </div>
          <div>
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Events/h</p>
            <p className="text-sm font-semibold text-foreground">{latestEvents}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-emerald-500/10 flex items-center justify-center">
            <Zap className="w-3 h-3 text-emerald-400" />
          </div>
          <div>
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Tasks</p>
            <p className="text-sm font-semibold text-foreground">{latestTasks}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-amber-500/10 flex items-center justify-center">
            <BarChart3 className="w-3 h-3 text-amber-400" />
          </div>
          <div>
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Load</p>
            <p className="text-sm font-semibold text-foreground">{latestLoad}%</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-purple-500/10 flex items-center justify-center">
            <TrendingUp className="w-3 h-3 text-purple-400" />
          </div>
          <div>
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Avg/h</p>
            <p className="text-sm font-semibold text-foreground">{avgEvents}</p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
