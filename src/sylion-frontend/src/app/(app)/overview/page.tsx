"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn, fmtDateTime, fmtTime } from "@/lib/utils";
import {
  useHealth,
  useModules,
  useDecisionGates,
} from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { AeisV2Summary } from "@/components/v2/AeisV2Summary";
import {
  Activity,
  Brain,
  Cpu,
  Shield,
  Zap,
  Lock,
  Eye,
  Database,
  Gauge,
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  Radio,
  Layers,
  Hexagon,
  ArrowRight,
  Lightbulb,
  Play,
  LayoutGrid,
  Settings,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CircleDot,
  GitBranch,
  Timer,
  FileText,
  Users,
  TrendingUp,
  Send,
} from "lucide-react";

/* ============================================================
   Category config — maps module ID prefixes to display info
   ============================================================ */

interface CategoryConfig {
  label: string;
  prefix: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: React.ElementType;
}

const MODULE_CATEGORIES: CategoryConfig[] = [
  { label: "Rdzeń", prefix: "core.", color: "#94A3B8", bgColor: "rgba(148,163,184,0.08)", borderColor: "rgba(148,163,184,0.25)", icon: Cpu },
  { label: "Poznawcze", prefix: "cognitive.", color: "#2F6BFF", bgColor: "rgba(47,107,255,0.08)", borderColor: "rgba(47,107,255,0.25)", icon: Brain },
  { label: "Zarządzanie", prefix: "governance.", color: "#F59E0B", bgColor: "rgba(245,158,11,0.08)", borderColor: "rgba(245,158,11,0.25)", icon: Shield },
  { label: "Wykonanie", prefix: "execution.", color: "#17C964", bgColor: "rgba(23,201,100,0.08)", borderColor: "rgba(23,201,100,0.25)", icon: Zap },
  { label: "Bezpieczeństwo", prefix: "security.", color: "#F31260", bgColor: "rgba(243,18,96,0.08)", borderColor: "rgba(243,18,96,0.25)", icon: Lock },
  { label: "Monitoring", prefix: "monitoring.", color: "#14B8A6", bgColor: "rgba(20,184,166,0.08)", borderColor: "rgba(20,184,166,0.25)", icon: Eye },
  { label: "Pamięć", prefix: "memory.", color: "#A855F7", bgColor: "rgba(168,85,247,0.08)", borderColor: "rgba(168,85,247,0.25)", icon: Database },
];

/* ============================================================
   Backend-unreachable banner
   ============================================================ */

/* ============================================================
   Fade-in animation wrapper
   ============================================================ */

function FadeSection({ children, delay = 0, className }: { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ============================================================
   Section header component
   ============================================================ */

function SectionHeader({ icon: Icon, iconColor, title, badge, action }: {
  icon: React.ElementType;
  iconColor: string;
  title: string;
  badge?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: `${iconColor}15` }}>
          <Icon className="w-3 h-3" style={{ color: iconColor }} />
        </div>
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {badge && <Badge variant="secondary" className="text-[10px]">{badge}</Badge>}
      </div>
      {action}
    </div>
  );
}

/* ============================================================
   Card wrapper
   ============================================================ */

function DarkCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <Card
      className={cn("rounded-xl p-5", className)}
      style={{
        background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
        borderColor: "rgba(148,163,184,0.06)",
      }}
    >
      {children}
    </Card>
  );
}

/* ============================================================
   MAIN PAGE
   ============================================================ */

export default function OverviewPage() {
  const router = useRouter();

  // API hooks
  const { data: health } = useHealth();
  const { data: modulesData } = useModules();
  const { data: gatesData } = useDecisionGates();

  const [pipelineRuns, setPipelineRuns] = useState<any[]>([]);
  const [decisionSnapshots, setDecisionSnapshots] = useState<any[]>([]);
  const [ideaStats, setIdeaStats] = useState<any>(null);
  const [complianceScore, setComplianceScore] = useState<number | null>(null);
  const [ideaInput, setIdeaInput] = useState("");

  const backendLive = health.status === "ok";
  const isOk = health.status === "ok";
  const isError = health.status === "error";

  // Fetch extra data on mount / when backend comes online
  useEffect(() => {
    if (!backendLive) return;

    api.listPipelineRuns().then((d) => setPipelineRuns(d.runs ?? [])).catch(() => {});
    api.getDecisionTimeline({}).then((d) => setDecisionSnapshots((d.timeline ?? []).slice(0, 5))).catch(() => {});
    api.ideaStats().then((d) => setIdeaStats(d)).catch(() => {});
    api.checkCompliance("global").then((d) => {
      const c = d.compliance;
      if (c && typeof c.score === "number") setComplianceScore(c.score);
      else if (c && typeof c.pass_rate === "number") setComplianceScore(c.pass_rate);
    }).catch(() => {});

    // Auto-refresh pipeline runs every 10s
    const interval = setInterval(() => {
      api.listPipelineRuns().then((d) => setPipelineRuns(d.runs ?? [])).catch(() => {});
    }, 10000);

    return () => clearInterval(interval);
  }, [backendLive]);

  // ---- Module categorization ----
  const modules = modulesData.modules ?? [];
  const totalModules = modules.length;

  const categoryBreakdown = useMemo(() => {
    const map: Record<string, { total: number; healthy: number }> = {};
    MODULE_CATEGORIES.forEach((c) => { map[c.label] = { total: 0, healthy: 0 }; });
    modules.forEach((m: any) => {
      const id = m.module_id ?? m.id ?? "";
      const status = m.status ?? m.health ?? "healthy";
      const match = MODULE_CATEGORIES.find((c) => id.startsWith(c.prefix));
      const key = match ? match.label : "Rdzeń";
      if (!map[key]) map[key] = { total: 0, healthy: 0 };
      map[key].total++;
      if (status === "healthy" || status === "ok" || status === "active") map[key].healthy++;
    });
    return map;
  }, [modules]);

  // ---- Expandable categories ----
  const [expandedCat, setExpandedCat] = useState<string | null>(null);

  const categoryModules = useMemo(() => {
    if (!expandedCat) return [];
    const cat = MODULE_CATEGORIES.find((c) => c.label === expandedCat);
    if (!cat) return [];
    return modules.filter((m: any) => {
      const id = m.module_id ?? m.id ?? "";
      return id.startsWith(cat.prefix);
    });
  }, [modules, expandedCat]);

  // ---- Active pipeline runs ----
  const activeRuns = useMemo(() => {
    return pipelineRuns.filter((r: any) => r.status === "running" || r.status === "pending" || r.status === "executing");
  }, [pipelineRuns]);

  // ---- Decision snapshots ----
  const recentDecisions = decisionSnapshots;

  // ---- Gate pass rate ----
  const gatePassRate = useMemo(() => {
    const gates = gatesData.gates ?? [];
    if (gates.length === 0) return null;
    const passed = gates.filter((g: any) => g.status === "pass" || g.status === "passed" || g.result === "pass").length;
    return Math.round((passed / gates.length) * 100);
  }, [gatesData]);

  // ---- Idea count ----
  const totalIdeas = useMemo(() => {
    if (ideaStats?.total) return ideaStats.total;
    if (ideaStats?.count) return ideaStats.count;
    return 0;
  }, [ideaStats]);

  // ---- System uptime (time since page load as proxy) ----
  const [uptimeSeconds, setUptimeSeconds] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const interval = setInterval(() => setUptimeSeconds(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${sec}s`;
    return `${sec}s`;
  };

  // ---- Submit idea handler ----
  const handleSubmitIdea = useCallback(() => {
    if (!ideaInput.trim()) return;
    if (backendLive) {
      api.submitIdea(ideaInput.trim()).catch(() => {});
    }
    router.push(`/idea-vault`);
  }, [ideaInput, backendLive, router]);

  // ---- Stats data ----
  const statsCards = [
    { label: "Wszystkie moduły", value: totalModules || "---", icon: Layers, color: "#2F6BFF", bg: "rgba(47,107,255,0.08)" },
    { label: "Aktywne przebiegi", value: activeRuns.length, icon: Activity, color: "#17C964", bg: "rgba(23,201,100,0.08)" },
    { label: "Bramki decyzji", value: gatePassRate !== null ? `${gatePassRate}%` : "---", icon: Shield, color: "#A855F7", bg: "rgba(168,85,247,0.08)" },
    { label: "Zgodność", value: complianceScore !== null ? `${complianceScore}%` : "---", icon: CheckCircle2, color: "#14B8A6", bg: "rgba(20,184,166,0.08)" },
    { label: "Wszystkie pomysły", value: totalIdeas || "---", icon: Lightbulb, color: "#F59E0B", bg: "rgba(245,158,11,0.08)" },
    { label: "Czas pracy systemu", value: formatUptime(uptimeSeconds), icon: Timer, color: "#06B6D4", bg: "rgba(6,182,212,0.08)" },
  ];

  return (
    <div className="space-y-5 min-h-screen bg-[#050816]">

      {/* ============================================================
          HEADER — Brand + Status + Quick Actions
          ============================================================ */}
      <FadeSection delay={0}>
        <Card
          className="relative overflow-hidden rounded-xl p-6 transition-all duration-300"
          style={{
            background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
            borderColor: isOk
              ? "rgba(23,201,100,0.35)"
              : isError
                ? "rgba(243,18,96,0.35)"
                : "rgba(148,163,184,0.08)",
            borderWidth: 1.5,
          }}
        >
          {/* Status glow */}
          <div
            className="absolute -top-20 -right-20 w-48 h-48 rounded-full opacity-20 blur-3xl pointer-events-none"
            style={{
              background: isOk
                ? "rgba(23,201,100,0.4)"
                : isError
                  ? "rgba(243,18,96,0.4)"
                  : "rgba(148,163,184,0.1)",
            }}
          />

          <div className="relative z-10 flex items-center justify-between">
            {/* Left: brand + status */}
            <div className="flex items-start gap-5">
              <div
                className="w-14 h-14 rounded-xl flex items-center justify-center shrink-0"
                style={{
                  background: isOk
                    ? "rgba(23,201,100,0.12)"
                    : isError
                      ? "rgba(243,18,96,0.12)"
                      : "rgba(47,107,255,0.08)",
                }}
              >
                <Brain className="w-7 h-7" style={{ color: isOk ? "#17C964" : isError ? "#F31260" : "#2F6BFF" }} />
              </div>
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h1 className="text-lg font-bold tracking-tight text-foreground">SYLION AEIS</h1>
                  <Badge
                    className={cn(
                      "text-[10px] font-semibold px-2.5 py-0.5",
                      isOk
                        ? "bg-emerald-500/15 text-emerald-400 border-emerald-400/20"
                        : isError
                          ? "bg-red-500/15 text-red-400 border-red-400/20"
                          : "bg-sylion-blue/15 text-sylion-blue border-sylion-blue/20",
                    )}
                  >
                    <span
                      className={cn(
                        "w-1.5 h-1.5 rounded-full mr-1.5",
                        isOk ? "bg-emerald-400 animate-pulse" : isError ? "bg-red-400" : "bg-sylion-blue"
                      )}
                    />
                    {isOk ? "NA ŻYWO" : isError ? "BŁĄD" : "POZA SIECIĄ"}
                  </Badge>
                  {!backendLive && (
                    <Badge variant="outline" className="text-[10px] border-sylion-red/30 text-sylion-red">
                      BACKEND NIEDOSTĘPNY
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">Autonomiczny system inteligencji inżynieryjnej v3.5</p>
                <div className="flex items-center gap-4 mt-3">
                  <div className="flex items-center gap-1.5">
                    <Radio className="w-3 h-3 text-muted-foreground/60" />
                    <span className="text-[10px] text-muted-foreground">Moduły</span>
                    <span className="text-[11px] font-semibold text-foreground">{health.modules || totalModules}</span>
                  </div>
                  <div className="w-px h-3 bg-white/10" />
                  <div className="flex items-center gap-1.5">
                    <Layers className="w-3 h-3 text-muted-foreground/60" />
                    <span className="text-[10px] text-muted-foreground">Endpointy</span>
                    <span className="text-[11px] font-semibold text-foreground">{health.endpoints || 0}</span>
                  </div>
                  <div className="w-px h-3 bg-white/10" />
                  <div className="flex items-center gap-1.5">
                    <Database className="w-3 h-3 text-muted-foreground/60" />
                    <span className="text-[10px] text-muted-foreground">DB</span>
                    <span className="text-[11px] font-semibold text-foreground">{health.db_mode || "---"}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: quick actions */}
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5 border-sylion-blue/25 text-sylion-blue hover:bg-sylion-blue/10"
                onClick={() => router.push("/idea-vault")}
              >
                <Lightbulb className="w-3.5 h-3.5" />
                Zgłoś pomysł
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5 border-sylion-green/25 text-sylion-green hover:bg-sylion-green/10"
                onClick={() => router.push("/pipeline")}
              >
                <Play className="w-3.5 h-3.5" />
                Uruchom pipeline
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5 border-sylion-amber/25 text-sylion-amber hover:bg-sylion-amber/10"
                onClick={() => router.push("/workspace")}
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                Otwórz workspace
              </Button>
            </div>
          </div>
        </Card>
      </FadeSection>

      {/* ============================================================
          STATS ROW — 6 metric cards
          ============================================================ */}
      <FadeSection delay={0.05}>
        <div className="grid grid-cols-6 gap-3">
          {statsCards.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.08 + i * 0.04 }}
            >
              <Card
                className="rounded-xl p-4 transition-all duration-300 hover:border-opacity-20"
                style={{
                  background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
                  borderColor: "rgba(148,163,184,0.06)",
                }}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{stat.label}</p>
                    <p className="text-2xl font-bold text-foreground tabular-nums">{stat.value}</p>
                  </div>
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ background: stat.bg }}
                  >
                    <stat.icon className="w-5 h-5" style={{ color: stat.color }} />
                  </div>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      </FadeSection>

      {/* ============================================================
          AEIS v2 SUMMARY — KPI panel for v2 plane (W15-W19)
          ============================================================ */}
      <FadeSection delay={0.09}>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded-md flex items-center justify-center"
              style={{ background: "rgba(168,85,247,0.15)" }}
            >
              <Sparkles className="w-3 h-3" style={{ color: "#A855F7" }} />
            </div>
            <h3 className="text-sm font-semibold text-foreground">
              AEIS v2 — przeglad
            </h3>
            <Badge variant="secondary" className="text-[10px]">
              W15-W19
            </Badge>
          </div>
          <AeisV2Summary />
        </div>
      </FadeSection>

      {/* ============================================================
          MAIN CONTENT — 4 sections in 2x2 grid
          ============================================================ */}
      <div className="grid grid-cols-12 gap-4">

        {/* ============================================================
            SECTION 1: System Health (7 cols, top-left)
            ============================================================ */}
        <FadeSection delay={0.12} className="col-span-7">
          <DarkCard>
            <SectionHeader
              icon={Hexagon}
              iconColor="#2F6BFF"
              title="Stan systemu"
              badge={`${totalModules} modułów`}
            />

            <div className="grid grid-cols-2 gap-2">
              {MODULE_CATEGORIES.map((cat, i) => {
                const breakdown = categoryBreakdown[cat.label] ?? { total: 0, healthy: 0 };
                const isExpanded = expandedCat === cat.label;
                const allHealthy = breakdown.total > 0 && breakdown.healthy === breakdown.total;
                const someDegraded = breakdown.total > 0 && breakdown.healthy < breakdown.total;

                return (
                  <div key={cat.label}>
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.3, delay: 0.15 + i * 0.03 }}
                      className={cn(
                        "relative p-3 rounded-lg border transition-all duration-200 cursor-pointer",
                        isExpanded && "ring-1 ring-opacity-30"
                      )}
                      style={{
                        background: cat.bgColor,
                        borderColor: isExpanded ? cat.borderColor : breakdown.total > 0 ? cat.borderColor : "rgba(148,163,184,0.06)",
                        ...(isExpanded ? { ringColor: cat.color } : {}),
                      }}
                      onClick={() => setExpandedCat(isExpanded ? null : cat.label)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <cat.icon className="w-4 h-4" style={{ color: cat.color }} />
                          <span className="text-[12px] font-medium" style={{ color: cat.color }}>
                            {cat.label}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {/* Status dots */}
                          <span className="flex items-center gap-1">
                            {allHealthy && breakdown.total > 0 && (
                              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                            )}
                            {someDegraded && (
                              <>
                                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                                <span className="w-2 h-2 rounded-full bg-amber-400" />
                              </>
                            )}
                            {breakdown.total === 0 && (
                              <span className="w-2 h-2 rounded-full bg-muted-foreground/30" />
                            )}
                          </span>
                          <span className="text-[10px] text-muted-foreground tabular-nums">
                            {breakdown.healthy}/{breakdown.total}
                          </span>
                          {isExpanded ? (
                            <ChevronDown className="w-3 h-3 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="w-3 h-3 text-muted-foreground" />
                          )}
                        </div>
                      </div>
                    </motion.div>

                    {/* Expanded module list */}
                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.25 }}
                          className="overflow-hidden"
                        >
                          <div className="mt-1 space-y-0.5 pl-3">
                            {categoryModules.map((m: any) => {
                              const mid = m.module_id ?? m.id ?? "unknown";
                              const mstatus = m.status ?? m.health ?? "unknown";
                              const isHealthy = mstatus === "healthy" || mstatus === "ok" || mstatus === "active";
                              const isDegraded = mstatus === "degraded" || mstatus === "busy";
                              return (
                                <div key={mid} className="flex items-center gap-2 px-2 py-1 rounded hover:bg-white/[0.02]">
                                  <span
                                    className={cn(
                                      "w-1.5 h-1.5 rounded-full shrink-0",
                                      isHealthy ? "bg-emerald-400" : isDegraded ? "bg-amber-400" : "bg-red-400"
                                    )}
                                  />
                                  <span className="text-[10px] text-muted-foreground truncate">{mid}</span>
                                  <span className="text-[9px] text-muted-foreground/50 ml-auto">{mstatus}</span>
                                </div>
                              );
                            })}
                            {categoryModules.length === 0 && (
                              <p className="text-[10px] text-muted-foreground/50 px-2 py-1">Nie wykryto modułów</p>
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          </DarkCard>
        </FadeSection>

        {/* ============================================================
            SECTION 2: Active Pipeline Runs (5 cols, top-right)
            ============================================================ */}
        <FadeSection delay={0.18} className="col-span-5">
          <DarkCard className="h-full flex flex-col">
            <SectionHeader
              icon={Activity}
              iconColor="#17C964"
              title="Aktywne przebiegi pipeline"
              badge={`${activeRuns.length} aktywne`}
              action={
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-[10px] text-muted-foreground hover:text-foreground gap-1"
                  onClick={() => router.push("/pipeline")}
                >
                  Pokaż wszystko <ArrowRight className="w-3 h-3" />
                </Button>
              }
            />

            <div className="flex-1 space-y-2.5 max-h-[380px] overflow-y-auto pr-1" style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(148,163,184,0.15) transparent" }}>
              {activeRuns.length === 0 && (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Play className="w-8 h-8 mb-2 opacity-30" />
                  <p className="text-xs">Brak aktywnych przebiegów</p>
                  <p className="text-[10px] mt-1 opacity-60">Zgłoś pomysł, aby zacząć</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3 h-7 text-[10px] gap-1.5 border-sylion-green/25 text-sylion-green hover:bg-sylion-green/10"
                    onClick={() => router.push("/idea-vault")}
                  >
                    <Lightbulb className="w-3 h-3" />
                    Zgłoś pomysł
                  </Button>
                </div>
              )}

              {activeRuns.map((run: any, i: number) => {
                const progress = run.progress ?? run.completion_pct ?? 0;
                const idea = run.idea ?? run.description ?? "Pipeline run";
                const status = run.status ?? "unknown";
                const ts = run.created_at ?? run.started_at;
                const tsStr = ts
                  ? (typeof ts === "number" && ts > 1e12
                    ? fmtDateTime(new Date(ts))
                    : fmtDateTime(ts))
                  : "---";

                const statusColor: Record<string, string> = {
                  running: "#17C964",
                  executing: "#2F6BFF",
                  pending: "#F59E0B",
                  queued: "#94A3B8",
                };

                return (
                  <motion.div
                    key={run.run_id ?? run.id ?? i}
                    initial={{ opacity: 0, x: 6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2, delay: 0.2 + i * 0.04 }}
                    className="p-3 rounded-lg border transition-colors hover:bg-white/[0.015]"
                    style={{
                      background: "rgba(15,22,41,0.6)",
                      borderColor: "rgba(148,163,184,0.06)",
                    }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <p className="text-[11px] font-medium text-foreground truncate pr-3 flex-1">{idea}</p>
                      <Badge
                        className="text-[9px] px-1.5 py-0 shrink-0"
                        style={{
                          background: `${statusColor[status] ?? "#94A3B8"}15`,
                          color: statusColor[status] ?? "#94A3B8",
                          borderColor: `${statusColor[status] ?? "#94A3B8"}30`,
                        }}
                      >
                        {status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1">
                        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(148,163,184,0.08)" }}>
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{
                              width: `${progress}%`,
                              background: progress >= 70 ? "#17C964" : progress >= 40 ? "#2F6BFF" : "#F59E0B",
                            }}
                          />
                        </div>
                      </div>
                      <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">{progress}%</span>
                    </div>
                    <div className="flex items-center gap-1.5 mt-1.5">
                      <Clock className="w-2.5 h-2.5 text-muted-foreground/40" />
                      <span className="text-[9px] text-muted-foreground/50">{tsStr}</span>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </DarkCard>
        </FadeSection>

        {/* ============================================================
            SECTION 3: Recent Decisions (7 cols, bottom-left)
            ============================================================ */}
        <FadeSection delay={0.24} className="col-span-7">
          <DarkCard>
            <SectionHeader
              icon={GitBranch}
              iconColor="#A855F7"
              title="Ostatnie decyzję"
              badge={`${recentDecisions.length} ostatnie`}
              action={
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-[10px] text-muted-foreground hover:text-foreground gap-1"
                  onClick={() => router.push("/decisions")}
                >
                  Pokaż wszystko <ArrowRight className="w-3 h-3" />
                </Button>
              }
            />

            <div className="space-y-1.5">
              {recentDecisions.length === 0 && (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <GitBranch className="w-6 h-6 mb-2 opacity-30" />
                  <p className="text-xs">Brak zapisanych decyzji</p>
                </div>
              )}

              {recentDecisions.map((dec: any, i: number) => {
                const dclass = dec.decision_class ?? "D0";
                const choice = dec.choice_made ?? dec.choice ?? "---";
                const gate = dec.gate_id ?? dec.gate ?? "---";
                const cascade = dec.cascade_status ?? "stable";
                const ts = dec.created_at ?? dec.timestamp;
                const tsStr = ts
                  ? (typeof ts === "number" && ts > 1e12
                    ? fmtDateTime(new Date(ts))
                    : fmtDateTime(ts))
                  : "---";

                const classColorMap: Record<string, string> = {
                  D0: "#17C964", D1: "#2F6BFF", D2: "#06B6D4",
                  D3: "#F59E0B", D4: "#F97316", D5: "#F31260",
                };
                const dcolor = classColorMap[dclass] ?? "#94A3B8";

                const isCascadeAlert = cascade === "cascade_pending" || cascade === "cascade_triggered";
                const isCascadeAcknowledged = cascade === "cascade_acknowledged";

                return (
                  <motion.div
                    key={dec.snapshot_id ?? dec.id ?? i}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2, delay: 0.28 + i * 0.04 }}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors hover:bg-white/[0.02]",
                      isCascadeAlert && "border border-sylion-red/20 bg-sylion-red/[0.03]",
                    )}
                  >
                    {/* Decision class badge */}
                    <Badge
                      className="text-[9px] font-bold px-1.5 py-0.5 shrink-0"
                      style={{
                        background: `${dcolor}15`,
                        color: dcolor,
                        borderColor: `${dcolor}30`,
                      }}
                    >
                      {dclass}
                    </Badge>

                    {/* Choice + gate */}
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] text-foreground truncate">{choice}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[9px] text-muted-foreground/60">{gate}</span>
                        <span className="text-[9px] text-muted-foreground/30">|</span>
                        <span className="text-[9px] text-muted-foreground/40">{tsStr}</span>
                      </div>
                    </div>

                    {/* Cascade status */}
                    {isCascadeAlert && (
                      <Badge className="text-[9px] px-1.5 py-0.5 bg-sylion-red/15 text-sylion-red border-sylion-red/20 shrink-0">
                        <AlertTriangle className="w-2.5 h-2.5 mr-0.5" />
                        CASCADE
                      </Badge>
                    )}
                    {isCascadeAcknowledged && (
                      <Badge className="text-[9px] px-1.5 py-0.5 bg-sylion-amber/15 text-sylion-amber border-sylion-amber/20 shrink-0">
                        <Eye className="w-2.5 h-2.5 mr-0.5" />
                        ACK
                      </Badge>
                    )}
                    {cascade === "stable" && (
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400/40 shrink-0" />
                    )}
                  </motion.div>
                );
              })}
            </div>
          </DarkCard>
        </FadeSection>

        {/* ============================================================
            SECTION 4: Quick Actions (5 cols, bottom-right)
            ============================================================ */}
        <FadeSection delay={0.30} className="col-span-5">
          <DarkCard className="h-full flex flex-col">
            <SectionHeader
              icon={Zap}
              iconColor="#F59E0B"
              title="Szybkie akcje"
            />

            <div className="flex-1 space-y-3">
              {/* Submit Idea inline */}
              <div className="p-3 rounded-lg border" style={{ background: "rgba(15,22,41,0.6)", borderColor: "rgba(148,163,184,0.06)" }}>
                <div className="flex items-center gap-2 mb-2">
                  <Lightbulb className="w-3.5 h-3.5 text-sylion-amber" />
                  <span className="text-[11px] font-medium text-foreground">Zgłoś pomysł</span>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={ideaInput}
                    onChange={(e) => setIdeaInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSubmitIdea()}
                    placeholder="Opisz swój pomysł..."
                    className="flex-1 h-8 px-3 rounded-md text-[11px] bg-[#0a0f1e] border border-white/[0.06] text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-sylion-blue/40 focus:ring-1 focus:ring-sylion-blue/20 transition-colors"
                  />
                  <Button
                    size="sm"
                    className="h-8 px-3 text-[10px] gap-1 bg-sylion-blue hover:bg-sylion-blue/80 text-white"
                    onClick={handleSubmitIdea}
                    disabled={!ideaInput.trim()}
                  >
                    <Send className="w-3 h-3" />
                    Wyślij
                  </Button>
                </div>
              </div>

              {/* Action buttons */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => router.push("/pipeline")}
                  className="flex items-center gap-2.5 p-3 rounded-lg border text-left transition-all duration-200 hover:bg-sylion-green/[0.04] hover:border-sylion-green/20"
                  style={{ background: "rgba(23,201,100,0.04)", borderColor: "rgba(23,201,100,0.12)" }}
                >
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "rgba(23,201,100,0.1)" }}>
                    <Play className="w-4 h-4 text-sylion-green" />
                  </div>
                  <div>
                    <p className="text-[11px] font-medium text-foreground">Uruchom pipeline</p>
                    <p className="text-[9px] text-muted-foreground">Wykonaj od początku</p>
                  </div>
                </button>

                <button
                  onClick={() => router.push("/workspace")}
                  className="flex items-center gap-2.5 p-3 rounded-lg border text-left transition-all duration-200 hover:bg-sylion-amber/[0.04] hover:border-sylion-amber/20"
                  style={{ background: "rgba(245,158,11,0.04)", borderColor: "rgba(245,158,11,0.12)" }}
                >
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "rgba(245,158,11,0.1)" }}>
                    <LayoutGrid className="w-4 h-4 text-sylion-amber" />
                  </div>
                  <div>
                    <p className="text-[11px] font-medium text-foreground">Otwórz workspace</p>
                    <p className="text-[9px] text-muted-foreground">Czat i Rada</p>
                  </div>
                </button>

                <button
                  onClick={() => router.push("/settings")}
                  className="flex items-center gap-2.5 p-3 rounded-lg border text-left transition-all duration-200 hover:bg-white/[0.02] hover:border-white/10"
                  style={{ background: "rgba(148,163,184,0.03)", borderColor: "rgba(148,163,184,0.08)" }}
                >
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "rgba(148,163,184,0.08)" }}>
                    <Settings className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-[11px] font-medium text-foreground">Pokaż ustawieńia</p>
                    <p className="text-[9px] text-muted-foreground">Klucze API i konfiguracja</p>
                  </div>
                </button>

                <button
                  onClick={() => router.push("/idea-vault")}
                  className="flex items-center gap-2.5 p-3 rounded-lg border text-left transition-all duration-200 hover:bg-sylion-blue/[0.04] hover:border-sylion-blue/20"
                  style={{ background: "rgba(47,107,255,0.04)", borderColor: "rgba(47,107,255,0.12)" }}
                >
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "rgba(47,107,255,0.1)" }}>
                    <FileText className="w-4 h-4 text-sylion-blue" />
                  </div>
                  <div>
                    <p className="text-[11px] font-medium text-foreground">Magazyn pomysłów</p>
                    <p className="text-[9px] text-muted-foreground">Przeglądaj wszystkie pomysły</p>
                  </div>
                </button>
              </div>

              {/* Backend offline warning */}
              {!backendLive && (
                <div className="flex items-center gap-2 mt-2 px-3 py-2 rounded-lg bg-sylion-red/[0.06] border border-sylion-red/15">
                  <AlertTriangle className="w-3.5 h-3.5 text-sylion-red" />
                  <p className="text-[10px] text-sylion-red">Backend niedostępny - dane na żywo są wyłączone. Uruchom backend, aby połączyć panel.</p>
                </div>
              )}
            </div>
          </DarkCard>
        </FadeSection>
      </div>
    </div>
  );
}
