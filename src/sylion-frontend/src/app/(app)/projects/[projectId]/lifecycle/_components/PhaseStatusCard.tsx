"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, fmtDateTime } from "@/lib/utils";
import { CheckCircle2, Clock, AlertOctagon, Loader2 } from "lucide-react";
import type { ProjectLifecyclePhase } from "@/lib/api/advisor";

const PHASE_TITLES: Record<string, string> = {
  H01: "Model setup",
  H02: "API providers",
  H03: "Budget",
  H04: "Idea intake",
  H05: "SoT model",
  H06: "Council formation",
  H07: "Autonomy policy",
  H08: "SoT drafting",
  H09: "Masterplan",
  H10: "Runtime topology",
  H11: "VPS scaling",
  H12: "Skill selection",
  H13: "Production deploy",
  H14: "Testing",
  H15: "Human Gate",
  H16: "Final approval",
};

const STATUS_TONE: Record<
  string,
  { icon: React.ComponentType<{ className?: string }>; cls: string; dot: string; label: string }
> = {
  approved: {
    icon: CheckCircle2,
    cls: "border-sylion-green/40 bg-sylion-green/5",
    dot: "bg-sylion-green",
    label: "approved",
  },
  in_progress: {
    icon: Loader2,
    cls: "border-sylion-blue/40 bg-sylion-blue/5",
    dot: "bg-sylion-blue",
    label: "in progress",
  },
  pending: {
    icon: Clock,
    cls: "border-muted-foreground/30 bg-muted/10",
    dot: "bg-muted-foreground",
    label: "pending",
  },
  blocked: {
    icon: AlertOctagon,
    cls: "border-sylion-red/40 bg-sylion-red/5",
    dot: "bg-sylion-red",
    label: "blocked",
  },
};

interface Props {
  phase: ProjectLifecyclePhase;
  selected?: boolean;
  onClick?: () => void;
}

export function PhaseStatusCard({ phase, selected, onClick }: Props) {
  const tone = STATUS_TONE[phase.status] ?? STATUS_TONE.pending;
  const Icon = tone.icon;
  const cardCount = phase.cards?.length ?? 0;
  const title = PHASE_TITLES[phase.hook_id] ?? phase.hook_id;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group flex w-full flex-col gap-2 rounded-md border p-3 text-left transition hover:translate-y-[-1px]",
        tone.cls,
        selected && "ring-2 ring-sylion-blue/60",
      )}
    >
      <div className="flex w-full items-center justify-between text-[10px] font-mono uppercase tracking-wider opacity-75">
        <span>{phase.hook_id}</span>
        <Icon className={cn("h-3.5 w-3.5", phase.status === "in_progress" && "animate-spin")} />
      </div>
      <div className="text-sm font-medium">{title}</div>
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wide opacity-80">
        <span className="flex items-center gap-1.5">
          <span className={cn("h-1.5 w-1.5 rounded-full", tone.dot)} />
          {tone.label}
        </span>
        {cardCount > 0 ? (
          <Badge variant="outline" className="h-4 gap-1 text-[9px]">
            {cardCount} card{cardCount === 1 ? "" : "s"}
          </Badge>
        ) : null}
      </div>
      {phase.last_event_at ? (
        <p className="text-[10px] text-muted-foreground">
          last event {fmtDateTime(new Date(phase.last_event_at * 1000).toISOString())}
        </p>
      ) : null}
    </button>
  );
}
