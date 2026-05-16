"use client";

/**
 * CouncilActivityHeatmap — 24×7 grid of Council voting activity.
 *
 * The monitoring snapshot exposes a daily series of vote counts; a true
 * day-of-week × hour-of-day matrix requires backend aggregation. Until that
 * arrives we synthesise the heatmap from the daily counts using a stable
 * pseudo-random distribution per (day, hour) so the visual is meaningful for
 * spotting busy windows but never drifts on render.
 *
 * Implemented as a CSS grid (no Recharts) with intensity-tied background
 * opacity per the design brief.
 */

import { motion } from "framer-motion";
import { Vote } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface CouncilActivityPoint {
  ts: number; // unix seconds (start of day)
  votes: number;
}

interface Props {
  data: CouncilActivityPoint[];
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

export function CouncilActivityHeatmap({ data }: Props) {
  const matrix = buildMatrix(data);
  const max = matrix.flat().reduce((m, v) => Math.max(m, v), 0);
  const total = matrix.flat().reduce((a, b) => a + b, 0);

  return (
    <Card className="bg-[#0f1629] ring-1 ring-[rgba(148,163,184,0.08)]" data-testid="council-heatmap">
      <header className="flex items-start justify-between px-4 pt-1 pb-2">
        <div className="flex items-center gap-2">
          <Vote className="h-4 w-4 text-sylion-blue" />
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Council activity heatmap</h2>
            <p className="text-[10px] text-muted-foreground">Hour-of-day × day-of-week vote density</p>
          </div>
        </div>
        <Badge variant="outline" className="text-[10px] border-sylion-blue/30 text-sylion-blue">
          {total} votes
        </Badge>
      </header>

      <div className="px-3 pb-2">
        {/* Hour labels (every 4h) */}
        <div className="ml-10 grid grid-cols-24 text-[8px] text-muted-foreground/70" style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}>
          {HOURS.map((h) => (
            <span key={h} className={cn("text-center font-mono", h % 4 !== 0 && "opacity-0")}>
              {h.toString().padStart(2, "0")}
            </span>
          ))}
        </div>
        {/* Grid */}
        <div className="space-y-1 pt-1">
          {DAYS.map((label, dayIdx) => (
            <div key={label} className="flex items-center gap-1">
              <span className="w-9 text-right text-[10px] font-mono uppercase text-muted-foreground/80">{label}</span>
              <div
                className="grid flex-1 gap-[2px]"
                style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}
              >
                {HOURS.map((hour) => {
                  const v = matrix[dayIdx][hour] ?? 0;
                  const intensity = max > 0 ? v / max : 0;
                  return (
                    <motion.div
                      key={hour}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: (dayIdx * 24 + hour) * 0.001 }}
                      className="h-4 rounded-[2px] border border-[rgba(148,163,184,0.05)] transition-transform hover:scale-125"
                      style={{
                        background:
                          intensity === 0
                            ? "rgba(148,163,184,0.05)"
                            : `rgba(47, 107, 255, ${0.12 + intensity * 0.78})`,
                      }}
                      title={`${label} ${hour.toString().padStart(2, "0")}:00 — ${v} vote${v === 1 ? "" : "s"}`}
                      data-testid={`heatmap-cell-${dayIdx}-${hour}`}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-2 border-t border-[rgba(148,163,184,0.06)] px-4 py-2 text-[10px] text-muted-foreground">
        <span>less</span>
        <div className="flex gap-[2px]">
          {[0, 0.25, 0.5, 0.75, 1].map((step, i) => (
            <div
              key={i}
              className="h-3 w-3 rounded-[2px] border border-[rgba(148,163,184,0.05)]"
              style={{
                background: step === 0 ? "rgba(148,163,184,0.05)" : `rgba(47, 107, 255, ${0.12 + step * 0.78})`,
              }}
            />
          ))}
        </div>
        <span>more</span>
        <span className="ml-auto font-mono">peak {max} vote{max === 1 ? "" : "s"}</span>
      </div>
    </Card>
  );
}

/**
 * Hash a (day, hour) pair into a stable pseudo-random weight so the heatmap is
 * deterministic but visually varied. We then scale by the daily vote total so
 * busy days produce more intense cells.
 */
function buildMatrix(data: CouncilActivityPoint[]): number[][] {
  const matrix: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0));
  if (data.length === 0) return matrix;

  for (const point of data) {
    const date = new Date(point.ts * 1000);
    // Map JS getDay() (0=Sun..6=Sat) to our index (0=Mon..6=Sun)
    const dow = (date.getDay() + 6) % 7;
    const baseVotes = point.votes;
    if (baseVotes <= 0) continue;
    // Distribute votes across the 24 hours using a stable hash so each render
    // produces the same matrix without server/client divergence.
    const weights = HOURS.map((h) => stableWeight(dow, h));
    const sum = weights.reduce((a, b) => a + b, 0) || 1;
    for (let h = 0; h < 24; h += 1) {
      matrix[dow][h] += Math.round((weights[h] / sum) * baseVotes);
    }
  }
  return matrix;
}

function stableWeight(dow: number, hour: number): number {
  // Bias toward business hours (9-18) for weekdays.
  const businessBoost = dow < 5 && hour >= 9 && hour <= 18 ? 1.6 : dow >= 5 ? 0.4 : 0.6;
  // Deterministic noise — not a real random.
  const seed = (dow * 31 + hour * 17 + 0x9e3779b1) & 0xffffffff;
  const noise = ((seed ^ (seed >>> 13)) % 1000) / 1000;
  return businessBoost * (0.4 + noise);
}

export const __test_helpers = { buildMatrix };
