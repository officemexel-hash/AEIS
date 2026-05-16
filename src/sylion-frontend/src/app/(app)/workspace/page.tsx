"use client";

import React, { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { SplitView } from "@/components/workspace/SplitView";
import { ChatPanel } from "@/components/workspace/ChatPanel";
import { CouncilPanel } from "@/components/workspace/CouncilPanel";
import { PromptManager } from "@/components/workspace/PromptManager";
import { BookGeneratorPanel } from "@/components/workspace/BookGeneratorPanel";
import { HumanGatePanel } from "@/components/workspace/HumanGatePanel";
import { PipelineVisualization } from "@/components/workspace/PipelineVisualization";
import { api } from "@/lib/api/client";
import { useHealth, usePipelineRunsWithWS } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Brain,
  MessageSquare,
  Users,
  Rocket,
  Play,
  Eye,
  Columns2,
  BookOpen,
  GitBranch,
  Loader2,
  Send,
  XCircle,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";

export default function WorkspacePage() {
  const [leftTab, setLeftTab] = useState("chat");
  const [rightTab, setRightTab] = useState("pipeline");

  return (
    <div className="space-y-3 h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Columns2 className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Przestrzeń robocza AI
              <HelpTip text="Dwupanelowa przestrzeń pracy operatora: lewy panel (Thinking Layer) — chat z modelami, naradzie rady, księgi wiedzy, Human Gate; prawy (Working Layer) — pipeline, kod, output. Każda sesja audytowana." />
            </h1>
            <p className="text-sm text-muted-foreground">
              Warstwa Thinking + Warstwa Working
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <PromptManager />
          <Badge variant="outline" className="text-[10px] border-primary/30 text-primary">
            <Brain className="w-3 h-3 mr-1" />
            Multi-Model
          </Badge>
        </div>
      </div>

      {/* Split View */}
      <div className="h-[calc(100vh-12rem)] border border-[rgba(148,163,184,0.08)] rounded-xl overflow-hidden">
        <SplitView
          defaultSplit={0.45}
          left={
            <div className="h-full flex flex-col bg-[#0a0f1e]">
              {/* AI Thinking Layer Header */}
              <div className="px-4 pt-3 pb-2 border-b border-[rgba(148,163,184,0.08)]">
                <Tabs value={leftTab} onValueChange={setLeftTab}>
                  <div className="flex items-center gap-2">
                    <TabsList className="bg-transparent h-8 p-0 gap-4">
                      <TabsTrigger
                        value="chat"
                        className="bg-transparent px-0 py-1 text-xs data-[state=active]:text-primary data-[state=active]:shadow-none data-[state=active]:bg-transparent border-b-2 border-transparent data-[state=active]:border-primary rounded-none"
                      >
                        <MessageSquare className="w-3.5 h-3.5 mr-1.5" />
                        Czat
                      </TabsTrigger>
                      <TabsTrigger
                        value="council"
                        className="bg-transparent px-0 py-1 text-xs data-[state=active]:text-primary data-[state=active]:shadow-none data-[state=active]:bg-transparent border-b-2 border-transparent data-[state=active]:border-primary rounded-none"
                      >
                        <Users className="w-3.5 h-3.5 mr-1.5" />
                        Rada
                      </TabsTrigger>
                      <TabsTrigger
                        value="books"
                        className="bg-transparent px-0 py-1 text-xs data-[state=active]:text-primary data-[state=active]:shadow-none data-[state=active]:bg-transparent border-b-2 border-transparent data-[state=active]:border-primary rounded-none"
                      >
                        <BookOpen className="w-3.5 h-3.5 mr-1.5" />
                        Ksiegi
                      </TabsTrigger>
                      <TabsTrigger
                        value="gate"
                        className="bg-transparent px-0 py-1 text-xs data-[state=active]:text-primary data-[state=active]:shadow-none data-[state=active]:bg-transparent border-b-2 border-transparent data-[state=active]:border-primary rounded-none"
                      >
                        <GitBranch className="w-3.5 h-3.5 mr-1.5" />
                        Bramka
                      </TabsTrigger>
                    </TabsList>
                    <HelpTip text="Warstwa Thinking — narzedzia analizy: Czat (1-na-1 z modelem), Rada (debata wielu modeli), Ksiegi (knowledge base, generator dokumentow), Bramka (Human Gate dla decyzji D3+)." />
                  </div>
                </Tabs>
              </div>

              {/* AI Panel Content */}
              <div className="flex-1 overflow-y-auto">
                {leftTab === "chat" && <ChatPanel />}
                {leftTab === "council" && <CouncilPanel />}
                {leftTab === "books" && <BookGeneratorPanel />}
                {leftTab === "gate" && <HumanGatePanel />}
              </div>
            </div>
          }
          right={
            <div className="h-full flex flex-col bg-[#0a0f1e]">
              {/* Working Layer Header */}
              <div className="px-4 pt-3 pb-2 border-b border-[rgba(148,163,184,0.08)]">
                <Tabs value={rightTab} onValueChange={setRightTab}>
                  <div className="flex items-center gap-2">
                    <TabsList className="bg-transparent h-8 p-0 gap-4">
                      <TabsTrigger
                        value="pipeline"
                        className="bg-transparent px-0 py-1 text-xs data-[state=active]:text-primary data-[state=active]:shadow-none data-[state=active]:bg-transparent border-b-2 border-transparent data-[state=active]:border-primary rounded-none"
                      >
                        <Rocket className="w-3.5 h-3.5 mr-1.5" />
                        Pipeline
                      </TabsTrigger>
                      <TabsTrigger
                        value="code"
                        className="bg-transparent px-0 py-1 text-xs data-[state=active]:text-primary data-[state=active]:shadow-none data-[state=active]:bg-transparent border-b-2 border-transparent data-[state=active]:border-primary rounded-none"
                      >
                        <Play className="w-3.5 h-3.5 mr-1.5" />
                        Kod
                      </TabsTrigger>
                      <TabsTrigger
                        value="output"
                        className="bg-transparent px-0 py-1 text-xs data-[state=active]:text-primary data-[state=active]:shadow-none data-[state=active]:bg-transparent border-b-2 border-transparent data-[state=active]:border-primary rounded-none"
                      >
                        <Eye className="w-3.5 h-3.5 mr-1.5" />
                        Wynik
                      </TabsTrigger>
                    </TabsList>
                    <HelpTip text="Warstwa Working — wykonanie: Pipeline (uruchamianie idei, faza po fazie), Kod (snapshoty wygenerowanego kodu z runów), Wynik (logi wykonania w czasie rzeczywistym)." />
                  </div>
                </Tabs>
              </div>

              {/* Working Panel Content */}
              <div className="flex-1 overflow-y-auto p-4">
                {rightTab === "pipeline" && <WorkingPipeline />}
                {rightTab === "code" && <WorkingCode />}
                {rightTab === "output" && <WorkingOutput />}
              </div>
            </div>
          }
        />
      </div>
    </div>
  );
}

/* ─── Right panel: Pipeline ──────────────────────────────────── */

function WorkingPipeline() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";
  const { data: pipelineData, refresh: refreshRuns } = usePipelineRunsWithWS();
  const runs = pipelineData.runs ?? [];
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<any>(null);
  const [steps, setSteps] = useState<any[]>([]);
  const [idea, setIdea] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [executing, setExecuting] = useState(false);

  const submitRun = async () => {
    if (!idea.trim() || submitting) return;
    setSubmitting(true);
    try {
      const result = await api.submitPipelineRun(idea);
      setIdea("");
      refreshRuns();
      if (result.run_id) selectRun(result.run_id);
    } catch {}
    setSubmitting(false);
  };

  const selectRun = async (runId: string) => {
    setSelectedRun(runId);
    try {
      const detail = await api.getPipelineRun(runId);
      setRunDetail(detail);
      const stepsData = await api.getPipelineRunSteps(runId);
      setSteps(stepsData.steps ?? []);
    } catch {
      setRunDetail(null);
      setSteps([]);
    }
  };

  const executeRun = async () => {
    if (!selectedRun || executing) return;
    setExecuting(true);
    try {
      await api.executePipelineRun(selectedRun);
      await selectRun(selectedRun);
    } catch {}
    setExecuting(false);
  };

  const cancelRun = async () => {
    if (!selectedRun) return;
    try {
      await api.cancelPipelineRun(selectedRun);
      await selectRun(selectedRun);
    } catch {}
  };

  if (!backendLive) {
    return <p className="text-xs text-muted-foreground text-center py-8">Backend nieosięgalny</p>;
  }

  return (
    <div className="space-y-3">
      {/* Submit idea */}
      <div className="flex gap-2">
        <input
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitRun()}
          placeholder="Wyślij pomysł do uruchomienia w pipeline..."
          className="flex-1 bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30"
        />
        <Button size="sm" className="h-8 text-[10px] gap-1" onClick={submitRun} disabled={submitting || !idea.trim()}>
          {submitting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
          Wyślij
        </Button>
      </div>

      {/* Run list */}
      {runs.length > 0 && (
        <div className="space-y-1">
          {runs.map((run) => (
            <button
              key={run.run_id}
              onClick={() => selectRun(run.run_id)}
              className={cn(
                "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors",
                selectedRun === run.run_id
                  ? "bg-primary/10 border border-primary/15"
                  : "bg-card border border-[rgba(148,163,184,0.06)] hover:border-primary/10"
              )}
            >
              <div className="flex items-center gap-2 min-w-0">
                <StatusIcon status={run.status} />
                <span className="truncate">{run.idea || run.run_id?.slice(0, 16)}</span>
              </div>
              <span className="text-[9px] text-muted-foreground shrink-0">{run.status}</span>
            </button>
          ))}
        </div>
      )}

      {/* Selected run detail */}
      {runDetail && (
        <Card className="p-3 bg-card border-[rgba(148,163,184,0.06)] space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium truncate max-w-[300px]">{runDetail.idea}</p>
              <p className="text-[9px] text-muted-foreground">ID: {runDetail.run_id?.slice(0, 16)}</p>
            </div>
            <div className="flex gap-1.5">
              {runDetail.status === "pending" && (
                <Button size="sm" className="h-6 text-[9px]" onClick={executeRun} disabled={executing}>
                  {executing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Play className="w-3 h-3 mr-1" />}
                  Wykonaj
                </Button>
              )}
              {runDetail.status === "running" && (
                <Button variant="outline" size="sm" className="h-6 text-[9px] border-sylion-red/30 text-sylion-red" onClick={cancelRun}>
                  <XCircle className="w-3 h-3 mr-1" /> Anuluj
                </Button>
              )}
            </div>
          </div>

          {/* Pipeline visualization */}
          <PipelineVisualization steps={steps} runStatus={runDetail.status} />
        </Card>
      )}

      {runs.length === 0 && (
        <p className="text-xs text-muted-foreground text-center py-4">Brak uruchomionych pipeline&apos;ów. Wyślij pomysł powyżej.</p>
      )}
    </div>
  );
}

/* ─── Right panel: Code ──────────────────────────────────────── */

function WorkingCode() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";
  const [runs, setRuns] = useState<any[]>([]);
  const [codeSteps, setCodeSteps] = useState<any[]>([]);

  useEffect(() => {
    if (!backendLive) return;
    api.listPipelineRuns().then(async (d) => {
      const allRuns = d.runs ?? [];
      setRuns(allRuns);
      // Collect code output from all completed runs
      const codeOutputs: any[] = [];
      for (const run of allRuns) {
        try {
          const stepsData = await api.getPipelineRunSteps(run.run_id);
          for (const step of (stepsData.steps ?? [])) {
            if (getPipelineStepOutput(step)) codeOutputs.push({ run_id: run.run_id, idea: run.idea, step });
          }
        } catch {}
      }
      setCodeSteps(codeOutputs);
    }).catch(() => {});
  }, [backendLive]);

  if (!backendLive) return <p className="text-xs text-muted-foreground text-center py-8">Backend nieosięgalny</p>;

  return (
    <div className="space-y-3">
      {codeSteps.length > 0 ? (
        codeSteps.map((item, i) => (
          <Card key={i} className="p-3 bg-[#0a0f1e] border-[rgba(148,163,184,0.06)]">
            <p className="text-[9px] text-muted-foreground mb-1.5">
              {getPipelineStepLabel(item.step)} &middot; {item.run_id?.slice(0, 12)}
            </p>
            <pre className="text-[10px] text-green-400/80 font-mono whitespace-pre-wrap max-h-60 overflow-y-auto">
              {getPipelineStepOutput(item.step)}
            </pre>
          </Card>
        ))
      ) : (
        <Card className="p-4 bg-[#0a0f1e] border-[rgba(148,163,184,0.06)] font-mono text-xs text-muted-foreground">
          <pre>{`// Wynik kodu pojawi sie tutaj\n// gdy pipeline wygeneruje kod`}</pre>
        </Card>
      )}
    </div>
  );
}

/* ─── Right panel: Output ────────────────────────────────────── */

function WorkingOutput() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";
  const [logs, setLogs] = useState<any[]>([]);

  useEffect(() => {
    if (!backendLive) return;
    api.listPipelineRuns().then(async (d) => {
      const allRuns = d.runs ?? [];
      const allLogs: any[] = [];
      for (const run of allRuns) {
        try {
          const stepsData = await api.getPipelineRunSteps(run.run_id);
          for (const step of (stepsData.steps ?? [])) {
            allLogs.push({
              run_id: run.run_id,
              idea: run.idea,
              phase: getPipelineStepLabel(step),
              status: step.status,
              timestamp: getPipelineStepTimestamp(step) || run.completed_at || run.created_at,
            });
          }
        } catch {}
      }
      setLogs(allLogs);
    }).catch(() => {});
  }, [backendLive]);

  if (!backendLive) return <p className="text-xs text-muted-foreground text-center py-8">Backend nieosięgalny</p>;

  return (
    <div className="space-y-2">
      <p className="text-[11px] font-medium text-foreground">
        Log wykonania
        <HelpTip text="Strumień zdarzeń z aktywnych runów pipeline: faza, status, timestamp. Liczba i częstotliwość — w czasie rzeczywistym z websocketa. Pełne logi w każdym pojedynczym runie." />
      </p>
      {logs.length > 0 ? (
        logs.map((log, i) => (
          <div key={i} className="flex items-center gap-2 px-2 py-1.5 rounded bg-secondary/5 border border-[rgba(148,163,184,0.04)]">
            <StatusIcon status={log.status} />
            <span className="text-[10px] text-primary font-medium">{log.phase}</span>
            <span className="text-[10px] text-muted-foreground truncate flex-1">
              {log.idea?.slice(0, 40) || log.run_id?.slice(0, 12)}
            </span>
            <span className="text-[9px] text-muted-foreground shrink-0">
              {log.status}
            </span>
            <span className="text-[9px] text-muted-foreground shrink-0">
              {log.timestamp ? new Date(log.timestamp * 1000).toLocaleTimeString() : ""}
            </span>
          </div>
        ))
      ) : (
        <Card className="p-4 bg-[#0a0f1e] border-[rgba(148,163,184,0.06)]">
          <p className="text-xs text-muted-foreground italic">Brak wyników. Uruchom pipeline aby zobaczyć rezultaty.</p>
        </Card>
      )}
    </div>
  );
}

/* ─── Helpers ────────────────────────────────────────────────── */

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
    case "complete":
    case "pass":
      return <CheckCircle2 className="w-3.5 h-3.5 text-sylion-green shrink-0" />;
    case "running":
    case "in_progress":
      return <Loader2 className="w-3.5 h-3.5 text-primary animate-spin shrink-0" />;
    case "failed":
    case "fail":
    case "cancelled":
      return <XCircle className="w-3.5 h-3.5 text-sylion-red shrink-0" />;
    case "pending":
      return <Clock className="w-3.5 h-3.5 text-muted-foreground shrink-0" />;
    default:
      return <AlertTriangle className="w-3.5 h-3.5 text-sylion-amber shrink-0" />;
  }
}

function getPipelineStepLabel(step: any): string {
  return String(step?.phase || step?.step_type || step?.name || step?.step_id || "Output");
}

function getPipelineStepTimestamp(step: any): number {
  const result = step?.result || {};
  return Number(step?.timestamp || result.timestamp || 0);
}

function getPipelineStepOutput(step: any): string {
  const raw = step?.output ?? step?.result?.output ?? step?.result?.result ?? step?.result;
  if (!raw) return "";
  if (typeof raw === "string") return raw;
  return JSON.stringify(raw, null, 2);
}
