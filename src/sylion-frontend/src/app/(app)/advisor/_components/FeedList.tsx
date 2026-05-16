"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { DecisionCardCard } from "@/components/advisor";
import type { AdvisorCardEnvelope } from "@/lib/api/advisor";
import { EmptyState } from "./EmptyState";

interface Props {
  cards: AdvisorCardEnvelope[];
  filtered: boolean;
  onOpenEvidence: (packId: string, cardId: string) => void;
}

export function FeedList({ cards, filtered, onOpenEvidence }: Props) {
  const router = useRouter();

  if (cards.length === 0) {
    return <EmptyState filtered={filtered} />;
  }

  return (
    <div className="space-y-3" data-testid="feed-list">
      <AnimatePresence mode="popLayout">
        {cards.map((envelope, index) => (
          <motion.div
            key={envelope.header.card_id}
            layout
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ delay: Math.min(index * 0.03, 0.2), duration: 0.22 }}
            data-testid="feed-card"
            data-card-id={envelope.header.card_id}
            data-risk={envelope.header.risk_level}
            onClick={() => router.push(`/advisor/${encodeURIComponent(envelope.header.card_id)}`)}
            className="cursor-pointer"
          >
            <DecisionCardCard
              envelope={envelope}
              variant="full"
              onOpenEvidence={(packId) => onOpenEvidence(packId, envelope.header.card_id)}
            />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
