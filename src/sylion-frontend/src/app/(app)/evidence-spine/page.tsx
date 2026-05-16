"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Link2,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Hash,
  ArrowDown,
  Search,
  X,
  FileCheck,
  Download,
  ArrowRight,
  Shield,
  Clock,
  WifiOff,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

/* ---------- types ---------- */

interface SpineEntry {
  entry_id: string;
  sequence: number;
  entry_hash: string;
  prev_hash: string;
  entry_type: "decision" | "gate_evaluation" | "code_change" | "cascade" | "chain_init" | "audit";
  decision_id: string;
  content_hash: string;
  evidence_pack: Record<string, unknown>;
  module_states_hash: string;
  metadata: Record<string, unknown>;
  timestamp: string;
  valid: boolean;
}

interface SpineStats {
  total_entries: number;
  chain_valid: boolean;
  last_hash: string;
  last_sequence: number;
}

interface VerificationResult {
  valid: boolean;
  total_entries: number;
  tampered_count: number;
  broken_at: string | null;
}

/* ---------- helpers ---------- */

const ENTRY_TYPE_CONFIG: Record<string, { color: string; bg: string; border: string; dot: string }> = {
  decision:         { color: "text-sylion-blue", bg: "bg-sylion-blue/10", border: "border-sylion-blue/30", dot: "bg-sylion-blue" },
  gate_evaluation:  { color: "text-sylion-green", bg: "bg-sylion-green/10", border: "border-sylion-green/30", dot: "bg-sylion-green" },
  code_change:      { color: "text-sylion-amber", bg: "bg-sylion-amber/10", border: "border-sylion-amber/30", dot: "bg-sylion-amber" },
  cascade:          { color: "text-sylion-red", bg: "bg-sylion-red/10", border: "border-sylion-red/30", dot: "bg-sylion-red" },
  chain_init:       { color: "text-primary", bg: "bg-primary/10", border: "border-primary/30", dot: "bg-primary" },
  audit:            { color: "text-muted-foreground", bg: "bg-muted/20", border: "border-muted/30", dot: "bg-muted-foreground" },
};

function getTypeConfig(type: string) {
  return ENTRY_TYPE_CONFIG[type] || ENTRY_TYPE_CONFIG.audit;
}

function shortHash(hash: string): string {
  if (!hash || hash === "0".repeat(64)) return "GENEZA";
  return hash.slice(0, 12);
}

function formatTimestamp(iso: string): string {
  if (!iso) return "--";
  return new Date(iso).toLocaleString();
}

function timeAgo(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "przed chwilą";
  if (mins < 60) return `${mins}m temu`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h temu`;
  const days = Math.floor(hrs / 24);
  return `${days}d temu`;
}

const ENTRY_TYPES = ["all", "decision", "gate_evaluation", "code_change", "cascade", "chain_init", "audit"];

/* ---------- main page ---------- */

export default function EvidenceSpinePage() {
  const { data: health } = useHealth();
  const backendLive = health.status === "ok";

  const [entries, setEntries] = useState<SpineEntry[]>([]);
  const [stats, setStats] = useState<SpineStats | null>(null);
  const [verification, setVerification] = useState<VerificationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [typeFilter, setTypeFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  // Fetch data
  useEffect(() => {
    let cancelled = false;
    async function fetchData() {
      setLoading(true);
      try {
        const [entriesRes, statsRes] = await Promise.all([
          api.getSpineEntries(),
          api.getSpineStats(),
        ]);
        if (!cancelled) {
          setEntries(entriesRes.entries || []);
          setStats(statsRes);
        }
      } catch {
        if (!cancelled) {
          setEntries([]);
          setStats(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    if (backendLive) fetchData();
    else {
      setEntries([]);
      setStats(null);
      setLoading(false);
    }
    return () => { cancelled = true; };
  }, [backendLive]);

  // Compute chain validity
  const chainValid = useMemo(() => {
    if (stats) return stats.chain_valid;
    return entries.every(e => e.valid);
  }, [stats, entries]);

  const tamperedCount = useMemo(() => entries.filter(e => !e.valid).length, [entries]);

  // Filtered entries
  const filteredEntries = useMemo(() => {
    return [...entries].reverse().filter(e => {
      if (typeFilter !== "all" && e.entry_type !== typeFilter) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const desc = typeof e.evidence_pack?.description === "string" ? e.evidence_pack.description : "";
        return (
          desc.toLowerCase().includes(q) ||
          e.entry_type.toLowerCase().includes(q) ||
          e.decision_id.toLowerCase().includes(q) ||
          e.entry_hash.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [entries, typeFilter, searchQuery]);

  // Verification handler
  const handleVerify = useCallback(async () => {
    if (!backendLive) return;
    setVerifying(true);
    try {
      const result = await api.verifySpineChain();
      setVerification(result);
    } catch {
      setVerification({ valid: false, total_entries: entries.length, tampered_count: 0, broken_at: null });
    } finally {
      setVerifying(false);
    }
  }, [backendLive, entries.length]);

  // Export handler
  const handleExport = useCallback(() => {
    const blob = new Blob([JSON.stringify({ entries, stats }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "evidence-spine-chain.json";
    a.click();
    URL.revokeObjectURL(url);
  }, [entries, stats]);

  const clearFilters = useCallback(() => {
    setTypeFilter("all");
    setSearchQuery("");
  }, []);

  const hasActiveFilters = typeFilter !== "all" || searchQuery !== "";

  /* ---------- loading skeleton ---------- */
  if (!mounted || loading) {
    return (
      <div className="space-y-5">
        <div className="h-8 w-48 bg-muted animate-pulse rounded" />
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => (
            <Card key={i} className="p-4 bg-[#0f1629] border-sylion-border">
              <div className="h-3 w-20 bg-muted animate-pulse rounded mb-2" />
              <div className="h-7 w-12 bg-muted animate-pulse rounded" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  /* ---------- rendered page ---------- */
  return (
    <div className="space-y-5">
      {/* ========== HEADER ========== */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 flex items-center justify-center">
            <Link2 className="w-5 h-5 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Kręgosłup dowodowy
              <HelpTip text="Hash-chained ścieżka audytu wszystkich kluczowych zdarzeń (decyzję, oceny bramek, zmiany kodu, kaskady, audyty). Każdy wpis powiązany z poprzednim przez prev_hash. Manipulacja wpisem złamie łańcuch." />
            </h1>
            <p className="text-xs text-muted-foreground">
              Łańcuch hashy ścieżki audytu decyzji
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Chain status badge */}
          {entries.length > 0 && (chainValid ? (
            <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green bg-sylion-green/5">
              <ShieldCheck className="w-3 h-3 mr-1" />
              ŁAŃCUCH SPÓJNY
            </Badge>
          ) : (
            <Badge variant="outline" className="text-[10px] border-sylion-red/30 text-sylion-red bg-sylion-red/5">
              <ShieldAlert className="w-3 h-3 mr-1" />
              ŁAŃCUCH ZŁAMANY
            </Badge>
          ))}
          <Badge variant="outline" className="text-[10px] border-border text-muted-foreground">
            {entries.length} wpisów
          </Badge>
          <Button variant="outline" size="sm" onClick={handleVerify} disabled={verifying || !backendLive}>
            <RefreshCw className={cn("w-3.5 h-3.5 mr-1.5", verifying && "animate-spin")} />
            {verifying ? "Weryfikuję..." : "Zweryfikuj łańcuch"}
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport} disabled={!backendLive || entries.length === 0}>
            <Download className="w-3.5 h-3.5 mr-1.5" />
            Eksport
          </Button>
        </div>
      </div>

      {/* ========== BACKEND NOT REACHABLE ========== */}
      {!backendLive && (
        <Card className="p-6 bg-[#0f1629] border-sylion-border">
          <div className="flex flex-col items-center justify-center py-6 text-center">
            <WifiOff className="w-8 h-8 text-sylion-red/60 mb-3" />
            <p className="text-sm text-sylion-red/80 font-medium">Backend niedostępny</p>
            <p className="text-xs text-muted-foreground mt-1">
              Uruchom backend: <code className="text-primary">python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010</code>
            </p>
          </div>
        </Card>
      )}

      {/* ========== STATS ROW ========== */}
      {backendLive && (
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-3 bg-[#0f1629] border-sylion-border">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
            Łącznie wpisów
            <HelpTip text="Liczba wszystkich wpisów w łańcuchu kręgosłupa dowodowego od genezy." />
          </p>
          <p className="text-2xl font-semibold mt-0.5">{stats?.total_entries ?? entries.length}</p>
        </Card>
        <Card className="p-3 bg-[#0f1629] border-sylion-border">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
            Łańcuch spójny
            <HelpTip text="Czy ostatnia weryfikacja wykazała pełną spójność hashy. Manipulacja jakimkolwiek wpisem złamie łańcuch." />
          </p>
          <div className="flex items-center gap-1.5 mt-1">
            {chainValid ? (
              <CheckCircle2 className="w-5 h-5 text-sylion-green" />
            ) : (
              <XCircle className="w-5 h-5 text-sylion-red" />
            )}
            <span className={cn("text-lg font-semibold", chainValid ? "text-sylion-green" : "text-sylion-red")}>
              {chainValid ? "Tak" : "Nie"}
            </span>
          </div>
        </Card>
        <Card className="p-3 bg-[#0f1629] border-sylion-border">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
            Hash ostatniego wpisu
            <HelpTip text="Skrócony hash najnowszego wpisu w łańcuchu — kotwica dla weryfikacji integralności." />
          </p>
          <p className="text-sm font-mono mt-1 text-muted-foreground">
            {shortHash(stats?.last_hash ?? entries[entries.length - 1]?.entry_hash ?? "")}
          </p>
        </Card>
        <Card className="p-3 bg-[#0f1629] border-sylion-border">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
            Liczba modyfikacji
            <HelpTip text="Liczba wpisów, których hash nie zgadza się z zawartością — sygnał manipulacji." />
          </p>
          <p className={cn("text-2xl font-semibold mt-0.5", tamperedCount === 0 ? "text-sylion-green" : "text-sylion-red")}>
            {tamperedCount}
          </p>
        </Card>
      </div>
      )}

      {/* ========== MAIN CONTENT: 3 SECTIONS ========== */}
      {backendLive && (
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">

        {/* ---- SECTION 1: CHAIN VISUALIZATION ---- */}
        <Card className="p-5 bg-[#0f1629] border-sylion-border xl:col-span-1">
          <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Link2 className="w-4 h-4 text-sylion-blue" />
            Wizualizacja łańcucha
            <HelpTip text="Sekwencyjny widok wpisów łańcucha — każdy z numerem, hashem, typem i flagą walidacji. Kliknij wpis, aby zobaczyć szczegóły." />
          </h2>
          <div className="space-y-0 max-h-[600px] overflow-y-auto pr-1">
            {entries.map((entry, idx) => {
              const tc = getTypeConfig(entry.entry_type);
              const isExpanded = expandedEntry === entry.entry_id;
              return (
                <div key={entry.entry_id}>
                  <motion.div
                    className={cn(
                      "relative flex items-center gap-2 p-2.5 rounded-lg cursor-pointer transition-colors border",
                      isExpanded ? tc.bg + " " + tc.border : "hover:bg-muted/30 border-transparent"
                    )}
                    onClick={() => setExpandedEntry(isExpanded ? null : entry.entry_id)}
                    whileHover={{ x: 2 }}
                    transition={{ duration: 0.15 }}
                  >
                    {/* Sequence badge */}
                    <div className={cn(
                      "w-8 h-8 rounded-md flex items-center justify-center text-[10px] font-bold shrink-0",
                      tc.bg, tc.color
                    )}>
                      #{entry.sequence}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[9px] font-mono text-muted-foreground truncate">
                          {shortHash(entry.entry_hash)}
                        </span>
                      </div>
                      <Badge variant="outline" className={cn("text-[8px] mt-0.5 border", tc.border, tc.color)}>
                        <span className={cn("w-1.5 h-1.5 rounded-full mr-1 inline-block", tc.dot)} />
                        {entry.entry_type.replace("_", " ")}
                      </Badge>
                    </div>
                    {/* Validity indicator */}
                    {entry.valid ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-sylion-green shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-sylion-red shrink-0" />
                    )}
                  </motion.div>
                  {/* Expanded details */}
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="ml-4 p-3 bg-muted/10 rounded-lg text-[10px] space-y-2 mb-2 border border-border/30">
                          <div>
                            <span className="text-muted-foreground uppercase tracking-wider">Entry Hash</span>
                            <p className="font-mono break-all">{entry.entry_hash}</p>
                          </div>
                          <div>
                            <span className="text-muted-foreground uppercase tracking-wider">Prev Hash</span>
                            <p className="font-mono break-all">{shortHash(entry.prev_hash)}</p>
                          </div>
                          {entry.decision_id && (
                            <div>
                              <span className="text-muted-foreground uppercase tracking-wider">Decision</span>
                              <p className="font-mono">{entry.decision_id}</p>
                            </div>
                          )}
                          <div>
                            <span className="text-muted-foreground uppercase tracking-wider">Content Hash</span>
                            <p className="font-mono">{shortHash(entry.content_hash)}</p>
                          </div>
                          <div>
                            <span className="text-muted-foreground uppercase tracking-wider">Time</span>
                            <p>{formatTimestamp(entry.timestamp)}</p>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                  {/* Chain connector arrow */}
                  {idx < entries.length - 1 && (
                    <div className="flex items-center justify-center py-0.5">
                      <div className="w-px h-4 bg-border" />
                      <ArrowDown className="w-3 h-3 text-muted-foreground/50 -mt-1 -mb-1" />
                      <div className="w-px h-4 bg-border" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        {/* ---- SECTION 2: ENTRY LIST ---- */}
        <Card className="p-5 bg-[#0f1629] border-sylion-border xl:col-span-1">
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <FileCheck className="w-4 h-4 text-sylion-green" />
            Lista wpisów
            <HelpTip text="Pełna lista wpisów łańcucha z filtrami po typie i wyszukiwaniem. Każdy wpis można rozwinąć dla szczegółów." />
          </h2>
          {/* Filter row */}
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <div className="relative flex-1 min-w-[140px]">
              <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Szukaj wpisów..."
                className="w-full h-7 rounded-md border border-sylion-border bg-background pl-7 pr-2 text-xs text-foreground placeholder:text-muted-foreground/50"
              />
            </div>
            <select
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value)}
              className="h-7 rounded-md border border-sylion-border bg-background px-2 text-xs text-foreground"
            >
              {ENTRY_TYPES.map(t => (
                <option key={t} value={t}>{t === "all" ? "Wszystkie typy" : t.replace("_", " ")}</option>
              ))}
            </select>
            {hasActiveFilters && (
              <button onClick={clearFilters} className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors">
                <X className="w-3 h-3" />
                Wyczyść
              </button>
            )}
          </div>
          {hasActiveFilters && (
            <p className="text-[10px] text-muted-foreground mb-2">
              {filteredEntries.length} z {entries.length} wpisów
            </p>
          )}
          {/* Entry list */}
          <div className="space-y-2 max-h-[560px] overflow-y-auto pr-1">
            {filteredEntries.map(entry => {
              const tc = getTypeConfig(entry.entry_type);
              const isExpanded = expandedEntry === entry.entry_id;
              return (
                <div
                  key={entry.entry_id}
                  className={cn(
                    "p-3 rounded-lg border transition-all cursor-pointer",
                    entry.valid
                      ? "border-border/50 hover:border-border bg-[#0a0f1e]"
                      : "border-sylion-red/30 bg-sylion-red/5"
                  )}
                  onClick={() => setExpandedEntry(isExpanded ? null : entry.entry_id)}
                >
                  {/* Top row */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-mono text-muted-foreground bg-muted/30 px-1.5 py-0.5 rounded">
                      #{entry.sequence}
                    </span>
                    <Badge variant="outline" className={cn("text-[8px] border", tc.border, tc.color)}>
                      <span className={cn("w-1.5 h-1.5 rounded-full mr-1 inline-block", tc.dot)} />
                      {entry.entry_type.replace("_", " ")}
                    </Badge>
                    {entry.decision_id && (
                      <span className="text-[9px] font-mono text-sylion-blue hover:underline">
                        {entry.decision_id}
                      </span>
                    )}
                    <span className="text-[10px] text-muted-foreground ml-auto flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {timeAgo(entry.timestamp)}
                    </span>
                  </div>
                  {/* Hash chain row */}
                  <div className="flex items-center gap-1.5 mt-2 text-[9px] font-mono">
                    <span className="text-muted-foreground">{shortHash(entry.prev_hash)}</span>
                    <ArrowRight className="w-3 h-3 text-muted-foreground/50 shrink-0" />
                    <span className="text-foreground">{shortHash(entry.entry_hash)}</span>
                  </div>
                  {/* Verified badge */}
                  <div className="flex items-center gap-2 mt-2">
                    {entry.valid ? (
                      <Badge variant="outline" className="text-[8px] border-sylion-green/30 text-sylion-green bg-sylion-green/5">
                        <CheckCircle2 className="w-2.5 h-2.5 mr-1" />
                        Zweryfikowano
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[8px] border-sylion-red/30 text-sylion-red bg-sylion-red/5">
                        <XCircle className="w-2.5 h-2.5 mr-1" />
                        Zmanipulowany
                      </Badge>
                    )}
                    <span className="text-[9px] text-muted-foreground ml-auto">
                      {formatTimestamp(entry.timestamp)}
                    </span>
                  </div>
                  {/* Expanded detail */}
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-3 pt-3 border-t border-border/30 space-y-2 text-[10px]">
                          {typeof entry.evidence_pack?.description === "string" && (
                            <div>
                              <span className="text-muted-foreground uppercase tracking-wider">Description</span>
                              <p className="mt-0.5">{entry.evidence_pack.description}</p>
                            </div>
                          )}
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <span className="text-muted-foreground uppercase tracking-wider">Entry Hash</span>
                              <p className="font-mono mt-0.5 break-all">{entry.entry_hash}</p>
                            </div>
                            <div>
                              <span className="text-muted-foreground uppercase tracking-wider">Content Hash</span>
                              <p className="font-mono mt-0.5 break-all">{entry.content_hash}</p>
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <span className="text-muted-foreground uppercase tracking-wider">Prev Hash</span>
                              <p className="font-mono mt-0.5 break-all">{entry.prev_hash}</p>
                            </div>
                            <div>
                              <span className="text-muted-foreground uppercase tracking-wider">Module States</span>
                              <p className="font-mono mt-0.5 break-all">{entry.module_states_hash}</p>
                            </div>
                          </div>
                          {Object.keys(entry.metadata).length > 0 && (
                            <div>
                              <span className="text-muted-foreground uppercase tracking-wider">Metadata</span>
                              <pre className="mt-0.5 text-muted-foreground whitespace-pre-wrap">
                                {JSON.stringify(entry.metadata, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
            {filteredEntries.length === 0 && (
              <div className="p-6 text-center">
                <FileCheck className="w-6 h-6 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-xs text-muted-foreground">No entries match filters</p>
                {hasActiveFilters && (
                  <button onClick={clearFilters} className="mt-1 text-[10px] text-sylion-blue hover:underline">Clear filters</button>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* ---- SECTION 3: CHAIN VERIFICATION ---- */}
        <Card className="p-5 bg-[#0f1629] border-sylion-border xl:col-span-1">
          <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Shield className="w-4 h-4 text-sylion-amber" />
            Weryfikacja łańcucha
            <HelpTip text="Pełna walidacja kryptograficzna — sprawdźa każdy hash względem zawartości i prev_hash. Konieczne przy podejrzeniu manipulacji." />
          </h2>
          <Button
            variant="outline"
            size="sm"
            className="w-full mb-4"
            onClick={handleVerify}
            disabled={verifying}
          >
            <RefreshCw className={cn("w-3.5 h-3.5 mr-1.5", verifying && "animate-spin")} />
            {verifying ? "Trwa weryfikacja..." : "Uruchom weryfikację"}
          </Button>

          {verification && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="space-y-3"
            >
              {/* Overall result */}
              <div className={cn(
                "p-4 rounded-lg border flex items-center gap-3",
                verification.valid ? "border-sylion-green/30 bg-sylion-green/5" : "border-sylion-red/30 bg-sylion-red/5"
              )}>
                {verification.valid ? (
                  <ShieldCheck className="w-8 h-8 text-sylion-green shrink-0" />
                ) : (
                  <ShieldAlert className="w-8 h-8 text-sylion-red shrink-0" />
                )}
                <div>
                  <p className={cn("text-sm font-semibold", verification.valid ? "text-sylion-green" : "text-sylion-red")}>
                    {verification.valid ? "Integralność łańcucha zweryfikowana" : "Naruszona integralność łańcucha"}
                  </p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {verification.valid
                      ? "Wszystkie powiązania hashy zweryfikowane — brak manipulacji"
                      : "Wykryto naruszenie integralności w łańcuchu dowodowym"}
                  </p>
                </div>
              </div>

              {/* Verification metrics */}
              <div className="grid grid-cols-2 gap-2">
                <div className="p-3 bg-muted/10 rounded-lg">
                  <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Łącznie wpisów</p>
                  <p className="text-lg font-semibold mt-0.5">{verification.total_entries}</p>
                </div>
                <div className="p-3 bg-muted/10 rounded-lg">
                  <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Spójne</p>
                  <p className="text-lg font-semibold text-sylion-green mt-0.5">
                    {verification.total_entries - verification.tampered_count}
                  </p>
                </div>
                <div className="p-3 bg-muted/10 rounded-lg">
                  <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Zmanipulowane</p>
                  <p className={cn(
                    "text-lg font-semibold mt-0.5",
                    verification.tampered_count === 0 ? "text-sylion-green" : "text-sylion-red"
                  )}>
                    {verification.tampered_count}
                  </p>
                </div>
                <div className="p-3 bg-muted/10 rounded-lg">
                  <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Status</p>
                  <p className={cn(
                    "text-lg font-semibold mt-0.5",
                    verification.valid ? "text-sylion-green" : "text-sylion-red"
                  )}>
                    {verification.valid ? "OK" : "BŁĄD"}
                  </p>
                </div>
              </div>

              {/* Broken at info */}
              {!verification.valid && verification.broken_at && (
                <div className="p-3 bg-sylion-red/10 border border-sylion-red/20 rounded-lg">
                  <p className="text-[10px] text-sylion-red font-semibold flex items-center gap-1.5">
                    <XCircle className="w-3.5 h-3.5" />
                    Łańcuch złamany na:
                  </p>
                  <p className="text-[10px] font-mono text-muted-foreground mt-1 break-all">
                    {verification.broken_at}
                  </p>
                </div>
              )}

              {/* Per-entry verification list */}
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
                  Weryfikacja wpisów
                  <HelpTip text="Indywidualny status każdego wpisu — zielony OK, czerwony X przy manipulacji." />
                </p>
                <div className="space-y-1 max-h-[240px] overflow-y-auto pr-1">
                  {entries.map(entry => (
                    <div
                      key={entry.entry_id}
                      className="flex items-center gap-2 py-1.5 px-2 rounded text-[10px]"
                    >
                      <span className="text-muted-foreground font-mono w-8">#{entry.sequence}</span>
                      <span className="font-mono text-muted-foreground truncate flex-1">
                        {shortHash(entry.entry_hash)}
                      </span>
                      {entry.valid ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-sylion-green shrink-0" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-sylion-red shrink-0" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {!verification && (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Hash className="w-8 h-8 text-muted-foreground/20 mb-3" />
              <p className="text-xs text-muted-foreground">
                Kliknij &quot;Uruchom weryfikację&quot;, aby zwalidować cały łańcuch hashy
              </p>
              <p className="text-[10px] text-muted-foreground/60 mt-1">
                Hash każdego wpisu zostanie sprawdźony względem jego zawartości
              </p>
            </div>
          )}
        </Card>
      </div>
      )}
    </div>
  );
}
