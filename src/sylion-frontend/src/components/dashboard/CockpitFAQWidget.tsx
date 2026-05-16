"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, MessageCircleQuestion } from "lucide-react";
import { cn } from "@/lib/utils";

const FAQ_ENTRIES = [
  {
    id: "faq-stop-prod",
    question: "Dlaczego produkcja została zatrzymana?",
    answer:
      "Karta ma D5, test bezpieczeństwa nie przeszedł, brakuje pełnego podpisu security_sentinel i rollback nie jest kompletny. Wymagany jest fixer flow oraz ponowny przegląd sentinela.",
  },
  {
    id: "faq-add-critic",
    question: "Kiedy dodać model krytyka?",
    answer:
      "Gdy pewność spada poniżej 0.75, modele dają sprzeczne werdykty, decyzja jest D2+ albo projekt wchodzi w produkcję, funding lub bezpieczeństwo.",
  },
  {
    id: "faq-subscription",
    question: "Czy mogę kupić subskrypcję automatycznie?",
    answer:
      "Nie. Doradca może policzyć ROI i przygotować Evidence Pack, ale każdy zakup wymaga Human Gate - nigdy automatycznego zakupu.",
  },
  {
    id: "faq-local-fallback",
    question: "Dlaczego karta użyła lokalnego modelu?",
    answer:
      "Dostawca premium przekroczył limit. Lokalny fallback obniżył poziom pewności - karta pokazuje oznaczenie i rekomenduje dodatkowego weryfikatora.",
  },
];

export function CockpitFAQWidget() {
  const [open, setOpen] = useState<string | null>(null);

  return (
    <section
      className="rounded-2xl border border-white/10 p-5"
      style={{ background: "linear-gradient(180deg,rgba(17,24,39,.92),rgba(10,14,25,.92))" }}
    >
      <div className="mb-4 flex items-center gap-2">
        <MessageCircleQuestion className="h-4 w-4 text-cyan-400" />
        <h3 className="text-base font-bold text-white">Częste pytania</h3>
      </div>

      <div className="space-y-2">
        {FAQ_ENTRIES.map((entry) => (
          <div
            key={entry.id}
            className="overflow-hidden rounded-xl border border-white/8 bg-white/[0.03]"
          >
            <button
              type="button"
              className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
              onClick={() => setOpen(open === entry.id ? null : entry.id)}
            >
              <span className="text-sm font-semibold text-slate-100">{entry.question}</span>
              {open === entry.id ? (
                <ChevronDown className="h-4 w-4 flex-none text-slate-400" />
              ) : (
                <ChevronRight className="h-4 w-4 flex-none text-slate-400" />
              )}
            </button>
            <div
              className={cn(
                "overflow-hidden transition-all",
                open === entry.id ? "max-h-40" : "max-h-0",
              )}
            >
              <p className="px-4 pb-3 text-sm leading-relaxed text-slate-400">{entry.answer}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 text-center">
        <a href="/faq" className="text-[12px] text-[#75a7ff] hover:underline">
          Zobacz wszystkie FAQ →
        </a>
      </div>
    </section>
  );
}
