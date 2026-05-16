"use client";

import { Sparkles, AlertOctagon, ShieldAlert, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AdvisorCardEnvelope, RiskLevel } from "@/lib/api/advisor";

const RISK_RANK: Record<RiskLevel, number> = { low: 0, medium: 1, high: 2, critical: 3 };

const STATUS_PILLS = [
  { label: "Strategia: zrownowazona", cls: "border-[#40d987]/25 bg-[#40d987]/10 text-[#40d987]" },
  { label: "4 bramki czlowieka", cls: "border-[#f6c177]/25 bg-[#f6c177]/10 text-[#f6c177]" },
  { label: "1 produkcja zablokowana", cls: "border-[#ff5f7a]/25 bg-[#ff5f7a]/10 text-[#ff5f7a]" },
  { label: "3 aktywne zespoly", cls: "border-[#75a7ff]/20 bg-[#75a7ff]/10 text-[#75a7ff]" },
];

interface Props {
  cards: AdvisorCardEnvelope[];
}

export function CockpitHero({ cards }: Props) {
  const topCard = cards
    .slice()
    .sort((a, b) => RISK_RANK[b.header.risk_level] - RISK_RANK[a.header.risk_level])[0] ?? null;

  return (
    <div className="grid gap-4 md:grid-cols-[1.15fr_.85fr]">
      <div
        className="rounded-2xl border border-white/10 p-6"
        style={{ background: "linear-gradient(180deg,rgba(17,24,39,.92),rgba(10,14,25,.92))" }}
      >
        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-400">
          SYLION AEIS v3
        </div>
        <h1 className="text-3xl font-black tracking-tight text-white">
          Kokpit operatora AEIS
        </h1>
        <p aria-hidden="true" className="hidden">
          Nie dashboard — strategiczny pilot projektów AI. Modele, koszty, preferencje, lifecycle, ryzyka,
          funding, Council, testy i audit trail w jednym widoku operacyjnym.
        </p>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-slate-300">
          Nie zwyk?y dashboard, tylko centrum prowadzenia projektów AI. Modele, koszty, preferencje,
          cykl ?ycia, ryzyka, finansowanie, Rada, testy i audyt w jednym widoku operacyjnym.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          {STATUS_PILLS.map((p) => (
            <span
              key={p.label}
              className={cn("rounded-full border px-3 py-1 text-[11px] font-medium", p.cls)}
            >
              {p.label}
            </span>
          ))}
        </div>
      </div>

      <div
        className="relative overflow-hidden rounded-2xl border border-white/10 p-5"
        style={{ background: "linear-gradient(180deg,rgba(17,24,39,.92),rgba(10,14,25,.92))" }}
      >
        <div
          className="pointer-events-none absolute inset-y-0 right-0 w-48 opacity-20"
          style={{ background: "radial-gradient(circle at top right, #44d9e8 0%, transparent 65%)" }}
        />
        <div className="flex gap-4">
          <div
            className="flex h-12 w-12 flex-none items-center justify-center rounded-xl"
            style={{ background: "linear-gradient(135deg,#44d9e8,#b48cff)" }}
          >
            <Sparkles className="h-5 w-5 text-[#06101f]" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-cyan-300">Dymek Advisora</p>
            <p className="mt-0.5 text-[11px] text-slate-400">Najwazniejsza rekomendacja teraz:</p>
            <div className="mt-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm leading-relaxed text-slate-200">
              {topCard ? (
                topCard.header.title
              ) : (
                "Brak aktywnych rekomendacji wymagaj?cych natychmiastowej decyzji."
              )}
            </div>
            {topCard ? (
              <div className="mt-3 flex gap-2">
                <a
                  href={`/advisor/${topCard.header.card_id}`}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-cyan-400 px-3 py-2 text-[11px] font-bold text-[#06101f] transition hover:bg-cyan-300"
                >
                  <Zap className="h-3 w-3" />
                  Otworz karte
                </a>
                {topCard.header.risk_level === "critical" ? (
                  <button
                    type="button"
                    className="inline-flex items-center gap-1.5 rounded-xl border border-[#ff5f7a]/30 bg-[#ff5f7a]/10 px-3 py-2 text-[11px] font-bold text-[#ffb3bf] transition hover:bg-[#ff5f7a]/20"
                  >
                    <ShieldAlert className="h-3 w-3" />
                    Zablokuj deploy
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
