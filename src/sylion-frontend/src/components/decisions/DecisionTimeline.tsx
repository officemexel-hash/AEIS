"use client";

import React, { useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Clock,
  GitCommitHorizontal,
  Layers,
  CheckCircle2,
} from "lucide-react";

/* -------------------------------------------------------------------------- */
/*  Types                                                                     */
/* -------------------------------------------------------------------------- */

export interface TimelineEntry {
  snapshot_id: string;
  decision_id: string;
  decision_class: string;
  choice_made: string;
  gate_id?: string;
  codebase_hash: string;
  module_states: Record<string, any>;
  is_active: boolean;
  superseded_by?: string;
  cascade_events_count: number;
  created_at: number;
}

export interface DecisionTimelineProps {
  entries: TimelineEntry[];
  onEntryClick?: (entry: TimelineEntry) => void;
  selectedId?: string;
}

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                   */
/* -------------------------------------------------------------------------- */

const DECISION_CLASS_COLORS: Record<string, string> = {
  D0: "bg-muted-foreground/30",
  D1: "bg-sylion-blue",
  D2: "bg-sylion-blue",
  D3: "bg-sylion-amber",
  D4: "bg-sylion-amber",
  D5: "bg-sylion-red",
};

const DECISION_CLASS_TEXT: Record<string, string> = {
  D0: "text-muted-foreground",
  D1: "text-sylion-blue",
  D2: "text-sylion-blue",
  D3: "text-sylion-amber",
  D4: "text-sylion-amber",
  D5: "text-sylion-red",
};

function relativeTime(epochSeconds: number): string {
  const diff = Math.floor(Date.now() / 1000) - epochSeconds;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function truncateHash(hash: string): string {
  return hash.slice(0, 8);
}

/* -------------------------------------------------------------------------- */
/*  TimelineEntryCard                                                         */
/* -------------------------------------------------------------------------- */

function TimelineEntryCard({
  entry,
  isSelected,
  onClick,
}: {
  entry: TimelineEntry;
  isSelected: boolean;
  onClick: () => void;
}) {
  const isSuperseded = !!entry.superseded_by;

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -6, transition: { duration: 0.15 } }}
      transition={{ duration: 0.25 }}
      onClick={onClick}
      className={cn(
        "relative flex-1 rounded-lg border p-3 cursor-pointer transition-all duration-200",
        "hover:scale-[1.005]",
        isSelected
          ? "border-primary/50 shadow-[0_0_12px_rgba(59,130,246,0.2)]"
          : "border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.16)]",
        isSuperseded && "opacity-60"
      )}
      style={{
        background:
          "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
        backdropFilter: "blur(12px)",
      }}
    >
      {/* Top row: decision class + badges */}
      <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
        <span
          className={cn(
            "text-[10px] font-bold font-mono tracking-wide",
            DECISION_CLASS_TEXT[entry.decision_class] ?? "text-muted-foreground"
          )}
        >
          {entry.decision_class}
        </span>

        {entry.is_active && (
          <Badge
            variant="outline"
            className="h-4 text-[8px] px-1.5 bg-sylion-green/15 text-sylion-green border-sylion-green/30"
          >
            <CheckCircle2 className="w-2.5 h-2.5 mr-0.5" />
            Active
          </Badge>
        )}

        {isSuperseded && (
          <Badge
            variant="outline"
            className="h-4 text-[8px] px-1.5 bg-muted/30 text-muted-foreground border-[rgba(148,163,184,0.12)]"
          >
            Superseded
          </Badge>
        )}

        {entry.gate_id && (
          <Badge
            variant="outline"
            className="h-4 text-[8px] px-1.5 bg-sylion-blue/10 text-sylion-blue border-sylion-blue/20"
          >
            {entry.gate_id}
          </Badge>
        )}
      </div>

      {/* Choice made */}
      <p className="text-[11px] text-foreground leading-relaxed">
        {entry.choice_made.length > 80
          ? entry.choice_made.slice(0, 80) + "..."
          : entry.choice_made}
      </p>

      {/* Bottom row: hash + timestamp + cascade count */}
      <div className="flex items-center gap-3 mt-2">
        <span className="text-[9px] text-muted-foreground/50 font-mono">
          {truncateHash(entry.codebase_hash)}
        </span>

        <span className="flex items-center gap-1 text-[9px] text-muted-foreground/50">
          <Clock className="w-2.5 h-2.5" />
          {relativeTime(entry.created_at)}
        </span>

        {entry.cascade_events_count > 0 && (
          <span className="flex items-center gap-1 text-[9px] text-sylion-amber/70">
            <Layers className="w-2.5 h-2.5" />
            {entry.cascade_events_count} cascade
            {entry.cascade_events_count !== 1 ? "s" : ""}
          </span>
        )}
      </div>
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Exported Component                                                        */
/* -------------------------------------------------------------------------- */

export function DecisionTimeline({
  entries,
  onEntryClick,
  selectedId,
}: DecisionTimelineProps) {
  const handleClick = useCallback(
    (entry: TimelineEntry) => {
      onEntryClick?.(entry);
    },
    [onEntryClick]
  );

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <GitCommitHorizontal className="w-6 h-6 text-muted-foreground/30 mb-2" />
        <p className="text-[11px] text-muted-foreground">
          No decision history yet
        </p>
      </div>
    );
  }

  return (
    <div className="relative flex">
      {/* Gradient timeline line */}
      <div
        className="absolute left-[7px] top-2 bottom-2 w-[2px]"
        style={{
          background:
            "linear-gradient(180deg, #22c55e, #3b82f6, #ef4444)",
        }}
      />

      {/* Entries */}
      <div className="flex flex-col gap-3 ml-5 flex-1 min-w-0">
        <AnimatePresence mode="popLayout">
          {entries.map((entry, idx) => {
            const isSelected = selectedId === entry.snapshot_id;
            const dotColor =
              DECISION_CLASS_COLORS[entry.decision_class] ??
              DECISION_CLASS_COLORS.D0;

            return (
              <div key={entry.snapshot_id} className="relative flex gap-3">
                {/* Timeline dot */}
                <div className="relative flex items-start pt-3">
                  <div
                    className={cn(
                      "w-3.5 h-3.5 rounded-full border-2 border-[#0a0f1e] shrink-0",
                      dotColor,
                      entry.is_active && "ring-2 ring-sylion-green/30"
                    )}
                  />
                </div>

                {/* Card */}
                <TimelineEntryCard
                  entry={entry}
                  isSelected={isSelected}
                  onClick={() => handleClick(entry)}
                />
              </div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
