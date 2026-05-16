"use client";

import { useState, useMemo, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useHealth, useGoldenSets, useRegressions, useKanonSections, useSelfModels } from "@/lib/api/hooks";
import { cn, fmtDate, fmtDateTime } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  BookOpen, Check, AlertTriangle, Search, Shield, Brain,
  FileCheck, Layers, Clock, Star, TrendingDown, Info,
  AlertOctagon, Zap, Activity, Cpu, Eye, Hash, ChevronRight,
  ChevronDown, ChevronUp, BarChart3, Target, Database, WifiOff,
  Plus, Filter, XCircle, CircleCheck, Sparkles, Gauge, Lightbulb,
  History, ThumbsUp, ThumbsDown, TrendingUp,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

/* ============================================================
   Types
   ============================================================ */

interface GoldenSet {
  set_id: string;
  name: string;
  description?: string;
  test_count?: number;
  pass_rate?: number;
  last_run?: string;
  created_at?: string;
  tags?: string[];
  status?: string;
  tests?: GoldenTest[];
}

interface GoldenTest {
  test_id: string;
  name: string;
  status: "pass" | "fail" | "skip";
  duration_ms?: number;
  message?: string;
}

interface RegressionAlert {
  alert_id: string;
  severity: "critical" | "warning" | "info";
  title: string;
  description?: string;
  metric?: string;
  expected?: number;
  actual?: number;
  delta?: number;
  timestamp?: string;
  source?: string;
  module?: string;
  resolved?: boolean;
}

interface KanonSection {
  section_id: string;
  title: string;
  content?: string;
  status?: string;
  coverage?: number;
  linked_modules?: string[];
  last_updated?: string;
  entry_count?: number;
  canonical_decisions?: number;
  open_questions?: number;
}

interface SelfModelEntry {
  model_id: string;
  name?: string;
  category?: string;
  description?: string;
  capabilities?: string[];
  limitations?: string[];
  confidence?: number;
  accuracy?: number;
  last_updated?: string;
  status?: string;
  traits?: Record<string, number>;
  learnings?: string[];
}

/* ============================================================
   Backend-only data; offline state does not synthesize entries.
   ============================================================ */

const severityIcon: Record<string, React.ElementType> = {
  critical: AlertOctagon,
  warning: AlertTriangle,
  info: Info,
};

const severityBg: Record<string, string> = {
  critical: "bg-sylion-red/15 text-sylion-red border-sylion-red/20",
  warning: "bg-sylion-amber/15 text-sylion-amber border-sylion-amber/20",
  info: "bg-sylion-blue/15 text-sylion-blue border-sylion-blue/20",
};

const statusBg: Record<string, string> = {
  complete: "bg-sylion-green/15 text-sylion-green",
  partial: "bg-sylion-amber/15 text-sylion-amber",
  missing: "bg-sylion-red/15 text-sylion-red",
  draft: "bg-primary/15 text-primary",
  active: "bg-sylion-green/15 text-sylion-green",
  degraded: "bg-sylion-amber/15 text-sylion-amber",
};

const categoryIcon: Record<string, React.ElementType> = {
  capabilities: ThumbsUp,
  limitations: ThumbsDown,
  performance_patterns: TrendingUp,
  learning_history: History,
};

function coverageColor(c: number): string {
  if (c >= 0.9) return "bg-sylion-green";
  if (c >= 0.6) return "bg-sylion-blue";
  if (c >= 0.4) return "bg-sylion-amber";
  return "bg-sylion-red";
}

function coverageTextColor(c: number): string {
  if (c >= 0.9) return "text-sylion-green";
  if (c >= 0.6) return "text-sylion-blue";
  if (c >= 0.4) return "text-sylion-amber";
  return "text-sylion-red";
}

function passRateColor(rate: number): string {
  if (rate >= 0.90) return "text-sylion-green";
  if (rate >= 0.70) return "text-sylion-amber";
  return "text-sylion-red";
}

function passRateBarColor(rate: number): string {
  if (rate >= 0.90) return "bg-sylion-green";
  if (rate >= 0.70) return "bg-sylion-amber";
  return "bg-sylion-red";
}

function passRateBadge(rate: number): string {
  if (rate >= 0.90) return "border-sylion-green/30 text-sylion-green bg-sylion-green/5";
  if (rate >= 0.70) return "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5";
  return "border-sylion-red/30 text-sylion-red bg-sylion-red/5";
}

/* ============================================================
   Sub-components
   ============================================================ */

function StatCard({ label, value, icon: Icon, accent, bgColor, helpText }: {
  label: string; value: string | number; icon: React.ElementType; accent: string; bgColor: string; helpText?: string;
}) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <Card className="relative overflow-hidden p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.15)] transition-all duration-300">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
              {label}
              {helpText ? <HelpTip text={helpText} /> : null}
            </p>
            <p className={cn("text-2xl font-semibold mt-1", accent)}>{value}</p>
          </div>
          <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center", bgColor)}>
            <Icon className={cn("w-4 h-4", accent)} />
          </div>
        </div>
        <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[rgba(148,163,184,0.1)] to-transparent" />
      </Card>
    </motion.div>
  );
}

/* ============================================================
   Main Page
   ============================================================ */

export default function BookPage() {
  const { data: health } = useHealth();
  const { data: goldenSetsData } = useGoldenSets();
  const { data: regressionsData } = useRegressions();
  const { data: kanonData } = useKanonSections();
  const { data: selfModelsData } = useSelfModels();

  const [activeTab, setActiveTab] = useState("golden-sets");
  const [kanonSearch, setKanonSearch] = useState("");
  const [expandedKanonId, setExpandedKanonId] = useState<string | null>(null);
  const [expandedGoldenId, setExpandedGoldenId] = useState<string | null>(null);
  const [regSeverityFilter, setRegSeverityFilter] = useState<string>("all");
  const [regStatusFilter, setRegStatusFilter] = useState<string>("all");
  const [resolvedAlerts, setResolvedAlerts] = useState<Set<string>>(new Set());

  const backendLive = health?.status === "ok";

  /* ---- Derive display data from backend only ---- */

  const goldenSets = useMemo<GoldenSet[]>(() => {
    if (!backendLive) return [];
    return (goldenSetsData.sets ?? []).map((s: any) => ({
      set_id: s.set_id ?? s.id ?? "",
      name: s.name ?? "",
      description: s.description ?? "",
      test_count: s.test_count ?? 0,
      pass_rate: s.pass_rate ?? 0,
      last_run: s.last_run ?? "",
      tags: s.tags ?? [],
      status: s.status ?? "active",
      tests: (s.tests ?? []).map((t: any) => ({
        test_id: t.test_id ?? t.id ?? "",
        name: t.name ?? "",
        status: t.status ?? "skip",
        duration_ms: t.duration_ms,
        message: t.message,
      })),
    }));
  }, [backendLive, goldenSetsData]);

  const regressions = useMemo<RegressionAlert[]>(() => {
    if (!backendLive) return [];
    return (regressionsData.alerts ?? []).map((a: any) => ({
      alert_id: a.alert_id ?? a.id ?? "",
      severity: a.severity ?? "info",
      title: a.title ?? "",
      description: a.description ?? "",
      metric: a.metric,
      expected: a.expected,
      actual: a.actual,
      delta: a.delta,
      timestamp: a.timestamp ?? "",
      source: a.source,
      module: a.module,
      resolved: a.resolved ?? false,
    }));
  }, [backendLive, regressionsData]);

  const kanonSections = useMemo<KanonSection[]>(() => {
    if (!backendLive) return [];
    return (kanonData.sections ?? []).map((s: any) => ({
      section_id: s.section_id ?? s.id ?? "",
      title: s.title ?? "",
      content: s.content ?? "",
      status: s.status ?? "draft",
      coverage: s.coverage ?? 0,
      linked_modules: s.linked_modules ?? [],
      last_updated: s.last_updated ?? "",
      entry_count: s.entry_count,
      canonical_decisions: s.canonical_decisions,
      open_questions: s.open_questions,
    }));
  }, [backendLive, kanonData]);

  const selfModels = useMemo<SelfModelEntry[]>(() => {
    if (!backendLive) return [];
    return (selfModelsData.models ?? []).map((m: any) => ({
      model_id: m.model_id ?? m.id ?? "",
      name: m.name ?? "",
      category: m.category ?? "",
      description: m.description ?? "",
      capabilities: m.capabilities ?? [],
      limitations: m.limitations ?? [],
      confidence: m.confidence ?? 0,
      accuracy: m.accuracy ?? 0,
      last_updated: m.last_updated ?? "",
      status: m.status ?? "active",
      traits: m.traits ?? {},
      learnings: m.learnings ?? [],
    }));
  }, [backendLive, selfModelsData]);

  /* ---- Filtered data ---- */

  const filteredKanonSections = useMemo(() => {
    if (!kanonSearch.trim()) return kanonSections;
    const q = kanonSearch.toLowerCase();
    return kanonSections.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        (s.content ?? "").toLowerCase().includes(q) ||
        (s.linked_modules ?? []).some((m) => m.toLowerCase().includes(q)),
    );
  }, [kanonSections, kanonSearch]);

  const filteredRegressions = useMemo(() => {
    return regressions.filter((a) => {
      if (regSeverityFilter !== "all" && a.severity !== regSeverityFilter) return false;
      const isResolved = a.resolved || resolvedAlerts.has(a.alert_id);
      if (regStatusFilter === "open" && isResolved) return false;
      if (regStatusFilter === "resolved" && !isResolved) return false;
      return true;
    });
  }, [regressions, regSeverityFilter, regStatusFilter, resolvedAlerts]);

  /* ---- Stats ---- */

  const totalTests = goldenSets.reduce((a, g) => a + (g.test_count ?? 0), 0);
  const avgPassRate = goldenSets.length > 0 ? goldenSets.reduce((a, g) => a + (g.pass_rate ?? 0), 0) / goldenSets.length : 0;
  const criticalAlerts = regressions.filter((a) => a.severity === "critical" && !a.resolved && !resolvedAlerts.has(a.alert_id)).length;
  const activeAlerts = regressions.filter((a) => !a.resolved && !resolvedAlerts.has(a.alert_id)).length;

  /* ---- Handlers ---- */

  const handleResolveAlert = useCallback((alertId: string) => {
    setResolvedAlerts((prev) => new Set(prev).add(alertId));
  }, []);

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                Księga: Jakość i Wiedza
                <HelpTip text="Centrum jako?ci platformy: Golden Sets (testy referencyjne), Regression Alerts (wykryte regresje), Kanon (zdecydowane decyzję architektoniczne), Self-Model (samowiedza systemu o swoich zdolno?ciach)." />
              </h1>
              <p className="text-sm text-muted-foreground">Golden sets, regresje, kanon i self-model</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {backendLive ? (
              <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green">
                <span className="w-1.5 h-1.5 rounded-full bg-sylion-green mr-1.5 animate-pulse" />
                LIVE
              </Badge>
            ) : (
              <Badge variant="outline" className="text-[10px] border-sylion-red/30 text-sylion-red">
                <WifiOff className="w-3 h-3 mr-1" />
                OFFLINE
              </Badge>
            )}
          </div>
        </div>
      </motion.div>

      {/* Offline message */}
      {!backendLive && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <div className="rounded-xl border border-sylion-red/20 p-8 flex flex-col items-center justify-center" style={{ background: "rgba(15,22,41,0.95)" }}>
            <WifiOff className="w-10 h-10 text-sylion-red/60 mb-3" />
            <p className="text-sm text-sylion-red/80 font-medium">Backend nieosięgalny</p>
            <p className="text-[11px] text-muted-foreground mt-1">Uruchom backend: <code className="text-primary">python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010</code></p>
          </div>
        </motion.div>
      )}

      {/* ====== Content (only when backend is live) ====== */}
      {backendLive && <div>
      <div className="grid grid-cols-4 gap-3">
        <StatCard
          label="Golden Sets"
          value={goldenSets.length}
          icon={Star}
          accent="text-sylion-green"
          bgColor="bg-sylion-green/10"
          helpText="Liczba zdefiniowanych zestawów testów z?otych — kanonicznych przypadków walidacji jako?ci. Każdy set ma test_count i pass_rate."
        />
        <StatCard
          label="Alerty regresji"
          value={activeAlerts}
          icon={AlertTriangle}
          accent={activeAlerts > 0 ? "text-sylion-red" : "text-sylion-green"}
          bgColor={activeAlerts > 0 ? "bg-sylion-red/10" : "bg-sylion-green/10"}
          helpText="Liczba aktywnych (nierozwiazanych) alert?w regresji. Generowane gdy metryka odbiegnie od wartośći oczekiwanej. Critical wymaga interwencji operatora."
        />
        <StatCard
          label="Sekcje kanonu"
          value={kanonSections.length}
          icon={BookOpen}
          accent="text-sylion-blue"
          bgColor="bg-sylion-blue/10"
          helpText="Liczba sekcji kanonu — zdecydowanych, opieczetowanych decyzji architektonicznych. Każda ma coverage (% pokrycia tematu) i status (complete/partial/missing/draft)."
        />
        <StatCard
          label="Wpisy Self-Model"
          value={selfModels.length}
          icon={Brain}
          accent="text-sylion-amber"
          bgColor="bg-sylion-amber/10"
          helpText="Liczba wpis?w w samoswiadomosci systemu: zdolno?ci, ograniczenia, wzorce wydajnosci, historia uczenia. Confidence + accuracy mowia jak pewne sa te zapisy."
        />
      </div>

      {/* ====== TABS ====== */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="flex items-center gap-2">
          <TabsList>
            <TabsTrigger value="golden-sets" className="text-[11px]">
              <Star className="w-3 h-3 mr-1" />
              Golden Sets
            </TabsTrigger>
            <TabsTrigger value="regressions" className="text-[11px]">
              <AlertTriangle className="w-3 h-3 mr-1" />
              Alerty regresji
            </TabsTrigger>
            <TabsTrigger value="kanon" className="text-[11px]">
              <BookOpen className="w-3 h-3 mr-1" />
              Kanon
            </TabsTrigger>
            <TabsTrigger value="self-model" className="text-[11px]">
              <Brain className="w-3 h-3 mr-1" />
              Self-Model
            </TabsTrigger>
          </TabsList>
          <HelpTip text="Cztery sekcje wiedzy: Golden Sets (testy referencyjne z pass rate), Regresje (anomalie metryczne wymagaj?ce fix), Kanon (zatwierdzone decyzję architektoniczne z coverage), Self-Model (samoswiadomosc systemu)." />
        </div>

        {/* ====== GOLDEN SETS TAB ====== */}
        <TabsContent value="golden-sets">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mt-4">
            {/* Summary bar */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{goldenSets.length} zestawów testów</span>
                <span className="text-[10px] text-muted-foreground">{totalTests} testów ??cznie</span>
              </div>
              <div className="flex items-center gap-3">
                <span className={cn("text-[10px] font-medium", passRateColor(avgPassRate))}>
                  Sredni pass rate: {(avgPassRate * 100).toFixed(1)}%
                </span>
                <button className="flex items-center gap-1.5 text-[10px] font-medium text-primary border border-primary/20 rounded-md px-2.5 py-1.5 hover:bg-primary/5 transition-colors">
                  <Plus className="w-3 h-3" />
                  Utworz Golden Set
                </button>
              </div>
            </div>

            {goldenSets.length === 0 ? (
              <div className="text-center py-12">
                <Star className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Brak skonfigurowanych golden sets.</p>
              </div>
            ) : (
              <div className="rounded-lg border border-[rgba(148,163,184,0.08)] overflow-hidden">
                {/* Table header */}
                <div className="grid grid-cols-[1fr_120px_100px_120px_140px_100px] gap-2 px-4 py-2.5 bg-[#0a0f1e] border-b border-[rgba(148,163,184,0.08)] text-[10px] text-muted-foreground uppercase tracking-wider">
                  <span>Nazwa</span>
                  <span>Liczba testów</span>
                  <span>Pass rate</span>
                  <span>Ostatni run</span>
                  <span>Status</span>
                  <span className="text-right">Rozwin</span>
                </div>

                {/* Table rows */}
                {goldenSets.map((gs) => {
                  const rate = gs.pass_rate ?? 0;
                  const isExpanded = expandedGoldenId === gs.set_id;

                  return (
                    <div key={gs.set_id}>
                      <motion.div
                        className={cn(
                          "grid grid-cols-[1fr_120px_100px_120px_140px_100px] gap-2 px-4 py-3 border-b border-[rgba(148,163,184,0.06)] cursor-pointer hover:bg-[rgba(148,163,184,0.02)] transition-colors",
                          isExpanded && "bg-[rgba(148,163,184,0.02)]",
                        )}
                        onClick={() => setExpandedGoldenId(isExpanded ? null : gs.set_id)}
                      >
                        {/* Name + description */}
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{gs.name}</p>
                          <p className="text-[10px] text-muted-foreground truncate mt-0.5">{gs.description ?? "Referencyjny zestaw testów jako?ci"}</p>
                        </div>

                        {/* Test count */}
                        <div className="flex items-center gap-1.5">
                          <FileCheck className="w-3 h-3 text-muted-foreground" />
                          <span className="text-sm">{gs.test_count ?? 0}</span>
                        </div>

                        {/* Pass rate */}
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className={cn("text-[10px] h-5 font-mono border", passRateBadge(rate))}>
                            {(rate * 100).toFixed(1)}%
                          </Badge>
                          <div className="w-12 h-1.5 rounded-full bg-secondary/40 hidden sm:block">
                            <motion.div
                              className={cn("h-full rounded-full", passRateBarColor(rate))}
                              initial={{ width: 0 }}
                              animate={{ width: `${rate * 100}%` }}
                              transition={{ duration: 0.5 }}
                            />
                          </div>
                        </div>

                        {/* Last run */}
                        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                          <Clock className="w-3 h-3" />
                          {gs.last_run ? fmtDate(gs.last_run) : "Nigdy"}
                        </div>

                        {/* Status */}
                        <div className="flex items-center justify-end">
                          <Badge variant="outline" className={cn("text-[9px] h-5 border", gs.status === "degraded" ? "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5" : "border-sylion-green/30 text-sylion-green bg-sylion-green/5")}>
                            {gs.status ?? "aktywny"}
                          </Badge>
                        </div>
                      </motion.div>

                      {/* Expanded test results */}
                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.25, ease: "easeInOut" }}
                            className="overflow-hidden bg-[#080c18] border-b border-[rgba(148,163,184,0.06)]"
                          >
                            <div className="px-6 py-3 space-y-1.5">
                              {gs.tags && gs.tags.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mb-2">
                                  {gs.tags.map((tag) => (
                                    <Badge key={tag} variant="outline" className="text-[9px] h-4 border-[rgba(148,163,184,0.12)] text-muted-foreground">
                                      {tag}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                              {(gs.tests ?? []).length > 0 ? (
                                <>
                                  <div className="grid grid-cols-[1fr_80px_80px_1fr] gap-2 text-[9px] text-muted-foreground uppercase tracking-wider mb-1">
                                    <span>Nazwa testu</span>
                                    <span>Status</span>
                                    <span>Czas</span>
                                    <span>Komunikat</span>
                                  </div>
                                  {(gs.tests ?? []).map((test) => (
                                    <div key={test.test_id} className="grid grid-cols-[1fr_80px_80px_1fr] gap-2 text-[11px] py-1.5 border-b border-[rgba(148,163,184,0.04)] last:border-0">
                                      <span className="text-muted-foreground">{test.name}</span>
                                      <span>
                                        <Badge variant="outline" className={cn(
                                          "text-[9px] h-4 border",
                                          test.status === "pass" ? "border-sylion-green/30 text-sylion-green bg-sylion-green/5" :
                                          test.status === "fail" ? "border-sylion-red/30 text-sylion-red bg-sylion-red/5" :
                                          "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5"
                                        )}>
                                          {test.status === "pass" ? <Check className="w-2.5 h-2.5 mr-0.5" /> :
                                           test.status === "fail" ? <XCircle className="w-2.5 h-2.5 mr-0.5" /> :
                                           <AlertTriangle className="w-2.5 h-2.5 mr-0.5" />}
                                          {test.status}
                                        </Badge>
                                      </span>
                                      <span className="text-muted-foreground font-mono">{test.duration_ms ? `${test.duration_ms}ms` : "-"}</span>
                                      <span className={cn("text-muted-foreground", test.message && "text-sylion-red/80")}>{test.message ?? "-"}</span>
                                    </div>
                                  ))}
                                </>
                              ) : (
                                <p className="text-[11px] text-muted-foreground italic">Brak wyników pojedynczych testów. Uruchom golden set aby je wypełnił.</p>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  );
                })}
              </div>
            )}
          </motion.div>
        </TabsContent>

        {/* ====== REGRESSION ALERTS TAB ====== */}
        <TabsContent value="regressions">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mt-4 space-y-4">
            {/* Filters */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <Filter className="w-3 h-3 text-muted-foreground" />
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                  Krytycznosc:
                  <HelpTip text="Filtr po poziomie ryzyka regresji. Critical — natychmiastowa interwencja; Warning — monitoruj; Info — odnotowane, ale niegrozne." />
                </span>
                {["all", "critical", "warning", "info"].map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setRegSeverityFilter(sev)}
                    className={cn(
                      "text-[10px] px-2 py-1 rounded border transition-colors capitalize",
                      regSeverityFilter === sev
                        ? "border-primary/30 bg-primary/10 text-primary"
                        : "border-[rgba(148,163,184,0.08)] text-muted-foreground hover:border-[rgba(148,163,184,0.15)]",
                    )}
                  >
                    {sev === "all" ? "wszystkie" : sev}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1.5 ml-4">
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                  Status:
                  <HelpTip text="Open — niezalatwione, wymagaj? akcji; Resolved — operator oznaczyl jako zalatwione (ich rozwiazanie zapisuje sie w audycie)." />
                </span>
                {["all", "open", "resolved"].map((st) => (
                  <button
                    key={st}
                    onClick={() => setRegStatusFilter(st)}
                    className={cn(
                      "text-[10px] px-2 py-1 rounded border transition-colors capitalize",
                      regStatusFilter === st
                        ? "border-primary/30 bg-primary/10 text-primary"
                        : "border-[rgba(148,163,184,0.08)] text-muted-foreground hover:border-[rgba(148,163,184,0.15)]",
                    )}
                  >
                    {st === "all" ? "wszystkie" : st === "open" ? "otwarte" : "rozwiazane"}
                  </button>
                ))}
              </div>
            </div>

            {/* Severity summary */}
            <div className="flex items-center gap-4">
              {(["critical", "warning", "info"] as const).map((sev) => {
                const count = regressions.filter((a) => a.severity === sev && !a.resolved && !resolvedAlerts.has(a.alert_id)).length;
                const SevIcon = severityIcon[sev];
                return (
                  <div key={sev} className="flex items-center gap-1.5">
                    <SevIcon className={cn("w-3.5 h-3.5", sev === "critical" ? "text-sylion-red" : sev === "warning" ? "text-sylion-amber" : "text-sylion-blue")} />
                    <span className={cn("text-[10px] font-medium", sev === "critical" ? "text-sylion-red" : sev === "warning" ? "text-sylion-amber" : "text-sylion-blue")}>
                      {count} {sev}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Alert list */}
            {filteredRegressions.length === 0 ? (
              <div className="text-center py-12">
                <Check className="w-8 h-8 text-sylion-green mx-auto mb-2" />
                <p className="text-sm text-sylion-green">Brak alert?w regresji pasujacych do filtrow.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredRegressions.map((alert) => {
                  const SevIcon = severityIcon[alert.severity] || Info;
                  const isResolved = alert.resolved || resolvedAlerts.has(alert.alert_id);
                  return (
                    <motion.div key={alert.alert_id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2 }}>
                      <Card className={cn(
                        "p-4 border transition-colors bg-[#0f1629] relative overflow-hidden",
                        alert.severity === "critical" && !isResolved ? "border-l-2 border-l-sylion-red border-sylion-red/20 hover:border-sylion-red/30" :
                        alert.severity === "warning" && !isResolved ? "border-l-2 border-l-sylion-amber border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.15)]" :
                        "border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.15)]",
                        isResolved && "opacity-60",
                      )}>
                        <div className="flex items-start gap-3">
                          <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center shrink-0", severityBg[alert.severity])}>
                            <SevIcon className="w-4 h-4" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h3 className="text-sm font-medium">{alert.title}</h3>
                              <Badge variant="outline" className={cn("text-[9px] h-4 border", severityBg[alert.severity])}>
                                {alert.severity}
                              </Badge>
                              {isResolved && (
                                <Badge variant="outline" className="text-[9px] h-4 border-sylion-green/30 text-sylion-green bg-sylion-green/5">
                                  rozwiazane
                                </Badge>
                              )}
                              {alert.module && (
                                <Badge variant="outline" className="text-[9px] h-4 border-[rgba(148,163,184,0.12)] text-muted-foreground">
                                  <Hash className="w-2.5 h-2.5 mr-0.5" />
                                  {alert.module}
                                </Badge>
                              )}
                            </div>
                            <p className="text-[11px] text-muted-foreground mt-1">{alert.description}</p>

                            {/* Metric details */}
                            {alert.metric && (
                              <div className="flex items-center gap-3 mt-2.5 text-[10px]">
                                <span className="text-muted-foreground flex items-center gap-1"><Target className="w-3 h-3" />{alert.metric}</span>
                                {alert.expected != null && <span className="text-muted-foreground">oczekiwano: {typeof alert.expected === "number" && alert.expected < 1 ? alert.expected.toFixed(2) : alert.expected}</span>}
                                {alert.actual != null && (
                                  <span className={cn(
                                    "font-medium",
                                    alert.severity === "critical" ? "text-sylion-red" :
                                    alert.severity === "warning" ? "text-sylion-amber" : "text-sylion-blue"
                                  )}>
                                    rzeczywiste: {typeof alert.actual === "number" && alert.actual < 1 ? alert.actual.toFixed(2) : alert.actual}
                                  </span>
                                )}
                                {alert.delta != null && (
                                  <span className={cn(
                                    "font-mono",
                                    alert.delta < 0 ? "text-sylion-red" : "text-sylion-amber"
                                  )}>
                                    ({alert.delta > 0 ? "+" : ""}{typeof alert.delta === "number" && Math.abs(alert.delta) < 1 ? alert.delta.toFixed(2) : alert.delta})
                                  </span>
                                )}
                              </div>
                            )}

                            {/* Source & timestamp */}
                            <div className="flex items-center justify-between mt-2">
                              <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                                {alert.source && <span className="flex items-center gap-1"><Database className="w-3 h-3" />{alert.source}</span>}
                                {alert.timestamp && <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{fmtDateTime(alert.timestamp)}</span>}
                              </div>
                              {!isResolved && (
                                <button
                                  onClick={() => handleResolveAlert(alert.alert_id)}
                                  className="flex items-center gap-1 text-[10px] font-medium text-sylion-green border border-sylion-green/20 rounded px-2 py-1 hover:bg-sylion-green/5 transition-colors"
                                >
                                  <CircleCheck className="w-3 h-3" />
                                  Rozwiaz
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      </Card>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </motion.div>
        </TabsContent>

        {/* ====== KANON TAB ====== */}
        <TabsContent value="kanon">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mt-4 space-y-4">
            {/* Search bar */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Szukaj sekcji, tresci, modulow..."
                value={kanonSearch}
                onChange={(e) => setKanonSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 rounded-md bg-[#0f1629] border border-[rgba(148,163,184,0.08)] text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30 transition-colors"
              />
            </div>

            {/* Section count */}
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                {filteredKanonSections.length} sekcj{filteredKanonSections.length === 1 ? "a" : filteredKanonSections.length < 5 ? "e" : "i"}
                {kanonSearch.trim() ? ` pasujac${filteredKanonSections.length === 1 ? "a" : filteredKanonSections.length < 5 ? "e" : "ych"} do "${kanonSearch}"` : ""}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {kanonSections.filter((s) => s.status === "complete").length}/{kanonSections.length} ukonczone
              </span>
            </div>

            {/* Sections accordion */}
            {filteredKanonSections.length === 0 ? (
              <div className="text-center py-8">
                <Search className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Zadna sekcja nie pasuje do wyszukiwania.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredKanonSections.map((section) => {
                  const cov = section.coverage ?? 0;
                  const isExpanded = expandedKanonId === section.section_id;
                  const statusIconMap: Record<string, React.ElementType> = {
                    complete: Check, partial: AlertTriangle, missing: AlertTriangle, draft: Info,
                  };
                  const Icon = statusIconMap[section.status ?? "draft"] ?? Info;

                  return (
                    <motion.div key={section.section_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
                      <Card
                        className={cn(
                          "border transition-colors cursor-pointer bg-[#0f1629]",
                          isExpanded ? "border-[rgba(148,163,184,0.2)]" : "border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.15)]",
                        )}
                        onClick={() => setExpandedKanonId(isExpanded ? null : section.section_id)}
                      >
                        <div className="p-4">
                          <div className="flex items-center gap-3">
                            <ChevronRight className={cn("w-4 h-4 text-muted-foreground shrink-0 transition-transform", isExpanded && "rotate-90")} />
                            <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center shrink-0", statusBg[section.status ?? "draft"])}>
                              <Icon className="w-4 h-4" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <h3 className="text-sm font-medium">{section.title}</h3>
                                <Badge variant="outline" className={cn("text-[9px] h-4 border", statusBg[section.status ?? "draft"])}>
                                  {section.status === "complete" ? "ukonczone" : section.status === "partial" ? "czesciowe" : section.status === "missing" ? "brakuje" : section.status === "draft" ? "szkic" : section.status ?? "szkic"}
                                </Badge>
                              </div>
                              <div className="flex items-center gap-3 mt-1 text-[10px] text-muted-foreground">
                                {section.entry_count != null && <span className="flex items-center gap-1"><Layers className="w-3 h-3" />{section.entry_count} wpis?w</span>}
                                {section.canonical_decisions != null && <span className="flex items-center gap-1"><Shield className="w-3 h-3" />{section.canonical_decisions} decyzji</span>}
                                {section.open_questions != null && section.open_questions > 0 && (
                                  <span className="flex items-center gap-1 text-sylion-amber"><AlertTriangle className="w-3 h-3" />{section.open_questions} otwartych</span>
                                )}
                                {section.last_updated && <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{fmtDate(section.last_updated)}</span>}
                              </div>
                              {!isExpanded && section.content && (
                                <p className="text-[10px] text-muted-foreground mt-1 truncate">{section.content}</p>
                              )}
                            </div>
                            {/* Coverage mini bar */}
                            <div className="w-20 shrink-0">
                              <div className="flex items-center justify-between mb-1">
                                <span className={cn("text-[10px] font-semibold", coverageTextColor(cov))}>{(cov * 100).toFixed(0)}%</span>
                              </div>
                              <div className="w-full h-1.5 rounded-full bg-secondary/40">
                                <motion.div
                                  className={cn("h-full rounded-full", coverageColor(cov))}
                                  initial={{ width: 0 }}
                                  animate={{ width: `${cov * 100}%` }}
                                  transition={{ duration: 0.5, ease: "easeOut" }}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Expanded content */}
                          <AnimatePresence>
                            {isExpanded && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.25, ease: "easeInOut" }}
                                className="overflow-hidden"
                              >
                                <div className="mt-4 pt-4 border-t border-[rgba(148,163,184,0.06)]">
                                  <p className="text-xs text-muted-foreground mb-3 leading-relaxed">{section.content ?? "Brak dostepnej tresci."}</p>
                                  {section.linked_modules && section.linked_modules.length > 0 && (
                                    <div>
                                      <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1.5">Powiazane moduly</p>
                                      <div className="flex flex-wrap gap-1.5">
                                        {section.linked_modules.map((mod) => (
                                          <Badge key={mod} variant="outline" className="text-[9px] h-5 border-[rgba(148,163,184,0.12)] text-muted-foreground">
                                            <Hash className="w-2.5 h-2.5 mr-0.5" />
                                            {mod}
                                          </Badge>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      </Card>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </motion.div>
        </TabsContent>

        {/* ====== SELF-MODEL TAB ====== */}
        <TabsContent value="self-model">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mt-4">
            {selfModels.length === 0 ? (
              <div className="text-center py-12">
                <Brain className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Brak dostepnych danych self-model.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                {selfModels.map((model) => {
                  const conf = model.confidence ?? 0;
                  const acc = model.accuracy ?? 0;
                  const CatIcon = categoryIcon[model.category ?? ""] ?? Brain;

                  return (
                    <motion.div key={model.model_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
                      <Card className="p-5 bg-[#0f1629] border border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.15)] transition-all duration-300 h-full">
                        {/* Header */}
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                              <CatIcon className="w-5 h-5 text-primary" />
                            </div>
                            <div>
                              <h3 className="text-sm font-semibold">
                                {model.name ?? "Self Model"}
                                <HelpTip text="Zapis samowiedzy: zdolno?ci, ograniczenia, wzorce, historia uczenia. Confidence — pewnosc systemu co do tego zapisu; Accuracy — historyczna trafnosc samooceny." />
                              </h3>
                              <p className="text-[11px] text-muted-foreground mt-0.5">{model.description ?? "Model samoreprezentacji AI"}</p>
                            </div>
                          </div>
                          <Badge variant="outline" className="text-[9px] h-5 border-sylion-green/30 text-sylion-green bg-sylion-green/5">
                            {model.status ?? "aktywny"}
                          </Badge>
                        </div>

                        {/* Category badge */}
                        {model.category && (
                          <div className="mb-3">
                            <Badge variant="outline" className="text-[9px] h-5 border-primary/20 text-primary bg-primary/5 capitalize">
                              {model.category.replace(/_/g, " ")}
                            </Badge>
                          </div>
                        )}

                        {/* Confidence & Accuracy */}
                        <div className="grid grid-cols-2 gap-3 mb-4">
                          <div>
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                                Pewnosc
                                <HelpTip text="Confidence — jak pewny jest system co do tego zapisu samoswiadomosci (0-100%). Niska wartość = potrzeba walidacji w praktyce." />
                              </span>
                              <span className={cn("text-sm font-bold", coverageTextColor(conf))}>{(conf * 100).toFixed(0)}%</span>
                            </div>
                            <div className="w-full h-2 rounded-full bg-secondary/40">
                              <motion.div
                                className={cn("h-full rounded-full", coverageColor(conf))}
                                initial={{ width: 0 }}
                                animate={{ width: `${conf * 100}%` }}
                                transition={{ duration: 0.6, ease: "easeOut" }}
                              />
                            </div>
                          </div>
                          <div>
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                                Trafnosc
                                <HelpTip text="Accuracy — historyczna trafnosc tej samooceny: ile razy system dobrze przewidzial sw?je zachowanie w tej domenie." />
                              </span>
                              <span className={cn("text-sm font-bold", coverageTextColor(acc))}>{(acc * 100).toFixed(0)}%</span>
                            </div>
                            <div className="w-full h-2 rounded-full bg-secondary/40">
                              <motion.div
                                className={cn("h-full rounded-full", coverageColor(acc))}
                                initial={{ width: 0 }}
                                animate={{ width: `${acc * 100}%` }}
                                transition={{ duration: 0.6, ease: "easeOut", delay: 0.1 }}
                              />
                            </div>
                          </div>
                        </div>

                        {/* Trait bars */}
                        {model.traits && Object.keys(model.traits).length > 0 && (
                          <div className="mb-4">
                            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-2">
                              Cechy
                              <HelpTip text="Cechy charakterystyczne (0-100%): np. ostrożność, kreatywno??, szybkość, dokładność. Pomagaja routerowi dobrac model do typu zadania." />
                            </p>
                            <div className="space-y-2">
                              {Object.entries(model.traits).map(([trait, value]) => (
                                <div key={trait} className="flex items-center gap-3">
                                  <span className="text-[10px] text-muted-foreground w-28 truncate shrink-0 capitalize">{trait.replace(/_/g, " ")}</span>
                                  <div className="flex-1 h-1.5 rounded-full bg-secondary/30">
                                    <motion.div
                                      className={cn("h-full rounded-full", coverageColor(value))}
                                      initial={{ width: 0 }}
                                      animate={{ width: `${value * 100}%` }}
                                      transition={{ duration: 0.5, ease: "easeOut", delay: 0.1 }}
                                    />
                                  </div>
                                  <span className={cn("text-[10px] font-medium w-8 text-right", coverageTextColor(value))}>
                                    {(value * 100).toFixed(0)}%
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Capabilities */}
                        {model.capabilities && model.capabilities.length > 0 && (
                          <div className="mb-3">
                            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                              Zdolnosci
                              <HelpTip text="Lista wykazanych zdolno?ci tego self-modelu. Wykorzystywane przy dobórze do zada?; brak zdolno?ci dla danej domeny dyskwalifikuje model w routingu." />
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {model.capabilities.map((cap) => (
                                <Badge key={cap} variant="outline" className="text-[9px] h-5 border-sylion-green/20 text-sylion-green bg-sylion-green/5">
                                  <Check className="w-2.5 h-2.5 mr-0.5" />
                                  {cap}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Limitations */}
                        {model.limitations && model.limitations.length > 0 && (
                          <div className="mb-3">
                            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                              Ograniczenia
                              <HelpTip text="Znane ograniczenia (np. brak wiedzy aktualnej, slabosc w danej domenie). System bedzie unikal tych modeli w odpowiednich kontekstach." />
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              {model.limitations.map((lim) => (
                                <Badge key={lim} variant="outline" className="text-[9px] h-5 border-sylion-amber/20 text-sylion-amber bg-sylion-amber/5">
                                  <AlertTriangle className="w-2.5 h-2.5 mr-0.5" />
                                  {lim}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Learnings */}
                        {model.learnings && model.learnings.length > 0 && (
                          <div className="mb-3">
                            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                              Ostatnie obserwacje
                              <HelpTip text="Krotkie zapisy z ostatnich uruchomien — co system zauwazyl o sobie w produkcyjnych warunkach. Staja sie podstawa do aktualizacji confidence." />
                            </p>
                            <div className="space-y-1.5">
                              {model.learnings.map((learning, i) => (
                                <div key={i} className="flex items-start gap-2 text-[11px] text-muted-foreground">
                                  <Zap className="w-3 h-3 text-primary shrink-0 mt-0.5" />
                                  <span>{learning}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Timestamp */}
                        {model.last_updated && (
                          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mt-3 pt-3 border-t border-[rgba(148,163,184,0.06)]">
                            <Clock className="w-3 h-3" />
                            <span>Ostatnia aktualizacja: {fmtDateTime(model.last_updated)}</span>
                          </div>
                        )}
                      </Card>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </motion.div>
        </TabsContent>
      </Tabs>
      </div>}
    </div>
  );
}
