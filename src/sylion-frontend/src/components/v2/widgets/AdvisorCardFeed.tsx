"use client";

/**
 * SYLION AEIS v2 — W16 G1 widget: AdvisorCardFeed.
 *
 * Lista AdvisorCards z W13 advisor — operator widzi sugestie w prawej kolumnie
 * aplikacji. Polling co `pollInterval` ms (0 = wyłącz). Akcje POST-owane do
 * `/api/v1/advisor/cards/{card_id}/actions`.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Sparkles, Loader2, AlertTriangle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { request } from "@/lib/api/client";

const DEFAULT_OPERATOR_ID = "00000000-0000-0000-0000-000000000001";

interface AdvisorCardEnvelope {
  header: {
    card_id: string;
    title: string;
    rationale: string;
    risk_level: "low" | "medium" | "high" | "critical";
    d_level: string;
    priority: string;
  };
  body?: Record<string, unknown> | null;
}

interface AdvisorCardsResponse {
  cards: AdvisorCardEnvelope[];
}

type AdvisorAction = "accept" | "reject" | "modify";

export interface AdvisorCardFeedProps {
  operatorId?: string;
  limit?: number;
  pollInterval?: number;
}

const RISK_VARIANT: Record<
  AdvisorCardEnvelope["header"]["risk_level"],
  "secondary" | "destructive" | "default" | "outline"
> = {
  low: "secondary",
  medium: "outline",
  high: "destructive",
  critical: "destructive",
};

export function AdvisorCardFeed({
  operatorId = DEFAULT_OPERATOR_ID,
  limit = 10,
  pollInterval = 30000,
}: AdvisorCardFeedProps) {
  const [cards, setCards] = useState<AdvisorCardEnvelope[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);
  const mounted = useRef<boolean>(true);

  const load = useCallback(async () => {
    if (!mounted.current) return;
    try {
      const qs = new URLSearchParams({ operator_id: operatorId, limit: String(limit) });
      const res = await request<AdvisorCardsResponse>(`/api/v1/advisor/cards?${qs.toString()}`);
      if (!mounted.current) return;
      setCards(res.cards ?? []);
      setError(null);
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [operatorId, limit]);

  useEffect(() => {
    mounted.current = true;
    load();
    if (pollInterval > 0) {
      const t = setInterval(() => {
        if (mounted.current) load();
      }, pollInterval);
      return () => {
        mounted.current = false;
        clearInterval(t);
      };
    }
    return () => {
      mounted.current = false;
    };
  }, [load, pollInterval]);

  async function handleAction(cardId: string, action: AdvisorAction): Promise<void> {
    setActingId(cardId);
    try {
      await request<{ action_event_id: string }>(
        `/api/v1/advisor/cards/${encodeURIComponent(cardId)}/actions`,
        { method: "POST", body: JSON.stringify({ action }) },
      );
      if (action === "accept" || action === "reject") {
        setCards((prev) => prev.filter((c) => c.header.card_id !== cardId));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setActingId(null);
    }
  }

  return (
    <Card className="overflow-hidden">
      <header className="flex items-center justify-between border-b border-foreground/10 px-4 py-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold">
          <Sparkles className="h-3.5 w-3.5 text-sylion-blue" />
          Sugestie doradcy
        </h3>
        <Badge variant="outline" className="text-[10px]">
          {cards.length}
        </Badge>
      </header>

      {loading && cards.length === 0 && (
        <div className="flex items-center justify-center gap-2 px-4 py-6 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Wczytywanie sugestii…
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 px-4 py-2 text-[11px] text-destructive">
          <AlertTriangle className="h-3.5 w-3.5" />
          {error}
        </div>
      )}

      {!loading && cards.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center gap-2 px-4 py-8 text-xs text-muted-foreground">
          <Sparkles className="h-5 w-5 opacity-40" />
          Brak sugestii doradcy
        </div>
      )}

      <ul className="flex flex-col gap-2 px-3 py-2">
        {cards.map((card) => (
          <li
            key={card.header.card_id}
            className="rounded-lg border border-foreground/10 bg-background/40 px-3 py-2"
          >
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="truncate text-sm font-medium">{card.header.title}</span>
              <div className="flex shrink-0 items-center gap-1">
                <Badge variant="outline" className="text-[10px]">
                  {card.header.d_level}
                </Badge>
                <Badge
                  variant={RISK_VARIANT[card.header.risk_level]}
                  className="text-[10px]"
                >
                  {card.header.risk_level}
                </Badge>
              </div>
            </div>
            <p className="mb-2 line-clamp-3 text-[11px] text-muted-foreground">
              {card.header.rationale}
            </p>
            <div className="flex items-center justify-end gap-1">
              <Button
                size="xs"
                variant="ghost"
                onClick={() => handleAction(card.header.card_id, "modify")}
                disabled={actingId === card.header.card_id}
              >
                Modyfikuj
              </Button>
              <Button
                size="xs"
                variant="outline"
                onClick={() => handleAction(card.header.card_id, "reject")}
                disabled={actingId === card.header.card_id}
              >
                Odrzuć
              </Button>
              <Button
                size="xs"
                onClick={() => handleAction(card.header.card_id, "accept")}
                disabled={actingId === card.header.card_id}
              >
                Akceptuj
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
