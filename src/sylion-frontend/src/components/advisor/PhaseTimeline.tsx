"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Clock, AlertOctagon, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProjectLifecycleState } from "@/lib/api/advisor";

const PHASE_TITLES: Record<string, string> = {
  H01: "Konfiguracja modeli",
  H02: "Providerzy API",
  H03: "Budzet",
  H04: "Intake pomyslu",
  H05: "Model SoT",
  H06: "Formowanie Rady",
  H07: "Polityka autonomii",
  H08: "Szkic SoT",
  H09: "Masterplan",
  H10: "Topologia runtime",
  H11: "Skalowanie VPS",
  H12: "Dobor skilli",
  H13: "Deploy produkcyjny",
  H14: "Testy",
  H15: "Human Gate",
  H16: "Finalna akceptacja",
};

const STATUS_TONE: Record<string, { icon: React.ComponentType<{ className?: string }>; cls: string; label: string }> = {
  approved: { icon: CheckCircle2, cls: "border-sylion-green/40 bg-sylion-green/10 text-sylion-green", label: "zatwierdzone" },
  in_progress: { icon: Loader2, cls: "border-sylion-blue/40 bg-sylion-blue/10 text-sylion-blue", label: "w toku" },
  pending: { icon: Clock, cls: "border-muted-foreground/30 bg-muted/10 text-muted-foreground", label: "oczekuje" },
  blocked: { icon: AlertOctagon, cls: "border-sylion-red/40 bg-sylion-red/10 text-sylion-red", label: "zablokowane" },
};

interface Props {
  lifecycle: ProjectLifecycleState;
  onPhaseClick?: (hookId: string) => void;
  selected?: string;
  className?: string;
}

export function PhaseTimeline({ lifecycle, onPhaseClick, selected, className }: Props) {
  return (
    <div className={cn("grid gap-2 sm:grid-cols-2 md:grid-cols-4", className)}>
      {lifecycle.phases.map((phase, i) => {
        const tone = STATUS_TONE[phase.status] ?? STATUS_TONE.pending;
        const Icon = tone.icon;
        const isSelected = selected === phase.hook_id;
        const cardCount = phase.cards?.length ?? 0;
        return (
          <motion.button
            key={phase.hook_id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.02 }}
            type="button"
            onClick={() => onPhaseClick?.(phase.hook_id)}
            className={cn(
              "flex flex-col items-start gap-1 rounded-md border p-3 text-left transition hover:scale-[1.01]",
              tone.cls,
              isSelected && "ring-2 ring-sylion-blue/60",
            )}
          >
            <div className="flex w-full items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider opacity-70">{phase.hook_id}</span>
              <Icon className={cn("h-3.5 w-3.5", phase.status === "in_progress" && "animate-spin")} />
            </div>
            <span className="text-sm font-medium">{PHASE_TITLES[phase.hook_id] ?? phase.hook_id}</span>
            <div className="mt-auto flex w-full items-center justify-between text-[10px] uppercase tracking-wide opacity-80">
              <span>{tone.label}</span>
              {cardCount > 0 ? <span className="font-mono">{cardCount} {cardCount === 1 ? "karta" : "kart"}</span> : null}
            </div>
          </motion.button>
        );
      })}
    </div>
  );
}
