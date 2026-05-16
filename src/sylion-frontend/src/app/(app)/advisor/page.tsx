"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useAdvisorFeed, useEvidencePack } from "@/lib/hooks/advisor";
import { BackendErrorBanner, EvidencePackViewer } from "@/components/advisor";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import type { AdvisorCardEnvelope, RiskLevel } from "@/lib/api/advisor";
import { FeedHeader } from "./_components/FeedHeader";
import { FeedList } from "./_components/FeedList";
import { FilterBar } from "./_components/FilterBar";
import { CardModal } from "./_components/CardModal";
import { ToastQueue } from "./_components/ToastQueue";
import { HelpTip } from "@/components/common/HelpTip";

const RISK_RANK: Record<RiskLevel, number> = { low: 0, medium: 1, high: 2, critical: 3 };

export default function AdvisorFeedPage() {
  const { data: cards, source, refresh } = useAdvisorFeed({ refreshMs: 6000 });

  const [filterRisk, setFilterRisk] = useState<RiskLevel | "all">("all");
  const [filterDomain, setFilterDomain] = useState<string>("all");
  const [historyOnly, setHistoryOnly] = useState<boolean>(false);

  const [modalCard, setModalCard] = useState<AdvisorCardEnvelope | null>(null);
  const dismissedRef = useRef<Set<string>>(new Set());
  const [evidencePackId, setEvidencePackId] = useState<string | null>(null);
  const { pack: evidencePack } = useEvidencePack(evidencePackId);

  const domains = useMemo(() => {
    const set = new Set<string>();
    for (const c of cards) if (c.header.project_domain) set.add(c.header.project_domain);
    return Array.from(set).sort();
  }, [cards]);

  const sorted = useMemo(() => {
    return cards.slice().sort((a, b) => {
      const r = RISK_RANK[b.header.risk_level] - RISK_RANK[a.header.risk_level];
      if (r !== 0) return r;
      return b.header.created_at - a.header.created_at;
    });
  }, [cards]);

  const filtered = useMemo(() => {
    return sorted.filter((c) => {
      if (filterRisk !== "all" && c.header.risk_level !== filterRisk) return false;
      if (filterDomain !== "all" && c.header.project_domain !== filterDomain) return false;
      if (historyOnly && !c.header.history_based) return false;
      return true;
    });
  }, [sorted, filterRisk, filterDomain, historyOnly]);

  const criticalCount = useMemo(
    () => cards.filter((c) => c.header.risk_level === "critical").length,
    [cards],
  );

  useEffect(() => {
    queueMicrotask(() => {
      if (modalCard) {
        const stillPresent = cards.find((c) => c.header.card_id === modalCard.header.card_id);
        if (!stillPresent) {
          setModalCard(null);
          return;
        }
        return;
      }
      const next = sorted.find(
        (c) =>
          (c.header.risk_level === "high" || c.header.risk_level === "critical") &&
          !dismissedRef.current.has(c.header.card_id),
      );
      if (next) setModalCard(next);
    });
  }, [cards, sorted, modalCard]);

  function closeModal() {
    if (modalCard) dismissedRef.current.add(modalCard.header.card_id);
    setModalCard(null);
  }

  const filtersActive = filterRisk !== "all" || filterDomain !== "all" || historyOnly;

  return (
    <div className="space-y-5" data-testid="advisor-feed-page">
      <div className="flex items-center justify-end">
        <HelpTip
          text="Strumie? na żywo Doradcy: karty rekomendacji ze wszystkich aktywnych projektów, sortowane po ryzyku (critical → low). Auto-modal dla kart high/critical. Karty z evidence pack można podpisać inline."
          side="left"
        />
      </div>
      <FeedHeader
        totalCards={cards.length}
        filteredCount={filtered.length}
        source={source}
        criticalCount={criticalCount}
        onRefresh={refresh}
      />

      <BackendErrorBanner source={source} />

      <FilterBar
        risk={filterRisk}
        onRiskChange={setFilterRisk}
        domain={filterDomain}
        onDomainChange={setFilterDomain}
        domains={domains}
        historyOnly={historyOnly}
        onHistoryOnlyChange={setHistoryOnly}
      />

      <FeedList
        cards={filtered}
        filtered={filtersActive}
        onOpenEvidence={(packId) => setEvidencePackId(packId)}
      />

      <ToastQueue cards={cards} />

      <CardModal
        card={modalCard}
        onClose={closeModal}
        onOpenEvidence={(packId) => setEvidencePackId(packId)}
      />

      <Dialog
        open={evidencePackId !== null}
        onOpenChange={(value) => {
          if (!value) setEvidencePackId(null);
        }}
      >
        <DialogContent
          showCloseButton
          className="max-h-[90vh] overflow-y-auto sm:max-w-3xl"
          data-testid="advisor-evidence-modal"
        >
          <DialogTitle className="sr-only">Evidence Pack</DialogTitle>
          {evidencePack ? (
            <EvidencePackViewer pack={evidencePack} onSigned={() => setEvidencePackId(null)} />
          ) : (
            <p className="p-6 text-center text-sm text-muted-foreground">Ładowanie evidence pack...</p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
