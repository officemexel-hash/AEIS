"use client";

import { useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Inbox, Sparkles } from "lucide-react";
import { useAdvisorFeed } from "@/lib/hooks/advisor";
import { DecisionCardCard } from "@/components/advisor/DecisionCardCard";
import type { AdvisorCardEnvelope } from "@/lib/api/advisor";

interface Props {
  projectId: string;
}

export function ActiveCardsPanel({ projectId }: Props) {
  const { data: cards, source, refresh } = useAdvisorFeed({ project_id: projectId, refreshMs: 8000 });

  const filtered = useMemo<AdvisorCardEnvelope[]>(() => {
    if (!projectId) return cards;
    return cards.filter(
      (envelope) => !envelope.header.project_id || envelope.header.project_id === projectId,
    );
  }, [cards, projectId]);

  return (
    <Card className="bg-card p-4" data-testid="active-cards-panel" data-project-id={projectId}>
      <header className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-sylion-blue" />
          <h3 className="text-sm font-semibold">Aktywne karty live</h3>
          <Badge variant="outline" className="text-[10px]">
            {filtered.length}
          </Badge>
        </div>
        <span
          className={cn(
            "text-[10px] uppercase tracking-wider",
            source === "live" ? "text-sylion-green" : "text-sylion-red",
          )}
        >
          {source === "live" ? "live" : source}
        </span>
      </header>
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
          <Inbox className="h-7 w-7 text-muted-foreground/40" />
          <p className="text-xs text-muted-foreground">Brak aktywnych kart dla tego projektu</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.slice(0, 6).map((envelope) => (
            <DecisionCardCard
              key={envelope.header.card_id}
              envelope={envelope}
              variant="compact"
              showActions
              onActionComplete={() => void refresh()}
              className="border-border/50"
            />
          ))}
          {filtered.length > 6 ? (
            <p className="text-center text-[11px] text-muted-foreground">
              +{filtered.length - 6} więcej
            </p>
          ) : null}
        </div>
      )}
    </Card>
  );
}
