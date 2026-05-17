"use client";

import React, { Suspense, useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { useHealth } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  Rocket,
  Zap,
  Play,
  X,
  Eye,
  RefreshCw,
  ListChecks,
  CheckCircle2,
  XCircle,
  Clock,
  Activity,
  Settings2,
  Brain,
  Send,
  ChevronUp,
  Loader2,
  FileJson,
  WifiOff,
} from "lucide-react";

/* ============================================================
   Types — matches backend PipelineController response
   ============================================================ */

interface PipelineStep {
  step_id: string;
  name: string;
  description: string;
  status: string;
  result: Record<string, unknown>;
}

interface PipelineRun {
  run_id: string;
  idea: string;
  status: string;
  plan: Record<string, unknown>;
  steps: PipelineStep[];
  context: Record<string, unknown>;
  created_at: number;
  completed_at: number;
}

interface ProductArtifact {
  contract?: string;
  quality_gate?: string;
  quality_findings?: Array<Record<string, unknown>>;
  model_trace?: string[];
  completed_steps?: number;
  failed_steps?: number;
  step_count?: number;
}

interface LLMConfig {
  provider: "anthropic" | "openai" | "ollama";
  modelName: string;
}

/* ============================================================
   Constants & Helpers
   ============================================================ */

const STATUS_COLORS: Record<string, string> = {
  pending: "border-muted-foreground/30 text-muted-foreground bg-muted/30",
  planning: "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5",
  generating: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5",
  reviewing: "border-purple-400/30 text-purple-400 bg-purple-400/5",
  complete: "border-sylion-green/30 text-sylion-green bg-sylion-green/5",
  failed: "border-sylion-red/30 text-sylion-red bg-sylion-red/5",
  cancelled: "border-muted-foreground/30 text-muted-foreground bg-muted/30",
};

const STATUS_ICONS: Record<string, React.ElementType> = {
  pending: Clock,
  planning: Brain,
  generating: Zap,
  reviewing: Eye,
  complete: CheckCircle2,
  failed: XCircle,
  cancelled: XCircle,
};

const STATUS_LABELS: Record<string, string> = {
  pending: "oczekuje",
  planning: "planowanie",
  generating: "generowanie",
  reviewing: "przegląd",
  complete: "ukończone",
  failed: "błąd",
  cancelled: "anulowane",
  running: "w toku",
  executing: "wykonanie",
  queued: "w kolejce",
  unknown: "nieznany",
};

const STEP_STATUS_COLORS: Record<string, string> = {
  pending: "text-muted-foreground",
  generating: "text-sylion-blue",
  reviewing: "text-purple-400",
  complete: "text-sylion-green",
  failed: "text-sylion-red",
};

const STEP_DOT_COLORS: Record<string, string> = {
  pending: "bg-muted-foreground",
  generating: "bg-sylion-blue animate-pulse",
  reviewing: "bg-purple-400 animate-pulse",
  complete: "bg-sylion-green",
  failed: "bg-sylion-red",
};

function formatRelative(ts: number): string {
  if (!ts) return "--";
  const diff = Date.now() - ts * 1000;
  if (diff < 0) return "teraz";
  if (diff < 1000) return "teraz";
  if (diff < 60000) return `${Math.floor(diff / 1000)} s temu`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)} min temu`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} h temu`;
  return `${Math.floor(diff / 86400000)} dni temu`;
}

function truncate(s: string, len: number): string {
  return s.length > len ? s.slice(0, len) + "..." : s;
}

function isTerminalStatus(status: string): boolean {
  return status === "complete" || status === "failed" || status === "cancelled";
}

function serializeResult(result: Record<string, unknown>): string {
  if (!result) return "";
  if (result.error) return String(result.error);
  if (result.output) return String(result.output);
  if (result.result) return String(result.result);
  const keys = Object.keys(result);
  if (keys.length === 0) return "";
  return JSON.stringify(result, null, 2).slice(0, 300);
}

function getProductArtifact(run: PipelineRun | undefined): ProductArtifact | null {
  const artifact = run?.plan?.product_artifact;
  return artifact && typeof artifact === "object" ? artifact as ProductArtifact : null;
}

function formatFinding(finding: Record<string, unknown>, index: number): string {
  const step = String(finding.step_name || finding.step_id || `krok ${index + 1}`);
  const reason = String(finding.finding || finding.reason || "nieznany błąd jakości");
  return `${step}: ${reason}`;
}

/* ============================================================
   Stat Card
   ============================================================ */

function StatCard({
  label,
  value,
  icon: Icon,
  accent,
  bgColor,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  accent: string;
  bgColor: string;
}) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <Card className="p-4 bg-[#0f1629] border border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.15)] transition-all duration-300">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</p>
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
   Step Details Expansion
   ============================================================ */

function StepDetails({ steps }: { steps: PipelineStep[] }) {
  if (!steps || steps.length === 0) {
    return (
      <div className="px-4 pb-4 pt-1">
        <p className="text-[10px] text-muted-foreground italic">Brak zapisanych kroków.</p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="overflow-hidden"
    >
      <div className="px-4 pb-4 pt-1">
        <div className="rounded-lg bg-[#0a0f1e] border border-[rgba(148,163,184,0.06)] p-4 space-y-3">
          {steps.map((step, idx) => {
            const StepIcon = step.status === "generating" ? Loader2 : STATUS_ICONS[step.status] || Clock;
            const resultText = serializeResult(step.result);
            return (
              <div key={step.step_id || idx} className="flex items-start gap-3">
                {/* Connector */}
                <div className="flex flex-col items-center shrink-0">
                  <div className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center border shrink-0",
                    step.status === "complete"
                      ? "bg-sylion-green/15 border-sylion-green/30"
                      : step.status === "generating" || step.status === "reviewing"
                      ? "bg-sylion-blue/15 border-sylion-blue/30"
                      : step.status === "failed"
                      ? "bg-sylion-red/15 border-sylion-red/30"
                      : "bg-secondary/30 border-border"
                  )}>
                    <StepIcon className={cn(
                      "w-3.5 h-3.5",
                      STEP_STATUS_COLORS[step.status] || "text-muted-foreground",
                      step.status === "generating" && "animate-spin"
                    )} />
                  </div>
                  {idx < steps.length - 1 && (
                    <div className={cn("w-px h-5", step.status === "complete" ? "bg-sylion-green/30" : "bg-border")} />
                  )}
                </div>
                {/* Content */}
                <div className="flex-1 min-w-0 pt-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-foreground">{step.name || step.step_id}</span>
                    <span className={cn("w-1.5 h-1.5 rounded-full", STEP_DOT_COLORS[step.status] || "bg-muted-foreground")} />
                    <span className="text-[9px] text-muted-foreground">{STATUS_LABELS[step.status] ?? step.status}</span>
                  </div>
                  {step.description && (
                    <p className="text-[10px] text-muted-foreground mt-0.5">{step.description}</p>
                  )}
                  {resultText && (
                    <div className="mt-1.5 px-2.5 py-1.5 rounded-md bg-muted/30 border border-border/30">
                      <p className="text-[10px] text-muted-foreground leading-relaxed font-mono">{truncate(resultText, 300)}</p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}

function ActiveRunQualityPanel({ run }: { run: PipelineRun }) {
  const artifact = getProductArtifact(run);
  const findings = artifact?.quality_findings ?? [];
  const modelTrace = artifact?.model_trace ?? [];
  const qualityGate = artifact?.quality_gate || "brak danych";
  const isBlocked = qualityGate === "failed" || run.status === "failed";

  return (
    <Card className="p-5 bg-[#0f1629] border border-[rgba(148,163,184,0.08)]">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-semibold">Aktywny przebieg runtime</h2>
            <Badge variant="outline" className={cn("text-[9px] h-5", STATUS_COLORS[run.status] || STATUS_COLORS.unknown)}>
              {STATUS_LABELS[run.status] ?? run.status}
            </Badge>
            <Badge
              variant="outline"
              className={cn(
                "text-[9px] h-5",
                qualityGate === "passed"
                  ? "border-sylion-green/30 text-sylion-green"
                  : qualityGate === "failed"
                  ? "border-sylion-red/30 text-sylion-red"
                  : "border-muted-foreground/30 text-muted-foreground"
              )}
            >
              quality gate: {qualityGate}
            </Badge>
          </div>
          <p className="mt-2 text-xs text-muted-foreground break-all">
            Run: <span className="font-mono text-foreground">{run.run_id}</span>
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{truncate(run.idea, 180)}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void navigator.clipboard?.writeText(run.run_id)}>
          Kopiuj ID
        </Button>
      </div>

      {isBlocked && (
        <div className="mt-4 rounded-lg border border-sylion-red/20 bg-sylion-red/5 px-4 py-3">
          <p className="text-xs font-medium text-sylion-red">Przebieg zablokowany przez jakość artefaktu</p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            AEIS nie zalicza tego wyniku jako produktu. Wymagane jest powtórzenie kroku mocniejszym modelem albo poprawa kontraktu jakości.
          </p>
        </div>
      )}

      <div className="mt-4 grid grid-cols-4 gap-3">
        <div className="rounded-lg bg-[#0a0f1e] border border-[rgba(148,163,184,0.06)] p-3">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Kroki</p>
          <p className="mt-1 text-lg font-semibold text-foreground">{artifact?.step_count ?? run.steps?.length ?? 0}</p>
        </div>
        <div className="rounded-lg bg-[#0a0f1e] border border-[rgba(148,163,184,0.06)] p-3">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Ukończone</p>
          <p className="mt-1 text-lg font-semibold text-sylion-green">{artifact?.completed_steps ?? run.steps?.filter((s) => s.status === "complete").length ?? 0}</p>
        </div>
        <div className="rounded-lg bg-[#0a0f1e] border border-[rgba(148,163,184,0.06)] p-3">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Błędy</p>
          <p className="mt-1 text-lg font-semibold text-sylion-red">{artifact?.failed_steps ?? run.steps?.filter((s) => s.status === "failed").length ?? 0}</p>
        </div>
        <div className="rounded-lg bg-[#0a0f1e] border border-[rgba(148,163,184,0.06)] p-3">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Modele</p>
          <p className="mt-1 text-xs font-mono text-foreground truncate">{modelTrace.length ? modelTrace.join(", ") : "brak śladu"}</p>
        </div>
      </div>

      <div className="mt-4 rounded-lg bg-[#0a0f1e] border border-[rgba(148,163,184,0.06)] p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-foreground">Findings quality-gate</p>
          <span className="text-[10px] text-muted-foreground">{findings.length}</span>
        </div>
        {findings.length > 0 ? (
          <div className="mt-3 space-y-2">
            {findings.slice(0, 8).map((finding, index) => (
              <div key={`${String(finding.step_id || index)}-${String(finding.finding || index)}`} className="rounded-md border border-sylion-red/10 bg-sylion-red/5 px-3 py-2">
                <p className="text-[11px] text-sylion-red">{formatFinding(finding, index)}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-[11px] text-muted-foreground">Brak zapisanych błędów jakości dla tego przebiegu.</p>
        )}
      </div>
    </Card>
  );
}

/* ============================================================
   Main Page Component
   ============================================================ */

function PipelineContent() {
  const searchParams = useSearchParams();
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";

  /* ---- State ---- */
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submittedIdea, setSubmittedIdea] = useState("");
  const [contextJson, setContextJson] = useState("");
  const [llmConfig, setLlmConfig] = useState<LLMConfig>({
    provider: "ollama",
    modelName: "qwen2.5:7b-instruct",
  });
  const [configSaving, setConfigSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
  const mountedRef = useRef(true);
  const autoExecutedRunRef = useRef<string | null>(null);

  /* ---- Load config from localStorage ---- */
  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const saved = localStorage.getItem("sylion-pipeline-llm-config");
        if (saved) {
          const parsed = JSON.parse(saved) as Partial<LLMConfig> & { provider?: string };
          setLlmConfig({
            provider: parsed.provider === "anthropic" || parsed.provider === "openai" || parsed.provider === "ollama"
              ? parsed.provider
              : "ollama",
            modelName: parsed.modelName || "qwen2.5:7b-instruct",
          });
        }
      } catch {}
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  /* ---- Fetch runs from backend ---- */
  const fetchRuns = useCallback(async () => {
    setFetchError(null);
    try {
      const data = await api.listRuns();
      if (mountedRef.current) {
        setRuns(data.runs ?? []);
        setLoading(false);
      }
    } catch {
      if (mountedRef.current) {
        setRuns([]);
        setFetchError("Backend niedostępny");
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    queueMicrotask(() => void fetchRuns());
    return () => { mountedRef.current = false; };
  }, [fetchRuns]);

  /* ---- Execute run ---- */
  const handleExecute = useCallback(async (runId: string) => {
    setActionLoading((prev) => ({ ...prev, [runId]: true }));
    try {
      await api.executeRun(runId);
    } catch {}
    setActionLoading((prev) => ({ ...prev, [runId]: false }));
    fetchRuns();
  }, [fetchRuns]);

  /* ---- Polling for active runs ---- */
  const hasActive = runs.some((r) => !isTerminalStatus(r.status));
  useEffect(() => {
    if (!hasActive) return;
    const interval = setInterval(fetchRuns, 5000);
    return () => clearInterval(interval);
  }, [hasActive, fetchRuns]);

  useEffect(() => {
    const targetRunId = searchParams.get("execute");
    if (!targetRunId || autoExecutedRunRef.current === targetRunId) return;
    const targetRun = runs.find((run) => run.run_id === targetRunId);
    if (!targetRun) return;
    setSelectedRunId(targetRunId);
    if (targetRun.status === "pending" || targetRun.status === "planning") {
      autoExecutedRunRef.current = targetRunId;
      void handleExecute(targetRunId);
    }
  }, [handleExecute, runs, searchParams]);

  /* ---- Derived stats ---- */
  const totalRuns = runs.length;
  const completedRuns = runs.filter((r) => r.status === "complete").length;
  const failedRuns = runs.filter((r) => r.status === "failed").length;
  const activeRuns = runs.filter((r) => !isTerminalStatus(r.status)).length;
  const selectedRun = selectedRunId ? runs.find((run) => run.run_id === selectedRunId) : undefined;

  /* ---- Submit idea ---- */
  const handleSubmitIdea = async () => {
    if (!submittedIdea.trim()) return;
    setSubmitting(true);
    try {
      let contextPayload = {};
      if (contextJson.trim()) {
        try { contextPayload = JSON.parse(contextJson); } catch { contextPayload = { raw_context: contextJson }; }
      }
      await api.submitPipelineIdea(submittedIdea, contextPayload);
    } catch {}
    setSubmitting(false);
    setSubmittedIdea("");
    setContextJson("");
    fetchRuns();
  };

  /* ---- Cancel run ---- */
  const handleCancel = async (runId: string) => {
    setActionLoading((prev) => ({ ...prev, [runId]: true }));
    try {
      await api.cancelRun(runId);
    } catch {}
    setActionLoading((prev) => ({ ...prev, [runId]: false }));
    fetchRuns();
  };

  /* ---- Save LLM config ---- */
  const handleSaveConfig = () => {
    setConfigSaving(true);
    try {
      localStorage.setItem("sylion-pipeline-llm-config", JSON.stringify(llmConfig));
    } catch {}
    setTimeout(() => setConfigSaving(false), 600);
  };

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Rocket className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Pipeline</h1>
            <p className="text-sm text-muted-foreground">Zgłaszaj pomysły, uruchamiaj przebiegi i śledź wyniki</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {backendLive ? (
            <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green">
              <span className="w-1.5 h-1.5 rounded-full bg-sylion-green mr-1.5 pulse-glow-green" />
              NA ŻYWO
            </Badge>
          ) : (
            <Badge variant="outline" className="text-[10px] border-sylion-red/30 text-sylion-red">
              <WifiOff className="w-3 h-3 mr-1" />
              POZA SIECIĄ
            </Badge>
          )}
          <Badge variant="outline" className="text-[10px] border-primary/30 text-primary">
            {totalRuns} przebiegów
          </Badge>
          <Button variant="outline" size="sm" onClick={fetchRuns}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Odśwież
          </Button>
        </div>
      </div>

      {/* ====== STATS ROW ====== */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Wszystkie przebiegi" value={totalRuns} icon={ListChecks} accent="text-primary" bgColor="bg-primary/10" />
        <StatCard label="Ukończone" value={completedRuns} icon={CheckCircle2} accent="text-sylion-green" bgColor="bg-sylion-green/10" />
        <StatCard label="Błędy" value={failedRuns} icon={XCircle} accent="text-sylion-red" bgColor="bg-sylion-red/10" />
        <StatCard label="Aktywne" value={activeRuns} icon={Activity} accent="text-sylion-blue" bgColor="bg-sylion-blue/10" />
      </div>

      {selectedRun && <ActiveRunQualityPanel run={selectedRun} />}

      {/* ====== TWO-COLUMN: Submit + LLM Config ====== */}
      <div className="grid grid-cols-12 gap-4">
        {/* ---- SUBMIT IDEA CARD ---- */}
        <div className="col-span-8">
          <Card className="p-5 bg-[#0f1629] border border-[rgba(148,163,184,0.08)]">
            <div className="flex items-center gap-2 mb-4">
              <Send className="w-4 h-4 text-primary" />
              <h2 className="text-sm font-semibold">Zgłoś pomysł</h2>
              <div className="flex-1 h-px bg-border" />
            </div>

            <div className="mb-3">
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5 block">Opis pomysłu</label>
              <textarea
                value={submittedIdea}
                onChange={(e) => setSubmittedIdea(e.target.value)}
                placeholder="Opisz, co pipeline ma zbudować, przeanalizować albo wygenerować..."
                rows={4}
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30 focus:ring-1 focus:ring-primary/20 resize-none"
              />
            </div>

            <div className="mb-4">
              <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                <FileJson className="w-3 h-3" />
                Kontekst (opcjonalny JSON)
              </label>
              <input
                type="text"
                value={contextJson}
                onChange={(e) => setContextJson(e.target.value)}
                placeholder='{"module": "evidence", "priority": "high"}'
                className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs text-foreground font-mono placeholder:text-muted-foreground focus:outline-none focus:border-primary/30 focus:ring-1 focus:ring-primary/20"
              />
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">
                {backendLive ? "Gotowe do wysłania" : "Uruchom backend, aby wysyłać zgłoszenia"}
              </span>
              <Button
                onClick={handleSubmitIdea}
                disabled={!submittedIdea.trim() || submitting || !backendLive}
                className="shadow-[0_0_20px_rgba(47,107,255,0.15)]"
              >
                {submitting ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Rocket className="w-3.5 h-3.5 mr-1.5" />
                )}
                {submitting ? "Wysyłanie..." : "Wyślij do pipeline"}
              </Button>
            </div>
          </Card>
        </div>

        {/* ---- LLM CONFIG CARD ---- */}
        <div className="col-span-4">
          <Card className="p-5 bg-[#0f1629] border border-[rgba(148,163,184,0.08)] h-full">
            <div className="flex items-center gap-2 mb-4">
              <Settings2 className="w-4 h-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold">Konfiguracja LLM</h2>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5 block">Dostawca</label>
                <select
                  value={llmConfig.provider}
                  onChange={(e) => setLlmConfig((c) => ({ ...c, provider: e.target.value as LLMConfig["provider"] }))}
                  className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs text-foreground focus:outline-none focus:border-primary/30 cursor-pointer"
                >
                  <option value="anthropic">Anthropic</option>
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama (lokalnie)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5 block">Nazwa modelu</label>
                <input
                  type="text"
                  value={llmConfig.modelName}
                  onChange={(e) => setLlmConfig((c) => ({ ...c, modelName: e.target.value }))}
                  placeholder={
                    llmConfig.provider === "anthropic" ? "claude-sonnet-4-20250514"
                      : llmConfig.provider === "openai" ? "gpt-4o"
                      : llmConfig.provider === "ollama" ? "llama3.1:8b"
                      : "nazwa modelu dostawcy"
                  }
                  className="w-full bg-secondary/30 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs text-foreground font-mono placeholder:text-muted-foreground focus:outline-none focus:border-primary/30 disabled:opacity-50"
                />
              </div>

              <Button onClick={handleSaveConfig} variant="outline" size="sm" className="w-full mt-1">
                {configSaving ? <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 text-sylion-green" /> : null}
                {configSaving ? "Zapisano" : "Zapisz konfigurację"}
              </Button>

              <p className="text-[9px] text-muted-foreground leading-relaxed">
                To jest wskazówka operatora. Wykonanie runtime używa KeyVault backendu i rejestru modeli z AI Models; syntetyczni dostawcy testówi nie wykonują zadań w trybie audytu.
              </p>
            </div>
          </Card>
        </div>
      </div>

      {/* ====== RUNS LIST ====== */}
      <Card className="p-0 bg-[#0f1629] border border-[rgba(148,163,184,0.08)] overflow-hidden">
        <div className="px-5 pt-4 pb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ListChecks className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-semibold">Przebiegi pipeline</h2>
            {hasActive && (
              <Badge variant="outline" className="text-[9px] border-sylion-blue/30 text-sylion-blue">
                <span className="w-1.5 h-1.5 rounded-full bg-sylion-blue mr-1 animate-pulse" />
                Auto-odświeżanie (5 s)
              </Badge>
            )}
          </div>
          <span className="text-[10px] text-muted-foreground">{totalRuns} razem</span>
        </div>

        <Table>
          <TableHeader>
            <TableRow className="border-b" style={{ borderBottomColor: "rgba(148,163,184,0.08)" }}>
              <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">ID przebiegu</TableHead>
              <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Pomysł</TableHead>
              <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Status</TableHead>
              <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Utworzono</TableHead>
              <TableHead className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium text-right">Akcje</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <Loader2 className="w-5 h-5 text-muted-foreground animate-spin mx-auto" />
                  <p className="text-xs text-muted-foreground mt-2">Ładowanie przebiegów...</p>
                </TableCell>
              </TableRow>
            ) : fetchError && runs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <WifiOff className="w-6 h-6 text-sylion-red/60 mx-auto mb-2" />
                  <p className="text-xs text-sylion-red/80 font-medium">Backend niedostępny</p>
                  <p className="text-[10px] text-muted-foreground mt-1">Uruchom backend: <code className="text-primary">python -m uvicorn sylion.api.app:app --port 8010</code></p>
                </TableCell>
              </TableRow>
            ) : runs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <Rocket className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
                  <p className="text-xs text-muted-foreground">Brak przebiegów pipeline. Zgłoś pomysł powyżej, aby zacząć.</p>
                </TableCell>
              </TableRow>
            ) : (
              runs.map((run) => {
                const StatusIcon = STATUS_ICONS[run.status] || Clock;
                const isExpanded = selectedRunId === run.run_id;
                const isActionLoading = actionLoading[run.run_id] ?? false;

                return (
                  <React.Fragment key={run.run_id}>
                    <TableRow
                      className="border-b hover:bg-muted/20 transition-colors cursor-pointer"
                      style={{ borderBottomColor: "rgba(148,163,184,0.04)" }}
                      onClick={() => setSelectedRunId(isExpanded ? null : run.run_id)}
                    >
                      {/* Run ID */}
                      <TableCell className="font-mono text-xs text-foreground">
                        {run.run_id.slice(0, 12)}
                      </TableCell>

                      {/* Idea */}
                      <TableCell className="max-w-[400px]">
                        <p className="text-xs text-foreground truncate">{truncate(run.idea, 80)}</p>
                      </TableCell>

                      {/* Status */}
                      <TableCell>
                        <Badge variant="outline" className={cn("text-[9px] h-5", STATUS_COLORS[run.status] || "border-muted-foreground/30 text-muted-foreground bg-muted/30")}>
                          <StatusIcon className={cn(
                            "w-2.5 h-2.5 mr-1",
                            run.status === "generating" && "animate-spin"
                          )} />
                          {STATUS_LABELS[run.status] ?? run.status}
                        </Badge>
                      </TableCell>

                      {/* Created */}
                      <TableCell className="text-[11px] text-muted-foreground whitespace-nowrap">
                        {formatRelative(run.created_at)}
                      </TableCell>

                      {/* Actions */}
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                          {/* Execute */}
                          {(run.status === "pending" || run.status === "planning") && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-sylion-green hover:text-sylion-green hover:bg-sylion-green/10"
                              onClick={() => handleExecute(run.run_id)}
                              disabled={isActionLoading}
                              title="Wykonaj przebieg"
                            >
                              {isActionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                            </Button>
                          )}

                          {/* Cancel */}
                          {(run.status === "pending" || run.status === "planning" || run.status === "generating") && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-sylion-red hover:text-sylion-red hover:bg-sylion-red/10"
                              onClick={() => handleCancel(run.run_id)}
                              disabled={isActionLoading}
                              title="Anuluj przebieg"
                            >
                              <X className="w-3.5 h-3.5" />
                            </Button>
                          )}

                          {/* View Steps toggle */}
                          <Button
                            variant="ghost"
                            size="sm"
                            className={cn(
                              "h-7 w-7 p-0",
                              isExpanded ? "text-primary" : "text-muted-foreground hover:text-foreground"
                            )}
                            onClick={() => setSelectedRunId(isExpanded ? null : run.run_id)}
                            title="Pokaż kroki"
                          >
                            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>

                    {/* Expanded step details */}
                    <AnimatePresence>
                      {isExpanded && (
                        <tr>
                          <td colSpan={5} className="p-0 border-b" style={{ borderBottomColor: "rgba(148,163,184,0.04)" }}>
                            <StepDetails steps={run.steps} />
                          </td>
                        </tr>
                      )}
                    </AnimatePresence>
                  </React.Fragment>
                );
              })
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}

export default function PipelinePage() {
  return (
    <Suspense
      fallback={
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-8 text-center text-sm text-muted-foreground">
          Ladowanie pipeline...
        </Card>
      }
    >
      <PipelineContent />
    </Suspense>
  );
}
