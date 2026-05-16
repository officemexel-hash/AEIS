"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { HelpTip } from "@/components/common/HelpTip";
import { api, request } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  Users,
  Code2,
  Image as ImageIcon,
  AudioLines,
  ScrollText,
  Smartphone,
  Globe2,
  BookOpenCheck,
  Compass,
  Sparkles,
  Loader2,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  Wand2,
  Workflow,
  Search,
  X,
  Download,
  LayoutGrid,
  Rows3,
  Copy,
  ArrowUpDown,
  Filter,
  Info,
  CheckCircle2,
  Send,
  Tags,
} from "lucide-react";

/* ============================================================
   Typy
   ============================================================ */

type Category =
  | "text"
  | "code"
  | "visual"
  | "audio"
  | "strategy"
  | "mobile"
  | "web"
  | "domain";

interface RoleSummary {
  role_id: string;
  name_pl?: string;
  name?: string;
  category: Category | string;
  cost_profile?: string;
  description?: string;
  description_pl?: string;
  preferred_models?: string[];
  fallback_models?: string[];
}

interface RoleCatalogResponse {
  count?: number;
  roles: RoleSummary[];
}

interface RoleDetail extends RoleSummary {
  typical_tasks?: string[];
  system_prompt?: string;
  tags?: string[];
  estimated_minutes?: number;
  [key: string]: unknown;
}

type SortKey = "default" | "cost_asc" | "cost_desc" | "models_desc";

interface CatalogPrefs {
  search?: string;
  sort?: SortKey;
  compact?: boolean;
  costFilter?: string | null;
  category?: Category | "all";
}

const PREFS_KEY = "sylion-v2-role-catalog-prefs";

function costRank(profile?: string): number {
  switch ((profile || "").toLowerCase()) {
    case "low":
    case "tani":
      return 1;
    case "medium":
    case "średni":
    case "sredni":
      return 2;
    case "high":
    case "drogi":
    case "wysoki":
      return 3;
    default:
      return 99;
  }
}

function costTier(profile?: string): "low" | "medium" | "high" | "other" {
  switch ((profile || "").toLowerCase()) {
    case "low":
    case "tani":
      return "low";
    case "medium":
    case "średni":
    case "sredni":
      return "medium";
    case "high":
    case "drogi":
    case "wysoki":
      return "high";
    default:
      return "other";
  }
}

const SORT_OPTIONS: { id: SortKey; label: string }[] = [
  { id: "default", label: "Domyślnie" },
  { id: "cost_asc", label: "Po koszcie ↑" },
  { id: "cost_desc", label: "Po koszcie ↓" },
  { id: "models_desc", label: "Po liczbie modeli" },
];

const COST_TIER_LABEL: Record<"low" | "medium" | "high", string> = {
  low: "niski",
  medium: "średni",
  high: "wysoki",
};

interface PipelineStep {
  step?: number;
  role_id: string;
  role_name?: string;
  preferred_model?: string;
  estimated_minutes?: number;
  estimated_cost?: number;
  description?: string;
}

interface SuggestPipelineResponse {
  steps?: PipelineStep[];
  pipeline?: PipelineStep[];
  confidence?: number;
  notes_pl?: string[];
}

/* ---- W7 capability taxonomy + match-task ---- */

type SkillLevel = "junior" | "mid" | "senior" | "principal" | "any";

interface CapabilityOption {
  id: string;
  role_count: number;
}

interface CapabilitiesResponse {
  count: number;
  capabilities: CapabilityOption[];
}

interface MatchTaskRoleSummary {
  id: string;
  name_pl?: string;
  name_en?: string;
  category?: string;
  cost_profile?: string;
  preferred_capabilities?: string[];
  capabilities?: string[];
  skill_level?: string;
}

interface MatchTaskHit {
  role: MatchTaskRoleSummary;
  score: number;
  matched_capabilities: string[];
}

interface MatchTaskResponse {
  task_description: string;
  required_capabilities: string[];
  skill_level: string;
  top_n: number;
  matches: MatchTaskHit[];
  engine: string;
  note?: string;
}

const SKILL_LEVELS: { id: SkillLevel; label: string; help: string }[] = [
  {
    id: "any",
    label: "dowolny",
    help: "Brak filtra po seniority — pokazuje wszystkie role.",
  },
  {
    id: "junior",
    label: "junior",
    help: "Min. junior (junior+).",
  },
  {
    id: "mid",
    label: "mid",
    help: "Min. mid (mid+).",
  },
  {
    id: "senior",
    label: "senior",
    help: "Min. senior (senior+).",
  },
  {
    id: "principal",
    label: "principal",
    help: "Tylko principal.",
  },
];

const METHOD_BADGE_STYLE: Record<string, { label: string; className: string; tooltip: string }> = {
  "capability-overlap-v0": {
    label: "zgodność tagów",
    className: "border-sylion-blue/40 bg-sylion-blue/10 text-sylion-blue",
    tooltip: "Dopasowanie przez nakładanie tagów umiejętności (+5 za umiejętność, +1 za słowo kluczowe w opisie).",
  },
  "embedding": {
    label: "wektory",
    className: "border-amber-500/40 bg-amber-500/10 text-amber-500",
    tooltip: "G1: podobieństwo wektorowe nomic-embed-text przez Ollama.",
  },
  "llm_generated": {
    label: "reranking LLM",
    className: "border-purple-500/40 bg-purple-500/10 text-purple-400",
    tooltip: "G2: reranking LLM na najlepszych kandydatach.",
  },
};

function methodBadge(engine: string): { label: string; className: string; tooltip: string } {
  return (
    METHOD_BADGE_STYLE[engine] ?? {
      label: engine,
      className: "border-border/40 bg-muted/30 text-muted-foreground",
      tooltip: engine,
    }
  );
}

function skillLevelPillStyle(level?: string): string {
  switch ((level || "").toLowerCase()) {
    case "junior":
      return "border-sylion-green/40 bg-sylion-green/10 text-sylion-green";
    case "mid":
      return "border-sylion-blue/40 bg-sylion-blue/10 text-sylion-blue";
    case "senior":
      return "border-sylion-amber/40 bg-sylion-amber/10 text-sylion-amber";
    case "principal":
      return "border-purple-400/40 bg-purple-400/10 text-purple-400";
    default:
      return "border-border/40 bg-muted/30 text-muted-foreground";
  }
}

/* ============================================================
   Pomocnicze
   ============================================================ */

const CATEGORIES: {
  id: Category | "all";
  label: string;
  icon: typeof Users;
  help: string;
}[] = [
  {
    id: "all",
    label: "Wszystkie",
    icon: Users,
    help: "Wszystkie role bez filtra kategorii.",
  },
  {
    id: "text",
    label: "Tekst",
    icon: ScrollText,
    help: "Role do generowania, redakcji i analizy tekstu (artykuły, copywriting, raporty).",
  },
  {
    id: "code",
    label: "Kod",
    icon: Code2,
    help: "Role programistyczne: backend, frontend, refaktor, code review, QA.",
  },
  {
    id: "visual",
    label: "Wizual",
    icon: ImageIcon,
    help: "Role do grafiki, layoutu, brandingu, ikon, ilustracji.",
  },
  {
    id: "audio",
    label: "Audio",
    icon: AudioLines,
    help: "Role do produkcji audio, podcastów, syntezy mowy, transkrypcji.",
  },
  {
    id: "strategy",
    label: "Strategia",
    icon: Compass,
    help: "Role strategiczne: research, planowanie, business case, roadmapa.",
  },
  {
    id: "mobile",
    label: "Mobile",
    icon: Smartphone,
    help: "Role mobilne: iOS, Android, React Native, Flutter, UX mobile.",
  },
  {
    id: "web",
    label: "Web",
    icon: Globe2,
    help: "Role webowe: full-stack, devops, frontend, backend, integracje.",
  },
  {
    id: "domain",
    label: "Domena",
    icon: BookOpenCheck,
    help: "Role specjalistyczne dziedzinowe: prawo, medycyna, finanse, edukacja.",
  },
];

const CATEGORY_HELP: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.id, c.help]),
);

function costPillStyle(profile?: string): string {
  switch ((profile || "").toLowerCase()) {
    case "low":
    case "tani":
      return "border-sylion-green/40 bg-sylion-green/10 text-sylion-green";
    case "medium":
    case "średni":
    case "sredni":
      return "border-sylion-amber/40 bg-sylion-amber/10 text-sylion-amber";
    case "high":
    case "drogi":
    case "wysoki":
      return "border-red-400/40 bg-red-400/10 text-red-400";
    default:
      return "border-border/40 bg-muted/30 text-muted-foreground";
  }
}

function categoryColor(cat: string): string {
  const map: Record<string, string> = {
    text: "border-sky-400/40 bg-sky-400/10 text-sky-400",
    code: "border-violet-400/40 bg-violet-400/10 text-violet-400",
    visual: "border-pink-400/40 bg-pink-400/10 text-pink-400",
    audio: "border-emerald-400/40 bg-emerald-400/10 text-emerald-400",
    strategy: "border-amber-400/40 bg-amber-400/10 text-amber-400",
    mobile: "border-indigo-400/40 bg-indigo-400/10 text-indigo-400",
    web: "border-cyan-400/40 bg-cyan-400/10 text-cyan-400",
    domain: "border-rose-400/40 bg-rose-400/10 text-rose-400",
  };
  return map[cat] || "border-border/40 bg-muted/30 text-muted-foreground";
}

/* ============================================================
   Strona
   ============================================================ */

export default function RoleCatalogPage() {
  const [roles, setRoles] = useState<RoleSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<Category | "all">("all");

  const [openRoleId, setOpenRoleId] = useState<string | null>(null);
  const [openRole, setOpenRole] = useState<RoleDetail | null>(null);
  const [openLoading, setOpenLoading] = useState<boolean>(false);
  const [promptCollapsed, setPromptCollapsed] = useState<boolean>(true);

  // Suggester
  const [taskInput, setTaskInput] = useState<string>("");
  const [suggesting, setSuggesting] = useState<boolean>(false);
  const [suggestion, setSuggestion] = useState<SuggestPipelineResponse | null>(null);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [suggestionCopied, setSuggestionCopied] = useState<boolean>(false);

  // UX: search / sort / compact / cost filter / selection
  const [search, setSearch] = useState<string>("");
  const [sortKey, setSortKey] = useState<SortKey>("default");
  const [compact, setCompact] = useState<boolean>(false);
  const [costFilter, setCostFilter] = useState<string | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [exporting, setExporting] = useState<boolean>(false);
  const [prefsHydrated, setPrefsHydrated] = useState<boolean>(false);

  // W7→W13: Studio Doboru Roli (capability filter + match-task)
  const studioRef = useRef<HTMLDivElement | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilityOption[]>([]);
  const [capsLoading, setCapsLoading] = useState<boolean>(true);
  const [capsError, setCapsError] = useState<string | null>(null);
  const [selectedCaps, setSelectedCaps] = useState<string[]>([]);
  const [skillLevelFilter, setSkillLevelFilter] = useState<SkillLevel>("any");
  const [capSearch, setCapSearch] = useState<string>("");
  const [matchLoading, setMatchLoading] = useState<boolean>(false);
  const [matchError, setMatchError] = useState<string | null>(null);
  const [matchResp, setMatchResp] = useState<MatchTaskResponse | null>(null);
  const [pickedToast, setPickedToast] = useState<string | null>(null);
  const [pickError, setPickError] = useState<string | null>(null);

  /* ---------- Hydracja preferencji ---------- */
  useEffect(() => {
    queueMicrotask(() => {
      try {
        const raw = localStorage.getItem(PREFS_KEY);
        if (raw) {
          const parsed = JSON.parse(raw) as CatalogPrefs;
          if (typeof parsed.search === "string") setSearch(parsed.search);
          if (parsed.sort) setSortKey(parsed.sort);
          if (typeof parsed.compact === "boolean") setCompact(parsed.compact);
          if (parsed.costFilter !== undefined) setCostFilter(parsed.costFilter);
          if (parsed.category) setActiveCategory(parsed.category);
        }
      } catch {
        /* ignore corrupt prefs */
      } finally {
        setPrefsHydrated(true);
      }
    });
  }, []);

  /* ---------- Zapis preferencji ---------- */
  useEffect(() => {
    if (!prefsHydrated) return;
    try {
      const prefs: CatalogPrefs = {
        search,
        sort: sortKey,
        compact,
        costFilter,
        category: activeCategory,
      };
      localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
    } catch {
      /* ignore quota / privacy mode */
    }
  }, [prefsHydrated, search, sortKey, compact, costFilter, activeCategory]);

  /* ---------- Pobranie ról ---------- */
  const fetchRoles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = (await api.listRoleCatalog()) as RoleCatalogResponse;
      const raw = Array.isArray(data?.roles) ? data.roles : [];
      // Normalise backend payload: API returns ``{id, name_pl, ...}`` but
      // the page-level types use ``role_id`` everywhere (sort comparators
      // call ``role_id.localeCompare`` without ?? "" — crash with undefined).
      // Mirror ``id`` into ``role_id`` and ``name_pl`` into ``name`` so
      // both shapes work without a wider refactor.
      const list = raw.map((r) => {
        const rec = r as unknown as Record<string, unknown>;
        const role_id = (rec.role_id ?? rec.id ?? "") as string;
        const name = (rec.name ?? rec.name_pl ?? rec.name_en ?? role_id) as string;
        return { ...r, role_id, name } as RoleSummary;
      });
      setRoles(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się pobrać ról.");
      setRoles([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchRoles();
    });
  }, [fetchRoles]);

  /* ---------- Pobranie capabilities (W7 taxonomy) ---------- */
  const fetchCapabilities = useCallback(async () => {
    setCapsLoading(true);
    setCapsError(null);
    try {
      const data = await request<CapabilitiesResponse>(
        "/api/v1/role-catalog/capabilities",
      );
      const list = Array.isArray(data?.capabilities) ? data.capabilities : [];
      setCapabilities(list);
    } catch (err) {
      setCapsError(
        err instanceof Error ? err.message : "Nie udało się pobrać taksonomii umiejętności.",
      );
      setCapabilities([]);
    } finally {
      setCapsLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchCapabilities();
    });
  }, [fetchCapabilities]);

  /* ---------- Toggle capability ---------- */
  const toggleCapability = useCallback((capId: string) => {
    setSelectedCaps((prev) =>
      prev.includes(capId) ? prev.filter((c) => c !== capId) : [...prev, capId],
    );
  }, []);

  const clearCapabilities = useCallback(() => {
    setSelectedCaps([]);
    setMatchResp(null);
    setMatchError(null);
  }, []);

  /* ---------- Match-task ---------- */
  const handleMatchTask = useCallback(async () => {
    if (matchLoading) return;
    setMatchLoading(true);
    setMatchError(null);
    setMatchResp(null);
    try {
      const data = await request<MatchTaskResponse>(
        "/api/v1/role-catalog/match-task",
        {
          method: "POST",
          body: JSON.stringify({
            task_description: "",
            required_capabilities: selectedCaps,
            skill_level: skillLevelFilter,
            top_n: 10,
          }),
        },
      );
      setMatchResp(data);
    } catch (err) {
      setMatchError(
        err instanceof Error ? err.message : "Nie udało się dopasować ról.",
      );
    } finally {
      setMatchLoading(false);
    }
  }, [matchLoading, selectedCaps, skillLevelFilter]);

  /* ---------- Scroll do studia ---------- */
  const scrollToStudio = useCallback(() => {
    studioRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  /* ---------- Pick role z match-resp ---------- */
  const handlePickRole = useCallback(async (role: MatchTaskRoleSummary) => {
    const display = role.name_pl || role.name_en || role.id;
    setPickError(null);
    try {
      const saved = await request<{ selection_id?: string }>(
        "/api/v1/role-catalog/selections",
        {
          method: "POST",
          body: JSON.stringify({
            role_id: role.id,
            task_description: matchResp?.task_description ?? "",
            required_capabilities: matchResp?.required_capabilities ?? selectedCaps,
            skill_level: matchResp?.skill_level ?? skillLevelFilter,
            selected_by: "operator-main",
            source: "role_catalog_dashboard",
          }),
        },
      );
      setPickedToast(
        saved.selection_id
          ? `Wybrano rolę "${display}" i zapisano wybor: ${saved.selection_id}.`
          : `Wybrano rolę "${display}" i zapisano wybor w katalogu.`,
      );
      window.setTimeout(() => setPickedToast(null), 3500);
    } catch (err) {
      setPickError(err instanceof Error ? err.message : "Nie udało się zapisać wyboru roli");
    }
  }, [matchResp, selectedCaps, skillLevelFilter]);

  /* ---------- Filtrowane capabilities (po tekście) ---------- */
  const filteredCapabilities = useMemo(() => {
    const q = capSearch.trim().toLowerCase();
    if (!q) return capabilities;
    return capabilities.filter((c) => c.id.toLowerCase().includes(q));
  }, [capabilities, capSearch]);

  /* ---------- Pobranie szczegółów ---------- */
  useEffect(() => {
    if (!openRoleId) {
      queueMicrotask(() => setOpenRole(null));
      return;
    }
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) setOpenLoading(true);
    });
    api
      .getRole(openRoleId)
      .then((d) => {
        if (cancelled) return;
        setOpenRole(d as RoleDetail);
      })
      .catch(() => {
        if (cancelled) return;
        setOpenRole(null);
      })
      .finally(() => {
        if (cancelled) return;
        setOpenLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [openRoleId]);

  /* ---------- Filtrowanie po kategorii ---------- */
  const categoryFiltered = useMemo(() => {
    if (activeCategory === "all") return roles;
    return roles.filter((r) => r.category === activeCategory);
  }, [roles, activeCategory]);

  /* ---------- Liczniki dla legendy kosztów (po kategorii, przed cost+search) ---------- */
  const costCounts = useMemo(() => {
    const counts = { low: 0, medium: 0, high: 0, other: 0 };
    for (const r of categoryFiltered) {
      counts[costTier(r.cost_profile)] += 1;
    }
    return counts;
  }, [categoryFiltered]);

  /* ---------- Pełny pipeline: search + cost-filter + sort ---------- */
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = categoryFiltered;

    if (costFilter) {
      list = list.filter((r) => costTier(r.cost_profile) === costFilter);
    }

    if (q) {
      list = list.filter((r) => {
        const detail = r as RoleDetail;
        const haystacks: string[] = [
          r.name_pl ?? "",
          r.name ?? "",
          r.role_id ?? "",
          r.description_pl ?? "",
          r.description ?? "",
        ];
        if (Array.isArray(detail.typical_tasks)) {
          haystacks.push(detail.typical_tasks.join(" "));
        }
        return haystacks.some((h) => h.toLowerCase().includes(q));
      });
    }

    const sorted = [...list];
    switch (sortKey) {
      case "cost_asc":
        sorted.sort(
          (a, b) =>
            costRank(a.cost_profile) - costRank(b.cost_profile) ||
            a.role_id.localeCompare(b.role_id),
        );
        break;
      case "cost_desc":
        sorted.sort(
          (a, b) =>
            costRank(b.cost_profile) - costRank(a.cost_profile) ||
            a.role_id.localeCompare(b.role_id),
        );
        break;
      case "models_desc":
        sorted.sort((a, b) => {
          const ac =
            (a.preferred_models?.length ?? 0) +
            (a.fallback_models?.length ?? 0);
          const bc =
            (b.preferred_models?.length ?? 0) +
            (b.fallback_models?.length ?? 0);
          return bc - ac || a.role_id.localeCompare(b.role_id);
        });
        break;
      default:
        sorted.sort((a, b) => a.role_id.localeCompare(b.role_id));
    }
    return sorted;
  }, [categoryFiltered, search, costFilter, sortKey]);

  /* ---------- Selekcja ---------- */
  const selectedIds = useMemo(
    () => Object.keys(selected).filter((k) => selected[k]),
    [selected],
  );

  const toggleSelect = useCallback((roleId: string) => {
    setSelected((prev) => {
      const next = { ...prev };
      if (next[roleId]) delete next[roleId];
      else next[roleId] = true;
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => setSelected({}), []);

  /* ---------- Bulk export do JSON ---------- */
  const handleExport = useCallback(async () => {
    if (selectedIds.length === 0 || exporting) return;
    setExporting(true);
    try {
      const manifests: RoleDetail[] = [];
      for (const id of selectedIds) {
        try {
          const d = (await api.getRole(id)) as RoleDetail;
          if (d) manifests.push(d);
        } catch {
          /* pomiń pojedyncze błędy — eksportujemy resztę */
        }
      }
      const payload = {
        kind: "sylion-role-pack",
        version: 1,
        exported_at: new Date().toISOString(),
        count: manifests.length,
        roles: manifests,
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const ts = new Date()
        .toISOString()
        .replace(/[:.]/g, "-")
        .replace(/-(\d{3})Z$/, "Z");
      const a = document.createElement("a");
      a.href = url;
      a.download = `sylion-role-pack-${ts}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }, [selectedIds, exporting]);

  /* ---------- Kopiuj sugestię jako JSON ---------- */
  const handleCopySuggestion = useCallback(async () => {
    if (!suggestion) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(suggestion, null, 2));
      setSuggestionCopied(true);
      setTimeout(() => setSuggestionCopied(false), 1500);
    } catch {
      /* clipboard zablokowany */
    }
  }, [suggestion]);

  /* ---------- Suggester ---------- */
  const handleSuggest = useCallback(async () => {
    const task = taskInput.trim();
    if (!task) return;
    setSuggesting(true);
    setSuggestion(null);
    setSuggestError(null);
    try {
      const resp = (await api.suggestPipeline(task, null)) as SuggestPipelineResponse;
      setSuggestion(resp);
    } catch (err) {
      setSuggestError(
        err instanceof Error ? err.message : "Nie udało się zasugerować pipeline'u.",
      );
    } finally {
      setSuggesting(false);
    }
  }, [taskInput]);

  const steps: PipelineStep[] = useMemo(() => {
    if (!suggestion) return [];
    const arr = (suggestion.steps ?? suggestion.pipeline ?? []) as PipelineStep[];
    return Array.isArray(arr) ? arr : [];
  }, [suggestion]);

  const confidencePct =
    suggestion?.confidence !== undefined
      ? Math.round(Math.max(0, Math.min(1, suggestion.confidence)) * 100)
      : null;

  /* ============================================================
     Render
     ============================================================ */
  return (
    <div className="space-y-5 p-6">
      {/* ===== Nagłówek ===== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-start justify-between gap-3"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Users className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight flex items-center">
              Katalog ról (W7)
              <HelpTip
                text={
                  "40 kreatywnych ról dla pipeline'ów AEIS. Każda rola = manifest z preferowanymi " +
                  "modelami i system_promptem. Domyślna kategoria: Wszystkie."
                }
                side="bottom"
              />
            </h1>
            <p className="text-sm text-muted-foreground">
              Filtruj po kategoriach, otwórz manifest, zaproponuj pipeline.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={scrollToStudio}
            title="Przewiń do filtra umiejętności i kreatora dopasowania zadań (W7→W13)"
          >
            <Filter className="w-3.5 h-3.5 mr-1.5" />
            Studio Doboru Roli (W7→W13)
          </Button>
          <Badge variant="outline" className="font-mono text-[11px]">
            {roles.length} ról
          </Badge>
        </div>
      </motion.div>

      {/* ===== Suggester pipeline'a ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Wand2 className="w-4 h-4 text-sylion-blue" />
            <h3 className="text-sm font-semibold">
              Suggester pipeline&apos;a
            </h3>
            <HelpTip
              text={
                "Wpisz zada?ie po polsku — backend (W13) zaproponuje sekwencję ról i modeli. " +
                "Domyślnie available_models = null, czyli wszystkie skonfigurowane modele."
              }
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase text-muted-foreground tracking-wider flex items-center">
                Opisz zada?ie
                <HelpTip
                  text={
                    "Krótki opis celu. Im bardziej konkretne wymagania (np. 'mobilna aplikacja iOS, MVP w 2 tygodnie'), " +
                    "tym lepsza sugestia."
                  }
                />
              </label>
              <textarea
                rows={3}
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                placeholder="np. Zbuduj landing page dla startupu fintech w 3 dni"
                className="w-full rounded-md border border-border/40 bg-black/30 px-3 py-2 text-xs font-mono outline-none focus:border-sylion-blue/40 resize-none"
              />
              <div className="flex flex-wrap items-center gap-1.5 mt-1">
                <span className="text-[10px] uppercase text-muted-foreground tracking-wider mr-1">
                  Przykłady
                </span>
                {[
                  "Napisz książkę o AI",
                  "Audyt bezpieczeństwa repo",
                  "Stwórz logo dla startupu",
                ].map((ex) => (
                  <Button
                    key={ex}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setTaskInput(ex)}
                    className="h-6 px-2 text-[10px]"
                  >
                    {ex}
                  </Button>
                ))}
              </div>
            </div>
            <div className="flex md:flex-col items-stretch gap-2">
              <Button
                onClick={handleSuggest}
                disabled={suggesting || !taskInput.trim()}
                className="md:w-full"
              >
                {suggesting ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Workflow className="w-3.5 h-3.5 mr-1.5" />
                )}
                Zasugeruj pipeline
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setTaskInput("");
                  setSuggestion(null);
                  setSuggestError(null);
                }}
                disabled={
                  suggesting ||
                  (!taskInput && !suggestion && !suggestError)
                }
                className="md:w-full"
              >
                <X className="w-3.5 h-3.5 mr-1.5" />
                Wyczyść
              </Button>
            </div>
          </div>

          {suggestError && (
            <div className="flex items-center gap-2 text-amber-600 text-xs">
              <AlertTriangle className="w-4 h-4" />
              <span>{suggestError}</span>
            </div>
          )}

          {/* Wynik */}
          {suggestion && (
            <div className="space-y-3">
              <div className="flex justify-end">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleCopySuggestion}
                  className="h-7 px-2 text-[10px]"
                >
                  <Copy className="w-3 h-3 mr-1" />
                  {suggestionCopied ? "Skopiowano" : "Kopiuj jako JSON"}
                </Button>
              </div>
              {/* Flow */}
              {steps.length > 0 ? (
                <div className="flex flex-wrap items-center gap-2">
                  {steps.map((s, i) => (
                    <div key={`${s.role_id}-${i}`} className="flex items-center">
                      <div className="rounded-md border border-sylion-blue/30 bg-sylion-blue/5 px-3 py-2 min-w-[160px]">
                        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                          Krok {s.step ?? i + 1}
                        </div>
                        <div className="text-xs font-semibold mt-0.5">
                          {s.role_name || s.role_id}
                        </div>
                        <div className="text-[10px] font-mono text-muted-foreground">
                          {s.role_id}
                        </div>
                        {s.preferred_model && (
                          <div className="text-[10px] mt-1">
                            <span className="text-muted-foreground">model:</span>{" "}
                            <span className="font-mono">{s.preferred_model}</span>
                          </div>
                        )}
                        {(s.estimated_minutes !== undefined ||
                          s.estimated_cost !== undefined) && (
                          <div className="text-[10px] text-muted-foreground mt-1">
                            {s.estimated_minutes !== undefined && (
                              <>~{s.estimated_minutes}min</>
                            )}
                            {s.estimated_minutes !== undefined &&
                              s.estimated_cost !== undefined &&
                              " · "}
                            {s.estimated_cost !== undefined && (
                              <>${s.estimated_cost.toFixed(2)}</>
                            )}
                          </div>
                        )}
                      </div>
                      {i < steps.length - 1 && (
                        <ChevronRight className="w-4 h-4 text-muted-foreground mx-1 shrink-0" />
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">
                  Backend nie zwrócił kroków pipeline&apos;u.
                </div>
              )}

              {/* Confidence + notes */}
              <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-3 items-start">
                {confidencePct !== null && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-[10px] uppercase text-muted-foreground tracking-wider">
                      Confidence
                      <HelpTip
                        text={
                          "Pewność advisora co do zaproponowanego pipeline'u (0-100%). " +
                          "<60% = sugestia eksperymentalna, wymaga przeglądu."
                        }
                      />
                    </div>
                    <div className="h-2 rounded-full bg-muted/40 overflow-hidden">
                      <div
                        className={cn(
                          "h-full transition-all",
                          confidencePct >= 70
                            ? "bg-sylion-green"
                            : confidencePct >= 50
                              ? "bg-sylion-amber"
                              : "bg-red-400",
                        )}
                        style={{ width: `${confidencePct}%` }}
                      />
                    </div>
                    <div className="text-xs font-mono">{confidencePct}%</div>
                  </div>
                )}
                {Array.isArray(suggestion.notes_pl) &&
                  suggestion.notes_pl.length > 0 && (
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 text-[10px] uppercase text-muted-foreground tracking-wider">
                        Notatki advisora
                        <HelpTip
                          text={
                            "Komentarze advisora do tego konkretnego zadania — np. ostrzeżenia, " +
                            "alternatywy, ograniczenia budżetowe."
                          }
                        />
                      </div>
                      <ul className="text-xs text-muted-foreground list-disc list-inside space-y-0.5">
                        {suggestion.notes_pl.map((note, i) => (
                          <li key={i}>{note}</li>
                        ))}
                      </ul>
                    </div>
                  )}
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* ===== Tabs kategorii ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3">
          <Tabs
            value={activeCategory}
            onValueChange={(v) => setActiveCategory(v as Category | "all")}
          >
            <TabsList className="flex flex-wrap h-auto">
              {CATEGORIES.map((cat) => {
                const Icon = cat.icon;
                return (
                  <TabsTrigger key={cat.id} value={cat.id}>
                    <Icon className="w-3.5 h-3.5 mr-1.5" />
                    {cat.label}
                  </TabsTrigger>
                );
              })}
            </TabsList>
          </Tabs>
        </div>
      </Card>

      {/* ===== Toolbar: search + sort + compact + bulk export + cost legend ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3 space-y-2">
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex-1 min-w-[220px] relative">
              <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Szukaj: nazwa, opis, typowe zadania..."
                className="w-full rounded-md border border-border/40 bg-black/30 pl-7 pr-7 py-1.5 text-xs font-mono outline-none focus:border-sylion-blue/40"
                aria-label="Szukaj ról"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Wyczyść wyszukiwanie"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            <div className="relative">
              <ArrowUpDown className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
              <select
                value={sortKey}
                onChange={(e) => setSortKey(e.target.value as SortKey)}
                className="rounded-md border border-border/40 bg-black/30 pl-7 pr-2 py-1.5 text-xs font-mono outline-none focus:border-sylion-blue/40"
                aria-label="Sortowanie"
              >
                {SORT_OPTIONS.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setCompact((v) => !v)}
              className="h-8 px-2 text-[11px]"
            >
              {compact ? (
                <LayoutGrid className="w-3.5 h-3.5 mr-1.5" />
              ) : (
                <Rows3 className="w-3.5 h-3.5 mr-1.5" />
              )}
              {compact ? "Widok pełny" : "Widok kompaktowy"}
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleExport}
              disabled={selectedIds.length === 0 || exporting}
              className="h-8 px-2 text-[11px]"
            >
              {exporting ? (
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5 mr-1.5" />
              )}
              Eksportuj zaznaczone ({selectedIds.length})
            </Button>
            {selectedIds.length > 0 && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={clearSelection}
                className="h-8 px-2 text-[11px]"
              >
                <X className="w-3.5 h-3.5 mr-1" />
                Odznacz
              </Button>
            )}
            <HelpTip
              text={
                "Wyszukiwanie po nazwie PL/EN, opisie i typowych zadaniach (case-insensitive). " +
                "Sortowanie: alfabetycznie, wg kosztu (niski, średni, wysoki) albo wg liczby modeli preferowanych i zapasowych. " +
                "Eksport: JSON z manifestami zaznaczonych ról. Stan zapisany w localStorage."
              }
            />
          </div>

          {/* Legenda kosztów (klikalna) */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] uppercase text-muted-foreground tracking-wider">
              Koszt
            </span>
            {(["low", "medium", "high"] as const).map((tier) => {
              const active = costFilter === tier;
              return (
                <button
                  key={tier}
                  type="button"
                  onClick={() =>
                    setCostFilter((prev) => (prev === tier ? null : tier))
                  }
                  className={cn(
                    "text-[10px] px-2 py-0.5 rounded-full border font-mono transition-colors",
                    costPillStyle(tier),
                    active
                      ? "ring-2 ring-offset-1 ring-offset-[#0f1629] ring-sylion-blue/40"
                      : "opacity-80 hover:opacity-100",
                  )}
                  aria-pressed={active}
                >
                  {COST_TIER_LABEL[tier]} · {costCounts[tier]}
                </button>
              );
            })}
            {costFilter && (
              <button
                type="button"
                onClick={() => setCostFilter(null)}
                className="text-[10px] text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
              >
                wyczyść filtr
              </button>
            )}
            {search && (
              <span className="ml-auto text-[10px] text-muted-foreground">
                Dopasowań: <span className="font-mono">{filtered.length}</span>
              </span>
            )}
          </div>
        </div>
      </Card>

      {/* ===== Lista ról ===== */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-sylion-blue" />
          <h3 className="text-sm font-semibold">
            {activeCategory === "all"
              ? "Wszystkie role"
              : `Kategoria: ${CATEGORIES.find((c) => c.id === activeCategory)?.label}`}
          </h3>
          <HelpTip text={CATEGORY_HELP[activeCategory] || "Lista ról."} />
          <Badge variant="outline" className="font-mono text-[10px]">
            {filtered.length}
          </Badge>
        </div>

        {error && (
          <Card className="border-amber-500/30 bg-amber-500/5">
            <div className="p-3 flex items-center gap-2 text-amber-600">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-xs">{error}</span>
            </div>
          </Card>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
              <div
                key={i}
                className="h-24 bg-muted/30 animate-pulse rounded-lg border border-border/30"
              />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <Card className="bg-[#0f1629] border-sylion-border">
            <div className="p-8 text-center text-xs text-muted-foreground">
              Brak ról w tej kategorii.
            </div>
          </Card>
        ) : (
          <div
            className={cn(
              "grid gap-3",
              compact
                ? "grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 2xl:grid-cols-6"
                : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4",
            )}
          >
            {filtered.map((role) => {
              const name = role.name_pl || role.name || role.role_id;
              const desc = role.description_pl || role.description || "";
              const isSelected = !!selected[role.role_id];
              return (
                <Card
                  key={role.role_id}
                  className={cn(
                    "bg-[#0f1629] border-sylion-border transition-colors h-full relative",
                    isSelected
                      ? "border-sylion-blue/60 ring-1 ring-sylion-blue/30"
                      : "hover:border-sylion-blue/40",
                  )}
                >
                  <label
                    className="absolute top-2 left-2 z-10 inline-flex items-center cursor-pointer"
                    onClick={(e) => e.stopPropagation()}
                    title="Zaznacz do eksportu"
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(role.role_id)}
                      className="w-3.5 h-3.5 accent-sylion-blue cursor-pointer"
                      aria-label={`Zaznacz ${name}`}
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setOpenRoleId(role.role_id);
                      setPromptCollapsed(true);
                    }}
                    className="text-left w-full"
                  >
                    <div className={cn("space-y-2", compact ? "p-2 pl-7" : "p-3 pl-8")}>
                      <div className="flex items-start justify-between gap-2">
                        <div className={cn("font-semibold", compact ? "text-[11px] line-clamp-1" : "text-xs")}>
                          {name}
                        </div>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[9px] font-mono",
                            categoryColor(String(role.category)),
                          )}
                        >
                          {String(role.category)}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-1">
                        {role.cost_profile && (
                          <span
                            className={cn(
                              "text-[9px] px-1.5 py-0.5 rounded-full border font-mono",
                              costPillStyle(role.cost_profile),
                            )}
                          >
                            {role.cost_profile}
                          </span>
                        )}
                        {!compact && (
                          <span className="text-[10px] text-muted-foreground font-mono truncate">
                            {role.role_id}
                          </span>
                        )}
                      </div>
                      {!compact && (
                        <p className="text-[11px] text-muted-foreground line-clamp-2">
                          {desc || "—"}
                        </p>
                      )}
                    </div>
                  </button>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* ===== Studio Doboru Roli (W7→W13) — capability filter + match-task wizard ===== */}
      <div ref={studioRef} className="space-y-4 pt-2">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="flex items-center gap-3"
        >
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Filter className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h2 className="text-lg font-semibold tracking-tight flex items-center">
              Studio Doboru Roli (W7→W13)
              <HelpTip
                text={
                  "Filtr po umiejętnościach i kreator dopasowania zadań. Backend: " +
                  "POST /api/v1/role-catalog/match-task. Obecnie działa przez nakładanie tagów umiejętności."
                }
                side="bottom"
              />
            </h2>
            <p className="text-sm text-muted-foreground">
              Wskaż wymagane umiejętności + minimalny seniority — system zwróci najlepiej dopasowane role.
            </p>
          </div>
        </motion.div>

        {/* Status banner */}
        <Card className="border-sylion-blue/30 bg-sylion-blue/5">
          <div className="p-3 flex items-start gap-2 text-xs">
            <Info className="w-4 h-4 text-sylion-blue mt-0.5 shrink-0" />
            <div className="space-y-1">
              <div>
                <span className="font-semibold text-sylion-blue">Status:</span>{" "}
                matcher punktuje role po nakładaniu tagów{" "}
                <span className="font-mono">umiejętności</span> (+5.0 za umiejętność,
                +1.0 za słowo kluczowe w opisie zadania) i odrzuca role poniżej
                wskazanego poziomu seniority.
              </div>
              <div className="text-muted-foreground">
                G1 doda wyszukiwanie semantyczne przez{" "}
                <span className="font-mono">nomic-embed-text</span> (wektory Ollama) —
                zamiast wyłącznie nakładania tagów dopasowanie pójdzie po semantycznej
                bliskości opisu zadania. G2 doda reranking LLM najlepszych kandydatów.
              </div>
            </div>
          </div>
        </Card>

        {/* Filtruj po umiejętnościach */}
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-4 space-y-4">
            <div className="flex items-center gap-2">
              <Tags className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-sm font-semibold">Filtruj po umiejętnościach</h3>
              <HelpTip
                text={
                  "Wybór wielu umiejętności. Każda opcja pokazuje nazwę i liczbę ról " +
                  "z tą umiejętnością. Filtr seniority ustawia minimalny poziom; „dowolny” oznacza brak filtra."
                }
              />
              <Badge variant="outline" className="font-mono text-[10px] ml-auto">
                {capabilities.length} umiejętności
              </Badge>
            </div>

            {capsError && (
              <div className="flex items-center gap-2 text-amber-600 text-xs">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{capsError}</span>
              </div>
            )}

            {/* Search po capabilities */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={capSearch}
                onChange={(e) => setCapSearch(e.target.value)}
                placeholder="Szukaj umiejętności (np. python, sql, design)..."
                className="w-full rounded-md border border-border/40 bg-black/30 pl-7 pr-7 py-1.5 text-xs font-mono outline-none focus:border-sylion-blue/40"
                aria-label="Szukaj umiejętności"
              />
              {capSearch && (
                <button
                  type="button"
                  onClick={() => setCapSearch("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Wyczyść"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Multi-select capability chips */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[10px] uppercase text-muted-foreground tracking-wider">
                <span>Wybrane umiejętności</span>
                <span className="font-mono">{selectedCaps.length}</span>
              </div>
              {capsLoading ? (
                <div className="flex flex-wrap gap-1.5">
                  {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                    <div
                      key={i}
                      className="h-6 w-16 bg-muted/30 animate-pulse rounded-full border border-border/30"
                    />
                  ))}
                </div>
              ) : filteredCapabilities.length === 0 ? (
                <div className="text-[11px] text-muted-foreground italic">
                  Brak umiejętności w taksonomii (lub żadna nie pasuje do filtra).
                </div>
              ) : (
                <div className="flex flex-wrap gap-1.5 max-h-[220px] overflow-auto pr-1 border border-border/20 rounded-md p-2 bg-black/20">
                  {filteredCapabilities.map((cap) => {
                    const active = selectedCaps.includes(cap.id);
                    return (
                      <button
                        key={cap.id}
                        type="button"
                        onClick={() => toggleCapability(cap.id)}
                        className={cn(
                          "text-[10px] px-2 py-0.5 rounded-full border font-mono transition-colors",
                          active
                            ? "border-sylion-blue/60 bg-sylion-blue/20 text-sylion-blue ring-1 ring-sylion-blue/40"
                            : "border-border/40 bg-muted/20 text-muted-foreground hover:bg-muted/40 hover:text-foreground",
                        )}
                        aria-pressed={active}
                        title={`${cap.id} — ${cap.role_count} rola/role`}
                      >
                        {cap.id}{" "}
                        <span className="opacity-70">({cap.role_count})</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Skill level radio */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-[10px] uppercase text-muted-foreground tracking-wider">
                <span>Minimalny seniority</span>
                <HelpTip
                  text={
                    "any = bez filtra (default). junior+/mid+/senior+/principal — odrzuca role poniżej."
                  }
                />
              </div>
              <div className="flex flex-wrap gap-1.5">
                {SKILL_LEVELS.map((lvl) => {
                  const active = skillLevelFilter === lvl.id;
                  return (
                    <label
                      key={lvl.id}
                      className={cn(
                        "inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-md border cursor-pointer transition-colors",
                        active
                          ? "border-sylion-blue/60 bg-sylion-blue/10 text-sylion-blue"
                          : "border-border/40 bg-muted/10 text-muted-foreground hover:bg-muted/30",
                      )}
                      title={lvl.help}
                    >
                      <input
                        type="radio"
                        name="skill-level"
                        value={lvl.id}
                        checked={active}
                        onChange={() => setSkillLevelFilter(lvl.id)}
                        className="w-3 h-3 accent-sylion-blue"
                      />
                      <span className="font-mono">{lvl.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Akcje */}
            <div className="flex items-center justify-end gap-2 pt-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={clearCapabilities}
                disabled={
                  matchLoading ||
                  (selectedCaps.length === 0 && !matchResp && !matchError)
                }
              >
                <X className="w-3.5 h-3.5 mr-1.5" />
                Wyczyść
              </Button>
              <Button
                size="sm"
                onClick={() => void handleMatchTask()}
                disabled={matchLoading}
                title={
                  selectedCaps.length === 0
                    ? "Brak wybranych umiejętności — wynik pokaże same role spełniające minimalny poziom seniority."
                    : "Dopasuj role po wybranych umiejętnościach"
                }
              >
                {matchLoading ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5 mr-1.5" />
                )}
                Pokaż dopasowane role
              </Button>
            </div>

            <div className="text-[10px] text-muted-foreground font-mono">
              Wywołanie: POST /api/v1/role-catalog/match-task
            </div>
          </div>
        </Card>

        {/* Match error */}
        {matchError && (
          <Card className="border-amber-500/30 bg-amber-500/5">
            <div className="p-3 flex items-center justify-between gap-2 text-amber-600">
              <div className="flex items-center gap-2 text-xs">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{matchError}</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleMatchTask()}
                disabled={matchLoading}
              >
                Ponów
              </Button>
            </div>
          </Card>
        )}

        {/* Match results */}
        {matchResp && (
          <MatchResultsPanel
            response={matchResp}
            onPick={handlePickRole}
          />
        )}
      </div>

      {/* ===== Toast po wyborze roli ===== */}
      {pickedToast && (
        <div
          className="fixed bottom-6 right-6 z-50 max-w-sm"
          role="status"
          aria-live="polite"
        >
          <Card className="border-sylion-blue/40 bg-sylion-blue/10 shadow-xl">
            <div className="p-3 flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-sylion-blue mt-0.5 shrink-0" />
              <div className="flex-1 text-xs leading-relaxed">{pickedToast}</div>
              <button
                type="button"
                onClick={() => setPickedToast(null)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Zamknij toast"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </Card>
        </div>
      )}

      {pickError && (
        <div
          className="fixed bottom-6 right-6 z-50 max-w-sm"
          role="alert"
          aria-live="assertive"
        >
          <Card className="border-red-500/40 bg-red-500/10 shadow-xl">
            <div className="p-3 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <div className="flex-1 text-xs leading-relaxed">{pickError}</div>
              <button
                type="button"
                onClick={() => setPickError(null)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Zamknij błąd"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </Card>
        </div>
      )}

      {/* ===== Modal szczegółów roli ===== */}
      <Dialog
        open={openRoleId !== null}
        onOpenChange={(value) => {
          if (!value) {
            setOpenRoleId(null);
            setOpenRole(null);
            setPromptCollapsed(true);
          }
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          {openLoading ? (
            <div className="py-12 flex items-center justify-center text-xs text-muted-foreground">
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Ładowanie manifestu...
            </div>
          ) : openRole ? (
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-2">
                <div className="space-y-1">
                  <DialogTitle className="text-base">
                    {openRole.name_pl || openRole.name || openRole.role_id}
                  </DialogTitle>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[10px] font-mono",
                        categoryColor(String(openRole.category)),
                      )}
                    >
                      {String(openRole.category)}
                    </Badge>
                    {openRole.cost_profile && (
                      <span
                        className={cn(
                          "text-[10px] px-2 py-0.5 rounded-full border font-mono",
                          costPillStyle(openRole.cost_profile),
                        )}
                      >
                        {openRole.cost_profile}
                      </span>
                    )}
                    {openRole.estimated_minutes !== undefined && (
                      <Badge variant="outline" className="text-[10px] font-mono">
                        ~{openRole.estimated_minutes}min
                      </Badge>
                    )}
                    <span className="text-[10px] text-muted-foreground font-mono">
                      {openRole.role_id}
                    </span>
                  </div>
                </div>
              </div>

              {(openRole.description_pl || openRole.description) && (
                <p className="text-xs text-muted-foreground">
                  {openRole.description_pl || openRole.description}
                </p>
              )}

              {Array.isArray(openRole.typical_tasks) &&
                openRole.typical_tasks.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-semibold">Typowe zadania</h4>
                      <HelpTip
                        text={
                          "Lista zadań które ta rola wykonuje najczęściej. Pomaga ocenić czy " +
                          "rola pasuje do Twojego use-case'u."
                        }
                      />
                    </div>
                    <ul className="text-xs text-muted-foreground list-disc list-inside space-y-0.5">
                      {openRole.typical_tasks.map((t, i) => (
                        <li key={i}>{t}</li>
                      ))}
                    </ul>
                  </div>
                )}

              {Array.isArray(openRole.preferred_models) &&
                openRole.preferred_models.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-semibold">Preferowane modele</h4>
                      <HelpTip
                        text={
                          "Modele, które advisor (W13) wybierze w pierwszej kolejności dla tej roli. " +
                          "Domyślnie pierwszy dostępny model z listy."
                        }
                      />
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {openRole.preferred_models.map((m) => (
                        <Badge
                          key={m}
                          variant="outline"
                          className="font-mono text-[10px]"
                        >
                          {m}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

              {Array.isArray(openRole.fallback_models) &&
                openRole.fallback_models.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-semibold">Modele fallback</h4>
                      <HelpTip
                        text={
                          "Modele zapasowe — używane gdy preferowane są niedostępne lub przekraczają budżet."
                        }
                      />
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {openRole.fallback_models.map((m) => (
                        <Badge
                          key={m}
                          variant="outline"
                          className="font-mono text-[10px] opacity-80"
                        >
                          {m}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

              {openRole.system_prompt && (
                <div className="space-y-1.5">
                  <button
                    type="button"
                    onClick={() => setPromptCollapsed((v) => !v)}
                    className="flex items-center gap-2 text-xs font-semibold hover:text-sylion-blue transition-colors"
                  >
                    {promptCollapsed ? (
                      <ChevronRight className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                    System prompt
                    <HelpTip
                      text={
                        "Pełny system_prompt roli — instrukcje dla modelu. Nie zawiera sekretów ani API kluczy."
                      }
                    />
                  </button>
                  {!promptCollapsed && (
                    <pre className="text-[11px] leading-relaxed font-mono bg-black/40 rounded-md p-3 overflow-auto max-h-[40vh] border border-border/30 whitespace-pre-wrap">
                      {openRole.system_prompt}
                    </pre>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="py-12 text-center text-xs text-muted-foreground">
              Nie udało się załadować manifestu roli.
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ============================================================
   MatchResultsPanel — wyniki match-task wizard
   ============================================================ */

function MatchResultsPanel({
  response,
  onPick,
}: {
  response: MatchTaskResponse;
  onPick: (role: MatchTaskRoleSummary) => void;
}) {
  const badge = methodBadge(response.engine);
  const maxScore = useMemo(() => {
    if (!response.matches.length) return 0;
    return Math.max(...response.matches.map((m) => m.score));
  }, [response.matches]);

  if (!response.matches.length) {
    return (
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-8 flex flex-col items-center justify-center text-muted-foreground">
          <Sparkles className="w-7 h-7 mb-2 opacity-40" />
          <p className="text-xs">
            Brak ról dopasowanych do wybranych umiejętności / seniority.
          </p>
          <p className="text-[10px] mt-1 opacity-60">
            Spróbuj zdjąć filtr seniority lub wybierz mniej wymagające umiejętności.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-sylion-blue" />
          <h3 className="text-sm font-semibold">Dopasowane role</h3>
          <Badge variant="outline" className="font-mono text-[10px]">
            {response.matches.length}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className={cn("font-mono text-[10px]", badge.className)}
            title={badge.tooltip}
          >
            metoda: {badge.label}
          </Badge>
          {response.skill_level && (
            <Badge
              variant="outline"
              className={cn(
                "font-mono text-[10px]",
                skillLevelPillStyle(response.skill_level),
              )}
              title={`poziom seniority: ${response.skill_level}`}
            >
              {response.skill_level}
            </Badge>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {response.matches.map((m, i) => (
          <MatchRoleCard
            key={`${m.role.id}-${i}`}
            match={m}
            maxScore={maxScore}
            onPick={() => onPick(m.role)}
          />
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   MatchRoleCard — pojedyncza karta wyniku
   ============================================================ */

function MatchRoleCard({
  match,
  maxScore,
  onPick,
}: {
  match: MatchTaskHit;
  maxScore: number;
  onPick: () => void;
}) {
  const role = match.role;
  const display = role.name_pl || role.name_en || role.id;
  const scorePct = maxScore > 0 ? Math.max(0, Math.min(100, (match.score / maxScore) * 100)) : 0;

  return (
    <Card className="bg-[#0f1629] border-sylion-border flex flex-col h-full">
      <div className="p-4 space-y-3 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Users className="w-4 h-4 text-sylion-blue shrink-0" />
            <h4 className="text-sm font-semibold truncate" title={display}>
              {display}
            </h4>
          </div>
          {role.skill_level && (
            <Badge
              variant="outline"
              className={cn(
                "font-mono text-[10px] shrink-0",
                skillLevelPillStyle(role.skill_level),
              )}
            >
              {role.skill_level}
            </Badge>
          )}
        </div>

        {/* Horizontal score progress */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px] uppercase text-muted-foreground tracking-wider">
            <span>Wynik dopasowania</span>
            <span className="font-mono">{match.score.toFixed(2)}</span>
          </div>
          <div
            className="h-1.5 w-full rounded-full bg-sylion-border/40 overflow-hidden"
            role="progressbar"
            aria-valuenow={scorePct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Wynik dopasowania ${match.score.toFixed(2)}`}
          >
            <div
              className="h-full bg-sylion-blue transition-[width] duration-500"
              style={{ width: `${scorePct}%` }}
            />
          </div>
        </div>

        {/* Metadata badges */}
        <div className="flex flex-wrap items-center gap-1">
          {role.category && (
            <Badge
              variant="outline"
              className={cn(
                "text-[9px] font-mono",
                categoryColor(String(role.category)),
              )}
            >
              {String(role.category)}
            </Badge>
          )}
          {role.cost_profile && (
            <span
              className={cn(
                "text-[9px] px-1.5 py-0.5 rounded-full border font-mono",
                costPillStyle(role.cost_profile),
              )}
            >
              {role.cost_profile}
            </span>
          )}
          <span className="text-[10px] text-muted-foreground font-mono ml-auto truncate">
            {role.id}
          </span>
        </div>

        {/* Matched capabilities */}
        {match.matched_capabilities.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-[10px] uppercase text-muted-foreground tracking-wider">
              <CheckCircle2 className="w-3 h-3 text-sylion-green" />
              <span>Pasujące umiejętności ({match.matched_capabilities.length})</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {match.matched_capabilities.map((c) => (
                <Badge
                  key={c}
                  variant="outline"
                  className="font-mono text-[10px] border-sylion-green/40 bg-sylion-green/10 text-sylion-green"
                >
                  {c}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* All role capabilities (informacyjnie) */}
        {Array.isArray(role.capabilities) && role.capabilities.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-[10px] uppercase text-muted-foreground tracking-wider">
              <Tags className="w-3 h-3" />
              <span>Wszystkie umiejętności</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {role.capabilities.map((c) => {
                const matched = match.matched_capabilities.includes(c);
                return (
                  <Badge
                    key={c}
                    variant="outline"
                    className={cn(
                      "font-mono text-[10px]",
                      matched
                        ? "border-sylion-green/40 bg-sylion-green/10 text-sylion-green"
                        : "border-border/40 bg-muted/20 text-muted-foreground",
                    )}
                  >
                    {c}
                  </Badge>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="p-3 border-t border-border/30 flex items-center justify-between gap-2">
        <span className="text-[10px] text-muted-foreground">
          Wybierz role i zapisz decyzję w rejestrze pipeline
        </span>
        <Button variant="default" size="sm" onClick={onPick}>
          <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
          Wybierz
        </Button>
      </div>
    </Card>
  );
}
