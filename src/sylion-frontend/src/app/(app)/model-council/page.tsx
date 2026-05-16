"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { HelpTip } from "@/components/common/HelpTip";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  Loader2,
  Plus,
  ShieldAlert,
  Sparkles,
  Users,
  Vote,
  WifiOff,
  XCircle,
} from "lucide-react";

// --------------------------------------------------------------------------
// Typy domenowe — ksztalt odpowiedzi backendu (workspace/council/*)
// --------------------------------------------------------------------------

type CouncilSession = {
  session_id: string;
  topic?: string;
  context?: string;
  status?: string;
  phase?: string;
  created_at?: number;
  closed_at?: number | null;
  consolidated_text?: string;
  consensus_level?: number;
};

type Participant = {
  participant_id?: string;
  model_id: string;
  role: string;
  rank: string;
  weight?: number;
};

type ConsensusByModel = {
  model_id?: string;
  verdict?: string;
  weight?: number;
  role?: string;
  rank?: string;
  confidence?: number;
};

type Consensus = {
  verdict?: string;
  weights?: Record<string, number>;
  total_weight?: number;
  by_model?: Record<string, ConsensusByModel> | ConsensusByModel[];
  critic_signed?: boolean;
  sentinel_blocks?: Array<Record<string, unknown>>;
  details?: string;
  [key: string]: unknown;
};

type Roles = {
  roles: string[];
  ranks: string[];
  default_role_weights: Record<string, number>;
  rank_multiplier: Record<string, number>;
  sentinel_roles: string[];
};

const ROLE_LABELS_PL: Record<string, string> = {
  planner: "Planista",
  architect: "Architekt",
  critic: "Krytyk",
  verifier: "Weryfikator",
  governance: "Zarzad",
  cost_sentinel: "Sentinel kosztu",
  security_sentinel: "Sentinel bezpiecze?stwa",
  domain_specialist: "Specjalista dziedziny",
  funding_specialist: "Specjalista finansowy",
};

const RANK_LABELS_PL: Record<string, string> = {
  primary: "Glowny",
  senior: "Senior",
  support: "Wsparcie",
  review_only: "Tylko przeglad",
  validation_only: "Tylko walidacja",
};

const VERDICT_LABELS_PL: Record<string, string> = {
  approve: "akceptacja",
  reject: "odrzucenie",
  conditional: "warunkowe",
  pass: "ok",
  fail: "blok",
};

function classForVerdict(verdict?: string): string {
  if (!verdict) return "text-muted-foreground";
  if (verdict === "approve" || verdict === "pass") return "text-sylion-green";
  if (verdict === "reject" || verdict === "fail") return "text-sylion-red";
  return "text-sylion-amber";
}

function formatNumber(n: number | undefined, frac = 2): string {
  if (typeof n !== "number" || Number.isNaN(n)) return "-";
  return n.toFixed(frac);
}

// --------------------------------------------------------------------------
// Strona /model-council
// --------------------------------------------------------------------------

export default function ModelCouncilPage() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";

  const [sessions, setSessions] = useState<CouncilSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeSession, setActiveSession] = useState<CouncilSession | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [criticSignatures, setCriticSignatures] = useState<any[]>([]);
  const [sentinelEvals, setSentinelEvals] = useState<any[]>([]);
  const [consensus, setConsensus] = useState<Consensus | null>(null);
  const [roles, setRoles] = useState<Roles | null>(null);
  const [tab, setTab] = useState<string>("participants");
  const [loading, setLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [discussionLoading, setDiscussionLoading] = useState(false);
  const [roundNotice, setRoundNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Nowa sesja modal
  const [newOpen, setNewOpen] = useState(false);
  const [newTopic, setNewTopic] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newModels, setNewModels] = useState("claude,gpt-4,ollama");

  // Add participant modal
  const [participantOpen, setParticipantOpen] = useState(false);
  const [partModelId, setPartModelId] = useState("");
  const [partRole, setPartRole] = useState("planner");
  const [partRank, setPartRank] = useState("primary");

  // Critic sign form
  const [criticModel, setCriticModel] = useState("");
  const [criticDecision, setCriticDecision] = useState("approve");
  const [criticRationale, setCriticRationale] = useState("");

  // Sentinel evaluation form
  const [sentRole, setSentRole] = useState("cost_sentinel");
  const [sentModel, setSentModel] = useState("");
  const [sentVerdict, setSentVerdict] = useState("pass");
  const [sentScore, setSentScore] = useState<string>("0");
  const [sentDetails, setSentDetails] = useState("");

  // Consolidate form
  const [consText, setConsText] = useState("");
  const [reqCritic, setReqCritic] = useState(true);
  const [reqSentinels, setReqSentinels] = useState(true);
  const [consolidatedResult, setConsolidatedResult] = useState<any>(null);

  // ---- Fetchery ----

  const refreshSessions = useCallback(async () => {
    if (!backendLive) return;
    try {
      const data = await api.listCouncilSessions();
      setSessions(data.sessions ?? []);
    } catch (e) {
      setError(`Lista sesji: ${(e as Error).message}`);
    }
  }, [backendLive]);

  const refreshActive = useCallback(
    async (sid: string) => {
      try {
        const [sess, parts, sigs, evals, cons] = await Promise.all([
          api.getCouncilSession(sid).catch(() => null),
          api.listCouncilParticipants(sid).catch(() => ({ participants: [] })),
          api.listCriticSignatures(sid).catch(() => ({ signatures: [], signed: false })),
          api.listSentinelEvaluations(sid).catch(() => ({ evaluations: [] })),
          api.getCouncilConsensus(sid).catch(() => null),
        ]);
        setActiveSession(sess);
        setParticipants(parts.participants ?? []);
        setCriticSignatures(sigs.signatures ?? []);
        setSentinelEvals(evals.evaluations ?? []);
        setConsensus(cons);
      } catch (e) {
        setError(`Sesja ${sid}: ${(e as Error).message}`);
      }
    },
    [],
  );

  useEffect(() => {
    if (!backendLive) return;
    void refreshSessions();
    api.getCouncilRoles().then(setRoles).catch(() => {});
  }, [backendLive, refreshSessions]);

  useEffect(() => {
    if (activeId) {
      void refreshActive(activeId);
    } else {
      setActiveSession(null);
      setParticipants([]);
      setCriticSignatures([]);
      setSentinelEvals([]);
      setConsensus(null);
      setConsolidatedResult(null);
      setRoundNotice(null);
    }
  }, [activeId, refreshActive]);

  // ---- Akcje ----

  const handleCreate = async () => {
    if (!newTopic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const ids = newModels
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const res = await api.createCouncilSession(newTopic.trim(), newDescription, ids);
      if (res.session_id) {
        setActiveId(res.session_id);
        setNewOpen(false);
        setNewTopic("");
        setNewDescription("");
        await refreshSessions();
      }
    } catch (e) {
      setError(`Tworzenie sesji: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAddParticipant = async () => {
    if (!activeId || !partModelId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await api.addCouncilParticipant(activeId, {
        model_id: partModelId.trim(),
        role: partRole,
        rank: partRank,
      });
      setParticipantOpen(false);
      setPartModelId("");
      await refreshActive(activeId);
    } catch (e) {
      setError(`Dodanie uczestnika: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRunAnalysis = async () => {
    if (!activeId) return;
    setAnalysisLoading(true);
    setError(null);
    setRoundNotice(null);
    try {
      const res = await api.runParallelAnalysis(activeId);
      const count = (res.created ?? res.analyses ?? []).length;
      setRoundNotice(`Analiza modeli zapisana: ${count} odpowiedzi.`);
      await refreshActive(activeId);
    } catch (e) {
      setError(`Analiza modeli: ${(e as Error).message}`);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleRunDiscussion = async () => {
    if (!activeId) return;
    setDiscussionLoading(true);
    setError(null);
    setRoundNotice(null);
    try {
      const res = await api.runDiscussion(activeId, 1);
      const count = (res.created ?? res.rounds ?? []).length;
      setRoundNotice(`Dyskusja cross-review zapisana: ${count} wypowiedzi.`);
      await refreshActive(activeId);
    } catch (e) {
      setError(`Dyskusja cross-review: ${(e as Error).message}`);
    } finally {
      setDiscussionLoading(false);
    }
  };

  const handleCriticSign = async () => {
    if (!activeId || !criticModel.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await api.signCriticDecision(activeId, {
        model_id: criticModel.trim(),
        signed_decision: criticDecision,
        rationale: criticRationale,
      });
      setCriticModel("");
      setCriticRationale("");
      await refreshActive(activeId);
    } catch (e) {
      setError(`Podpis krytyka: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSentinelEvaluate = async () => {
    if (!activeId || !sentModel.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await api.evaluateSentinel(activeId, {
        sentinel_role: sentRole,
        model_id: sentModel.trim(),
        verdict: sentVerdict,
        score: Number.parseFloat(sentScore || "0") || 0,
        details: sentDetails,
      });
      setSentModel("");
      setSentDetails("");
      await refreshActive(activeId);
    } catch (e) {
      setError(`Sentinel: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleConsolidate = async () => {
    if (!activeId || !consText.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.consolidateGated(activeId, {
        consolidated_text: consText.trim(),
        require_critic: reqCritic,
        require_sentinels_pass: reqSentinels,
      });
      setConsolidatedResult(res);
      await refreshActive(activeId);
    } catch (e) {
      setError(`Konsolidacja: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const consensusByModelEntries = useMemo(() => {
    if (!consensus?.by_model) return [] as Array<[string, ConsensusByModel]>;
    if (Array.isArray(consensus.by_model)) {
      return consensus.by_model.map((m, idx) => [m.model_id ?? `m_${idx}`, m] as [string, ConsensusByModel]);
    }
    return Object.entries(consensus.by_model);
  }, [consensus]);

  const maxWeight = useMemo(() => {
    let max = 0;
    consensusByModelEntries.forEach(([, m]) => {
      if (typeof m.weight === "number" && m.weight > max) max = m.weight;
    });
    return max || 1;
  }, [consensusByModelEntries]);

  // ---- Render ----

  if (!backendLive) {
    return (
      <div className="flex h-[60vh] flex-col items-center justify-center gap-3 text-center">
        <WifiOff className="h-8 w-8 text-sylion-red/60" />
        <p className="text-sm text-muted-foreground">
          Backend nieosięgalny — uruchom `python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010`.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="model-council-page">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight">
              Rada modeli
              <HelpTip text="Wieloagentówa narada modeli AI: 9 ról, 5 rang, krytyk, sentinele kosztu i bezpiecze?stwa. Decyzje D3+ wymagaj? kworum ról; konsolidacja jest bramkowana podpisem krytyka i wynikiem sentineli." />
            </h1>
            <Badge variant="outline" className="border-sylion-blue/30 text-sylion-blue">
              LIVE
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Tworzenie sesji rady, przypisywanie ról/rang, podpis krytyka, ewaluacja sentineli, głosowanie wazone, bramkowana konsolidacja.
          </p>
        </div>
        <Button
          size="sm"
          data-testid="model-council-new-session"
          onClick={() => setNewOpen(true)}
        >
          <Plus className="mr-1.5 h-3.5 w-3.5" /> Nowa sesja
        </Button>
        <Dialog open={newOpen} onOpenChange={setNewOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Nowa sesja rady modeli</DialogTitle>
              <DialogDescription>
                Sesja dziedziczy 9 ról kanonicznych i 5 rang. Modele dodasz po jej utworzeniu.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <label className="block text-xs">
                Temat
                <HelpTip text="Krotki opis decyzji do rozstrzygniecia. Pojawi sie w lewej liscie sesji." />
                <input
                  data-testid="new-session-topic"
                  className="mt-1 block w-full rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                  value={newTopic}
                  onChange={(e) => setNewTopic(e.target.value)}
                />
              </label>
              <label className="block text-xs">
                Opis
                <HelpTip text="Kontekst decyzji widoczny dla wszystkich uczestnikow rady." />
                <textarea
                  data-testid="new-session-description"
                  rows={3}
                  className="mt-1 block w-full rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                />
              </label>
              <label className="block text-xs">
                Modele (lista, oddzielone przecinkami)
                <HelpTip text="Lista identyfikatorow modeli: np. 'claude,gpt-4,ollama'. Backend dopasuje role po dodaniu uczestnikow." />
                <input
                  data-testid="new-session-models"
                  className="mt-1 block w-full rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                  value={newModels}
                  onChange={(e) => setNewModels(e.target.value)}
                />
              </label>
            </div>
            <DialogFooter>
              <Button
                onClick={handleCreate}
                disabled={!newTopic.trim() || loading}
                data-testid="new-session-submit"
              >
                {loading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Sparkles className="mr-1.5 h-3.5 w-3.5" />}
                Utworz
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {error && (
        <Card className="border-sylion-red/30 bg-sylion-red/5 p-2 text-xs text-sylion-red" data-testid="model-council-error">
          {error}
        </Card>
      )}

      {/* Layout — left sidebar + right detail panel */}
      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        {/* Sessions sidebar */}
        <Card className="h-fit border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-2">
          <div className="px-2 pb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            Sesje rady
            <HelpTip text="Lista wszystkich sesji rady; klik wybiera sesje. Sortowanie: najnowsze pierwsze." />
          </div>
          <div className="max-h-[60vh] space-y-1 overflow-y-auto" data-testid="sessions-list">
            {sessions.length === 0 && (
              <p className="px-2 py-3 text-[11px] text-muted-foreground">Brak sesji. Kliknij "Nowa sesja".</p>
            )}
            {sessions.map((s) => (
              <button
                key={s.session_id}
                onClick={() => setActiveId(s.session_id)}
                data-testid={`session-${s.session_id}`}
                className={cn(
                  "w-full rounded-md px-2 py-1.5 text-left text-[11px] transition-colors",
                  activeId === s.session_id
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted/20",
                )}
              >
                <span className="block truncate font-medium">{s.topic || s.session_id?.slice(0, 16)}</span>
                {s.phase && <span className="text-[9px] opacity-70">{s.phase}</span>}
              </button>
            ))}
          </div>
        </Card>

        {/* Right detail panel */}
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-4">
          {!activeId && (
            <div className="flex flex-col items-center justify-center py-16 text-center text-xs text-muted-foreground">
              <Users className="mb-3 h-8 w-8 text-primary/30" />
              Wybierz sesje z lewej listy lub utworz nowa.
            </div>
          )}
          {activeId && (
            <div className="space-y-3" data-testid="session-detail">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-sm font-semibold">
                  {activeSession?.topic || activeId}
                  <HelpTip text="Aktywna sesja rady — sklada sie z uczestnikow (rola+ranga), podpisu krytyka, ewaluacji sentineli, konsensusu i zbramkowanej konsolidacji." />
                </h2>
                {activeSession?.phase && (
                  <Badge variant="outline" className="border-primary/30 text-primary">
                    {activeSession.phase}
                  </Badge>
                )}
                {activeSession?.status && (
                  <Badge variant="outline" className="border-muted-foreground/30 text-muted-foreground">
                    {activeSession.status}
                  </Badge>
                )}
              </div>

              <Tabs value={tab} onValueChange={setTab}>
                <TabsList>
                  <TabsTrigger value="participants" data-testid="tab-participants">
                    <Users className="mr-1 h-3 w-3" /> Uczestnicy
                  </TabsTrigger>
                  <TabsTrigger value="critic" data-testid="tab-critic">
                    <ShieldAlert className="mr-1 h-3 w-3" /> Krytyk + sentinele
                  </TabsTrigger>
                  <TabsTrigger value="consensus" data-testid="tab-consensus">
                    <Vote className="mr-1 h-3 w-3" /> Konsensus
                  </TabsTrigger>
                  <TabsTrigger value="consolidate" data-testid="tab-consolidate">
                    <Sparkles className="mr-1 h-3 w-3" /> Konsolidacja
                  </TabsTrigger>
                </TabsList>

                {/* TAB 1 — Uczestnicy */}
                <TabsContent value="participants" className="mt-3 space-y-3">
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <p className="text-[11px] text-muted-foreground">
                      9 ról kanonicznych, 5 rang. Każdy uczestnik dostaje wagę = waga roli * mno?nik rangi.
                      <HelpTip text="Role: planner, architect, critic, verifier, governance, cost_sentinel, security_sentinel, domain_specialist, funding_specialist. Rangi: primary, senior, support, review_only, validation_only." />
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      data-testid="run-council-analysis"
                      onClick={handleRunAnalysis}
                      disabled={!activeId || loading || analysisLoading || participants.length === 0}
                    >
                      {analysisLoading ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Sparkles className="mr-1 h-3 w-3" />}
                      Uruchom analizę modeli
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      data-testid="run-council-discussion"
                      onClick={handleRunDiscussion}
                      disabled={!activeId || loading || discussionLoading || participants.length < 2}
                    >
                      {discussionLoading ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Vote className="mr-1 h-3 w-3" />}
                      Uruchom dyskusję cross-review
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      data-testid="add-participant-trigger"
                      onClick={() => setParticipantOpen(true)}
                    >
                      <Plus className="mr-1 h-3 w-3" /> Dodaj uczestnika
                    </Button>
                    </div>
                    <Dialog open={participantOpen} onOpenChange={setParticipantOpen}>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Dodaj uczestnika rady</DialogTitle>
                          <DialogDescription>
                            Powiaz model z rola i ranga. Backend obliczy efektywna wagę głosu.
                            <span className="mt-1 block text-[10px] text-muted-foreground">
                              Glebokosc myslenia (fast / balanced / deep / research / council_grade) i profil jezykowy (multilingual / polish_primary / english_primary / code_heavy / documentation / funding_formal) sa konfigurowane na poziomie modelu w <a href="/ai-models" className="text-sylion-blue underline">Modele AI -&gt; Rejestr modeli</a>.
                            </span>
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-3">
                          <label className="block text-xs">
                            ID modelu
                            <input
                              data-testid="participant-model-id"
                              className="mt-1 block w-full rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                              value={partModelId}
                              onChange={(e) => setPartModelId(e.target.value)}
                              placeholder="np. claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5, gpt-5, gpt-5-mini, qwen2.5:72b-instruct"
                            />
                          </label>
                          <label className="block text-xs">
                            Rola
                            <select
                              data-testid="participant-role"
                              className="mt-1 block w-full rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                              value={partRole}
                              onChange={(e) => setPartRole(e.target.value)}
                            >
                              {(roles?.roles ?? []).map((r) => (
                                <option key={r} value={r}>
                                  {ROLE_LABELS_PL[r] ?? r} ({r})
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="block text-xs">
                            Ranga
                            <select
                              data-testid="participant-rank"
                              className="mt-1 block w-full rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                              value={partRank}
                              onChange={(e) => setPartRank(e.target.value)}
                            >
                              {(roles?.ranks ?? []).map((r) => (
                                <option key={r} value={r}>
                                  {RANK_LABELS_PL[r] ?? r} ({r})
                                </option>
                              ))}
                            </select>
                          </label>
                        </div>
                        <DialogFooter>
                          <Button
                            onClick={handleAddParticipant}
                            disabled={!partModelId.trim() || loading}
                            data-testid="add-participant-submit"
                          >
                            Dodaj
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>

                  {roundNotice && (
                    <Card
                      className="border-sylion-blue/30 bg-sylion-blue/5 p-2 text-[11px] text-sylion-blue"
                      data-testid="council-round-notice"
                    >
                      {roundNotice}
                    </Card>
                  )}

                  <div className="overflow-x-auto" data-testid="participants-table">
                    <table className="w-full text-[11px]">
                      <thead>
                        <tr className="text-left text-muted-foreground">
                          <th className="py-1 pr-3">Model</th>
                          <th className="py-1 pr-3">Rola</th>
                          <th className="py-1 pr-3">Ranga</th>
                          <th className="py-1 pr-3">Waga</th>
                        </tr>
                      </thead>
                      <tbody>
                        {participants.length === 0 && (
                          <tr>
                            <td colSpan={4} className="py-3 text-center text-muted-foreground">
                              Brak uczestnikow. Dodaj przynajmniej jednego z kazdej roli kanonicznej.
                            </td>
                          </tr>
                        )}
                        {participants.map((p, idx) => (
                          <tr key={p.participant_id ?? `${p.model_id}-${idx}`} className="border-t border-[rgba(148,163,184,0.06)]">
                            <td className="py-1.5 pr-3 font-mono">{p.model_id}</td>
                            <td className="py-1.5 pr-3">
                              {ROLE_LABELS_PL[p.role] ?? p.role}{" "}
                              <span className="opacity-50">({p.role})</span>
                            </td>
                            <td className="py-1.5 pr-3">
                              {RANK_LABELS_PL[p.rank] ?? p.rank}{" "}
                              <span className="opacity-50">({p.rank})</span>
                            </td>
                            <td className="py-1.5 pr-3">{formatNumber(p.weight ?? 0, 2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </TabsContent>

                {/* TAB 2 — Krytyk + sentinele */}
                <TabsContent value="critic" className="mt-3 space-y-4">
                  {/* Critic */}
                  <Card className="border-[rgba(148,163,184,0.08)] bg-[#0a1224] p-3">
                    <div className="mb-2 flex items-center gap-1 text-[11px] font-semibold">
                      <ShieldAlert className="h-3 w-3 text-sylion-amber" /> Podpis krytyka
                      <HelpTip text="Tylko model z rola 'critic' moze podpisać decyzję. Bez podpisu krytyka konsolidacja D3+ jest blokowana." />
                    </div>
                    <div className="grid gap-2 md:grid-cols-3">
                      <input
                        data-testid="critic-model-id"
                        className="rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                        placeholder="ID modelu krytyka"
                        value={criticModel}
                        onChange={(e) => setCriticModel(e.target.value)}
                      />
                      <select
                        data-testid="critic-decision"
                        className="rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                        value={criticDecision}
                        onChange={(e) => setCriticDecision(e.target.value)}
                      >
                        <option value="approve">approve</option>
                        <option value="reject">reject</option>
                        <option value="conditional">conditional</option>
                      </select>
                      <Button onClick={handleCriticSign} disabled={!criticModel.trim() || loading} data-testid="critic-sign-submit">
                        Podpisz
                      </Button>
                    </div>
                    <textarea
                      data-testid="critic-rationale"
                      rows={2}
                      className="mt-2 w-full rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                      placeholder="Uzasadnienie..."
                      value={criticRationale}
                      onChange={(e) => setCriticRationale(e.target.value)}
                    />
                    <div className="mt-2 text-[10px] text-muted-foreground">
                      Podpisow: {criticSignatures.length}
                      {criticSignatures.length > 0 && <CheckCircle2 className="ml-1 inline h-3 w-3 text-sylion-green" />}
                    </div>
                  </Card>

                  {/* Sentinels */}
                  <Card className="border-[rgba(148,163,184,0.08)] bg-[#0a1224] p-3">
                    <div className="mb-2 flex items-center gap-1 text-[11px] font-semibold">
                      <ShieldAlert className="h-3 w-3 text-sylion-blue" /> Sentinele kosztu i bezpiecze?stwa
                      <HelpTip text="Sentinele to dwie role specjalne: cost_sentinel (kontrola budżetu) i security_sentinel (kontrola ryzyka). Werdykt 'fail' obu moze zablokowac konsolidacje." />
                    </div>
                    <div className="grid gap-2 md:grid-cols-5">
                      <select
                        data-testid="sentinel-role"
                        className="rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                        value={sentRole}
                        onChange={(e) => setSentRole(e.target.value)}
                      >
                        {(roles?.sentinel_roles ?? ["cost_sentinel", "security_sentinel"]).map((r) => (
                          <option key={r} value={r}>{ROLE_LABELS_PL[r] ?? r}</option>
                        ))}
                      </select>
                      <input
                        data-testid="sentinel-model"
                        className="rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                        placeholder="ID modelu"
                        value={sentModel}
                        onChange={(e) => setSentModel(e.target.value)}
                      />
                      <select
                        data-testid="sentinel-verdict"
                        className="rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                        value={sentVerdict}
                        onChange={(e) => setSentVerdict(e.target.value)}
                      >
                        <option value="pass">pass</option>
                        <option value="warn">warn</option>
                        <option value="fail">fail</option>
                      </select>
                      <input
                        data-testid="sentinel-score"
                        type="number"
                        step="0.01"
                        className="rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                        placeholder="Score"
                        value={sentScore}
                        onChange={(e) => setSentScore(e.target.value)}
                      />
                      <Button onClick={handleSentinelEvaluate} disabled={!sentModel.trim() || loading} data-testid="sentinel-submit">
                        Oceń
                      </Button>
                    </div>
                    <textarea
                      data-testid="sentinel-details"
                      rows={2}
                      className="mt-2 w-full rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                      placeholder="Detale werdyktu..."
                      value={sentDetails}
                      onChange={(e) => setSentDetails(e.target.value)}
                    />
                    <div className="mt-2 grid gap-1 text-[10px]" data-testid="sentinel-evaluations-list">
                      {sentinelEvals.length === 0 && (
                        <span className="text-muted-foreground">Brak ewaluacji sentineli.</span>
                      )}
                      {sentinelEvals.map((e: any, idx: number) => (
                        <div key={idx} className="flex gap-2 border-t border-[rgba(148,163,184,0.06)] py-1">
                          <span className="font-mono">{e.model_id}</span>
                          <span className="opacity-70">{e.sentinel_role}</span>
                          <span className={classForVerdict(e.verdict)}>
                            {VERDICT_LABELS_PL[e.verdict] ?? e.verdict}
                          </span>
                          {typeof e.score === "number" && <span className="opacity-60">score={formatNumber(e.score)}</span>}
                        </div>
                      ))}
                    </div>
                  </Card>
                </TabsContent>

                {/* TAB 3 — Konsensus */}
                <TabsContent value="consensus" className="mt-3 space-y-3" data-testid="consensus-panel">
                  {!consensus && (
                    <p className="text-[11px] text-muted-foreground">
                      Brak danych konsensusu. Po dodaniu uczestnikow i ewentualnym głosowaniu backend wyliczy waga.
                    </p>
                  )}
                  {consensus && (
                    <>
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="font-semibold">Werdykt:</span>
                        <Badge variant="outline" className={cn("border-current", classForVerdict(consensus.verdict))}>
                          {VERDICT_LABELS_PL[consensus.verdict ?? ""] ?? consensus.verdict ?? "-"}
                        </Badge>
                        <span className="opacity-70">
                          Suma wag: {formatNumber(consensus.total_weight ?? 0, 2)}
                        </span>
                        <span className={cn("flex items-center gap-1", consensus.critic_signed ? "text-sylion-green" : "text-sylion-amber")}>
                          {consensus.critic_signed ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                          podpis krytyka
                        </span>
                      </div>
                      <div className="overflow-x-auto" data-testid="consensus-table">
                        <table className="w-full text-[11px]">
                          <thead>
                            <tr className="text-left text-muted-foreground">
                              <th className="py-1 pr-3">Model</th>
                              <th className="py-1 pr-3">Werdykt</th>
                              <th className="py-1 pr-3">Waga</th>
                              <th className="py-1 pr-3">Wykres</th>
                            </tr>
                          </thead>
                          <tbody>
                            {consensusByModelEntries.length === 0 && (
                              <tr>
                                <td colSpan={4} className="py-3 text-center text-muted-foreground">
                                  Brak głosow.
                                </td>
                              </tr>
                            )}
                            {consensusByModelEntries.map(([key, m]) => {
                              const w = typeof m.weight === "number" ? m.weight : 0;
                              const pct = (w / maxWeight) * 100;
                              return (
                                <tr key={key} className="border-t border-[rgba(148,163,184,0.06)]">
                                  <td className="py-1.5 pr-3 font-mono">{m.model_id ?? key}</td>
                                  <td className={cn("py-1.5 pr-3", classForVerdict(m.verdict))}>
                                    {VERDICT_LABELS_PL[m.verdict ?? ""] ?? m.verdict ?? "-"}
                                  </td>
                                  <td className="py-1.5 pr-3">{formatNumber(w, 2)}</td>
                                  <td className="w-1/2 py-1.5 pr-3">
                                    <div className="h-2 w-full rounded-full bg-secondary/40">
                                      <div
                                        className={cn(
                                          "h-full rounded-full",
                                          m.verdict === "approve" ? "bg-sylion-green" :
                                          m.verdict === "reject" ? "bg-sylion-red" : "bg-sylion-amber",
                                        )}
                                        style={{ width: `${pct}%` }}
                                      />
                                    </div>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      {Array.isArray(consensus.sentinel_blocks) && consensus.sentinel_blocks.length > 0 && (
                        <Card className="border-sylion-red/30 bg-sylion-red/5 p-2 text-[11px]" data-testid="sentinel-blocks">
                          <span className="font-semibold text-sylion-red">Blokady sentineli:</span>{" "}
                          {consensus.sentinel_blocks.length}
                        </Card>
                      )}
                    </>
                  )}
                </TabsContent>

                {/* TAB 4 — Konsolidacja bramkowana */}
                <TabsContent value="consolidate" className="mt-3 space-y-3" data-testid="consolidate-panel">
                  <p className="text-[11px] text-muted-foreground">
                    Bramkowana konsolidacja — backend odrzuci probe gdy `require_critic` i nie ma podpisu, lub `require_sentinels_pass` i sentinele zwróci?y 'fail'.
                    <HelpTip text="Konsolidacja = ostateczny tekst decyzji rady. Bramki sa rozne dla D2/D3+: krytyk gwarantuje review, sentinele kontrola kosztu/bezpiecze?stwa." />
                  </p>
                  <textarea
                    data-testid="consolidate-text"
                    rows={5}
                    className="w-full rounded-md border border-[rgba(148,163,184,0.18)] bg-secondary/20 px-2 py-1 text-xs"
                    placeholder="Tekst skonsolidowanej decyzji..."
                    value={consText}
                    onChange={(e) => setConsText(e.target.value)}
                  />
                  <div className="flex flex-wrap items-center gap-4 text-xs">
                    <label className="flex items-center gap-1">
                      <input
                        data-testid="require-critic"
                        type="checkbox"
                        checked={reqCritic}
                        onChange={(e) => setReqCritic(e.target.checked)}
                      />
                      wymagaj podpisu krytyka
                      <HelpTip text="Gdy zaznaczone, backend zablokuje konsolidacje bez aktywnego podpisu krytyka." />
                    </label>
                    <label className="flex items-center gap-1">
                      <input
                        data-testid="require-sentinels"
                        type="checkbox"
                        checked={reqSentinels}
                        onChange={(e) => setReqSentinels(e.target.checked)}
                      />
                      wymagaj OK sentineli
                      <HelpTip text="Gdy zaznaczone, backend zablokuje konsolidacje gdy którykolwiek sentinel zwróci? 'fail'." />
                    </label>
                    <Button
                      onClick={handleConsolidate}
                      disabled={!consText.trim() || loading}
                      data-testid="consolidate-submit"
                    >
                      {loading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Sparkles className="mr-1.5 h-3.5 w-3.5" />}
                      Konsoliduj (bramkowana)
                    </Button>
                  </div>
                  {consolidatedResult && (
                    <Card className="border-sylion-green/30 bg-sylion-green/5 p-3 text-[11px]" data-testid="consolidate-result">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-3.5 w-3.5 text-sylion-green" />
                        <span className="font-semibold text-sylion-green">Skonsolidowano</span>
                      </div>
                      <pre className="mt-1 whitespace-pre-wrap text-[10px] opacity-80">
                        {JSON.stringify(consolidatedResult, null, 2)}
                      </pre>
                    </Card>
                  )}
                </TabsContent>
              </Tabs>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
