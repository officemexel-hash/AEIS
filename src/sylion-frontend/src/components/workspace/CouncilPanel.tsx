"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useHealth } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import {
  Loader2,
  CheckCircle2,
  Users,
  Play,
  ArrowRight,
  WifiOff,
  Sparkles,
  ThumbsUp,
  ThumbsDown,
  MinusCircle,
  Plus,
  RotateCcw,
} from "lucide-react";

const PHASES = ["parallel", "verdicts", "discussion", "consolidated"] as const;
const PHASE_LABELS = ["Analysis", "Verdicts", "Discussion", "Consolidated"];

const VERDICT_STYLES: Record<string, { color: string; icon: React.ElementType }> = {
  approve: { color: "text-sylion-green", icon: ThumbsUp },
  reject: { color: "text-sylion-red", icon: ThumbsDown },
  conditional: { color: "text-sylion-amber", icon: MinusCircle },
};

export function CouncilPanel() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";

  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);

  // New council form state
  const [topic, setTopic] = useState("");
  const [description, setDescription] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [phase, setPhase] = useState<string | null>(null);
  const [analyses, setAnalyses] = useState<any[]>([]);
  const [discussion, setDiscussion] = useState<any[]>([]);
  const [consolidated, setConsolidated] = useState<string>("");
  const [loading, setLoading] = useState(false);

  // Fetch sessions
  useEffect(() => {
    if (!backendLive) return;
    api.listCouncilSessions().then((d) => setSessions(d.sessions ?? [])).catch(() => {});
  }, [backendLive]);

  // Auto-refresh session list
  useEffect(() => {
    if (!backendLive) return;
    const interval = setInterval(() => {
      api.listCouncilSessions().then((d) => setSessions(d.sessions ?? [])).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [backendLive]);

  const resetActive = useCallback(() => {
    setSessionId(null);
    setPhase(null);
    setAnalyses([]);
    setDiscussion([]);
    setConsolidated("");
    setActiveSessionId(null);
    setShowNew(false);
    setTopic("");
    setDescription("");
  }, []);

  const startCouncil = async () => {
    if (!topic.trim() || !backendLive) return;
    setLoading(true);
    try {
      const models = ["claude", "gpt-4", "ollama"];
      const result = await api.openHybridCouncil(topic, description, models);
      if (result.session_id) {
        setSessionId(result.session_id);
        setActiveSessionId(result.session_id);
        setPhase("parallel");
        setShowNew(false);
        // Refresh session list
        const d = await api.listCouncilSessions();
        setSessions(d.sessions ?? []);
      }
    } catch {}
    setLoading(false);
  };

  const selectSession = (id: string) => {
    setActiveSessionId(id);
    // If the session is the one currently being deliberated, restore state
    if (id === sessionId) return;
    // For previous sessions, just show the ID; user would need to resume phases
    setSessionId(id);
    setPhase(null);
    setAnalyses([]);
    setDiscussion([]);
    setConsolidated("");
  };

  const runAnalysis = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const result = await api.runParallelAnalysis(sessionId);
      setAnalyses(result.analyses ?? []);
      setPhase("verdicts");
    } catch {}
    setLoading(false);
  };

  const runDiscussion = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const result = await api.runDiscussion(sessionId, 2);
      setDiscussion(result.rounds ?? []);
      setPhase("discussion");
    } catch {}
    setLoading(false);
  };

  const runConsolidate = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const result = await api.consolidateCouncil(sessionId);
      setConsolidated(result.consolidated?.suggestion ?? result.consolidated_suggestion ?? "");
      setPhase("consolidated");
    } catch {}
    setLoading(false);
  };

  if (!backendLive) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <WifiOff className="w-8 h-8 text-sylion-red/50 mb-3" />
        <p className="text-xs text-muted-foreground">Backend niedostępny</p>
        <p className="text-[10px] text-muted-foreground mt-1">
          Start: <code className="text-primary">python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010</code>
        </p>
      </div>
    );
  }

  const currentPhaseIdx = phase ? PHASES.indexOf(phase as any) : -1;

  return (
    <div className="flex h-full">
      {/* Session List Sidebar */}
      <div className="w-48 shrink-0 border-r border-[rgba(148,163,184,0.06)] p-2 space-y-1 overflow-y-auto">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-[11px] h-7"
          onClick={() => { setShowNew(true); resetActive(); }}
        >
          <Plus className="w-3 h-3 mr-1.5" /> New Council
        </Button>
        {sessions.map((s) => (
          <button
            key={s.session_id}
            onClick={() => selectSession(s.session_id)}
            className={cn(
              "w-full text-left px-2.5 py-2 rounded-lg text-[11px] transition-colors",
              activeSessionId === s.session_id
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted/20"
            )}
          >
            <span className="truncate block">{s.topic || s.session_id?.slice(0, 12)}</span>
            {s.phase && (
              <span className="text-[9px] text-muted-foreground/60">{s.phase}</span>
            )}
          </button>
        ))}
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* New Council Form */}
        {showNew && (
          <div className="flex-1 flex flex-col items-center justify-center max-w-md mx-auto p-4">
            <Users className="w-8 h-8 text-primary/30 mb-4" />
            <h3 className="text-sm font-semibold mb-3">Start Council Deliberation</h3>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Topic for council deliberation..."
              className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30 mb-2"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detailed description (optional)..."
              rows={3}
              className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded-lg px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30 resize-none mb-3"
            />
            <Button onClick={startCouncil} disabled={!topic.trim() || loading} className="w-full">
              {loading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Users className="w-3.5 h-3.5 mr-1.5" />}
              Start Council
            </Button>
          </div>
        )}

        {/* Empty State (no session selected, not creating new) */}
        {!showNew && !sessionId && (
          <div className="flex-1 flex flex-col items-center justify-center">
            <Users className="w-8 h-8 text-primary/30 mb-3" />
            <p className="text-xs text-muted-foreground">Select or create a council session</p>
          </div>
        )}

        {/* Active Council */}
        {sessionId && !showNew && (
          <>
            {/* Phase Stepper */}
            {phase && (
              <div className="flex items-center gap-1 px-4 pt-3 pb-2 border-b border-[rgba(148,163,184,0.06)]">
                {PHASES.map((p, i) => (
                  <React.Fragment key={p}>
                    <div className={cn(
                      "flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-medium",
                      i <= currentPhaseIdx ? "bg-primary/10 text-primary" : "text-muted-foreground/40"
                    )}>
                      {i < currentPhaseIdx ? (
                        <CheckCircle2 className="w-3 h-3 text-sylion-green" />
                      ) : i === currentPhaseIdx ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <div className="w-3 h-3 rounded-full border border-muted-foreground/20" />
                      )}
                      {PHASE_LABELS[i]}
                    </div>
                    {i < PHASES.length - 1 && <ArrowRight className="w-3 h-3 text-muted-foreground/20" />}
                  </React.Fragment>
                ))}
              </div>
            )}

            {/* Session info when no phase (previous session selected) */}
            {!phase && activeSessionId && (
              <div className="p-4 space-y-3">
                <Card className="p-3 bg-card border-sylion-border">
                  <p className="text-[11px] font-medium mb-1">Council Session</p>
                  <p className="text-[9px] text-muted-foreground">ID: {activeSessionId.slice(0, 24)}</p>
                  <p className="text-[10px] text-muted-foreground mt-2">
                    Use the action buttons below to run council phases for this session.
                  </p>
                </Card>
              </div>
            )}

            {/* Phase Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {/* Verdicts */}
              {phase === "verdicts" && analyses.map((a, i) => {
                const style = VERDICT_STYLES[a.verdict] || VERDICT_STYLES.conditional;
                const VerdictIcon = style.icon;
                return (
                  <Card key={i} className="p-3 bg-card border-sylion-border">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium">{a.model_id}</span>
                      <Badge variant="outline" className={cn("text-[9px]", style.color)}>
                        <VerdictIcon className="w-2.5 h-2.5 mr-1" />
                        {a.verdict}
                      </Badge>
                    </div>
                    {a.confidence > 0 && (
                      <div className="w-full h-1.5 rounded-full bg-secondary mb-2">
                        <div className={cn("h-full rounded-full", a.verdict === "approve" ? "bg-sylion-green" : a.verdict === "reject" ? "bg-sylion-red" : "bg-sylion-amber")} style={{ width: `${a.confidence * 100}%` }} />
                      </div>
                    )}
                    {a.rationale && <p className="text-[10px] text-muted-foreground">{a.rationale}</p>}
                  </Card>
                );
              })}

              {/* Discussion */}
              {(phase === "discussion" || phase === "consolidated") && discussion.map((r, i) => (
                <Card key={i} className="p-3 bg-card border-sylion-border">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="outline" className="text-[9px]">Round {r.round_number}</Badge>
                    <span className="text-[10px] font-medium text-primary">{r.speaker_model_id}</span>
                  </div>
                  <p className="text-[10px] text-muted-foreground leading-relaxed">{r.content}</p>
                </Card>
              ))}

              {/* Consolidated */}
              {phase === "consolidated" && consolidated && (
                <Card className="p-4 bg-sylion-green/5 border-sylion-green/20">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4 text-sylion-green" />
                    <span className="text-xs font-semibold text-sylion-green">Consolidated Suggestion</span>
                  </div>
                  <p className="text-xs leading-relaxed">{consolidated}</p>
                </Card>
              )}
            </div>

            {/* Action Buttons */}
            <div className="px-4 pb-3 pt-2 border-t border-[rgba(148,163,184,0.06)] flex gap-2">
              {(phase === "parallel" || !phase) && (
                <Button size="sm" onClick={runAnalysis} disabled={loading}>
                  {loading ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Play className="w-3.5 h-3.5 mr-1" />}
                  Run Analysis
                </Button>
              )}
              {phase === "verdicts" && (
                <Button size="sm" onClick={runDiscussion} disabled={loading}>
                  {loading ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Users className="w-3.5 h-3.5 mr-1" />}
                  Start Discussion
                </Button>
              )}
              {phase === "discussion" && (
                <Button size="sm" onClick={runConsolidate} disabled={loading}>
                  {loading ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1" />}
                  Consolidate
                </Button>
              )}
              <Button size="sm" variant="outline" onClick={resetActive} className="ml-auto">
                <RotateCcw className="w-3 h-3 mr-1" /> Reset
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
