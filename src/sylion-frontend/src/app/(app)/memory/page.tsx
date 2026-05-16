"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, Database, FileText, GitBranch, Link2, RefreshCw, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { HelpTip } from "@/components/common/HelpTip";
import { api } from "@/lib/api/client";

type MemoryStats = {
  kanon?: { sections?: number };
  evidence?: { total?: number; total_evidence?: number; by_type?: Record<string, number> };
  indexer?: { total?: number; sections?: number; indexed_sections?: number };
  kb?: Record<string, unknown>;
  obsidian?: { nodes?: number; edges?: number };
};

type ObsidianGraph = {
  vault_root?: string;
  nodes?: ObsidianNode[];
  edges?: ObsidianEdge[];
  counts?: { nodes?: number; edges?: number };
};

type ObsidianNode = {
  id: string;
  label?: string;
  domain?: string;
};

type ObsidianEdge = {
  source: string;
  target: string;
};

type RecentMemoryItem = {
  kind?: string;
  id?: string;
  artefact_type?: string;
  title?: string;
  count?: number;
};

type MemorySearchItem = {
  title?: string;
  section_id?: string;
};

const DEFAULT_MEMORY_TEXT =
  "Manualny test pamięci AEIS: lokalny projekt CRM ma preferować lokalne skille CRM, tani profil modeli i brak VPS bez zgody Human Gate.";

const RECENT_KIND_LABELS: Record<string, string> = {
  evidence_summary: "Podsumowanie dowodów",
  obsidian_graph: "Graf Obsidian",
  kanon_section: "Sekcja kanonu",
  index_section: "Sekcja indeksu",
};

const RECENT_TITLE_LABELS: Record<string, string> = {
  memory_reuse_note: "Notatka ponownego użycia pamięci",
  "Obsidian long-horizon memory": "Pamięć długoterminowa Obsidian",
};

function labelRecentKind(value?: string): string {
  const normalized = String(value || "").trim();
  return RECENT_KIND_LABELS[normalized.toLowerCase()] || normalized.replace(/_/g, " ") || "rekord pamięci";
}

function labelRecentTitle(value?: string): string {
  const normalized = String(value || "").trim();
  return RECENT_TITLE_LABELS[normalized] || normalized.replace(/_/g, " ") || "rekord pamięci";
}

export default function MemoryPage() {
  const [stats, setStats] = useState<MemoryStats>({});
  const [recent, setRecent] = useState<RecentMemoryItem[]>([]);
  const [memoryText, setMemoryText] = useState(DEFAULT_MEMORY_TEXT);
  const [query, setQuery] = useState("lokalne skille CRM tani profil modeli");
  const [resultText, setResultText] = useState("");
  const [obsidianGraph, setObsidianGraph] = useState<ObsidianGraph>({ counts: { nodes: 0, edges: 0 } });
  const [obsidianProjectId, setObsidianProjectId] = useState("proj_demo_01_mobile_field_inspector");
  const [obsidianRelatedIds, setObsidianRelatedIds] = useState("");
  const [obsidianResult, setObsidianResult] = useState("");
  const [busy, setBusy] = useState(false);

  const refreshMemory = useCallback(async () => {
    const [nextStats, nextRecent, nextGraph] = await Promise.all([
      api.memoryStats(),
      api.memoryRecent(12),
      api.obsidianGraph().catch(() => ({ nodes: [], edges: [], counts: { nodes: 0, edges: 0 } })),
    ]);
    setStats(nextStats);
    setRecent(nextRecent.items ?? []);
    setObsidianGraph(nextGraph);
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshMemory().catch((error) => {
      setResultText(error instanceof Error ? error.message : "Nie udało się odświeżyć pamięci");
    });
  }, [refreshMemory]);

  const runMemoryAction = useCallback(
    async (action: "store" | "evidence" | "index" | "search") => {
      if (busy) return;
      setBusy(true);
      setResultText("");
      try {
        const suffix = Date.now();
        if (action === "store") {
          const sectionId = `manual_memory_${suffix}`;
          await api.storeKanonSection({
            section_id: sectionId,
            title: "Manualny test pamięci",
            content: memoryText,
            chapter: "Manualne testy AEIS",
            section_number: 1,
          });
          setResultText(`Zapisano sekcję kanonu ${sectionId}`);
        } else if (action === "evidence") {
          const evidenceId = `manual_memory_evidence_${suffix}`;
          await api.storeMemoryEvidence({
            evidence_id: evidenceId,
            pack_id: "aeis_manual_memory",
            artefact_type: "memory_reuse_note",
            name: "Dowód manualnego testu pamięci",
            content: memoryText,
            metadata: { source: "memory_dashboard", query },
          });
          setResultText(`Zapisano dowód ${evidenceId}`);
        } else if (action === "index") {
          const sectionId = `manual_memory_index_${suffix}`;
          await api.indexMemorySection({
            section_id: sectionId,
            title: "Ręcznie indeksowana sekcja pamięci",
            content: memoryText,
          });
          setResultText(`Zaindeksowano sekcję ${sectionId}`);
        } else {
          const search = await api.memorySearch(query, 5);
          const context = await api.memoryContext(query, 1200);
          const titles = (search.results ?? [])
            .map((item: MemorySearchItem) => item.title ?? item.section_id ?? "wynik")
            .join(", ");
          setResultText(
            `Wyniki: ${titles || "brak"} | Kontekst: ${String(context.context ?? "").slice(0, 240)}`,
          );
        }
        await refreshMemory();
      } catch (error) {
        setResultText(error instanceof Error ? error.message : "Akcja pamięci nie powiodła się");
      } finally {
        setBusy(false);
      }
    },
    [busy, memoryText, query, refreshMemory],
  );

  const runObsidianSync = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setObsidianResult("");
    try {
      const related_project_ids = obsidianRelatedIds
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const synced = await api.obsidianSyncProject({
        project_id: obsidianProjectId.trim(),
        related_project_ids,
        source: "memory_dashboard",
      });
      setObsidianResult(`Zsynchronizowano: ${synced.note_path}`);
      setObsidianGraph(await api.obsidianGraph());
      await refreshMemory();
    } catch (error) {
      setObsidianResult(error instanceof Error ? error.message : "Synchronizacja Obsidian nie powiodła się");
    } finally {
      setBusy(false);
    }
  }, [busy, obsidianProjectId, obsidianRelatedIds, refreshMemory]);

  const evidenceTypes = Object.entries(stats.evidence?.by_type ?? {});

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Pamięć
            <HelpTip text="Warstwa pamięci AEIS: kanon, dowody, indeks wyszukiwania, retrieval i kontekst używany ponownie w kolejnych etapach." />
          </h1>
          <p className="text-sm text-muted-foreground">
            Zapis, indeksowanie i odzyskiwanie pamięci projektu
            <Badge variant="outline" className="ml-2 text-[9px] border-sylion-green/30 text-sylion-green">
              BACKEND DZIAŁA
            </Badge>
          </p>
        </div>
        <button
          type="button"
          onClick={() => refreshMemory()}
          className="inline-flex items-center gap-2 rounded-md border border-[rgba(148,163,184,0.16)] bg-secondary/30 px-3 py-2 text-xs font-medium text-foreground"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Odśwież
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <Card className="p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)]">
          <BookOpen className="h-4 w-4 text-primary" />
          <p className="mt-2 text-[10px] uppercase tracking-wider text-muted-foreground">Sekcje kanonu</p>
          <p className="text-2xl font-semibold text-primary">{stats.kanon?.sections ?? 0}</p>
        </Card>
        <Card className="p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)]">
          <FileText className="h-4 w-4 text-sylion-amber" />
          <p className="mt-2 text-[10px] uppercase tracking-wider text-muted-foreground">Dowody</p>
          <p className="text-2xl font-semibold text-sylion-amber">
            {stats.evidence?.total_evidence ?? stats.evidence?.total ?? 0}
          </p>
        </Card>
        <Card className="p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)]">
          <Search className="h-4 w-4 text-sylion-green" />
          <p className="mt-2 text-[10px] uppercase tracking-wider text-muted-foreground">Indeks</p>
          <p className="text-2xl font-semibold text-sylion-green">
            {stats.indexer?.indexed_sections ?? stats.indexer?.sections ?? stats.indexer?.total ?? 0}
          </p>
        </Card>
        <Card className="p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)]">
          <Database className="h-4 w-4 text-sylion-blue" />
          <p className="mt-2 text-[10px] uppercase tracking-wider text-muted-foreground">Typy dowodów</p>
          <p className="text-2xl font-semibold text-sylion-blue">{evidenceTypes.length}</p>
        </Card>
      </div>

      <Card className="p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)]">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_320px]">
          <label className="space-y-1">
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Treść do zapamiętania
            </span>
            <textarea
              value={memoryText}
              onChange={(event) => setMemoryText(event.target.value)}
              className="min-h-28 w-full rounded-md border border-[rgba(148,163,184,0.16)] bg-[#0a0f1e] px-3 py-2 text-xs text-foreground outline-none focus:border-primary/50"
            />
          </label>
          <div className="space-y-3">
            <label className="space-y-1 block">
              <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Zapytanie retrieval
              </span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="w-full rounded-md border border-[rgba(148,163,184,0.16)] bg-[#0a0f1e] px-3 py-2 text-xs text-foreground outline-none focus:border-primary/50"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button type="button" disabled={busy} onClick={() => runMemoryAction("store")} className="rounded-md border border-primary/20 bg-primary/10 px-3 py-2 text-xs font-medium text-primary disabled:opacity-50">
                Zapisz kanon
              </button>
              <button type="button" disabled={busy} onClick={() => runMemoryAction("evidence")} className="rounded-md border border-sylion-amber/20 bg-sylion-amber/10 px-3 py-2 text-xs font-medium text-sylion-amber disabled:opacity-50">
                Zapisz dowód
              </button>
              <button type="button" disabled={busy} onClick={() => runMemoryAction("index")} className="rounded-md border border-sylion-green/20 bg-sylion-green/10 px-3 py-2 text-xs font-medium text-sylion-green disabled:opacity-50">
                Indeksuj
              </button>
              <button type="button" disabled={busy} onClick={() => runMemoryAction("search")} className="rounded-md border border-[rgba(148,163,184,0.16)] bg-secondary/30 px-3 py-2 text-xs font-medium text-foreground disabled:opacity-50">
                Szukaj kontekst
              </button>
            </div>
          </div>
        </div>
        {resultText && <p className="mt-3 text-[11px] text-muted-foreground">{resultText}</p>}
      </Card>

      <Card className="p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <GitBranch className="h-4 w-4 text-sylion-green" />
              Pamięć długoterminowa Obsidian
              <HelpTip text="Trwały zapis zamkniętych projektów do lokalnego skarbca Markdown, z powiązaniami zwrotnymi, automatycznymi tagami i grafem relacji." />
            </h2>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Skarbiec: {obsidianGraph.vault_root || "nie skonfigurowano"} | Węzły: {obsidianGraph.counts?.nodes ?? 0} | Relacje: {obsidianGraph.counts?.edges ?? 0}
            </p>
          </div>
          <div className="grid w-full grid-cols-1 gap-2 lg:w-[520px] lg:grid-cols-[1fr_1fr_auto]">
            <input
              value={obsidianProjectId}
              onChange={(event) => setObsidianProjectId(event.target.value)}
              className="rounded-md border border-[rgba(148,163,184,0.16)] bg-[#0a0f1e] px-3 py-2 text-xs text-foreground outline-none focus:border-primary/50"
              placeholder="project_id"
            />
            <input
              value={obsidianRelatedIds}
              onChange={(event) => setObsidianRelatedIds(event.target.value)}
              className="rounded-md border border-[rgba(148,163,184,0.16)] bg-[#0a0f1e] px-3 py-2 text-xs text-foreground outline-none focus:border-primary/50"
              placeholder="powiązane ID, po przecinku"
            />
            <button
              type="button"
              disabled={busy}
              onClick={runObsidianSync}
              className="inline-flex items-center justify-center gap-2 rounded-md border border-sylion-green/20 bg-sylion-green/10 px-3 py-2 text-xs font-medium text-sylion-green disabled:opacity-50"
            >
              <Link2 className="h-3.5 w-3.5" />
              Synchronizuj
            </button>
          </div>
        </div>
        {obsidianResult && <p className="mt-3 text-[11px] text-muted-foreground">{obsidianResult}</p>}
        <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
          <div className="rounded-md border border-[rgba(148,163,184,0.08)] bg-[#0a0f1e] p-3">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Węzły grafu</p>
            <div className="mt-2 space-y-2">
              {(obsidianGraph.nodes ?? []).slice(0, 6).map((node) => (
                <div key={node.id} className="flex items-center justify-between gap-2 text-xs">
                  <span className="truncate text-foreground">{node.label ?? node.id}</span>
                  <Badge variant="outline" className="border-sylion-green/30 text-[9px] text-sylion-green">
                    {node.domain || "pamięć"}
                  </Badge>
                </div>
              ))}
              {(obsidianGraph.nodes ?? []).length === 0 && <p className="text-xs text-muted-foreground">Brak zsynchronizowanych projektów.</p>}
            </div>
          </div>
          <div className="rounded-md border border-[rgba(148,163,184,0.08)] bg-[#0a0f1e] p-3">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Powiązania</p>
            <div className="mt-2 space-y-2">
              {(obsidianGraph.edges ?? []).slice(0, 6).map((edge, index) => (
                <div key={`${edge.source}-${edge.target}-${index}`} className="text-xs text-muted-foreground">
                  <span className="text-foreground">{edge.source}</span> -&gt; <span className="text-foreground">{edge.target}</span>
                </div>
              ))}
              {(obsidianGraph.edges ?? []).length === 0 && <p className="text-xs text-muted-foreground">Brak relacji w indeksie Obsidian.</p>}
            </div>
          </div>
        </div>
      </Card>

      <Card className="p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)]">
        <h2 className="text-sm font-semibold text-foreground">Ostatnia pamięć</h2>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
          {recent.length === 0 ? (
            <p className="text-xs text-muted-foreground">Brak rekordów pamięci.</p>
          ) : (
            recent.map((item, index) => (
              <div key={`${item.kind}-${item.id || item.artefact_type || "item"}-${index}`} className="rounded-md border border-[rgba(148,163,184,0.08)] bg-[#0a0f1e] p-3">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{labelRecentKind(item.kind)}</p>
                <p className="mt-1 text-xs font-medium text-foreground">
                  {labelRecentTitle(item.title ?? item.id ?? item.artefact_type)}
                </p>
                {item.count != null && <p className="text-[11px] text-muted-foreground">liczba: {item.count}</p>}
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
