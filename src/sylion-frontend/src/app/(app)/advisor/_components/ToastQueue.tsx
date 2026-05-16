"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import type { AdvisorCardEnvelope } from "@/lib/api/advisor";
import { CardToast } from "./CardToast";

const MAX_VISIBLE = 3;

interface Props {
  cards: AdvisorCardEnvelope[];
}

export function ToastQueue({ cards }: Props) {
  const eligible = cards.filter(
    (c) => c.header.risk_level === "low" || c.header.risk_level === "medium",
  );

  const dismissedRef = useRef<Set<string>>(new Set());
  const [, setTick] = useState(0);

  useEffect(() => {
    const known = new Set(eligible.map((c) => c.header.card_id));
    let changed = false;
    for (const id of Array.from(dismissedRef.current)) {
      if (!known.has(id)) {
        dismissedRef.current.delete(id);
        changed = true;
      }
    }
    if (changed) setTick((v) => v + 1);
  }, [eligible]);

  const dismiss = useCallback((cardId: string) => {
    dismissedRef.current.add(cardId);
    setTick((v) => v + 1);
  }, []);

  const visible = eligible.filter((c) => !dismissedRef.current.has(c.header.card_id));
  const shown = visible.slice(0, MAX_VISIBLE);
  const queueCount = Math.max(0, visible.length - shown.length);

  if (shown.length === 0 && queueCount === 0) return null;

  return (
    <div
      className="pointer-events-none fixed bottom-20 right-5 z-40 flex flex-col items-end gap-2"
      data-testid="advisor-toast-queue"
    >
      <AnimatePresence>
        {shown.map((card) => (
          <CardToast key={card.header.card_id} card={card} onDismiss={dismiss} />
        ))}
      </AnimatePresence>
      {queueCount > 0 ? (
        <div
          className="pointer-events-auto rounded-full border border-border bg-background/95 px-3 py-1 text-[11px] font-medium text-muted-foreground shadow-md backdrop-blur"
          data-testid="advisor-toast-queue-counter"
        >
          +{queueCount} more
        </div>
      ) : null}
    </div>
  );
}
