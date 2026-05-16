"use client";

import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AdvisorCardEnvelope, RiskLevel } from "@/lib/api/advisor";
import { DecisionCardCard } from "@/components/advisor/DecisionCardCard";

const RISK_RANK: Record<RiskLevel, number> = { low: 0, medium: 1, high: 2, critical: 3 };
const D_RANK: Record<string, number> = { D5: 5, D4: 4, D3: 3, D2: 2, D1: 1, D0: 0 };

interface Props {
  cards: AdvisorCardEnvelope[];
  source: "live" | "error" | "loading";
  onActionComplete?: () => void;
}

export function CockpitDecisionSection({ cards, source, onActionComplete }: Props) {
  const sorted = cards
    .slice()
    .sort(
      (a, b) =>
        RISK_RANK[b.header.risk_level] - RISK_RANK[a.header.risk_level] ||
        (D_RANK[b.header.d_level] ?? 0) - (D_RANK[a.header.d_level] ?? 0),
    )
    .slice(0, 3);

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-white">Co wymaga decyzji teraz</h2>
          <p className="mt-0.5 text-[12px] text-slate-400">
            {"Priorytet: D5/D4 -> D3 Human Gates -> koszty -> konfiguracja -> batch low-risk."}
          </p>
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-medium",
            sorted.some((c) => c.header.risk_level === "critical")
              ? "border-[#ff5f7a]/30 bg-[#ff5f7a]/10 text-[#ff5f7a]"
              : "border-[#f6c177]/25 bg-[#f6c177]/10 text-[#f6c177]",
          )}
        >
          <AlertTriangle className="h-3 w-3" />
          {cards.length} kart aktywnych
          {source === "error" ? " · backend offline" : ""}
        </span>
      </div>

      {sorted.length === 0 ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 text-center text-sm text-slate-400">
          Brak aktywnych rekomendacji wymagaj?cych decyzji.
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          {sorted.map((card) => (
            <DecisionCardCard
              key={card.header.card_id}
              envelope={card}
              variant="full"
              onActionComplete={onActionComplete}
            />
          ))}
        </div>
      )}

      {cards.length > 3 ? (
        <div className="mt-3 text-center">
          <Link href="/advisor" className="text-[12px] text-[#75a7ff] hover:underline">
            {`Zobacz wszystkie ${cards.length} kart w feed ->`}
          </Link>
        </div>
      ) : null}
    </section>
  );
}
