"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { RiskBadge, DLevelBadge } from "@/components/advisor";
import type { AdvisorCardEnvelope } from "@/lib/api/advisor";

const AUTO_DISMISS_MS = 5000;

interface Props {
  card: AdvisorCardEnvelope;
  onDismiss: (cardId: string) => void;
}

export function CardToast({ card, onDismiss }: Props) {
  const router = useRouter();
  const [hovered, setHovered] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (hovered) {
      if (timer.current) clearTimeout(timer.current);
      return;
    }
    timer.current = setTimeout(() => onDismiss(card.header.card_id), AUTO_DISMISS_MS);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [hovered, card.header.card_id, onDismiss]);

  const tone =
    card.header.risk_level === "medium"
      ? "border-sylion-amber/40 bg-sylion-amber/5"
      : "border-sylion-blue/30 bg-sylion-blue/5";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 24 }}
      transition={{ duration: 0.2 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      data-testid="advisor-toast"
      data-card-id={card.header.card_id}
      data-risk={card.header.risk_level}
      className={cn(
        "pointer-events-auto w-[340px] max-w-[calc(100vw-2rem)] rounded-lg border bg-background/95 p-3 shadow-lg backdrop-blur",
        tone,
      )}
    >
      <div className="flex items-start gap-2">
        <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sylion-blue" />
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-1.5">
            <RiskBadge level={card.header.risk_level} />
            <DLevelBadge level={card.header.d_level} />
            <span className="text-[10px] text-muted-foreground">{card.header.project_domain}</span>
          </div>
          <p className="line-clamp-2 text-xs font-medium leading-snug">{card.header.title}</p>
          <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{card.header.rationale}</p>
          <div className="mt-2 flex items-center justify-between gap-2">
            <Button
              variant="link"
              size="xs"
              onClick={() => {
                router.push(`/advisor/${encodeURIComponent(card.header.card_id)}`);
                onDismiss(card.header.card_id);
              }}
              data-testid="advisor-toast-open"
              className="px-0 text-[11px]"
            >
              Open card
            </Button>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => onDismiss(card.header.card_id)}
              aria-label="Dismiss"
              data-testid="advisor-toast-dismiss"
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
