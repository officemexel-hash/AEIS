"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import {
  Check, Loader2, Lock, Circle,
  Lightbulb, Search, BookOpen, Blocks, Rocket, TestTube, Flag,
} from "lucide-react";
import type { PipelineStage } from "@/lib/types";

const stageIconMap: Record<string, React.ElementType> = {
  "Idea & Scope": Lightbulb,
  "Skill Discovery": Search,
  "Book / Ksiega": BookOpen,
  "Module Design": Blocks,
  "Execution": Rocket,
  "Validation": TestTube,
  "Rollout": Flag,
};

const statusIconMap: Record<PipelineStage["status"], React.ElementType> = {
  completed: Check,
  active: Loader2,
  blocked: Lock,
  pending: Circle,
};

export function PipelineHero({ stages }: { stages: PipelineStage[] }) {
  const activeIdx = stages.findIndex((s) => s.status === "active");
  const overallProgress = Math.round(
    stages.reduce((acc, s) => acc + s.progress, 0) / stages.length
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.15 }}
      className="relative overflow-hidden rounded-xl border p-6"
      style={{
        background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
        borderColor: "rgba(148,163,184,0.08)",
      }}
    >
      {/* Subtle radial glow behind active stage */}
      <div
        className="absolute pointer-events-none"
        style={{
          top: "30%",
          left: `${((activeIdx + 0.5) / stages.length) * 100}%`,
          transform: "translate(-50%, -50%)",
          width: 200,
          height: 200,
          background: "radial-gradient(circle, rgba(47,107,255,0.08) 0%, transparent 70%)",
          borderRadius: "50%",
        }}
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-sm font-semibold text-foreground tracking-wide">Pipeline Progress</h3>
          <p className="text-xs text-muted-foreground mt-0.5">From Idea to Execution — 7-stage lifecycle</p>
        </div>
        <div className="flex items-center gap-2.5">
          <span className="text-xs text-muted-foreground">Overall</span>
          <span className="text-2xl font-bold text-gradient-blue">{overallProgress}%</span>
        </div>
      </div>

      {/* Stepper */}
      <div className="relative flex items-start">
        {stages.map((stage, i) => {
          const StageIcon = stageIconMap[stage.name] || Circle;
          const StatusIcon = statusIconMap[stage.status];
          const isActive = stage.status === "active";
          const isCompleted = stage.status === "completed";
          const isBlocked = stage.status === "blocked";
          const isPending = stage.status === "pending";
          const isLast = i === stages.length - 1;

          return (
            <div key={stage.id} className="flex flex-col items-center flex-1 min-w-0 relative">
              {/* Connector + Node row */}
              <div className="flex items-center w-full">
                {/* Left connector */}
                {i > 0 && (
                  <div className="flex-1 h-[2px] relative overflow-hidden">
                    <div
                      className={cn(
                        "absolute inset-0",
                        isCompleted ? "bg-sylion-blue/50" : isActive ? "bg-gradient-to-r from-sylion-blue/50 to-sylion-blue/15" : "bg-white/5"
                      )}
                    />
                    {isCompleted && (
                      <motion.div
                        className="absolute top-0 bottom-0 w-4 bg-sylion-blue/30 rounded-full"
                        animate={{ left: ["-20%", "120%"] }}
                        transition={{ duration: 2.5, repeat: Infinity, ease: "linear", delay: i * 0.3 }}
                      />
                    )}
                  </div>
                )}
                {i === 0 && <div className="flex-1" />}

                {/* Node */}
                <motion.div
                  className={cn(
                    "relative w-10 h-10 rounded-full flex items-center justify-center shrink-0 border-2 transition-all duration-300 z-10",
                    isCompleted && "bg-sylion-blue/15 border-sylion-blue/40",
                    isActive && "bg-sylion-blue/10 border-sylion-blue/60",
                    isBlocked && "bg-sylion-red/10 border-sylion-red/40",
                    isPending && "bg-white/[0.03] border-white/10",
                  )}
                  style={{
                    boxShadow: isActive
                      ? "0 0 24px rgba(47,107,255,0.25), 0 0 48px rgba(47,107,255,0.10)"
                      : isBlocked
                      ? "0 0 24px rgba(243,18,96,0.20), 0 0 48px rgba(243,18,96,0.08)"
                      : isCompleted
                      ? "0 0 12px rgba(47,107,255,0.10)"
                      : "none",
                  }}
                  whileHover={{ scale: 1.1 }}
                >
                  {isCompleted ? (
                    <Check className="w-4 h-4 text-sylion-blue" />
                  ) : isActive ? (
                    <>
                      <StageIcon className="w-4 h-4 text-sylion-blue" />
                      {/* Active pulse ring */}
                      <motion.div
                        className="absolute inset-0 rounded-full border-2 border-sylion-blue/30"
                        animate={{ scale: [1, 1.4], opacity: [0.5, 0] }}
                        transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
                      />
                    </>
                  ) : isBlocked ? (
                    <Lock className="w-4 h-4 text-sylion-red animate-pulse" />
                  ) : (
                    <StageIcon className="w-4 h-4 text-muted-foreground/50" />
                  )}
                </motion.div>

                {/* Right connector */}
                {!isLast && (
                  <div className="flex-1 h-[2px] relative overflow-hidden">
                    <div
                      className={cn(
                        "absolute inset-0",
                        isCompleted ? "bg-sylion-blue/50" : "bg-white/5"
                      )}
                    />
                    {isCompleted && (
                      <motion.div
                        className="absolute top-0 bottom-0 w-4 bg-sylion-blue/30 rounded-full"
                        animate={{ left: ["-20%", "120%"] }}
                        transition={{ duration: 2.5, repeat: Infinity, ease: "linear", delay: i * 0.3 + 0.15 }}
                      />
                    )}
                  </div>
                )}
                {isLast && <div className="flex-1" />}
              </div>

              {/* Label + Progress */}
              <div className="mt-3 text-center w-full px-0.5">
                <p className={cn(
                  "text-[11px] font-medium truncate leading-tight",
                  isActive ? "text-sylion-blue" : isCompleted ? "text-foreground" : isBlocked ? "text-sylion-red" : "text-muted-foreground/60"
                )}>
                  {stage.label}
                </p>

                {/* Progress bar for active/completed */}
                {(isActive || isCompleted) && (
                  <div className="mt-1.5 mx-auto max-w-[80%]">
                    <div className="h-1 rounded-full bg-white/5 overflow-hidden">
                      <motion.div
                        className={cn(
                          "h-full rounded-full",
                          isCompleted ? "bg-sylion-blue/50" : "bg-sylion-blue"
                        )}
                        initial={{ width: 0 }}
                        animate={{ width: `${stage.progress}%` }}
                        transition={{ duration: 1, delay: i * 0.1, ease: "easeOut" }}
                      />
                    </div>
                    {isActive && (
                      <p className="text-[10px] text-sylion-blue mt-1 font-medium">{stage.progress}%</p>
                    )}
                  </div>
                )}

                {isBlocked && (
                  <p className="text-[10px] text-sylion-red mt-1 font-medium">Blocked</p>
                )}

                {/* Description on hover */}
                <p className="text-[9px] text-muted-foreground/40 mt-1 truncate hidden group-hover:block">
                  {stage.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-5 mt-5 pt-4 border-t" style={{ borderColor: "rgba(148,163,184,0.06)" }}>
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <div className="w-2.5 h-2.5 rounded-full bg-sylion-blue/40 flex items-center justify-center">
            <Check className="w-1.5 h-1.5 text-sylion-blue" />
          </div>
          Completed
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <div className="w-2.5 h-2.5 rounded-full border border-sylion-blue/60 bg-sylion-blue/10 pulse-glow-blue" />
          Active
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <div className="w-2.5 h-2.5 rounded-full border border-sylion-red/40 bg-sylion-red/10" />
          Blocked
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <div className="w-2.5 h-2.5 rounded-full border border-white/10 bg-white/[0.03]" />
          Pending
        </div>
      </div>
    </motion.div>
  );
}
