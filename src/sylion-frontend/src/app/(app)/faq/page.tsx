"use client";

import { useMemo, useState, useEffect } from "react";
import { BookOpen } from "lucide-react";
import { FAQ_ENTRIES, FAQ_CATEGORY_LABELS, type FaqCategory } from "@/data/faq-entries";
import { FaqSearch } from "@/components/faq/FaqSearch";
import { FaqEntryCard } from "@/components/faq/FaqEntry";
import { HelpTip } from "@/components/common/HelpTip";

const ALL_CATEGORIES = Object.keys(FAQ_CATEGORY_LABELS) as FaqCategory[];

function matchesQuery(entry: (typeof FAQ_ENTRIES)[number], q: string): boolean {
  if (!q) return true;
  const needle = q.toLowerCase();
  return (
    entry.question.toLowerCase().includes(needle) ||
    entry.shortAnswer.toLowerCase().includes(needle) ||
    entry.fullAnswer.toLowerCase().includes(needle) ||
    entry.tags.some((t) => t.toLowerCase().includes(needle))
  );
}

export default function FaqPage() {
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<FaqCategory | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash) {
      setOpenId(hash);
      setTimeout(() => {
        document.getElementById(hash)?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  }, []);

  const filtered = useMemo(() => {
    return FAQ_ENTRIES.filter((e) => {
      if (activeCategory && e.category !== activeCategory) return false;
      return matchesQuery(e, query);
    });
  }, [query, activeCategory]);

  const categoryCounts = useMemo(() => {
    const counts: Partial<Record<FaqCategory, number>> = {};
    for (const entry of FAQ_ENTRIES) {
      if (!matchesQuery(entry, query)) continue;
      counts[entry.category] = (counts[entry.category] ?? 0) + 1;
    }
    return counts;
  }, [query]);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: "linear-gradient(135deg, oklch(0.55 0.2 260), oklch(0.45 0.25 240))" }}
        >
          <BookOpen className="w-5 h-5" style={{ color: "oklch(0.98 0 0)" }} />
        </div>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "oklch(0.93 0.01 260)" }}>
            Pomoc i FAQ
            <HelpTip text="Praktyczny przewodnik po SYLION AEIS - wyszukiwarka po pytaniach, krótkich odpowiedziach i tagach. Filtry kategorii zawężają zakres; deep link przez #anchor otwiera konkretne pytanie." />
          </h1>
          <p className="text-sm" style={{ color: "oklch(0.52 0.01 260)" }}>
            Praktyczny przewodnik po systemie SYLION AEIS — {FAQ_ENTRIES.length} pytan i odpowiedzi
          </p>
        </div>
      </div>

      {/* Search */}
      <FaqSearch value={query} onChange={setQuery} resultCount={filtered.length} />

      {/* Category chips */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActiveCategory(null)}
          className="text-xs px-3 py-1.5 rounded-full border transition-colors duration-150"
          style={{
            backgroundColor: activeCategory === null ? "oklch(0.55 0.2 260 / 15%)" : "transparent",
            borderColor: activeCategory === null ? "oklch(0.55 0.2 260 / 40%)" : "rgba(148,163,184,0.12)",
            color: activeCategory === null ? "oklch(0.7 0.15 260)" : "oklch(0.52 0.01 260)",
          }}
        >
          Wszystkie ({FAQ_ENTRIES.filter((e) => matchesQuery(e, query)).length})
        </button>
        {ALL_CATEGORIES.filter((c) => (categoryCounts[c] ?? 0) > 0).map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
            className="text-xs px-3 py-1.5 rounded-full border transition-colors duration-150"
            style={{
              backgroundColor: activeCategory === cat ? "oklch(0.55 0.2 260 / 15%)" : "transparent",
              borderColor:
                activeCategory === cat ? "oklch(0.55 0.2 260 / 40%)" : "rgba(148,163,184,0.12)",
              color: activeCategory === cat ? "oklch(0.7 0.15 260)" : "oklch(0.52 0.01 260)",
            }}
          >
            {FAQ_CATEGORY_LABELS[cat]} ({categoryCounts[cat] ?? 0})
          </button>
        ))}
      </div>

      {/* Entries */}
      {filtered.length === 0 ? (
        <div
          className="rounded-lg border px-6 py-10 text-center"
          style={{ borderColor: "rgba(148,163,184,0.1)", backgroundColor: "oklch(0.13 0.005 280)" }}
        >
          <p className="text-sm" style={{ color: "oklch(0.52 0.01 260)" }}>
            Brak wyników dla &quot;{query}&quot;
            {activeCategory && ` w kategorii ${FAQ_CATEGORY_LABELS[activeCategory]}`}
          </p>
          <button
            onClick={() => { setQuery(""); setActiveCategory(null); }}
            className="mt-3 text-xs"
            style={{ color: "oklch(0.6 0.15 260)" }}
          >
            Wyczysc filtry
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((entry) => (
            <FaqEntryCard
              key={entry.id}
              entry={entry}
              defaultOpen={openId === entry.id}
            />
          ))}
        </div>
      )}

      {/* Footer note */}
      <p className="text-xs text-center pb-6" style={{ color: "oklch(0.4 0.01 260)" }}>
        Zrodlo: SYLION AEIS FAQ/Runbook v3 — 2026-04-26
      </p>
    </div>
  );
}
