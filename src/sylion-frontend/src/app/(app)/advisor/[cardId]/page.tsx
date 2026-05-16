"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAdvisorCard, useEvidencePack } from "@/lib/hooks/advisor";
import { BackendErrorBanner, DecisionCardCard, EvidencePackViewer } from "@/components/advisor";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, BookOpen } from "lucide-react";

export default function AdvisorCardDetailPage() {
  const params = useParams<{ cardId: string }>();
  const decoded = decodeURIComponent(String(params.cardId || ""));
  const { card, source, loading, refresh } = useAdvisorCard(decoded);

  const cardPackId = card?.header.evidence_pack_id ?? null;
  const [activePackId, setActivePackId] = useState<string | null>(null);
  const { pack: evidencePack } = useEvidencePack(activePackId);

  if (loading && !card) {
    return (
      <div className="space-y-5">
        <PageHeader />
        <Card className="p-8 text-center text-sm text-muted-foreground">Loading card...</Card>
      </div>
    );
  }

  if (!card) {
    return (
      <div className="space-y-5" data-testid="advisor-detail-missing">
        <PageHeader />
        <Card className="flex flex-col items-center gap-2 p-10 text-center">
          <h2 className="text-base font-semibold">Card not found</h2>
          <p className="text-xs text-muted-foreground">
            No card with id <span className="font-mono text-foreground/80">{decoded}</span> exists in the current feed.
          </p>
          <Link href="/advisor" className="mt-3">
            <Button variant="outline" size="sm">Back to feed</Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="advisor-detail-page" data-card-id={card.header.card_id}>
      <PageHeader
        title={card.header.title}
        onRefresh={refresh}
        evidencePackId={cardPackId}
        onOpenEvidence={() => setActivePackId(cardPackId)}
      />

      <BackendErrorBanner source={source} />

      <DecisionCardCard
        envelope={card}
        variant="full"
        onOpenEvidence={(packId) => setActivePackId(packId)}
      />

      {activePackId ? (
        <div data-testid="advisor-detail-evidence">
          {evidencePack ? (
            <EvidencePackViewer pack={evidencePack} onSigned={() => setActivePackId(null)} />
          ) : (
            <Card className="p-6 text-center text-xs text-muted-foreground">Loading evidence pack...</Card>
          )}
        </div>
      ) : null}
    </div>
  );
}

function PageHeader({
  title,
  onRefresh,
  evidencePackId,
  onOpenEvidence,
}: {
  title?: string;
  onRefresh?: () => void;
  evidencePackId?: string | null;
  onOpenEvidence?: () => void;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-center gap-3">
        <Link href="/advisor" data-testid="advisor-detail-back">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-3.5 w-3.5" />
            Feed
          </Button>
        </Link>
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Advisor card</p>
          <h1 className="truncate text-base font-semibold tracking-tight">{title ?? "Card detail"}</h1>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {evidencePackId ? (
          <Button variant="outline" size="sm" onClick={onOpenEvidence} data-testid="advisor-detail-evidence-toggle">
            <BookOpen className="h-3.5 w-3.5" />
            Evidence pack
          </Button>
        ) : null}
        {onRefresh ? (
          <Button variant="outline" size="sm" onClick={onRefresh}>
            Refresh
          </Button>
        ) : null}
      </div>
    </div>
  );
}
