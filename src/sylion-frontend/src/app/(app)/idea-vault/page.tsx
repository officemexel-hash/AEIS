"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Plus, RefreshCw, Search, Loader2, Archive, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HelpTip } from "@/components/common/HelpTip";
import { cn } from "@/lib/utils";
import {
  listIdeas,
  setIdeaStatus,
  isStaleIdea,
  getDomain,
  IDEA_STATUSES,
  STATUS_LABELS,
  DOMAINS,
  DOMAIN_LABELS,
} from "@/lib/api/ideas";
import type { Idea, IdeaStatus } from "@/lib/api/ideas";
import { IdeaCard } from "@/components/idea-vault/idea-card";
import { CreateIdeaModal } from "@/components/idea-vault/create-idea-modal";
import { StatusTransitionModal } from "@/components/idea-vault/status-transition-modal";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SortMode = "newest" | "oldest" | "stale_first";
type StatusFilter = "all" | IdeaStatus | "stale";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function applyFilter(
  ideas: Idea[],
  statusFilter: StatusFilter,
  domainFilter: string,
  search: string
): Idea[] {
  return ideas.filter((idea) => {
    if (statusFilter === "stale") {
      if (!isStaleIdea(idea)) return false;
    } else if (statusFilter !== "all") {
      if (idea.status !== statusFilter) return false;
    }
    if (domainFilter && getDomain(idea) !== domainFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      if (
        !idea.title.toLowerCase().includes(q) &&
        !idea.description.toLowerCase().includes(q) &&
        !idea.tags.some((t) => t.includes(q))
      ) return false;
    }
    return true;
  });
}

function applySort(ideas: Idea[], sort: SortMode): Idea[] {
  const sorted = [...ideas];
  if (sort === "newest") {
    sorted.sort((a, b) => b.created_at - a.created_at);
  } else if (sort === "oldest") {
    sorted.sort((a, b) => a.created_at - b.created_at);
  } else {
    sorted.sort((a, b) => {
      const aStale = isStaleIdea(a) ? 0 : 1;
      const bStale = isStaleIdea(b) ? 0 : 1;
      if (aStale !== bStale) return aStale - bStale;
      return b.created_at - a.created_at;
    });
  }
  return sorted;
}

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: "newest", label: "Najnowsze" },
  { value: "oldest", label: "Najstarsze" },
  { value: "stale_first", label: "Najpierw nieaktywne" },
];

function ideaCountLabel(count: number): string {
  if (count === 1) return "1 pomysł";
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) {
    return `${count} pomysły`;
  }
  return `${count} pomysłów`;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function IdeaVaultPage() {
  const router = useRouter();

  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [domainFilter, setDomainFilter] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortMode>("newest");

  const [showCreate, setShowCreate] = useState(false);
  const [softDeleteTarget, setSoftDeleteTarget] = useState<Idea | null>(null);
  const [staleActionTarget, setStaleActionTarget] = useState<{
    idea: Idea;
    action: "archive" | "reactivate";
  } | null>(null);

  // ---------------------------------------------------------------------------
  // Fetch
  // ---------------------------------------------------------------------------

  const fetchAll = useCallback(async () => {
    setFetchError(null);
    setLoading(true);
    try {
      const statuses: IdeaStatus[] = [
        "draft", "created", "clarification", "submitted",
        "council_review", "awaiting_approval", "approved", "accepted",
        "rejected", "implemented", "stale", "abandoned",
        "archived", "deleted_soft",
      ];
      const results = await Promise.allSettled(
        statuses.map((s) => listIdeas({ status: s, limit: 100 }))
      );
      const all: Idea[] = [];
      const seen = new Set<string>();
      for (const r of results) {
        if (r.status === "fulfilled") {
          for (const idea of r.value) {
            if (!seen.has(idea.idea_id)) {
              seen.add(idea.idea_id);
              all.push(idea);
            }
          }
        }
      }
      // Fallback: un-filtered list to catch anything not status-indexed
      try {
        const fallback = await listIdeas({ limit: 200 });
        for (const idea of fallback) {
          if (!seen.has(idea.idea_id)) {
            seen.add(idea.idea_id);
            all.push(idea);
          }
        }
      } catch { /* ignore */ }

      setIdeas(all);
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : "Błąd pobierania");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(fetchAll);
  }, [fetchAll]);

  // ---------------------------------------------------------------------------
  // Derived state
  // ---------------------------------------------------------------------------

  const staleCount = useMemo(
    () => ideas.filter(isStaleIdea).length,
    [ideas]
  );

  const statusCounts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const idea of ideas) map[idea.status] = (map[idea.status] ?? 0) + 1;
    return map;
  }, [ideas]);

  const filteredAndSorted = useMemo(
    () => applySort(applyFilter(ideas, statusFilter, domainFilter, search), sort),
    [ideas, statusFilter, domainFilter, search, sort]
  );

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  function handleCreated(idea: Idea) {
    setIdeas((prev) => [idea, ...prev]);
    setShowCreate(false);
  }

  function handleTransitioned(updated: Idea) {
    setIdeas((prev) =>
      prev.map((i) => (i.idea_id === updated.idea_id ? updated : i))
    );
    setSoftDeleteTarget(null);
    setStaleActionTarget(null);
  }

  async function handleRestore(idea: Idea) {
    try {
      const updated = await setIdeaStatus(idea.idea_id, "draft");
      setIdeas((prev) => prev.map((i) => (i.idea_id === idea.idea_id ? updated : i)));
    } catch { /* ignore */ }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col min-h-full px-6 py-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground flex items-center gap-1.5">
            Skarbiec Pomysłów
            <HelpTip text="Tu zaczyna się przyjęcie projektu. Operator wpisuje krótki opis, dodaje załączniki i pozwala AEIS wykryć domenę, braki, poziom decyzji D0-D5 oraz wymaganą bramkę człowieka przed promocją do projektu." />
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {loading ? "..." : ideaCountLabel(ideas.length)}
            {!loading && staleCount > 0 && ` \u00b7 ${staleCount} nieaktywnych`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchAll}
            disabled={loading}
            className="h-8 w-8 p-0"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
          </Button>
          <Button size="sm" onClick={() => setShowCreate(true)} className="h-8 gap-1.5">
            <Plus className="w-3.5 h-3.5" />
            Nowy pomysł
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground/50 pointer-events-none" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Szukaj pomysłów..."
          className={cn(
            "w-full pl-8 pr-3 py-1.5 text-sm rounded-md",
            "border border-border/40 bg-background/60",
            "focus:outline-none focus:ring-1 focus:ring-primary/50",
            "placeholder:text-muted-foreground/40"
          )}
        />
      </div>

      {/* Status filter chips */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <FilterChip
          active={statusFilter === "all"}
          onClick={() => setStatusFilter("all")}
        >
          Wszystkie ({ideas.length})
        </FilterChip>

        {staleCount > 0 && (
          <FilterChip
            active={statusFilter === "stale"}
            onClick={() => setStatusFilter(statusFilter === "stale" ? "all" : "stale")}
            variant="amber"
          >
            Nieaktywne ({staleCount})
          </FilterChip>
        )}

        {IDEA_STATUSES.filter((s) => (statusCounts[s] ?? 0) > 0).map((s) => (
          <FilterChip
            key={s}
            active={statusFilter === s}
            onClick={() => setStatusFilter(statusFilter === s ? "all" : s)}
          >
            {STATUS_LABELS[s]} ({statusCounts[s]})
          </FilterChip>
        ))}
      </div>

      {/* Domain + sort */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value)}
          className={cn(
            "text-xs px-2 py-1.5 rounded-md border border-border/40 bg-background/60",
            "focus:outline-none focus:ring-1 focus:ring-primary/50"
          )}
        >
          <option value="">Wszystkie domeny</option>
          {DOMAINS.map((d) => (
            <option key={d} value={d}>{DOMAIN_LABELS[d]}</option>
          ))}
        </select>

        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortMode)}
          className={cn(
            "text-xs px-2 py-1.5 rounded-md border border-border/40 bg-background/60",
            "focus:outline-none focus:ring-1 focus:ring-primary/50"
          )}
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Error */}
      {fetchError && (
        <Card className="px-4 py-3 border-red-400/20 bg-red-400/5 text-xs text-red-400">
          {fetchError}
        </Card>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-10 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" />
          Pobieranie pomysłów...
        </div>
      )}

      {/* Ideas list */}
      {!loading && !fetchError && (
        filteredAndSorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-muted-foreground text-sm">
              {ideas.length === 0
                ? "Brak pomysłów. Dodaj pierwszy \u2192"
                : "Brak wyników dla wybranych filtrów."}
            </p>
            {ideas.length === 0 && (
              <Button
                size="sm"
                variant="outline"
                className="mt-4"
                onClick={() => setShowCreate(true)}
              >
                <Plus className="w-3.5 h-3.5 mr-1.5" />
                Dodaj pomysł
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredAndSorted.map((idea) => (
              <div key={idea.idea_id} className="relative group/row">
                <IdeaCard
                  idea={idea}
                  onView={() => router.push(`/idea-vault/${idea.idea_id}`)}
                  onSoftDelete={(i) => setSoftDeleteTarget(i)}
                />

                {/* Stale quick-actions (shown in the row) */}
                {isStaleIdea(idea) && (
                  <div className="absolute right-14 top-1/2 -translate-y-1/2 flex gap-1 z-10 opacity-0 group-hover/row:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => { e.stopPropagation(); setStaleActionTarget({ idea, action: "archive" }); }}
                      className="flex items-center gap-1 text-[10px] px-2 py-1 rounded border border-slate-400/30 text-slate-400 hover:bg-slate-400/10 transition-colors bg-card"
                    >
                      <Archive className="w-3 h-3" />
                      Archiwizuj
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setStaleActionTarget({ idea, action: "reactivate" }); }}
                      className="flex items-center gap-1 text-[10px] px-2 py-1 rounded border border-blue-400/30 text-blue-400 hover:bg-blue-400/10 transition-colors bg-card"
                    >
                      <RotateCcw className="w-3 h-3" />
                      Reaktywuj
                    </button>
                  </div>
                )}

                {/* Soft-deleted: restore inline */}
                {idea.status === "deleted_soft" && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 z-10">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleRestore(idea); }}
                      className="flex items-center gap-1 text-[10px] px-2 py-1 rounded border border-blue-400/30 text-blue-400 hover:bg-blue-400/10 transition-colors bg-card"
                    >
                      <RotateCcw className="w-3 h-3" />
                      Przywróć
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )
      )}

      {/* Modals */}
      {showCreate && (
        <CreateIdeaModal
          open={showCreate}
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      )}

      <StatusTransitionModal
        open={!!softDeleteTarget}
        idea={softDeleteTarget}
        targetStatus="deleted_soft"
        onClose={() => setSoftDeleteTarget(null)}
        onTransitioned={handleTransitioned}
      />

      <StatusTransitionModal
        open={staleActionTarget?.action === "archive"}
        idea={staleActionTarget?.idea ?? null}
        targetStatus="archived"
        onClose={() => setStaleActionTarget(null)}
        onTransitioned={handleTransitioned}
      />

      <StatusTransitionModal
        open={staleActionTarget?.action === "reactivate"}
        idea={staleActionTarget?.idea ?? null}
        targetStatus="draft"
        onClose={() => setStaleActionTarget(null)}
        onTransitioned={handleTransitioned}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// FilterChip
// ---------------------------------------------------------------------------

function FilterChip({
  active,
  onClick,
  children,
  variant = "blue",
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  variant?: "blue" | "amber";
}) {
  const activeClass =
    variant === "amber"
      ? "border-yellow-600/50 bg-yellow-600/10 text-yellow-600"
      : "border-primary/50 bg-primary/10 text-primary";
  return (
    <button
      onClick={onClick}
      className={cn(
        "text-[11px] px-2.5 py-1 rounded-full border transition-colors",
        active
          ? activeClass
          : "border-border/40 text-muted-foreground hover:border-border/70 hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}
