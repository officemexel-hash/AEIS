"use client";

import { useState, useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  useHealth,
  useAutonomyStatus,
  useLifecycleStages,
  useLifecycleEntries,
  useDecisionGates,
  useModules,
} from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import type { ModuleLifecycle } from "@/lib/types";
import {
  Activity,
  ArrowRight,
  Bot,
  Brain,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clock,
  Eye,
  FileCheck,
  Gauge,
  GitBranch,
  Lock,
  MessageSquare,
  Rocket,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Unlock,
  User,
  Zap,
  Ban,
  AlertTriangle,
  Layers,
  XCircle,
  Hourglass,
  Users,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

/* ================================================================
   LIFECYCLE STAGE DEFINITIONS
   ================================================================ */

interface LifecycleStageDef {
  id: ModuleLifecycle;
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: React.ElementType;
}

const LIFECYCLE_STAGES: LifecycleStageDef[] = [
  { id: "draft", label: "Draft", color: "text-muted-foreground", bgColor: "bg-muted/20", borderColor: "border-border/30", icon: FileCheck },
  { id: "build", label: "Build", color: "text-sylion-blue", bgColor: "bg-sylion-blue/10", borderColor: "border-sylion-blue/20", icon: Zap },
  { id: "validate", label: "Validate", color: "text-sylion-blue", bgColor: "bg-sylion-blue/10", borderColor: "border-sylion-blue/20", icon: ShieldCheck },
  { id: "shadow", label: "Shadow", color: "text-sylion-amber", bgColor: "bg-sylion-amber/10", borderColor: "border-sylion-amber/20", icon: Eye },
  { id: "dual", label: "Dual", color: "text-sylion-amber", bgColor: "bg-sylion-amber/10", borderColor: "border-sylion-amber/20", icon: Layers },
  { id: "cutover", label: "Cutover", color: "text-primary", bgColor: "bg-primary/10", borderColor: "border-primary/20", icon: Rocket },
  { id: "stable", label: "Stable", color: "text-sylion-green", bgColor: "bg-sylion-green/10", borderColor: "border-sylion-green/20", icon: Shield },
  { id: "deprecated", label: "Deprecated", color: "text-sylion-red", bgColor: "bg-sylion-red/10", borderColor: "border-sylion-red/20", icon: Ban },
];

/* ================================================================
   AUTONOMY LEVEL DEFINITIONS (L0-L5)
   ================================================================ */

interface AutonomyLevel {
  level: number;
  key: string;
  label: string;
  description: string;
  icon: React.ElementType;
  capabilities: string[];
  requirements: string[];
}

const AUTONOMY_LEVELS: AutonomyLevel[] = [
  {
    level: 0, key: "L0", label: "Manual", description: "All decisions by human. AI provides no autonomous action.",
    icon: Lock, capabilities: ["Observation only", "Data collection", "Reporting"], requirements: [],
  },
  {
    level: 1, key: "L1", label: "Assisted", description: "AI suggests, human decides. Recommendations only.",
    icon: User, capabilities: ["Analysis & insights", "Pattern detection", "Recommendation engine"], requirements: ["Stable telemetry pipeline", "Recommendation accuracy > 70%"],
  },
  {
    level: 2, key: "L2", label: "Partial", description: "AI handles routine tasks, escalates complex decisions.",
    icon: Eye, capabilities: ["Routine task execution", "Automated monitoring", "Smart alerting"], requirements: ["Escalation framework tested", "Routine task accuracy > 90%", "Human override latency < 5s"],
  },
  {
    level: 3, key: "L3", label: "Conditional", description: "AI autonomous within defined bounds and policies.",
    icon: Zap, capabilities: ["Bounded autonomy", "Policy-driven actions", "Self-explanation"], requirements: ["Policy engine 100% coverage", "Self-explanation fidelity > 0.95", "30d stable operation at L2"],
  },
  {
    level: 4, key: "L4", label: "High", description: "AI autonomous with human oversight and veto.",
    icon: Rocket, capabilities: ["Complex decision making", "Multi-agent coordination", "Self-improvement loops"], requirements: ["Council voting active", "Veto mechanism < 2s", "60d stable operation at L3"],
  },
  {
    level: 5, key: "L5", label: "Full", description: "AI fully autonomous with continuous audit trail.",
    icon: Bot, capabilities: ["Full self-governance", "Autonomous architecture", "Continuous audit & evolution"], requirements: ["Self-improvement loop 90d stable", "Governance compliance 100%", "Council unanimous approval"],
  },
];

const DEFAULT_CURRENT_LEVEL = 2;

interface LifecycleModule {
  id: string;
  name: string;
  lifecycle: ModuleLifecycle;
  timeInStage: string;
  classLetter: string;
}

interface LifecycleModuleSource {
  module_id?: string;
  id?: string;
  name?: string;
  lifecycle?: string;
  stage?: string;
  time_in_stage?: string;
  stage_duration?: string;
  registered_at?: number;
  kind?: string;
  module_kind?: string;
  class?: string;
  module_class?: string;
}

interface GateRequirement {
  id: string;
  fromStage: ModuleLifecycle;
  toStage: ModuleLifecycle;
  title: string;
  requiredEvidence: string[];
  timeInStageReq: string;
  councilApproval: boolean;
  status: "pass" | "fail" | "pending";
}

interface GateRequirementSource {
  id?: string;
  gate_id?: string;
  from_stage?: string;
  source_stage?: string;
  to_stage?: string;
  target_stage?: string;
  title?: string;
  name?: string;
  required_evidence?: string[];
  evidence?: string[];
  requirements?: string[];
  time_in_stage_req?: string;
  min_time?: string;
  council_approval?: boolean;
  requires_council?: boolean;
  status?: string;
  result?: string;
}

/* ================================================================
   HELPERS
   ================================================================ */

/** Convert a unix-timestamp (seconds or ms) to a human-readable duration like "3d" or "5h". */
function fmtTimeInStage(ts: number | undefined | null): string {
  if (!ts) return "--";
  const then = ts > 1e12 ? ts : ts * 1000; // normalise to ms
  const diffMs = Date.now() - then;
  if (diffMs < 0) return "--";
  const hours = Math.floor(diffMs / 3_600_000);
  if (hours < 1) return "<1h";
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d`;
  return `${Math.floor(days / 30)}mo`;
}

/* ================================================================
   PAGE
   ================================================================ */

export default function LifecyclePage() {
  const { data: health } = useHealth();
  const { data: autonomyStatus } = useAutonomyStatus();
  const { data: lifecycleStagesData } = useLifecycleStages();
  const { data: lifecycleEntriesData } = useLifecycleEntries();
  const { data: gatesData } = useDecisionGates();
  const { data: modulesData } = useModules();
  const [activeTab, setActiveTab] = useState("pipeline");
  const [selectedModule, setSelectedModule] = useState<LifecycleModule | null>(null);

  const backendLive = health.status === "ok";

  /* ---- Resolve current autonomy level ---- */
  const liveLevel = autonomyStatus?.status?.current_level ?? autonomyStatus?.status?.level;
  const liveLevelNum = typeof liveLevel === "number"
    ? liveLevel
    : typeof liveLevel === "string"
      ? parseInt(liveLevel.replace(/[^0-9]/g, ""), 10)
      : NaN;
  const currentLevelIdx = !isNaN(liveLevelNum) && liveLevelNum >= 0 && liveLevelNum <= 5
    ? liveLevelNum
    : DEFAULT_CURRENT_LEVEL;
  const currentLevel = AUTONOMY_LEVELS[currentLevelIdx];

  /* ---- Resolve lifecycle modules ---- */
  const displayModules: LifecycleModule[] = useMemo(() => {
    if (!backendLive) return [];
    const source = lifecycleEntriesData?.entries?.length
      ? lifecycleEntriesData.entries
      : modulesData?.modules?.length
        ? modulesData.modules
        : [];
    return source.map((m: LifecycleModuleSource) => ({
      id: m.module_id ?? m.id ?? "",
      name: m.name ?? m.module_id ?? m.id ?? "",
      lifecycle: (m.lifecycle ?? m.stage ?? "draft") as ModuleLifecycle,
      timeInStage: m.time_in_stage ?? m.stage_duration ?? fmtTimeInStage(m.registered_at),
      classLetter: m.kind ?? m.module_kind ?? m.class ?? m.module_class ?? "?",
    }));
  }, [backendLive, lifecycleEntriesData, modulesData]);

  /* ---- Resolve gates ---- */
  const displayGates: GateRequirement[] = useMemo(() => {
    if (backendLive && gatesData?.gates?.length) {
      return gatesData.gates.map((g: GateRequirementSource) => ({
        id: g.id ?? g.gate_id ?? "",
        fromStage: (g.from_stage ?? g.source_stage ?? "draft") as ModuleLifecycle,
        toStage: (g.to_stage ?? g.target_stage ?? "build") as ModuleLifecycle,
        title: g.title ?? g.name ?? "",
        requiredEvidence: g.required_evidence ?? g.evidence ?? g.requirements ?? [],
        timeInStageReq: g.time_in_stage_req ?? g.min_time ?? "--",
        councilApproval: g.council_approval ?? g.requires_council ?? false,
        status: (g.status ?? g.result ?? "pending") as "pass" | "fail" | "pending",
      }));
    }
    return [];
  }, [backendLive, gatesData]);

  /* ---- Resolve lifecycle stages from API ---- */
  const apiStages = useMemo(() => {
    if (backendLive && lifecycleStagesData?.stages?.length) {
      return lifecycleStagesData.stages;
    }
    return null;
  }, [backendLive, lifecycleStagesData]);

  /* ---- Derived stats ---- */
  const activeStaging = displayModules.filter(
    (m) => m.lifecycle === "shadow" || m.lifecycle === "dual",
  ).length;
  const stableModules = displayModules.filter(
    (m) => m.lifecycle === "stable",
  ).length;

  /* ---- Gate status helpers ---- */
  const gateStatusIcon: Record<string, React.ElementType> = {
    pass: CheckCircle2,
    fail: XCircle,
    pending: Hourglass,
  };
  const gateStatusColor: Record<string, string> = {
    pass: "text-sylion-green",
    fail: "text-sylion-red",
    pending: "text-sylion-amber",
  };
  const gateStatusBg: Record<string, string> = {
    pass: "border-sylion-green/20 bg-sylion-green/5",
    fail: "border-sylion-red/20 bg-sylion-red/5",
    pending: "border-sylion-amber/20 bg-sylion-amber/5",
  };

  /* ---- Module detail panel ---- */
  const moduleHistory = useMemo(() => {
    if (!selectedModule) return [];
    const stageOrder = LIFECYCLE_STAGES.map((s) => s.id);
    const currentIdx = stageOrder.indexOf(selectedModule.lifecycle);
    return stageOrder.slice(0, currentIdx + 1).map((stage, i) => ({
      stage,
      completed: i < currentIdx,
      current: i === currentIdx,
      date: i === currentIdx ? "Now" : `${currentIdx - i}w ago`,
    }));
  }, [selectedModule]);

  return (
    <div className="space-y-6">
      {/* ============================================================
          HEADER
          ============================================================ */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
            <Activity className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Cykl życia modułów
              <HelpTip text="Postęp modułów przez etapy: draft → build → validate → shadow → dual → cutover → stable → deprecated. Każda zmiana etapu wymaga przejścia bramki — z dowodami i opcjonalnym zatwierdzeniem rady." />
            </h1>
            <p className="text-sm text-muted-foreground">
              Postęp etapów z egzekwowaniem bramek
            </p>
          </div>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px]",
            backendLive
              ? "border-sylion-green/30 text-sylion-green"
              : "border-border text-muted-foreground",
          )}
        >
          <span
            className={cn(
              "w-1.5 h-1.5 rounded-full mr-1.5",
              backendLive ? "bg-sylion-green" : "bg-muted-foreground",
            )}
          />
          {backendLive ? "NA ŻYWO" : "OFFLINE"}
        </Badge>
      </div>

      {/* ============================================================
          STATS ROW
          ============================================================ */}
      <div className="grid grid-cols-4 gap-3">
        <Card className="p-4 bg-[#0f1629] border-sylion-border">
          <div className="flex items-center gap-2 mb-1">
            <Layers className="w-3.5 h-3.5 text-primary" />
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Łącznie modułów
              <HelpTip text="Wszystkie moduły zarejestrowane w systemie, niezależnie od etapu cyklu życia." />
            </p>
          </div>
          <p className="text-2xl font-semibold text-primary">
            {displayModules.length}
          </p>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            w {apiStages?.length ?? LIFECYCLE_STAGES.length} etapach
          </p>
        </Card>

        <Card className="p-4 bg-[#0f1629] border-sylion-border">
          <div className="flex items-center gap-2 mb-1">
            <Eye className="w-3.5 h-3.5 text-sylion-amber" />
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Aktywne wdrożenia
              <HelpTip text="Moduły w fazie shadow (read-only mirror) lub dual (równoległe wykonanie). Najbardziej krytyczna faza — wymaga obserwacji." />
            </p>
          </div>
          <p className="text-2xl font-semibold text-sylion-amber">
            {activeStaging}
          </p>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            shadow / dual
          </p>
        </Card>

        <Card className="p-4 bg-[#0f1629] border-sylion-border">
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-sylion-green" />
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Stabilne
              <HelpTip text="Moduły gotowe do produkcji — przeszły wszystkie bramki walidacyjne." />
            </p>
          </div>
          <p className="text-2xl font-semibold text-sylion-green">
            {stableModules}
          </p>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            gotowe do produkcji
          </p>
        </Card>

        <Card className="p-4 bg-[#0f1629] border-sylion-border">
          <div className="flex items-center gap-2 mb-1">
            <Gauge className="w-3.5 h-3.5 text-sylion-blue" />
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Poziom autonomii
              <HelpTip text="Aktualny poziom L0-L5. Wyższe poziomy odblokowują bardziej autonomiczne działania bez zatwierdzenia operatora." />
            </p>
          </div>
          <p className="text-2xl font-semibold text-sylion-blue">
            {currentLevel.key}
          </p>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            {currentLevel.label}
          </p>
        </Card>
      </div>

      {/* ============================================================
          TABS
          ============================================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <HelpTip text="Pipeline cyklu życia: kanban modułów po etapach. Poziomy autonomii: L0-L5 z wymaganiami przejścia. Wymagania bramek: lista bramek transferu między etapami." />
        <TabsList>
          <TabsTrigger value="pipeline">
            <GitBranch className="w-3.5 h-3.5 mr-1.5" />
            Pipeline cyklu życia
          </TabsTrigger>
          <TabsTrigger value="autonomy">
            <Brain className="w-3.5 h-3.5 mr-1.5" />
            Poziomy autonomii
          </TabsTrigger>
          <TabsTrigger value="gates">
            <ShieldAlert className="w-3.5 h-3.5 mr-1.5" />
            Wymagania bramek
          </TabsTrigger>
        </TabsList>

        {/* ============================================================
            TAB 1: LIFECYCLE PIPELINE
            ============================================================ */}
        <TabsContent value="pipeline" className="mt-4">
          <div className="space-y-4">
            {/* Horizontal pipeline header */}
            <Card className="p-4 bg-[#0f1629] border-sylion-border overflow-x-auto">
              <div className="min-w-[900px]">
                <div className="flex items-center gap-0">
                  {LIFECYCLE_STAGES.map((stage, idx) => {
                    const StageIcon = stage.icon;
                    const modulesInStage = displayModules.filter(
                      (m) => m.lifecycle === stage.id,
                    );
                    return (
                      <div key={stage.id} className="flex items-center flex-1">
                        {/* Stage column */}
                        <div className="flex-1 min-w-0">
                          {/* Stage header */}
                          <div
                            className={cn(
                              "rounded-t-lg border-b-2 px-3 py-2.5 text-center",
                              stage.bgColor,
                              stage.borderColor,
                            )}
                          >
                            <div className="flex items-center justify-center gap-1.5 mb-0.5">
                              <StageIcon className={cn("w-3.5 h-3.5", stage.color)} />
                              <span className={cn("text-xs font-semibold", stage.color)}>
                                {stage.label}
                              </span>
                            </div>
                            <Badge
                              variant="outline"
                              className={cn("text-[8px] h-4", stage.borderColor, stage.color)}
                            >
                              {modulesInStage.length} moduł{modulesInStage.length !== 1 ? "ów" : ""}
                            </Badge>
                          </div>

                          {/* Module cards */}
                          <div className="space-y-1.5 p-2 min-h-[120px]">
                            {modulesInStage.map((mod) => (
                              <motion.button
                                key={mod.id}
                                initial={{ opacity: 0, y: 4 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.2 }}
                                onClick={() =>
                                  setSelectedModule(
                                    selectedModule?.id === mod.id ? null : mod,
                                  )
                                }
                                className={cn(
                                  "w-full text-left p-2 rounded-md border text-[10px] transition-colors hover:bg-muted/20",
                                  stage.borderColor,
                                  selectedModule?.id === mod.id && "ring-1 ring-primary/40",
                                )}
                              >
                                <div className="flex items-center justify-between mb-0.5">
                                  <span className="font-medium truncate text-[11px]">
                                    {mod.name}
                                  </span>
                                  <Badge
                                    variant="outline"
                                    className={cn(
                                      "text-[7px] h-3.5 shrink-0 ml-1",
                                      stage.borderColor,
                                      stage.color,
                                    )}
                                  >
                                    {mod.classLetter}
                                  </Badge>
                                </div>
                                <div className="flex items-center gap-1 text-muted-foreground">
                                  <Clock className="w-2.5 h-2.5" />
                                  <span>{mod.timeInStage}</span>
                                </div>
                              </motion.button>
                            ))}
                            {modulesInStage.length === 0 && (
                              <div className="flex items-center justify-center h-16 text-[10px] text-muted-foreground/40">
                                Pusty
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Arrow connector */}
                        {idx < LIFECYCLE_STAGES.length - 1 && (
                          <div className="flex items-center px-0.5 self-start mt-3">
                            <div className="flex items-center gap-0">
                              <div className="w-3 h-px bg-border/50" />
                              <ChevronRight className="w-3 h-3 text-muted-foreground/40" />
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </Card>

            {/* Module detail panel */}
            <AnimatePresence>
              {selectedModule && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <Card className="p-4 bg-[#0f1629] border-primary/20">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <CircleDot className="w-4 h-4 text-primary" />
                        <h3 className="text-sm font-semibold">{selectedModule.name}</h3>
                        <Badge variant="outline" className="text-[8px] h-4 font-mono">
                          {selectedModule.id}
                        </Badge>
                      </div>
                      <button
                        onClick={() => setSelectedModule(null)}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Stage history */}
                    <div className="flex items-center gap-1 flex-wrap">
                      {moduleHistory.map((entry, i) => {
                        const stageDef = LIFECYCLE_STAGES.find(
                          (s) => s.id === entry.stage,
                        );
                        if (!stageDef) return null;
                        return (
                          <div key={entry.stage} className="flex items-center">
                            <div
                              className={cn(
                                "flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-[10px]",
                                entry.current
                                  ? "border-primary/30 bg-primary/10"
                                  : "border-border/20 bg-muted/10",
                              )}
                            >
                              {entry.completed ? (
                                <CheckCircle2 className="w-3 h-3 text-sylion-green" />
                              ) : (
                                <CircleDot className={cn("w-3 h-3", stageDef.color, entry.current && "animate-pulse")} />
                              )}
                              <span className={cn(entry.current ? "text-primary font-medium" : "text-muted-foreground")}>
                                {stageDef.label}
                              </span>
                              <span className="text-muted-foreground/60">{entry.date}</span>
                            </div>
                            {i < moduleHistory.length - 1 && (
                              <ChevronRight className="w-3 h-3 text-muted-foreground/30 mx-0.5" />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </TabsContent>

        {/* ============================================================
            TAB 2: AUTONOMY LEVELS
            ============================================================ */}
        <TabsContent value="autonomy" className="mt-4">
          <div className="grid grid-cols-12 gap-4">
            {/* L0-L5 vertical scale */}
            <Card className="col-span-5 p-5 bg-[#0f1629] border-sylion-border">
              <div className="flex items-center gap-2 mb-4">
                <Gauge className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold">
                  Skala autonomii
                  <HelpTip text="L0-L5 — od ręcznego przez asysty, częściową, warunkową, wysoką do pełnej autonomii. Każdy poziom wymaga spełnienia wymagań." />
                </h3>
                <Badge variant="secondary" className="text-[10px]">
                  {currentLevel.key} - {currentLevel.label}
                </Badge>
              </div>

              <div className="space-y-2">
                {[...AUTONOMY_LEVELS].reverse().map((lvl) => {
                  const isCompleted = lvl.level < currentLevelIdx;
                  const isActive = lvl.level === currentLevelIdx;
                  const isLocked = lvl.level > currentLevelIdx;
                  const LIcon = lvl.icon;

                  return (
                    <motion.div
                      key={lvl.key}
                      initial={false}
                      animate={isActive ? { scale: [1, 1.01, 1] } : {}}
                      transition={{ duration: 2, repeat: Infinity, repeatType: "loop" }}
                    >
                      <div
                        className={cn(
                          "p-3 rounded-lg border transition-all",
                          isActive && "border-primary/40 bg-primary/5 ring-1 ring-primary/20 shadow-lg shadow-primary/10",
                          isCompleted && "border-sylion-green/20 bg-sylion-green/5",
                          isLocked && "border-border/20 bg-muted/5 opacity-50",
                        )}
                      >
                        <div className="flex items-center gap-3">
                          <div
                            className={cn(
                              "w-10 h-10 rounded-lg border-2 flex items-center justify-center shrink-0",
                              isActive && "border-primary/60 bg-primary/10",
                              isCompleted && "border-sylion-green/40 bg-sylion-green/10",
                              isLocked && "border-border/30 bg-muted/20",
                            )}
                          >
                            <LIcon
                              className={cn(
                                "w-4 h-4",
                                isActive && "text-primary",
                                isCompleted && "text-sylion-green",
                                isLocked && "text-muted-foreground/40",
                              )}
                            />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span
                                className={cn(
                                  "text-sm font-bold",
                                  isActive && "text-primary",
                                  isCompleted && "text-sylion-green",
                                  isLocked && "text-muted-foreground/40",
                                )}
                              >
                                {lvl.key}
                              </span>
                              <span
                                className={cn(
                                  "text-xs font-medium",
                                  isActive ? "text-primary/80" : isCompleted ? "text-sylion-green/80" : "text-muted-foreground/50",
                                )}
                              >
                                {lvl.label}
                              </span>
                              {isActive && (
                                <Badge variant="outline" className="text-[8px] h-4 border-primary/30 text-primary animate-pulse">
                                  AKTUALNY
                                </Badge>
                              )}
                              {isCompleted && (
                                <CheckCircle2 className="w-3 h-3 text-sylion-green" />
                              )}
                            </div>
                            <p className={cn("text-[10px] mt-0.5", isActive ? "text-foreground/70" : "text-muted-foreground/60")}>
                              {lvl.description}
                            </p>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </Card>

            {/* Capabilities & Requirements */}
            <div className="col-span-7 space-y-4">
              {/* Current level detail */}
              <Card className="p-5 bg-[#0f1629] border-sylion-border">
                <div className="flex items-center gap-2 mb-4">
                  <Zap className="w-4 h-4 text-primary" />
                  <h3 className="text-sm font-semibold">
                    {currentLevel.key}: Możliwości {currentLevel.label}
                    <HelpTip text="Funkcje dostępne na obecnym poziomie autonomii. Wyższe poziomy dodają więcej autonomicznych zachowań." />
                  </h3>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {currentLevel.capabilities.map((cap, i) => (
                    <div
                      key={i}
                      className="p-2.5 rounded-md border border-primary/15 bg-primary/5 text-center"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 text-primary mx-auto mb-1" />
                      <span className="text-[10px] text-foreground/80">{cap}</span>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Requirements to reach next level */}
              {currentLevelIdx < 5 && (
                <Card className="p-5 bg-[#0f1629] border-sylion-amber/15">
                  <div className="flex items-center gap-2 mb-4">
                    <Lock className="w-4 h-4 text-sylion-amber" />
                    <h3 className="text-sm font-semibold">
                      Wymagania dla {AUTONOMY_LEVELS[currentLevelIdx + 1].key}: {AUTONOMY_LEVELS[currentLevelIdx + 1].label}
                      <HelpTip text="Lista wymagań do spełnienia, aby przejść na wyższy poziom autonomii. Wszystkie muszą zostać zwalidowane przez radę." />
                    </h3>
                  </div>
                  <div className="space-y-2">
                    {AUTONOMY_LEVELS[currentLevelIdx + 1].requirements.map((req, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <ArrowRight className="w-3 h-3 text-sylion-amber shrink-0" />
                        <span className="text-[11px] text-muted-foreground">{req}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* Autonomy limitations from API */}
              <Card className="p-5 bg-[#0f1629] border-sylion-border">
                <div className="flex items-center gap-2 mb-4">
                  <ShieldAlert className="w-4 h-4 text-sylion-red" />
                  <h3 className="text-sm font-semibold">
                    Ograniczenia autonomii
                    <HelpTip text="Polityki bezpieczeństwa egzekwowane na obecnym poziomie autonomii. Niektóre ograniczenia są usuwane przy wyższych poziomach." />
                  </h3>
                </div>
                <div className="space-y-2">
                  {currentLevelIdx < 3 && (
                    <>
                      <div className="flex items-start gap-2 p-2.5 rounded-md border border-sylion-amber/15 bg-sylion-amber/5">
                        <AlertTriangle className="w-3.5 h-3.5 text-sylion-amber mt-0.5 shrink-0" />
                        <div>
                          <p className="text-[11px] font-medium text-sylion-amber">Human-in-the-loop required</p>
                          <p className="text-[10px] text-muted-foreground">Critical decisions require explicit human approval before execution.</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-2 p-2.5 rounded-md border border-sylion-blue/15 bg-sylion-blue/5">
                        <MessageSquare className="w-3.5 h-3.5 text-sylion-blue mt-0.5 shrink-0" />
                        <div>
                          <p className="text-[11px] font-medium text-sylion-blue">Self-explanation limited</p>
                          <p className="text-[10px] text-muted-foreground">Decision rationale explanations are generated only for escalated items.</p>
                        </div>
                      </div>
                    </>
                  )}
                  {currentLevelIdx >= 3 && currentLevelIdx < 5 && (
                    <>
                      <div className="flex items-start gap-2 p-2.5 rounded-md border border-sylion-green/15 bg-sylion-green/5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-sylion-green mt-0.5 shrink-0" />
                        <div>
                          <p className="text-[11px] font-medium text-sylion-green">Bounded autonomy active</p>
                          <p className="text-[10px] text-muted-foreground">AI operates within policy-defined boundaries with human veto capability.</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-2 p-2.5 rounded-md border border-sylion-amber/15 bg-sylion-amber/5">
                        <Users className="w-3.5 h-3.5 text-sylion-amber mt-0.5 shrink-0" />
                        <div>
                          <p className="text-[11px] font-medium text-sylion-amber">Council oversight required</p>
                          <p className="text-[10px] text-muted-foreground">D3+ decisions need council voting quorum for approval.</p>
                        </div>
                      </div>
                    </>
                  )}
                  {currentLevelIdx === 5 && (
                    <div className="flex items-start gap-2 p-2.5 rounded-md border border-sylion-green/15 bg-sylion-green/5">
                      <Shield className="w-3.5 h-3.5 text-sylion-green mt-0.5 shrink-0" />
                      <div>
                        <p className="text-[11px] font-medium text-sylion-green">Full self-governance</p>
                        <p className="text-[10px] text-muted-foreground">Complete autonomous operation with continuous audit trail and self-improvement.</p>
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ============================================================
            TAB 3: GATE REQUIREMENTS
            ============================================================ */}
        <TabsContent value="gates" className="mt-4">
          <Card className="p-4 bg-[#0f1629] border-sylion-border">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-semibold">
                  Bramki przejścia cyklu życia
                  <HelpTip text="Lista bramek wymaganych do przejścia modułu między etapami. Każda bramka ma wymagane dowody, czas w etapie i opcjonalnie zatwierdzenie rady." />
                </h3>
              </div>
              <div className="flex items-center gap-2">
                {displayGates.filter((g) => g.status === "pass").length > 0 && (
                  <Badge variant="outline" className="text-[10px] h-5 border-sylion-green/30 text-sylion-green">
                    <CheckCircle2 className="w-3 h-3 mr-1" />
                    {displayGates.filter((g) => g.status === "pass").length} przeszło
                  </Badge>
                )}
                {displayGates.filter((g) => g.status === "pending").length > 0 && (
                  <Badge variant="outline" className="text-[10px] h-5 border-sylion-amber/30 text-sylion-amber">
                    <Hourglass className="w-3 h-3 mr-1" />
                    {displayGates.filter((g) => g.status === "pending").length} oczekuje
                  </Badge>
                )}
                {displayGates.filter((g) => g.status === "fail").length > 0 && (
                  <Badge variant="outline" className="text-[10px] h-5 border-sylion-red/30 text-sylion-red">
                    <XCircle className="w-3 h-3 mr-1" />
                    {displayGates.filter((g) => g.status === "fail").length} nieudane
                  </Badge>
                )}
              </div>
            </div>

            <div className="space-y-3">
              {displayGates.map((gate) => {
                const GIcon = gateStatusIcon[gate.status];
                const fromDef = LIFECYCLE_STAGES.find((s) => s.id === gate.fromStage);
                const toDef = LIFECYCLE_STAGES.find((s) => s.id === gate.toStage);

                return (
                  <motion.div
                    key={gate.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={cn(
                      "p-4 rounded-lg border transition-colors",
                      gateStatusBg[gate.status],
                    )}
                  >
                    {/* Gate header */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <GIcon className={cn("w-4 h-4", gateStatusColor[gate.status])} />
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-muted-foreground">{gate.id}</span>
                            <span className="text-sm font-semibold">{gate.title}</span>
                          </div>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            {fromDef && (
                              <Badge variant="outline" className={cn("text-[8px] h-4", fromDef.borderColor, fromDef.color)}>
                                {fromDef.label}
                              </Badge>
                            )}
                            <ArrowRight className="w-3 h-3 text-muted-foreground" />
                            {toDef && (
                              <Badge variant="outline" className={cn("text-[8px] h-4", toDef.borderColor, toDef.color)}>
                                {toDef.label}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[9px] h-5",
                            gate.status === "pass" && "border-sylion-green/30 text-sylion-green",
                            gate.status === "fail" && "border-sylion-red/30 text-sylion-red",
                            gate.status === "pending" && "border-sylion-amber/30 text-sylion-amber",
                          )}
                        >
                          <GIcon className="w-2.5 h-2.5 mr-1" />
                          {gate.status.toUpperCase()}
                        </Badge>
                        {gate.councilApproval && (
                          <Badge variant="outline" className="text-[8px] h-5 border-primary/30 text-primary">
                            <Users className="w-2.5 h-2.5 mr-1" />
                            Council
                          </Badge>
                        )}
                      </div>
                    </div>

                    {/* Evidence & time requirements */}
                    <div className="grid grid-cols-12 gap-3">
                      <div className="col-span-7">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider font-medium mb-1.5">
                          Wymagane dowody
                          <HelpTip text="Artefakty, logi i certyfikaty potrzebne do otwarcia bramki. Lista budowana z kontraktu kanonicznego." />
                        </p>
                        <div className="space-y-1">
                          {gate.requiredEvidence.map((ev, i) => (
                            <div key={i} className="flex items-center gap-1.5">
                              {gate.status === "pass" ? (
                                <CheckCircle2 className="w-2.5 h-2.5 text-sylion-green shrink-0" />
                              ) : (
                                <ArrowRight className="w-2.5 h-2.5 text-muted-foreground shrink-0" />
                              )}
                              <span className="text-[10px] text-muted-foreground">{ev}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="col-span-3">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider font-medium mb-1.5">
                          Czas w etapie
                          <HelpTip text="Minimalny czas, jaki moduł musi spędzić w bieżącym etapie przed przejściem dalej." />
                        </p>
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3 h-3 text-muted-foreground" />
                          <span className="text-[10px] text-foreground/70">{gate.timeInStageReq}</span>
                        </div>
                      </div>
                      <div className="col-span-2">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wider font-medium mb-1.5">
                          Zatwierdzenie
                          <HelpTip text="Auto = bramka otwierana automatycznie po spełnieniu warunków. Council = wymaga głosowania rady." />
                        </p>
                        <div className="flex items-center gap-1.5">
                          {gate.councilApproval ? (
                            <>
                              <Users className="w-3 h-3 text-primary" />
                              <span className="text-[10px] text-primary">Council</span>
                            </>
                          ) : (
                            <>
                              <Unlock className="w-3 h-3 text-muted-foreground" />
                              <span className="text-[10px] text-muted-foreground">Auto</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
