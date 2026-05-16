"use client";

import { useRouter } from "next/navigation";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { DecisionCardCard, RiskBadge, DLevelBadge } from "@/components/advisor";
import type { AdvisorCardEnvelope } from "@/lib/api/advisor";
import { ExternalLink } from "lucide-react";

interface Props {
  card: AdvisorCardEnvelope | null;
  onClose: () => void;
  onOpenEvidence: (packId: string, cardId: string) => void;
}

export function CardModal({ card, onClose, onOpenEvidence }: Props) {
  const router = useRouter();
  const open = card !== null;

  return (
    <Dialog
      open={open}
      disablePointerDismissal
      onOpenChange={(value, details) => {
        if (value) return;
        const reason = details?.reason;
        if (reason === "outside-press" || reason === "escape-key" || reason === "focus-out") return;
        onClose();
      }}
    >
      <DialogContent
        showCloseButton={false}
        data-testid="advisor-modal"
        data-card-id={card?.header.card_id ?? ""}
        className="max-h-[90vh] overflow-y-auto sm:max-w-2xl"
      >
        {card ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <RiskBadge level={card.header.risk_level} />
                <DLevelBadge level={card.header.d_level} withLabel />
                <DialogTitle className="text-sm">Wymagana akcja</DialogTitle>
              </div>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => {
                  router.push(`/advisor/${encodeURIComponent(card.header.card_id)}`);
                  onClose();
                }}
                data-testid="advisor-modal-open-detail"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Otwórz szczegóły
              </Button>
            </div>
            <Separator />
            <DecisionCardCard
              envelope={card}
              variant="full"
              onOpenEvidence={(packId) => onOpenEvidence(packId, card.header.card_id)}
              onActionComplete={onClose}
            />
            <p className="text-[11px] text-muted-foreground">
              Ta karta wymaga jawnej decyzji, bo została sklasyfikowana jako ryzyko{" "}
              <span className="font-medium text-foreground">{card.header.risk_level}</span>. Wybierz akcję powyżej,
              aby zamknąć modal.
            </p>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
