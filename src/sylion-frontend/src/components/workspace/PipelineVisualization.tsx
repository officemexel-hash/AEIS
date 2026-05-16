"use client";

import React from "react";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  Loader2,
  Clock,
  XCircle,
  ChevronRight,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface PipelineStep {
  phase: string;
  step_type?: string;
  status: string;
  output?: any;
  timestamp?: number;
}

export interface PipelineVisualizationProps {
  steps: PipelineStep[];
  runStatus?: string;
}

/* ============================================================
   Constants
   ============================================================ */

const PHASES = ["analyze", "design", "implement", "test", "review"] as const;

const PHASE_LABELS: Record<string, string> = {
  analyze: "Analyze",
  design: "Design",
  implement: "Implement",
  test: "Test",
  review: "Review",
};

/* ============================================================
   Helpers
   ============================================================ */

type PhaseStatus = "completed" | "running" | "failed" | "pending";

function normaliseStatus(raw: string): PhaseStatus {
  const s = raw.toLowerCase();
  if (s === "completed" || s === "complete" || s === "pass") return "completed";
  if (s === "running" || s === "in_progress") return "running";
  if (s === "failed" || s === "fail" || s === "cancelled") return "failed";
  return "pending";
}

/**
 * Find a step matching a given phase name.
 * Matches against `phase` and `step_type` fields, case-insensitive,
 * via partial inclusion so values like "analysis" match "analyze".
 */
function findStepForPhase(
  steps: PipelineStep[],
  phase: string
): PipelineStep | undefined {
  const target = phase.toLowerCase();
  return steps.find((step) => {
    const ph = (step.phase ?? "").toLowerCase();
    const st = (step.step_type ?? "").toLowerCase();
    return ph.includes(target) || target.includes(ph) || st.includes(target) || target.includes(st);
  });
}

/**
 * Derive the status of a phase from its matched step and the overall
 * pipeline run status.  If no step exists yet the phase is "pending"
 * unless it is the first phase of a running pipeline.
 */
function derivePhaseStatus(
  step: PipelineStep | undefined,
  phase: string,
  runStatus?: string
): PhaseStatus {
  if (step) return normaliseStatus(step.status);

  // No step recorded yet — infer from run-level status.
  const run = (runStatus ?? "").toLowerCase();
  if (run !== "running" && run !== "in_progress") return "pending";

  // The first phase with no step yet on a running pipeline is "running"
  // (the pipeline just started and hasn't produced its step record).
  const phaseIdx = PHASES.indexOf(phase as any);
  if (phaseIdx === 0) return "running";

  return "pending";
}

/* ============================================================
   Sub-components
   ============================================================ */

function PhaseIcon({ status }: { status: PhaseStatus }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="w-4 h-4 text-sylion-green" />;
    case "running":
      return <Loader2 className="w-4 h-4 text-primary animate-spin" />;
    case "failed":
      return <XCircle className="w-4 h-4 text-sylion-red" />;
    case "pending":
    default:
      return <Clock className="w-4 h-4 text-muted-foreground" />;
  }
}

function Connector({ completed }: { completed: boolean }) {
  return (
    <div className="flex items-center shrink-0 px-0.5">
      <div
        className={cn(
          "h-px w-5",
          completed
            ? "bg-sylion-green/50"
            : "bg-[rgba(148,163,184,0.1)] border-t border-dashed border-muted-foreground/20"
        )}
      />
      <ChevronRight
        className={cn(
          "w-3 h-3 shrink-0 -mx-0.5",
          completed ? "text-sylion-green/50" : "text-muted-foreground/20"
        )}
      />
    </div>
  );
}

function PhaseCard({
  phase,
  status,
  step,
}: {
  phase: string;
  status: PhaseStatus;
  step?: PipelineStep;
}) {
  const isRunning = status === "running";

  return (
    <div
      className={cn(
        "flex flex-col items-center gap-1.5 rounded-lg border px-3 py-2.5 min-w-[72px] transition-colors",
        // Background & border per status
        status === "completed" &&
          "bg-sylion-green/5 border-sylion-green/15",
        status === "running" &&
          "bg-primary/5 border-primary/20 animate-pulse",
        status === "failed" &&
          "bg-sylion-red/5 border-sylion-red/15",
        status === "pending" &&
          "bg-card border-[rgba(148,163,184,0.06)]"
      )}
    >
      <PhaseIcon status={status} />
      <span
        className={cn(
          "text-[10px] font-medium leading-tight",
          status === "completed" && "text-sylion-green",
          status === "running" && "text-primary",
          status === "failed" && "text-sylion-red",
          status === "pending" && "text-muted-foreground"
        )}
      >
        {PHASE_LABELS[phase] ?? phase}
      </span>
      {step && (
        <span className="text-[9px] text-muted-foreground leading-tight text-center max-w-[80px] truncate">
          {step.status}
        </span>
      )}
    </div>
  );
}

/* ============================================================
   Main component
   ============================================================ */

export function PipelineVisualization({
  steps,
  runStatus,
}: PipelineVisualizationProps) {
  return (
    <div className="w-full bg-[#050816] rounded-xl border border-[rgba(148,163,184,0.06)] p-4">
      <div className="flex items-center justify-center gap-0 overflow-x-auto py-2">
        {PHASES.map((phase, idx) => {
          const step = findStepForPhase(steps, phase);
          const status = derivePhaseStatus(step, phase, runStatus);
          const prevStep =
            idx > 0 ? findStepForPhase(steps, PHASES[idx - 1]) : undefined;
          const prevStatus =
            idx > 0
              ? derivePhaseStatus(prevStep, PHASES[idx - 1], runStatus)
              : undefined;
          const connectorCompleted = prevStatus === "completed";

          return (
            <React.Fragment key={phase}>
              {idx > 0 && <Connector completed={connectorCompleted} />}
              <PhaseCard phase={phase} status={status} step={step} />
            </React.Fragment>
          );
        })}
      </div>

      {/* Step detail summary */}
      {steps.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[rgba(148,163,184,0.06)] space-y-1">
          {PHASES.map((phase) => {
            const step = findStepForPhase(steps, phase);
            if (!step) return null;
            return (
              <div
                key={phase}
                className="flex items-center gap-2 px-2 py-1 rounded bg-secondary/5"
              >
                <PhaseIcon status={derivePhaseStatus(step, phase, runStatus)} />
                <span className="text-[10px] font-medium text-primary">
                  {PHASE_LABELS[phase]}
                </span>
                {step.step_type && step.step_type !== phase && (
                  <span className="text-[10px] text-muted-foreground">
                    ({step.step_type})
                  </span>
                )}
                <span className="text-[10px] text-muted-foreground ml-auto">
                  {step.timestamp
                    ? new Date(step.timestamp * 1000).toLocaleTimeString()
                    : step.status}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
