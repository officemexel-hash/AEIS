"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { api } from "@/lib/api/client";
import {
  useHealth,
  useExplanations,
  useImprovements,
  useSelfObservation,
  useAutonomyStatus,
  useRuntimeAgents,
  useAgentRuntimeStats,
  useAgentExecutions,
} from "@/lib/api/hooks";
import { cn, fmtDateTime } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Bot,
  Eye,
  Brain,
  Lightbulb,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  MessageCircle,
  Shield,
  Zap,
  Cpu,
  TrendingUp,
  Sparkles,
  Gauge,
  ArrowRight,
  BarChart3,
  WifiOff,
  Plus,
  Save,
  Trash2,
  Play,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Explanation {
  id: string;
  decision_id: string;
  rationale: string;
  source_module: string;
  confidence: number;
  validated: boolean;
  timestamp: string;
}

interface Improvement {
  id: string;
  text: string;
  priority: "critical" | "high" | "medium" | "low";
  status: "proposed" | "in-progress" | "applied";
  module: string;
  timestamp: string;
}

interface SelfObsData {
  mode: string;
  metrics: Record<string, number>;
  status: string;
  [key: string]: any;
}

interface AgentForm {
  name: string;
  agent_type: string;
  provider: string;
  model_id: string;
  system_prompt: string;
  max_tokens: number;
  temperature: number;
  tools: string;
  capabilities: string;
  status: string;
}

const defaultAgentForm: AgentForm = {
  name: "Planista AEIS",
  agent_type: "planner",
  provider: "openai",
  model_id: "gpt-4.1",
  system_prompt: "Jesteś agentem AEIS. Pracujesz zgodnie z HumanGate, polityką kosztów, audytem i regułami Rady.",
  max_tokens: 4096,
  temperature: 0.3,
  tools: "filesystem,terminal,browser",
  capabilities: "planowanie,analiza,wykonanie,testy",
  status: "active",
};

const agentTypeOptions = ["planner", "coder", "critic", "qa", "security", "funding", "runtime", "memory", "custom"];
const providerOptions = ["openai", "anthropic", "google", "kimi", "z_ai", "openrouter", "perplexity", "local"];
const statusOptions = ["active", "paused", "disabled"];
const statusLabels: Record<string, string> = {
  active: "aktywny",
  paused: "pauza",
  disabled: "wyłączony",
  healthy: "zdrowy",
  degraded: "zdegradowany",
  critical: "krytyczny",
  unknown: "nieznany",
};

const autonomyLabels: Record<string, string> = {
  MANUAL: "RĘCZNY",
  SUPERVISED: "NADZOROWANY",
  AUTONOMOUS: "AUTONOMICZNY",
};

/* ============================================================
   Color Maps
   ============================================================ */

const priorityBadgeMap: Record<string, string> = {
  critical: "border-sylion-red/30 text-sylion-red",
  high: "border-orange-400/30 text-orange-400",
  medium: "border-sylion-amber/30 text-sylion-amber",
  low: "border-sylion-blue/30 text-sylion-blue",
};

const priorityBgMap: Record<string, string> = {
  critical: "border-sylion-red/15 bg-sylion-red/3",
  high: "border-orange-400/15 bg-orange-400/3",
  medium: "border-sylion-amber/15 bg-sylion-amber/3",
  low: "border-sylion-blue/15 bg-sylion-blue/3",
};

const impStatusBadge: Record<string, string> = {
  proposed: "border-muted-foreground/30 text-muted-foreground",
  "in-progress": "border-sylion-blue/30 text-sylion-blue",
  applied: "border-sylion-green/30 text-sylion-green",
};

const impStatusDot: Record<string, string> = {
  proposed: "bg-muted-foreground",
  "in-progress": "bg-sylion-blue",
  applied: "bg-sylion-green",
};

const confidenceColor = (c: number) =>
  c >= 0.9 ? "text-sylion-green" : c >= 0.8 ? "text-sylion-amber" : "text-sylion-red";

const confidenceBarColor = (c: number) =>
  c >= 0.9 ? "bg-sylion-green" : c >= 0.8 ? "bg-sylion-amber" : "bg-sylion-red";

const obsModeBadge: Record<string, string> = {
  active: "border-sylion-green/30 text-sylion-green",
  passive: "border-sylion-amber/30 text-sylion-amber",
  degraded: "border-sylion-red/30 text-sylion-red",
};

const obsStatusColor: Record<string, string> = {
  healthy: "text-sylion-green",
  degraded: "text-sylion-amber",
  critical: "text-sylion-red",
};

function labelStatus(status: string | undefined): string {
  if (!status) return statusLabels.unknown;
  return statusLabels[status] ?? status;
}

function labelAutonomy(stage: string | undefined): string {
  if (!stage) return "---";
  return autonomyLabels[stage] ?? stage;
}

/* ============================================================
   Main Page
   ============================================================ */

export default function AgentsPage() {
  const { data: health } = useHealth();
  const { data: explanationsData } = useExplanations();
  const { data: improvementsData } = useImprovements();
  const { data: selfObsData } = useSelfObservation();
  const { data: autonomyData } = useAutonomyStatus();
  const { data: runtimeAgentsData } = useRuntimeAgents();
  const { data: agentRuntimeStatsData } = useAgentRuntimeStats();
  const { data: agentExecutionsData } = useAgentExecutions(20);

  const [activeTab, setActiveTab] = useState<string>("explanations");
  const [agentForm, setAgentForm] = useState<AgentForm>(defaultAgentForm);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [localRuntimeAgents, setLocalRuntimeAgents] = useState<any[] | null>(null);
  const [agentActionStatus, setAgentActionStatus] = useState("");
  const [agentBusy, setAgentBusy] = useState("");

  const backendChecking = health.status === "unknown";
  const backendLive = health.status === "ok" || backendChecking;

  const updateAgentForm = (field: keyof AgentForm, value: string | number) => {
    setAgentForm((prev) => ({ ...prev, [field]: value }));
  };

  const refreshAgents = async () => {
    const data = await api.listRuntimeAgents();
    setLocalRuntimeAgents(Array.isArray(data.agents) ? data.agents : []);
  };

  const registerAgent = async () => {
    setAgentBusy("register");
    setAgentActionStatus("");
    try {
      const created = await api.registerRuntimeAgent(agentForm);
      await api.updateRuntimeAgent(created.agent_id, { status: agentForm.status });
      await refreshAgents();
      setSelectedAgentId(created.agent_id);
      setAgentActionStatus(`Zarejestrowano agenta ${created.name || created.agent_id}.`);
    } catch (err: any) {
      setAgentActionStatus(`Błąd rejestracji agenta: ${err.message || String(err)}`);
    } finally {
      setAgentBusy("");
    }
  };

  const saveSelectedAgent = async () => {
    if (!selectedAgentId) {
      setAgentActionStatus("Wybierz agenta do konfiguracji.");
      return;
    }
    setAgentBusy("save");
    setAgentActionStatus("");
    try {
      const saved = await api.updateRuntimeAgent(selectedAgentId, agentForm);
      await refreshAgents();
      setAgentActionStatus(`Zapisano konfigurację agenta ${saved.name || selectedAgentId}.`);
    } catch (err: any) {
      setAgentActionStatus(`Błąd zapisu konfiguracji: ${err.message || String(err)}`);
    } finally {
      setAgentBusy("");
    }
  };

  const deleteSelectedAgent = async () => {
    if (!selectedAgentId) {
      setAgentActionStatus("Wybierz agenta do usunięcia.");
      return;
    }
    setAgentBusy("delete");
    setAgentActionStatus("");
    try {
      await api.deleteRuntimeAgent(selectedAgentId);
      await refreshAgents();
      setSelectedAgentId("");
      setAgentActionStatus("Agent został usunięty z runtime.");
    } catch (err: any) {
      setAgentActionStatus(`Błąd usuwania agenta: ${err.message || String(err)}`);
    } finally {
      setAgentBusy("");
    }
  };

  const runSmokeTask = async () => {
    if (!selectedAgentId) {
      setAgentActionStatus("Wybierz agenta do testu.");
      return;
    }
    setAgentBusy("smoke");
    setAgentActionStatus("");
    try {
      const execution = await api.executeRuntimeAgent(selectedAgentId, {
        task: "Self-check: opisz sw?ją rolę, model, limit tokenów i jedną zasadę HumanGate.",
        context: "Operator uruchomił test dymny z dashboardu Agenty AEIS.",
      });
      setAgentActionStatus(`Uruchomiono test agenta: ${execution.execution_id || "wykonanie utworzone"}.`);
    } catch (err: any) {
      setAgentActionStatus(`Błąd testu agenta: ${err.message || String(err)}`);
    } finally {
      setAgentBusy("");
    }
  };

  const loadAgentIntoForm = (agent: any) => {
    setSelectedAgentId(agent.agent_id);
    setAgentForm({
      name: agent.name || "",
      agent_type: agent.agent_type || "custom",
      provider: agent.provider || "openai",
      model_id: agent.model_id || "",
      system_prompt: agent.system_prompt || "",
      max_tokens: Number(agent.max_tokens ?? 4096),
      temperature: Number(agent.temperature ?? 0.7),
      tools: Array.isArray(agent.tools) ? agent.tools.join(",") : agent.tools || "",
      capabilities: Array.isArray(agent.capabilities) ? agent.capabilities.join(",") : agent.capabilities || "",
      status: agent.status || "active",
    });
  };

  /* ---- Resolve data from backend ---- */

  const displayExplanations: Explanation[] = useMemo(() => {
    if (explanationsData?.explanations?.length) {
      return explanationsData.explanations.map((e: any) => ({
        id: e.id ?? e.explanation_id ?? "",
        decision_id: e.decision_id ?? e.decisionId ?? "",
        rationale: e.rationale ?? e.explanation ?? e.text ?? "",
        source_module: e.source_module ?? e.module ?? e.source ?? "",
        confidence: e.confidence ?? 0.5,
        validated: e.validated ?? false,
        timestamp: e.timestamp ?? e.created_at ?? new Date().toISOString(),
      }));
    }
    return [];
  }, [explanationsData]);

  const displayImprovements: Improvement[] = useMemo(() => {
    if (improvementsData?.items?.length) {
      return improvementsData.items.map((i: any) => ({
        id: i.id ?? i.improvement_id ?? "",
        text: i.text ?? i.description ?? i.improvement ?? "",
        priority: i.priority ?? "medium",
        status: i.status ?? "proposed",
        module: i.module ?? i.source_module ?? "",
        timestamp: i.timestamp ?? i.created_at ?? new Date().toISOString(),
      }));
    }
    return [];
  }, [improvementsData]);

  const displaySelfObs: SelfObsData = useMemo(() => {
    if (selfObsData?.mode) {
      return {
        mode: selfObsData.mode ?? "active",
        status: selfObsData.status ?? "healthy",
        metrics: selfObsData.metrics ?? {},
        observation_loop_ms: selfObsData.observation_loop_ms ?? 0,
        anomaly_score: selfObsData.anomaly_score ?? 0,
        last_cycle: selfObsData.last_cycle ?? "",
        cycles_completed: selfObsData.cycles_completed ?? 0,
        anomalies_detected: selfObsData.anomalies_detected ?? 0,
        self_repairs_triggered: selfObsData.self_repairs_triggered ?? 0,
      };
    }
    return { mode: "active", status: "healthy", metrics: {} };
  }, [selfObsData]);

  const displayAutonomy = useMemo(() => {
    if (autonomyData?.status) {
      const s = autonomyData.status;
      return {
        current_stage: s.current_stage ?? "SUPERVISED",
        stage_index: s.stage_index ?? 2,
        available_actions: s.available_actions ?? 0,
        pending_approvals: s.pending_approvals ?? 0,
        escalation_count: s.escalation_count ?? 0,
      };
    }
    return { current_stage: "SUPERVISED", stage_index: 2, available_actions: 0, pending_approvals: 0, escalation_count: 0 };
  }, [autonomyData]);

  const runtimeAgents = useMemo(() => {
    if (localRuntimeAgents) return localRuntimeAgents;
    return Array.isArray(runtimeAgentsData?.agents) ? runtimeAgentsData.agents : [];
  }, [runtimeAgentsData, localRuntimeAgents]);

  const agentExecutions = useMemo(() => {
    return Array.isArray(agentExecutionsData?.executions) ? agentExecutionsData.executions : [];
  }, [agentExecutionsData]);

  const agentRuntimeStats = useMemo(() => {
    return agentRuntimeStatsData ?? {};
  }, [agentRuntimeStatsData]);

  /* ---- Computed stats ---- */

  const stats = useMemo(() => {
    const validated = displayExplanations.filter((e) => e.validated).length;
    const applied = displayImprovements.filter((i) => i.status === "applied").length;
    const inProgress = displayImprovements.filter((i) => i.status === "in-progress").length;
    const critical = displayImprovements.filter((i) => i.priority === "critical" && i.status !== "applied").length;
    return { validated, applied, inProgress, critical };
  }, [displayExplanations, displayImprovements]);

  const autonomyLevel = displayAutonomy.current_stage ?? "SUPERVISED";

  const autonomyLevelColor = useMemo(() => {
    const stage = autonomyLevel.toUpperCase();
    if (stage === "AUTONOMOUS") return "text-sylion-green";
    if (stage === "MANAGED") return "text-sylion-blue";
    if (stage === "SUPERVISED") return "text-sylion-amber";
    if (stage === "ASSISTED") return "text-orange-400";
    return "text-muted-foreground";
  }, [autonomyLevel]);

  const autonomyLevelBadge = useMemo(() => {
    const stage = autonomyLevel.toUpperCase();
    if (stage === "AUTONOMOUS") return "border-sylion-green/30 text-sylion-green";
    if (stage === "MANAGED") return "border-sylion-blue/30 text-sylion-blue";
    if (stage === "SUPERVISED") return "border-sylion-amber/30 text-sylion-amber";
    if (stage === "ASSISTED") return "border-orange-400/30 text-orange-400";
    return "border-muted-foreground/30 text-muted-foreground";
  }, [autonomyLevel]);

  /* ---- Backend unreachable ---- */
  if (!backendLive) {
    return (
      <div className="space-y-5">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
              <Bot className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                Agenty AEIS
                <HelpTip text="Flota agentów AEIS — samo-wyjaśnianie, samo-doskonalenie, samo-obserwacja. Każdy agent ma rolę, model, dostawcę i limit zadań. Tutaj zobaczysz status, decyzję i ulepszenia." />
              </h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                Samo-wyjaśnianie, samo-doskonalenie i samo-obserwacja
              </p>
            </div>
          </div>
        </div>
        <Card className="p-8 bg-card border-sylion-border flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Dane agentów, ulepszenia i samo-obserwacja wymagają działającego backendu.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* ============================================================
          HEADER
          ============================================================ */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
            <Bot className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Agenty AEIS</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Samo-wyjaśnianie, samo-doskonalenie i samo-obserwacja
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green">
            <span className="w-1.5 h-1.5 rounded-full bg-sylion-green mr-1.5 pulse-glow-green" />
            NA ŻYWO
          </Badge>
          <Badge variant="outline" className={cn("text-[10px]", autonomyLevelBadge)}>
            <Gauge className="w-3 h-3 mr-1" />
            {labelAutonomy(autonomyLevel)}
          </Badge>
        </div>
      </div>

      {/* ============================================================
          STATS ROW
          ============================================================ */}
      <div className="grid grid-cols-4 gap-3">
        {/* Explanations */}
        <Card className="p-4 bg-card border-sylion-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                <MessageCircle className="w-3 h-3" /> Wyjaśnienia
                <HelpTip text="Liczba zarejestrowanych wyjaśnień decyzji rady. Każde wyjaśnienie ma pewność (confidence) i flagę walidacji." />
              </p>
              <p className="text-2xl font-semibold mt-1">{displayExplanations.length}</p>
            </div>
            <div className="w-9 h-9 rounded-lg bg-sylion-blue/8 flex items-center justify-center">
              <Brain className="w-4 h-4 text-sylion-blue" />
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground mt-2">
            <span className="text-sylion-green font-medium">{stats.validated}</span> zatwierdzone
          </p>
        </Card>

        {/* Improvements */}
        <Card className="p-4 bg-card border-sylion-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                <Lightbulb className="w-3 h-3 text-sylion-amber" /> Ulepszenia
                <HelpTip text="Propozycje samo-doskonalenia od silnika AEIS. Krytyczne ulepszenia powinny być zaaplikowane szybko; pozostałe priorytetyzowane przez radę." />
              </p>
              <p className="text-2xl font-semibold mt-1">{displayImprovements.length}</p>
            </div>
            <div className="w-9 h-9 rounded-lg bg-sylion-amber/8 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-sylion-amber" />
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground mt-2">
            <span className="text-sylion-blue font-medium">{stats.inProgress}</span> w toku
            {stats.critical > 0 && (
              <> &middot; <span className="text-sylion-red font-medium">{stats.critical}</span> krytyczne</>
            )}
          </p>
        </Card>

        {/* Autonomy Level */}
        <Card className="p-4 bg-card border-sylion-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                <Gauge className="w-3 h-3" /> Poziom autonomii
                <HelpTip text="Aktualny poziom autonomii systemu (MANUAL → AUTONOMOUS). Im wyżej, tym mniej decyzji wymaga zatwierdzenia operatora. Zmień w panelu /autonomy." />
              </p>
              <p className={cn("text-2xl font-semibold mt-1", autonomyLevelColor)}>
                {labelAutonomy(autonomyLevel)}
              </p>
            </div>
            <div className="w-9 h-9 rounded-lg bg-primary/8 flex items-center justify-center">
              <Shield className="w-4 h-4 text-primary" />
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground mt-2">
            <span className="font-medium">{displayAutonomy.pending_approvals}</span> oczekujące zatwierdzenia
          </p>
        </Card>

        {/* Self-Observation */}
        <Card className="p-4 bg-card border-sylion-border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                <Eye className="w-3 h-3 text-sylion-green" /> Samo-obserwacja
                <HelpTip text="Tryb i status silnika samo-obserwacji. Aktywny = pełne monitorowanie metryk i wykrywanie anomalii." />
              </p>
              <p className="text-2xl font-semibold mt-1 capitalize">{labelStatus(displaySelfObs.mode)}</p>
            </div>
            <div className="w-9 h-9 rounded-lg bg-sylion-green/8 flex items-center justify-center">
              <Activity className="w-4 h-4 text-sylion-green" />
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground mt-2">
            <span className={obsStatusColor[displaySelfObs.status] ?? "text-sylion-green"}>
              {labelStatus(displaySelfObs.status)}
            </span>
            {displaySelfObs.anomaly_score != null && (
              <> &middot; anomalia <span className="font-mono">{(displaySelfObs.anomaly_score * 100).toFixed(0)}%</span></>
            )}
          </p>
        </Card>
      </div>

      <Card className="p-4 bg-card border-sylion-border">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Bot className="w-4 h-4 text-primary" />
              Flota wykonawcza
              <HelpTip text="Zarejestrowani agenci runtime z dostawcami, modelami, statusem oraz statystykami wykonań/tokenów/kosztów." />
            </h2>
            <p className="text-[11px] text-muted-foreground mt-1">
              Zarejestrowani agenci, dostawcy, powiązania modeli, wykonania, zużycie tokenów i koszty.
            </p>
          </div>
          <div className="grid grid-cols-4 gap-2 text-right">
            <div className="surface-inset rounded-lg px-3 py-2">
              <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Agenty</p>
              <p className="text-lg font-semibold">{agentRuntimeStats.total_agents ?? runtimeAgents.length}</p>
            </div>
            <div className="surface-inset rounded-lg px-3 py-2">
              <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Wykonania</p>
              <p className="text-lg font-semibold">{agentRuntimeStats.total_executions ?? agentExecutions.length}</p>
            </div>
            <div className="surface-inset rounded-lg px-3 py-2">
              <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Tokeny</p>
              <p className="text-lg font-semibold">{Number(agentRuntimeStats.total_tokens ?? 0).toLocaleString()}</p>
            </div>
            <div className="surface-inset rounded-lg px-3 py-2">
              <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Koszt</p>
              <p className="text-lg font-semibold">${Number(agentRuntimeStats.total_cost ?? 0).toFixed(4)}</p>
            </div>
          </div>
        </div>

        <div className="mb-4 grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="rounded-lg border border-sylion-border bg-muted/10 p-3">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div>
                <h3 className="text-xs font-semibold">Konfiguracja agenta runtime</h3>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  Rejestracja, model, dostawca, narzędzia, możliwości, limity i status pracy.
                </p>
              </div>
              {selectedAgentId ? (
                <Badge variant="outline" className="h-5 max-w-[220px] truncate text-[9px]">
                  {selectedAgentId}
                </Badge>
              ) : null}
            </div>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
              <label className="grid gap-1 text-[10px] text-muted-foreground md:col-span-2">
                Nazwa
                <input className="h-8 rounded-md border border-sylion-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50" value={agentForm.name} onChange={(event) => updateAgentForm("name", event.target.value)} />
              </label>
              <label className="grid gap-1 text-[10px] text-muted-foreground">
                Typ
                <select className="h-8 rounded-md border border-sylion-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50" value={agentForm.agent_type} onChange={(event) => updateAgentForm("agent_type", event.target.value)}>
                  {agentTypeOptions.map((type) => <option key={type} value={type}>{type}</option>)}
                </select>
              </label>
              <label className="grid gap-1 text-[10px] text-muted-foreground">
                Status
                <select className="h-8 rounded-md border border-sylion-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50" value={agentForm.status} onChange={(event) => updateAgentForm("status", event.target.value)}>
                  {statusOptions.map((status) => <option key={status} value={status}>{labelStatus(status)}</option>)}
                </select>
              </label>
              <label className="grid gap-1 text-[10px] text-muted-foreground">
                Dostawca
                <select className="h-8 rounded-md border border-sylion-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50" value={agentForm.provider} onChange={(event) => updateAgentForm("provider", event.target.value)}>
                  {providerOptions.map((provider) => <option key={provider} value={provider}>{provider}</option>)}
                </select>
              </label>
              <label className="grid gap-1 text-[10px] text-muted-foreground md:col-span-2">
                Model
                <input className="h-8 rounded-md border border-sylion-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50" value={agentForm.model_id} onChange={(event) => updateAgentForm("model_id", event.target.value)} placeholder="np. gpt-4.1, claude-sonnet-4, kimi-k2" />
              </label>
              <label className="grid gap-1 text-[10px] text-muted-foreground">
                Max tokenów
                <input type="number" min={256} max={128000} step={256} className="h-8 rounded-md border border-sylion-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50" value={agentForm.max_tokens} onChange={(event) => updateAgentForm("max_tokens", Number(event.target.value))} />
              </label>
              <label className="grid gap-1 text-[10px] text-muted-foreground">
                Temperatura
                <input type="number" min={0} max={2} step={0.1} className="h-8 rounded-md border border-sylion-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50" value={agentForm.temperature} onChange={(event) => updateAgentForm("temperature", Number(event.target.value))} />
              </label>
              <label className="grid gap-1 text-[10px] text-muted-foreground md:col-span-2">
                Narzędzia
                <input className="h-8 rounded-md border border-sylion-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50" value={agentForm.tools} onChange={(event) => updateAgentForm("tools", event.target.value)} placeholder="po przecinku: terminal,browser,filesystem" />
              </label>
              <label className="grid gap-1 text-[10px] text-muted-foreground md:col-span-2">
                Możliwości
                <input className="h-8 rounded-md border border-sylion-border bg-background px-2 text-xs text-foreground outline-none focus:border-primary/50" value={agentForm.capabilities} onChange={(event) => updateAgentForm("capabilities", event.target.value)} placeholder="po przecinku: planowanie,testy,naprawa" />
              </label>
              <label className="grid gap-1 text-[10px] text-muted-foreground md:col-span-4">
                Prompt systemowy
                <textarea className="min-h-[72px] rounded-md border border-sylion-border bg-background px-2 py-2 text-xs text-foreground outline-none focus:border-primary/50" value={agentForm.system_prompt} onChange={(event) => updateAgentForm("system_prompt", event.target.value)} />
              </label>
            </div>
          </div>

          <div className="rounded-lg border border-sylion-border bg-muted/10 p-3">
            <h3 className="text-xs font-semibold">Akcje operatora</h3>
            <p className="mt-1 text-[10px] text-muted-foreground">
              Wybierz agenta z listy, edytuj pola i zapisz. Test dymny tworzy wykonanie w runtime.
            </p>
            <div className="mt-3 grid gap-2">
              <Button size="sm" className="h-8 text-xs" onClick={registerAgent} disabled={agentBusy === "register" || !agentForm.name.trim()}>
                <Plus className="mr-1 h-3 w-3" />
                Zarejestruj nowego agenta
              </Button>
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={saveSelectedAgent} disabled={agentBusy === "save" || !selectedAgentId}>
                <Save className="mr-1 h-3 w-3" />
                Zapisz wybranego
              </Button>
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={runSmokeTask} disabled={agentBusy === "smoke" || !selectedAgentId}>
                <Play className="mr-1 h-3 w-3" />
                Uruchom test dymny
              </Button>
              <Button variant="destructive" size="sm" className="h-8 text-xs" onClick={deleteSelectedAgent} disabled={agentBusy === "delete" || !selectedAgentId}>
                <Trash2 className="mr-1 h-3 w-3" />
                Usuń z runtime
              </Button>
              <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={() => void refreshAgents()}>
                Odśwież flotę
              </Button>
            </div>
            {agentActionStatus ? (
              <div className="mt-3 rounded-md border border-sylion-border bg-background px-3 py-2 text-[10px] text-muted-foreground">
                {agentActionStatus}
              </div>
            ) : null}
          </div>
        </div>

        {runtimeAgents.length > 0 ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {runtimeAgents.slice(0, 9).map((agent: any) => (
              <button
                key={agent.agent_id}
                type="button"
                onClick={() => loadAgentIntoForm(agent)}
                className={cn(
                  "rounded-lg border bg-muted/10 p-3 text-left transition-colors hover:border-primary/40",
                  selectedAgentId === agent.agent_id ? "border-primary/50 bg-primary/10" : "border-sylion-border",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold truncate">{agent.name || agent.agent_id}</p>
                    <p className="text-[10px] text-muted-foreground font-mono truncate">{agent.agent_id}</p>
                  </div>
                  <Badge variant="outline" className={cn(
                    "text-[8px] h-4",
                    agent.status === "active" ? "border-sylion-green/30 text-sylion-green" : "border-muted-foreground/30 text-muted-foreground",
                  )}>
                    {labelStatus(agent.status)}
                  </Badge>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-[10px]">
                  <div>
                    <span className="text-muted-foreground">Typ</span>
                    <p className="font-mono">{agent.agent_type || "własny"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Dostawca</span>
                    <p className="font-mono">{agent.provider || "nieznany"}</p>
                  </div>
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Model</span>
                    <p className="font-mono truncate">{agent.model_id || "niepowiązany"}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-sylion-border p-6 text-center">
            <Bot className="w-7 h-7 text-muted-foreground/30 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Brak zarejestrowanych agentów</p>
            <p className="text-[10px] text-muted-foreground mt-1">
              Zarejestruj agenty przez API Runtime lub przyszłe kontrolki operatora.
            </p>
          </div>
        )}
      </Card>

      {/* ============================================================
          TABBED CONTENT
          ============================================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList variant="line">
          <HelpTip text="Wyjaśnienia: rationale decyzji rady. Ulepszenia: kolejka samo-doskonalenia. Samo-obserwacja: metryki, anomalie i samonaprawy." />
          <TabsTrigger value="explanations" className="flex items-center gap-1.5">
            <MessageCircle className="w-3.5 h-3.5" />
            Wyjaśnienia
            <Badge variant="secondary" className="text-[8px] h-4 ml-1">
              {displayExplanations.length}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="improvements" className="flex items-center gap-1.5">
            <Lightbulb className="w-3.5 h-3.5" />
            Ulepszenia
            <Badge variant="secondary" className="text-[8px] h-4 ml-1">
              {displayImprovements.length}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="self-observation" className="flex items-center gap-1.5">
            <Eye className="w-3.5 h-3.5" />
            Samo-obserwacja
          </TabsTrigger>
        </TabsList>

        {/* ---- EXPLANATIONS TAB ---- */}
        <TabsContent value="explanations">
          <div className="space-y-2 mt-3">
            <AnimatePresence mode="popLayout">
              {displayExplanations.map((exp, idx) => (
                <motion.div
                  key={exp.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ delay: idx * 0.04, duration: 0.2 }}
                >
                  <Card className={cn(
                    "p-4 bg-card border-sylion-border hover:bg-muted/10 transition-colors",
                    exp.validated ? "border-l-2 border-l-sylion-green/40" : "border-l-2 border-l-sylion-amber/40",
                  )}>
                    {/* Header row */}
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <Badge variant="outline" className="text-[9px] h-5 font-mono shrink-0">
                          {exp.decision_id}
                        </Badge>
                        <span className="text-[10px] text-muted-foreground font-mono truncate">
                          {exp.source_module.split(".").pop()}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {/* Confidence */}
                        <div className="flex items-center gap-1.5">
                          <span className="text-[9px] text-muted-foreground">Pewność</span>
                          <div className="w-16 h-1.5 rounded-full bg-secondary">
                            <div
                              className={cn("h-full rounded-full transition-all", confidenceBarColor(exp.confidence))}
                              style={{ width: `${exp.confidence * 100}%` }}
                            />
                          </div>
                          <span className={cn("text-[10px] font-semibold font-mono", confidenceColor(exp.confidence))}>
                            {(exp.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        {/* Validated badge */}
                        {exp.validated ? (
                          <Badge variant="outline" className="text-[8px] h-4 border-sylion-green/30 text-sylion-green">
                            <CheckCircle2 className="w-2.5 h-2.5 mr-0.5" /> Zatwierdzone
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-[8px] h-4 border-sylion-amber/30 text-sylion-amber">
                            <Clock className="w-2.5 h-2.5 mr-0.5" /> Oczekujące
                          </Badge>
                        )}
                        {/* Timestamp */}
                        <span className="text-[9px] text-muted-foreground whitespace-nowrap">
                          {fmtDateTime(exp.timestamp)}
                        </span>
                      </div>
                    </div>

                    {/* Rationale */}
                    <div className="ml-0">
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        {exp.rationale}
                      </p>
                    </div>

                    {/* Source module full path */}
                    <div className="flex items-center gap-1.5 mt-2 ml-0">
                      <Cpu className="w-3 h-3 text-muted-foreground" />
                      <span className="text-[9px] text-muted-foreground font-mono">{exp.source_module}</span>
                    </div>
                  </Card>
                </motion.div>
              ))}
            </AnimatePresence>

            {displayExplanations.length === 0 && (
              <div className="py-12 text-center">
                <Brain className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Brak zarejestrowanych wyjaśnień</p>
              </div>
            )}
          </div>
        </TabsContent>

        {/* ---- IMPROVEMENTS TAB ---- */}
        <TabsContent value="improvements">
          <div className="space-y-2 mt-3">
            <AnimatePresence mode="popLayout">
              {displayImprovements.map((imp, idx) => (
                <motion.div
                  key={imp.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ delay: idx * 0.04, duration: 0.2 }}
                >
                  <Card className={cn(
                    "p-4 bg-card border-sylion-border hover:bg-muted/10 transition-colors",
                    priorityBgMap[imp.priority] ?? "",
                  )}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-2.5 min-w-0 flex-1">
                        {/* Status dot */}
                        <span className={cn("w-2 h-2 rounded-full mt-1.5 shrink-0", impStatusDot[imp.status])} />
                        <div className="min-w-0 flex-1">
                          {/* Title row */}
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium truncate">{imp.text}</span>
                          </div>
                          {/* Meta row */}
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant="outline" className={cn("text-[8px] h-4", impStatusBadge[imp.status])}>
                              {imp.status}
                            </Badge>
                            <Badge variant="outline" className={cn("text-[8px] h-4", priorityBadgeMap[imp.priority])}>
                              {imp.priority}
                            </Badge>
                            <span className="text-[9px] text-muted-foreground font-mono">
                              {imp.module.split(".").pop()}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Right side: timestamp + module path */}
                      <div className="flex flex-col items-end shrink-0 gap-1">
                        <span className="text-[9px] text-muted-foreground whitespace-nowrap">
                          {fmtDateTime(imp.timestamp)}
                        </span>
                        <span className="text-[8px] text-muted-foreground font-mono">
                          {imp.module}
                        </span>
                      </div>
                    </div>
                  </Card>
                </motion.div>
              ))}
            </AnimatePresence>

            {displayImprovements.length === 0 && (
              <div className="py-12 text-center">
                <Lightbulb className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Brak zidentyfikowanych ulepszeń</p>
              </div>
            )}
          </div>
        </TabsContent>

        {/* ---- SELF-OBSERVATION TAB ---- */}
        <TabsContent value="self-observation">
          <div className="mt-3 space-y-4">
            {/* Mode & Status Header */}
            <Card className="p-4 bg-card border-sylion-border">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-10 h-10 rounded-lg flex items-center justify-center",
                    displaySelfObs.status === "healthy" ? "bg-sylion-green/10" :
                    displaySelfObs.status === "degraded" ? "bg-sylion-amber/10" : "bg-sylion-red/10",
                  )}>
                    <Activity className={cn(
                      "w-5 h-5",
                      obsStatusColor[displaySelfObs.status] ?? "text-sylion-green",
                    )} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold">
                        Silnik samo-obserwacji
                        <HelpTip text="Główny motor monitorujący system w czasie rzeczywistym. Tryb aktywny oznacza pełną pętlę obserwacji + wykrywanie anomalii." />
                      </h3>
                      <Badge variant="outline" className={cn("text-[9px] h-5", obsModeBadge[displaySelfObs.mode] ?? "border-muted-foreground/30 text-muted-foreground")}>
                        {labelStatus(displaySelfObs.mode)}
                      </Badge>
                      <Badge variant="outline" className={cn(
                        "text-[9px] h-5",
                        displaySelfObs.status === "healthy" ? "border-sylion-green/30 text-sylion-green" :
                        displaySelfObs.status === "degraded" ? "border-sylion-amber/30 text-sylion-amber" :
                        "border-sylion-red/30 text-sylion-red",
                      )}>
                        {labelStatus(displaySelfObs.status)}
                      </Badge>
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      Ciągłe samo-monitorowanie i wykrywanie anomalii
                    </p>
                  </div>
                </div>
              </div>

              {/* Observation Metrics Grid */}
              <div className="grid grid-cols-4 gap-3">
                {[
                  { key: "cpu_usage", label: "Użycie CPU", value: displaySelfObs.metrics.cpu_usage, unit: "%", icon: Cpu, color: "text-sylion-blue" },
                  { key: "memory_usage", label: "Pamięć", value: displaySelfObs.metrics.memory_usage, unit: "%", icon: Activity, color: "text-purple-400" },
                  { key: "event_throughput", label: "Zdarzeń/h", value: displaySelfObs.metrics.event_throughput, unit: "", icon: Zap, color: "text-sylion-green" },
                  { key: "error_rate", label: "Wskaźnik błędów", value: displaySelfObs.metrics.error_rate, unit: "%", icon: AlertTriangle, color: "text-sylion-red" },
                ].map((metric) => {
                  const MIcon = metric.icon;
                  const numVal = Number(metric.value ?? 0);
                  const barPct = metric.unit === "%" ? Math.min(numVal, 100) : Math.min(numVal, 300) / 3;
                  return (
                    <div key={metric.key} className="p-3 rounded-lg surface-inset">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-1.5">
                          <MIcon className={cn("w-3.5 h-3.5", metric.color)} />
                          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                            {metric.label}
                          </span>
                        </div>
                        <span className={cn("text-sm font-semibold font-mono", metric.color)}>
                          {numVal}{metric.unit}
                        </span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-secondary">
                        <motion.div
                          className={cn("h-full rounded-full", metric.color.replace("text-", "bg-"))}
                          initial={{ width: 0 }}
                          animate={{ width: `${barPct}%` }}
                          transition={{ duration: 0.6, ease: "easeOut" }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Observation Stats */}
            <div className="grid grid-cols-3 gap-3">
              <Card className="p-4 bg-card border-sylion-border">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-sylion-blue" />
                    <span className="text-xs font-semibold">Statystyki cykli</span>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">Pętla obserwacji</span>
                    <span className="text-[11px] font-mono font-medium">{displaySelfObs.observation_loop_ms ?? 0}ms</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">Ukończone cykle</span>
                    <span className="text-[11px] font-mono font-medium">{(displaySelfObs.cycles_completed ?? 0).toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">Ostatni cykl</span>
                    <span className="text-[10px] font-mono text-muted-foreground">
                      {displaySelfObs.last_cycle ? fmtDateTime(displaySelfObs.last_cycle) : "--"}
                    </span>
                  </div>
                </div>
              </Card>

              <Card className="p-4 bg-card border-sylion-border">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-sylion-amber" />
                    <span className="text-xs font-semibold">Wykrywanie anomalii</span>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">Wynik anomalii</span>
                    <span className={cn(
                      "text-[11px] font-mono font-semibold",
                      (displaySelfObs.anomaly_score ?? 0) < 0.3 ? "text-sylion-green" :
                      (displaySelfObs.anomaly_score ?? 0) < 0.7 ? "text-sylion-amber" : "text-sylion-red",
                    )}>
                      {((displaySelfObs.anomaly_score ?? 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">Wykryte anomalie</span>
                    <span className="text-[11px] font-mono font-medium">{displaySelfObs.anomalies_detected ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">Samonaprawy</span>
                    <span className="text-[11px] font-mono font-medium text-sylion-green">{displaySelfObs.self_repairs_triggered ?? 0}</span>
                  </div>
                </div>
              </Card>

              <Card className="p-4 bg-card border-sylion-border">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-primary" />
                    <span className="text-xs font-semibold">Zdrowie modułów</span>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">Aktywne moduły</span>
                    <span className="text-[11px] font-mono font-medium">{displaySelfObs.metrics.active_modules ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">Zdrowe moduły</span>
                    <span className="text-[11px] font-mono font-medium text-sylion-green">
                      {displaySelfObs.metrics.healthy_modules ?? 0}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">Wskaźnik zdrowia</span>
                    <span className={cn(
                      "text-[11px] font-mono font-semibold",
                      ((displaySelfObs.metrics.healthy_modules ?? 0) / Math.max(displaySelfObs.metrics.active_modules ?? 1, 1)) >= 0.95
                        ? "text-sylion-green"
                        : ((displaySelfObs.metrics.healthy_modules ?? 0) / Math.max(displaySelfObs.metrics.active_modules ?? 1, 1)) >= 0.85
                          ? "text-sylion-amber"
                          : "text-sylion-red",
                    )}>
                      {((displaySelfObs.metrics.healthy_modules ?? 0) / Math.max(displaySelfObs.metrics.active_modules ?? 1, 1) * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
