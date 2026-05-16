"use client";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn, fmtDateTime } from "@/lib/utils";
import { DecisionCardCard } from "@/components/advisor/DecisionCardCard";
import type { ProjectLifecyclePhase } from "@/lib/api/advisor";
import { Activity, FileText, Hash } from "lucide-react";

const PHASE_TITLES: Record<string, string> = {
  H01: "Konfiguracja modeli",
  H02: "Providerzy API",
  H03: "Konfiguracja budżetu",
  H04: "Intake pomyslu",
  H05: "Model Source of Truth",
  H06: "Formowanie Rady",
  H07: "Polityka autonomii",
  H08: "Szkic Source of Truth",
  H09: "Masterplan",
  H10: "Topologia runtime",
  H11: "Skalowanie VPS",
  H12: "Dobor skilli",
  H13: "Deploy produkcyjny",
  H14: "Testy",
  H15: "Human Gate",
  H16: "Finalna akceptacja",
};

const STATUS_BADGE: Record<string, string> = {
  approved: "border-sylion-green/30 text-sylion-green",
  in_progress: "border-sylion-blue/30 text-sylion-blue",
  pending: "border-muted-foreground/30 text-muted-foreground",
  blocked: "border-sylion-red/30 text-sylion-red",
};

interface Props {
  phase: ProjectLifecyclePhase | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onActionComplete?: () => void;
}

export function PhaseDetailModal({ phase, open, onOpenChange, onActionComplete }: Props) {
  const title = phase ? PHASE_TITLES[phase.hook_id] ?? phase.hook_id : "";
  const status = phase?.status ?? "pending";
  const cards = phase?.cards ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl" data-testid="phase-detail-modal">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-[10px]">
              {phase?.hook_id ?? "—"}
            </Badge>
            <DialogTitle>{title}</DialogTitle>
            <Badge variant="outline" className={cn("text-[10px] capitalize", STATUS_BADGE[status])}>
              {statusLabel(status)}
            </Badge>
          </div>
          <DialogDescription>
            <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Hash className="h-3 w-3" />
              <span className="font-mono">{phase?.hook_event_type ?? "—"}</span>
            </span>
          </DialogDescription>
        </DialogHeader>

        <div className="mt-2 grid grid-cols-2 gap-2 rounded-md border border-border/40 bg-muted/10 p-3 text-xs">
          <div className="flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-muted-foreground">Ostatnie zdarze?ie</span>
            <span className="ml-auto font-mono">
              {phase?.last_event_at
                ? fmtDateTime(new Date(phase.last_event_at * 1000).toISOString())
                : "—"}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-muted-foreground">Wyemitowane karty</span>
            <span className="ml-auto font-mono">{cards.length}</span>
          </div>
        </div>

        <ScrollArea className="mt-3 max-h-[55vh] pr-3">
          {cards.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted-foreground" data-testid="phase-modal-empty">
              W tej fazie nie wyemitowano jeszcze kart doradcy.
            </p>
          ) : (
            <div className="space-y-2">
              {cards.map((card) => (
                <DecisionCardCard
                  key={card.header.card_id}
                  envelope={card}
                  variant="compact"
                  showActions={phase?.status === "in_progress"}
                  onActionComplete={onActionComplete}
                />
              ))}
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

function statusLabel(status: string): string {
  if (status === "approved") return "zatwierdzone";
  if (status === "in_progress") return "w toku";
  if (status === "blocked") return "zablokowane";
  return "oczekuje";
}
