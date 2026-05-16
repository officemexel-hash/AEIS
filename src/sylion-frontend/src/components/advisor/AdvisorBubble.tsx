"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { AdvisorCardEnvelope, RiskLevel } from "@/lib/api/advisor";
import { useAdvisorFeed } from "@/lib/hooks/advisor";
import { RiskBadge } from "./RiskBadge";

const RISK_RANK: Record<RiskLevel, number> = { low: 0, medium: 1, high: 2, critical: 3 };

export function AdvisorBubble() {
  const pathname = usePathname();
  const { data: cards, source } = useAdvisorFeed({ refreshMs: 6000 });
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState<Set<string>>(new Set());

  const toggleOpen = () => {
    const nextOpen = !open;
    if (nextOpen) {
      setSeen(new Set(cards.map((c) => c.header.card_id)));
    }
    setOpen(nextOpen);
  };

  if (pathname?.startsWith("/onboarding")) {
    return null;
  }

  const unseen = cards.filter((c) => !seen.has(c.header.card_id));
  const headlines = cards
    .slice()
    .sort((a, b) => RISK_RANK[b.header.risk_level] - RISK_RANK[a.header.risk_level])
    .slice(0, 3);
  const queueCount = Math.max(0, cards.length - headlines.length);
  const hasCritical = cards.some((c) => c.header.risk_level === "critical");

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex flex-col items-end gap-2">
      <AnimatePresence>
        {open ? (
          <motion.div
            key="panel"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            transition={{ duration: 0.2 }}
            className="pointer-events-auto w-[360px] max-w-[calc(100vw-2.5rem)] rounded-lg border border-border bg-background/95 p-3 shadow-lg backdrop-blur"
          >
            <div className="mb-2 flex items-center justify-between">
              <h3 className="flex items-center gap-1.5 text-sm font-semibold">
                <Sparkles className="h-4 w-4 text-sylion-blue" />
                Doradca — live feed
                {source === "error" ? (
                  <span className="rounded bg-sylion-red/20 px-1 py-0.5 text-[9px] font-medium uppercase tracking-wide text-sylion-red">
                    offline
                  </span>
                ) : null}
              </h3>
              <Link
                href="/advisor"
                className="text-[11px] text-sylion-blue hover:underline"
                onClick={() => setOpen(false)}
              >
                otwórz feed →
              </Link>
            </div>
            {headlines.length === 0 ? (
              <p className="px-2 py-4 text-center text-xs text-muted-foreground">Brak aktywnych rekomendacji</p>
            ) : (
              <ul className="space-y-2">
                {headlines.map((c) => (
                  <BubbleItem key={c.header.card_id} card={c} />
                ))}
              </ul>
            )}
            {queueCount > 0 ? (
              <p className="mt-2 text-center text-[11px] text-muted-foreground">+{queueCount} więcej w kolejce</p>
            ) : null}
          </motion.div>
        ) : null}
      </AnimatePresence>

      <button
        type="button"
        className={cn(
          "pointer-events-auto inline-flex items-center gap-2 rounded-full border border-border bg-background/95 px-4 py-2 text-sm font-medium shadow-md backdrop-blur transition-all hover:scale-[1.02]",
          hasCritical && "border-sylion-red/40 bg-sylion-red/5 text-sylion-red",
        )}
        onClick={toggleOpen}
        aria-label="Advisor feed"
      >
        <Bell className={cn("h-4 w-4", hasCritical && "animate-pulse")} />
        <span className="tabular-nums">{cards.length}</span>
        {unseen.length > 0 ? (
          <span className="rounded-full bg-sylion-blue px-2 py-0.5 text-[10px] font-bold text-white">{unseen.length}</span>
        ) : null}
      </button>
    </div>
  );
}

function BubbleItem({ card }: { card: AdvisorCardEnvelope }) {
  return (
    <li className="rounded-md border border-border/50 bg-muted/10 p-2">
      <div className="mb-1 flex items-center gap-1.5">
        <RiskBadge level={card.header.risk_level} />
        <span className="text-[10px] font-mono text-muted-foreground">{card.header.d_level}</span>
      </div>
      <p className="line-clamp-2 text-xs font-medium">{card.header.title}</p>
    </li>
  );
}
