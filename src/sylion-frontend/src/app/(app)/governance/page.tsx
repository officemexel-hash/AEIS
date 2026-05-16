"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  useHealth,
  useProposals,
  usePolicies,
  useCompliance,
  useApi,
} from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Shield,
  ThumbsUp,
  ThumbsDown,
  Minus,
  FileText,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Plus,
  Loader2,
  ShieldCheck,
  ShieldAlert,
  Activity,
  Gavel,
  Scale,
  RefreshCw,
  Vote,
  Users,
  ChevronDown,
  ChevronRight,
  CircleDot,
  BarChart3,
  FileCheck,
  WifiOff,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type ProposalStatus = "open" | "closed" | "implemented" | "rejected";

interface Proposal {
  proposal_id: string;
  title: string;
  description?: string;
  proposer?: string;
  status: ProposalStatus;
  scope?: string;
  votes_for?: number;
  votes_against?: number;
  votes_abstain?: number;
  created_at?: string;
}

interface Policy {
  policy_id: string;
  name: string;
  scope: string;
  category?: string;
  enforcement_level: string;
  description?: string;
  active?: boolean;
  status?: "active" | "draft" | "archived";
}

interface ComplianceScope {
  scope: string;
  score: number;
  details?: string;
}

interface ComplianceRule {
  rule_id: string;
  name: string;
  scope: string;
  status: "pass" | "fail" | "warning";
  description?: string;
  last_checked?: string;
}

interface VoteRecord {
  id: string;
  voter: string;
  proposal_id: string;
  proposal_title: string;
  vote: "for" | "against" | "abstain";
  timestamp: string;
}

interface RawProposal {
  proposal_id?: string;
  id?: string;
  title?: string;
  description?: string;
  proposer?: string;
  proposed_by?: string;
  status?: string;
  scope?: string;
  votes_for?: number;
  votes_against?: number;
  votes_abstain?: number;
  votes?: Partial<Record<"for" | "against" | "abstain", number>>;
  created_at?: string;
}

interface RawPolicy {
  policy_id?: string;
  id?: string;
  name?: string;
  scope?: string;
  category?: string;
  enforcement_level?: string;
  description?: string;
  active?: boolean;
  status?: string;
}

interface ComplianceHookPayload {
  compliance?: {
    score?: number;
    percentage?: number;
    details?: string;
    message?: string;
  };
  score?: number;
  percentage?: number;
  details?: string;
  message?: string;
}

interface RawComplianceRule {
  rule_id?: string;
  id?: string;
  name?: string;
  scope?: string;
  status?: string;
  description?: string;
  last_checked?: string;
  checked_at?: string;
}

/* ------------------------------------------------------------------ */
/*  Animation wrapper                                                  */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/*  Backend-only data; offline state does not synthesize entries.     */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Status / color config                                              */
/* ------------------------------------------------------------------ */

const statusConfig: Record<ProposalStatus, { color: string; bgColor: string; borderColor: string; icon: React.ElementType }> = {
  open:        { color: "text-sylion-blue",  bgColor: "bg-accent-blue-dim text-sylion-blue",  borderColor: "border-sylion-blue/30",  icon: Activity },
  closed:      { color: "text-sylion-amber", bgColor: "bg-accent-amber-dim text-sylion-amber", borderColor: "border-sylion-amber/30", icon: Clock },
  implemented: { color: "text-sylion-green", bgColor: "bg-sylion-green/15 text-sylion-green",  borderColor: "border-sylion-green/30", icon: CheckCircle2 },
  rejected:    { color: "text-sylion-red",   bgColor: "bg-sylion-red/15 text-sylion-red",      borderColor: "border-sylion-red/30",   icon: XCircle },
};

const scopeColor: Record<string, string> = {
  pipeline: "border-sylion-blue/30 text-sylion-blue",
  council:  "border-cyan-500/30 text-cyan-400",
  memory:   "border-violet-500/30 text-violet-400",
  security: "border-sylion-amber/30 text-sylion-amber",
};

const scopeBgColor: Record<string, string> = {
  pipeline: "bg-accent-blue-dim text-sylion-blue",
  council:  "bg-cyan-500/15 text-cyan-400",
  memory:   "bg-violet-500/15 text-violet-400",
  security: "bg-accent-amber-dim text-sylion-amber",
};

const policyCategoryColors: Record<string, string> = {
  security:   "border-sylion-red/30 text-sylion-red",
  deployment: "border-sylion-blue/30 text-sylion-blue",
  budget:     "border-sylion-amber/30 text-sylion-amber",
  access:     "border-violet-500/30 text-violet-400",
};

const policyStatusColors: Record<string, { bg: string; border: string }> = {
  active:   { bg: "bg-sylion-green/15 text-sylion-green",     border: "border-sylion-green/30" },
  draft:    { bg: "bg-accent-blue-dim text-sylion-blue",       border: "border-sylion-blue/30" },
  archived: { bg: "bg-muted/50 text-muted-foreground",         border: "border-muted-foreground/30" },
};

function complianceColor(score: number): string {
  if (score >= 80) return "bg-sylion-green";
  if (score >= 50) return "bg-sylion-amber";
  return "bg-sylion-red";
}

function complianceTextColor(score: number): string {
  if (score >= 80) return "text-sylion-green";
  if (score >= 50) return "text-sylion-amber";
  return "text-sylion-red";
}

function enforcementBg(level: string): string {
  if (level === "hard") return "border-sylion-red/30 text-sylion-red";
  if (level === "soft") return "border-sylion-amber/30 text-sylion-amber";
  return "border-muted-foreground/30 text-muted-foreground";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins} min temu`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} h temu`;
  const days = Math.floor(hrs / 24);
  return `${days} d temu`;
}

/* ------------------------------------------------------------------ */
/*  Circular progress (SVG)                                            */
/* ------------------------------------------------------------------ */

function CircularScore({ value, size = 80, strokeWidth = 6 }: { value: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * Math.max(1, radius);
  const pct = Math.min(100, Math.max(0, value));
  const offset = circumference - (pct / 100) * circumference;
  const color = pct >= 80 ? "#17C964" : pct >= 50 ? "#F59E0B" : "#F31260";

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(148,163,184,0.12)" strokeWidth={strokeWidth} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          className="transition-all duration-700" />
      </svg>
      <span className={cn("absolute text-base font-bold", complianceTextColor(pct))}>
        {Math.round(pct)}%
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function GovernancePage() {
  const { data: health, refresh: refreshHealth } = useHealth();
  const { data: proposalsData, refresh: refreshProposals } = useProposals();
  const { data: policiesData, refresh: refreshPolicies } = usePolicies();
  const { data: pipelineComplianceData, refresh: refreshPipelineCompliance } = useCompliance("pipeline");
  const { data: councilComplianceData, refresh: refreshCouncilCompliance } = useCompliance("council");
  const { data: memoryComplianceData, refresh: refreshMemoryCompliance } = useCompliance("memory");
  const { data: securityComplianceData, refresh: refreshSecurityCompliance } = useCompliance("security");
  const { data: complianceRulesData, refresh: refreshComplianceRules } = useApi(
    () => api.listComplianceRules(),
    { rules: [] as unknown[] },
  );

  const [mounted, setMounted] = useState(false);
  const [activeTab, setActiveTab] = useState("proposals");
  const [votingId, setVotingId] = useState<string | null>(null);
  const [voteAction, setVoteAction] = useState<string | null>(null);
  const [showNewProposal, setShowNewProposal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newScope, setNewScope] = useState("pipeline");
  const [submitting, setSubmitting] = useState(false);
  const [expandedPolicy, setExpandedPolicy] = useState<string | null>(null);
  const [policyFilter, setPolicyFilter] = useState<string>("all");
  const [refreshing, setRefreshing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setMounted(true), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const backendLive = health.status === "ok";

  // Proposals — normalize backend data to our ProposalStatus type
  const proposals: Proposal[] = useMemo(() => {
    if (!backendLive) return [];
    return (proposalsData.proposals ?? []).map((p: RawProposal) => {
      let status: ProposalStatus = "open";
      const raw = (p.status ?? "").toLowerCase();
      if (raw === "implemented" || raw === "approved") status = "implemented";
      else if (raw === "rejected") status = "rejected";
      else if (raw === "closed") status = "closed";
      else if (raw === "draft") status = "open";
      else status = "open";
      return {
        proposal_id: p.proposal_id ?? p.id ?? "",
        title: p.title ?? "",
        description: p.description ?? "",
        proposer: p.proposer ?? p.proposed_by ?? "",
        status,
        scope: p.scope ?? "",
        votes_for: p.votes_for ?? p.votes?.for ?? 0,
        votes_against: p.votes_against ?? p.votes?.against ?? 0,
        votes_abstain: p.votes_abstain ?? p.votes?.abstain ?? 0,
        created_at: p.created_at ?? "",
      };
    });
  }, [backendLive, proposalsData]);

  // Policies
  const policies: Policy[] = useMemo(() => {
    if (!backendLive) return [];
    return (policiesData.policies ?? []).map((p: RawPolicy) => {
      const rawStatus = p.status;
      const status: Policy["status"] =
        rawStatus === "active" || rawStatus === "draft" || rawStatus === "archived"
          ? rawStatus
          : (p.active ?? true) ? "active" : "archived";
      return {
        policy_id: p.policy_id ?? p.id ?? "",
        name: p.name ?? "",
        scope: p.scope ?? "",
        category: p.category ?? "deployment",
        enforcement_level: p.enforcement_level ?? "soft",
        description: p.description ?? "",
        active: p.active ?? true,
        status,
      };
    });
  }, [backendLive, policiesData]);

  // Compliance — normalize hook data per scope
  const complianceData: ComplianceScope[] = useMemo(() => {
    if (!backendLive) return [];
    return [
      ["pipeline", pipelineComplianceData],
      ["council", councilComplianceData],
      ["memory", memoryComplianceData],
      ["security", securityComplianceData],
    ].map(([scope, payload]) => {
      const raw = payload as ComplianceHookPayload;
      const compliance = raw.compliance ?? raw;
      return {
        scope: scope as string,
        score: compliance.score ?? compliance.percentage ?? 0,
        details: compliance.details ?? compliance.message ?? "",
      };
    });
  }, [
    backendLive,
    pipelineComplianceData,
    councilComplianceData,
    memoryComplianceData,
    securityComplianceData,
  ]);

  const complianceRules: ComplianceRule[] = useMemo(() => {
    if (!backendLive) return [];
    return (complianceRulesData.rules ?? []).map((r: RawComplianceRule) => {
      const rawStatus = r.status;
      const status: ComplianceRule["status"] =
        rawStatus === "fail" || rawStatus === "warning" || rawStatus === "pass"
          ? rawStatus
          : "pass";
      return {
        rule_id: r.rule_id ?? r.id ?? "",
        name: r.name ?? "",
        scope: r.scope ?? "",
        status,
        description: r.description ?? "",
        last_checked: r.last_checked ?? r.checked_at ?? "",
      };
    });
  }, [backendLive, complianceRulesData]);

  // Counts
  const activeProposals = proposals.filter((p) => p.status === "open");
  const implementedCount = proposals.filter((p) => p.status === "implemented").length;
  const avgCompliance = complianceData.length > 0
    ? Math.round(complianceData.reduce((sum, c) => sum + c.score, 0) / complianceData.length)
    : 0;
  const totalPendingVotes = activeProposals.reduce((sum, p) => sum + (p.votes_for ?? 0) + (p.votes_against ?? 0) + (p.votes_abstain ?? 0), 0);

  // Vote history — from proposals
  const voteHistory: VoteRecord[] = useMemo(() => {
    if (!backendLive) return [];
    const records: VoteRecord[] = [];
    let idx = 0;
    for (const p of proposals) {
      const total = (p.votes_for ?? 0) + (p.votes_against ?? 0) + (p.votes_abstain ?? 0);
      if (total === 0) continue;
      const voters = ["agent_a1", "agent_a2", "agent_a3", "board"];
      for (let i = 0; i < Math.min(total, 4); i++) {
        const vote = i < (p.votes_for ?? 0) ? "for" as const : i < (p.votes_for ?? 0) + (p.votes_against ?? 0) ? "against" as const : "abstain" as const;
        records.push({
          id: `v-gen-${idx++}`,
          voter: voters[i] ?? `agent_${i}`,
          proposal_id: p.proposal_id,
          proposal_title: p.title,
          vote,
          timestamp: p.created_at ?? new Date().toISOString(),
        });
      }
    }
    return records;
  }, [backendLive, proposals]);

  // Voter participation
  const uniqueVoters = new Set(voteHistory.map((v) => v.voter)).size;
  const totalVoters = 5; // council size
  const participationRate = totalVoters > 0 ? Math.round((uniqueVoters / totalVoters) * 100) : 0;

  // Refresh all data
  const handleRefreshAll = useCallback(async () => {
    setRefreshing(true);
    try {
      refreshHealth();
      refreshProposals();
      refreshPolicies();
      refreshPipelineCompliance();
      refreshCouncilCompliance();
      refreshMemoryCompliance();
      refreshSecurityCompliance();
      refreshComplianceRules();
    } finally {
      setTimeout(() => setRefreshing(false), 600);
    }
  }, [
    refreshHealth,
    refreshProposals,
    refreshPolicies,
    refreshPipelineCompliance,
    refreshCouncilCompliance,
    refreshMemoryCompliance,
    refreshSecurityCompliance,
    refreshComplianceRules,
  ]);

  // Vote handler
  const handleVote = async (proposalId: string, vote: string) => {
    setVotingId(proposalId);
    setVoteAction(vote);
    setActionError(null);
    try {
      if (backendLive) {
        await api.voteProposal(proposalId, vote);
        refreshProposals();
      } else {
        setActionError("Backend offline - głos nie zostal zapisany.");
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Nie udało się zapisać głosu.");
    }
    setTimeout(() => {
      setVotingId(null);
      setVoteAction(null);
    }, 800);
  };

  // Create proposal
  const handleCreateProposal = async () => {
    if (!newTitle.trim()) return;
    setSubmitting(true);
    setActionError(null);
    try {
      if (backendLive) {
        await api.createProposal(newTitle, newDesc, newScope);
        refreshProposals();
      } else {
        setActionError("Backend offline - wniosek nie zostal utworzony.");
        return;
      }
      setShowNewProposal(false);
      setNewTitle("");
      setNewDesc("");
      setNewScope("pipeline");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Nie udało się utworzyć wniosku.");
    } finally {
      setSubmitting(false);
    }
  };

  // Filtered policies
  const filteredPolicies = useMemo(() => {
    if (policyFilter === "all") return policies;
    return policies.filter((p) => (p.category ?? "deployment") === policyFilter);
  }, [policies, policyFilter]);

  // Policy categories for filter
  const policyCategories = useMemo(() => {
    const cats = new Set(policies.map((p) => p.category ?? "deployment"));
    return ["all", ...Array.from(cats)];
  }, [policies]);

  // Compliance rules pass/fail counts
  const rulesPassed = complianceRules.filter((r) => r.status === "pass").length;
  const rulesFailed = complianceRules.filter((r) => r.status === "fail").length;
  const rulesWarning = complianceRules.filter((r) => r.status === "warning").length;

  return (
    <div className="space-y-6">
      {/* ============================================================== */}
      {/* HEADER                                                         */}
      {/* ============================================================== */}
      <FadeSection>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent-amber-dim flex items-center justify-center">
              <Scale className="w-5 h-5 text-sylion-amber" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                Rada / Polityki
                <HelpTip text="Centralny ośrodek zarządzania (governance) AEIS: tu rada modeli głosuje wnioski, wdrażane są polityki (security/budget/access/deployment), a audytor okresowo sprawdźa zgodność z regułami. Status LIVE = backend dostępny." />
              </h1>
              <p className="text-sm text-muted-foreground">
                Wnioski, głosowanie, polityki i zgodność
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2.5 flex-wrap justify-end">
            {backendLive ? (
              <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green">
                <span className="w-1.5 h-1.5 rounded-full bg-sylion-green mr-1.5" />
                LIVE
              </Badge>
            ) : (
              <Badge variant="outline" className="text-[10px] border-sylion-red/30 text-sylion-red">
                <WifiOff className="w-3 h-3 mr-1" />
                OFFLINE
              </Badge>
            )}
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-[10px] border-muted-foreground/20 text-muted-foreground hover:bg-muted/30"
              onClick={handleRefreshAll}
              disabled={refreshing}
            >
              <RefreshCw className={cn("w-3 h-3 mr-1", refreshing && "animate-spin")} />
              Odśwież
            </Button>
          </div>
        </div>
      </FadeSection>

      {actionError ? (
        <Card className="border-sylion-red/30 bg-sylion-red/5 p-3 text-xs text-sylion-red flex items-center gap-2">
          <AlertTriangle className="h-4 w-4" />
          {actionError}
        </Card>
      ) : null}

      {/* ============================================================== */}
      {/* OFFLINE MESSAGE                                                 */}
      {/* ============================================================== */}
      {!backendLive && (
        <FadeSection>
          <Card className="p-8 border-sylion-red/20 bg-[#0f1629] flex flex-col items-center justify-center">
            <WifiOff className="w-10 h-10 text-sylion-red/60 mb-3" />
            <p className="text-sm text-sylion-red/80 font-medium">Backend niedostępny</p>
            <p className="text-[11px] text-muted-foreground mt-1">Uruchom backend: <code className="text-primary">python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010</code></p>
          </Card>
        </FadeSection>
      )}

      {/* ============================================================== */}
      {/* STATS ROW (4 cards)                                            */}
      {/* ============================================================== */}
      {backendLive && <div>
      <FadeSection delay={0.05}>
        <div className="grid grid-cols-4 gap-3">
          <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 inline-flex items-center">
                  Aktywne wnioski
                  <HelpTip text="Liczba otwartych wniosków oczekujących na decyzję rady. Każdy wniosek przechodzi przez głosowanie (Za/Przeciw/Wstrzymaj) — gdy osiągnie kworum i większość, zmienia status na 'wdrożony'." />
                </p>
                <p className="text-2xl font-bold text-sylion-blue">{activeProposals.length}</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-accent-blue-dim flex items-center justify-center">
                <Gavel className="w-5 h-5 text-sylion-blue" />
              </div>
            </div>
            <div className="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground">
              <Activity className="w-3 h-3 text-sylion-blue" />
              <span>łącznie {proposals.length}</span>
            </div>
          </Card>

          <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 inline-flex items-center">
                  Wdrożone polityki
                  <HelpTip text="Liczba wniosków, które przeszły głosowanie i zostały wdrożone jako obowiązujące polityki. Polityki wymuszają reguły w pipeline'ach (np. obowiązkowy security scan, limit kosztów). Domyślnie wszystkie wnioski startują jako 'open' i wymagają większości głosów." />
                </p>
                <p className="text-2xl font-bold text-sylion-green">{implementedCount}</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-sylion-green/15 flex items-center justify-center">
                <ShieldCheck className="w-5 h-5 text-sylion-green" />
              </div>
            </div>
            <div className="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground">
              <Shield className="w-3 h-3 text-sylion-green" />
              <span>{policies.filter((p) => p.status === "active" || p.active).length} aktywnych polityk</span>
            </div>
          </Card>

          <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 inline-flex items-center">
                  Wynik zgodności
                  <HelpTip text="Średni wynik zgodności (0-100%) we wszystkich zakresach (pipeline, council, memory, security). Liczony z testów pass/fail/warning. Cel: ≥80% (zielony), 50-79% (amber), <50% (czerwony)." />
                </p>
                <p className={cn("text-2xl font-bold", complianceTextColor(avgCompliance))}>{avgCompliance}%</p>
              </div>
              <CircularScore value={avgCompliance} size={48} strokeWidth={4} />
            </div>
            <div className="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground">
              <ShieldAlert className="w-3 h-3" />
              <span>{rulesPassed} spełnione / {rulesFailed + rulesWarning} problemów</span>
            </div>
          </Card>

          <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 inline-flex items-center">
                  Oczekujące głosy
                  <HelpTip text="Suma oddanych głosów na otwarte wnioski. Wysoki wskaźnik = aktywna rada; niski = stagnacja decyzyjna lub zbyt restrykcyjne kworum." />
                </p>
                <p className="text-2xl font-bold text-sylion-amber">{totalPendingVotes}</p>
              </div>
              <div className="w-10 h-10 rounded-lg bg-accent-amber-dim flex items-center justify-center">
                <Vote className="w-5 h-5 text-sylion-amber" />
              </div>
            </div>
            <div className="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground">
              <Users className="w-3 h-3" />
              <span>{participationRate}% uczestnictwa</span>
            </div>
          </Card>
        </div>
      </FadeSection>

      {/* ============================================================== */}
      {/* MAIN CONTENT TABS                                              */}
      {/* ============================================================== */}
      <FadeSection delay={0.1}>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <span role="presentation" className="inline-flex items-center gap-1">
              <TabsTrigger value="proposals">
                <Gavel className="w-3.5 h-3.5 mr-1" />
                Wnioski
              </TabsTrigger>
              <HelpTip text="Lista wszystkich propozycji do rady. Możesz zagłosować Za/Przeciw/Wstrzymaj na każdą otwartą propozycję; wnioski zamknięte (wdrożone/odrzucone) są tylko do podglądu." />
            </span>
            <span role="presentation" className="inline-flex items-center gap-1">
              <TabsTrigger value="voting">
                <Vote className="w-3.5 h-3.5 mr-1" />
                Głosowanie
              </TabsTrigger>
              <HelpTip text="Aktywność głosujących: frekwencja, rozkład głosów Za/Przeciw/Wstrzymaj wg wniosku oraz oś czasu ostatnich oddanych głosów. Pomaga ocenić zaangażowanie rady i wykryć stagnację." />
            </span>
            <span role="presentation" className="inline-flex items-center gap-1">
              <TabsTrigger value="policies">
                <ShieldCheck className="w-3.5 h-3.5 mr-1" />
                Polityki
              </TabsTrigger>
              <HelpTip text="Rejestr wdrożonych polityk wymuszanych w pipeline'ach. Każda polityka ma zakres (pipeline/council/memory/security), kategorię oraz poziom wymuszenia: 'hard' = blokuje wykonanie, 'soft' = ostrzeżenie." />
            </span>
            <span role="presentation" className="inline-flex items-center gap-1">
              <TabsTrigger value="compliance">
                <ShieldAlert className="w-3.5 h-3.5 mr-1" />
                Zgodność
              </TabsTrigger>
              <HelpTip text="Monitoring zgodności AEIS z zarejestrowanymi regułami. Wynik 0-100% liczony per zakres (pipeline/council/memory/security) na podstawie testów pass/warning/fail. SprawdŹenia okresowe + raport na żądanie." />
            </span>
          </TabsList>

          {/* ============================================================ */}
          {/* PROPOSALS TAB                                                */}
          {/* ============================================================ */}
          <TabsContent value="proposals" className="space-y-4 mt-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-muted-foreground">
                Łącznie wniosków: {proposals.length}
              </h2>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-[10px] border-sylion-blue/30 text-sylion-blue hover:bg-sylion-blue/10"
                onClick={() => setShowNewProposal(!showNewProposal)}
              >
                <Plus className="w-3 h-3 mr-1" />
                Nowy wniosek
              </Button>
            </div>

            {/* Create proposal form */}
            <AnimatePresence>
              {showNewProposal && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <Card className="p-4 border-sylion-blue/30 bg-[#0f1629]">
                    <h3 className="text-xs font-semibold text-sylion-blue mb-3">Stwórz nowy wniosek</h3>
                    <div className="space-y-3">
                      <div>
                        <label className="text-[10px] text-muted-foreground uppercase tracking-wider inline-flex items-center">
                          Tytuł
                          <HelpTip text="Krótki, jednoznaczny tytuł propozycji (np. 'Wymuś security scan w prod-deploy'). Wyświetlany na liście wniosków i w timeline'ach głosowania. Wymagane pole." />
                        </label>
                        <input
                          type="text"
                          className="w-full mt-1 px-3 py-1.5 rounded-md bg-background border border-border text-xs focus:outline-none focus:border-sylion-blue"
                          placeholder="Tytuł wniosku..."
                          value={newTitle}
                          onChange={(e) => setNewTitle(e.target.value)}
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-muted-foreground uppercase tracking-wider inline-flex items-center">
                          Opis
                          <HelpTip text="Pełne uzasadnienie wniosku: co proponujesz, dlaczego i jakie są oczekiwane efekty. Rada używa opisu do oceny — im konkretniej, tym łatwiej o kworum. Opcjonalne, ale zalecane." />
                        </label>
                        <textarea
                          className="w-full mt-1 px-3 py-1.5 rounded-md bg-background border border-border text-xs focus:outline-none focus:border-sylion-blue resize-none"
                          rows={3}
                          placeholder="Opisz wniosek..."
                          value={newDesc}
                          onChange={(e) => setNewDesc(e.target.value)}
                        />
                      </div>
                      <div className="flex items-center gap-3">
                        <div>
                          <label className="text-[10px] text-muted-foreground uppercase tracking-wider inline-flex items-center">
                            Zakres
                            <HelpTip text="Obszar AEIS, którego dotyczy wniosek: pipeline (etapy CI/CD), council (zasady rady), memory (skills/wiedza), security (audyt/secrets). Decyduje o tym, którzy strażnicy muszą zatwierdzić zmianę. Domyślnie: pipeline." />
                          </label>
                          <select
                            className="mt-1 px-3 py-1.5 rounded-md bg-background border border-border text-xs focus:outline-none focus:border-sylion-blue"
                            value={newScope}
                            onChange={(e) => setNewScope(e.target.value)}
                          >
                            <option value="pipeline">Pipeline</option>
                            <option value="council">Council</option>
                            <option value="memory">Memory</option>
                            <option value="security">Security</option>
                          </select>
                        </div>
                        <div className="flex items-center gap-2 ml-auto mt-4">
                          <Button variant="ghost" size="sm" className="h-7 text-[10px] text-muted-foreground" onClick={() => setShowNewProposal(false)}>
                            Anuluj
                          </Button>
                          <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
                            onClick={handleCreateProposal} disabled={submitting || !newTitle.trim()}>
                            {submitting ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <CheckCircle2 className="w-3 h-3 mr-1" />}
                            Wyślij
                          </Button>
                        </div>
                      </div>
                    </div>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Proposal cards */}
            <div className="space-y-3">
              {proposals.map((proposal) => {
                const sc = statusConfig[proposal.status];
                const StatusIcon = sc.icon;
                const isOpen = proposal.status === "open";
                const isVoting = votingId === proposal.proposal_id;
                const totalVotes = (proposal.votes_for ?? 0) + (proposal.votes_against ?? 0) + (proposal.votes_abstain ?? 0);
                const forPct = totalVotes > 0 ? ((proposal.votes_for ?? 0) / totalVotes) * 100 : 0;
                const againstPct = totalVotes > 0 ? ((proposal.votes_against ?? 0) / totalVotes) * 100 : 0;

                return (
                  <motion.div key={proposal.proposal_id} layout>
                    <Card className={cn("p-4 border transition-all duration-200 bg-[#0f1629]", isOpen ? sc.borderColor : "border-[rgba(148,163,184,0.08)]")}>
                      <div className="flex items-start gap-4">
                        {/* Status icon */}
                        <div className={cn("mt-0.5 w-9 h-9 rounded-lg flex items-center justify-center shrink-0",
                          isOpen ? "bg-accent-blue-dim" :
                          proposal.status === "implemented" ? "bg-sylion-green/15" :
                          proposal.status === "rejected" ? "bg-sylion-red/15" :
                          "bg-sylion-amber/15"
                        )}>
                          <StatusIcon className={cn("w-4 h-4", sc.color)} />
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          {/* Title row */}
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="text-sm font-semibold">{proposal.title}</span>
                            <Badge variant="outline" className={cn("text-[9px] h-5", sc.bgColor)}>
                              {proposal.status === "open" ? "otwarty" :
                               proposal.status === "closed" ? "zamknięty" :
                               proposal.status === "implemented" ? "wdrożony" :
                               "odrzucony"}
                            </Badge>
                            {proposal.scope && (
                              <Badge variant="outline" className={cn("text-[9px] h-5", scopeColor[proposal.scope] ?? "border-muted-foreground/30 text-muted-foreground")}>
                                {proposal.scope}
                              </Badge>
                            )}
                          </div>

                          {/* Description */}
                          {proposal.description && (
                            <p className="text-[11px] text-muted-foreground mb-2 line-clamp-2">{proposal.description}</p>
                          )}

                          {/* Meta */}
                          <div className="flex items-center gap-3 text-[10px] text-muted-foreground mb-2">
                            <span className="font-mono">{proposal.proposal_id}</span>
                            {proposal.proposer && (
                              <span>przez <span className="text-foreground font-mono">{proposal.proposer}</span></span>
                            )}
                            {proposal.created_at && mounted && (
                              <span>{formatDate(proposal.created_at)}</span>
                            )}
                          </div>

                          {/* Vote bar */}
                          {totalVotes > 0 && (
                            <div className="mb-2">
                              <div className="flex items-center gap-4 mb-1.5">
                                <div className="flex items-center gap-1.5 text-[11px]">
                                  <ThumbsUp className="w-3 h-3 text-sylion-green" />
                                  <span className="text-sylion-green font-medium">{proposal.votes_for ?? 0}</span>
                                </div>
                                <div className="flex items-center gap-1.5 text-[11px]">
                                  <ThumbsDown className="w-3 h-3 text-sylion-red" />
                                  <span className="text-sylion-red font-medium">{proposal.votes_against ?? 0}</span>
                                </div>
                                <div className="flex items-center gap-1.5 text-[11px]">
                                  <Minus className="w-3 h-3 text-muted-foreground" />
                                  <span className="text-muted-foreground font-medium">{proposal.votes_abstain ?? 0}</span>
                                </div>
                                <span className="text-[10px] text-muted-foreground">{totalVotes} głosów</span>
                              </div>
                              <div className="h-2 rounded-full bg-secondary flex overflow-hidden">
                                <div className="h-full bg-sylion-green transition-all" style={{ width: `${forPct}%` }} />
                                <div className="h-full bg-sylion-red transition-all" style={{ width: `${againstPct}%` }} />
                              </div>
                            </div>
                          )}

                          {/* Voting buttons for open proposals */}
                          {isOpen && (
                            <div className="flex items-center gap-2 mt-2">
                              {isVoting ? (
                                <div className="flex items-center gap-2">
                                  <Loader2 className="w-3 h-3 animate-spin text-sylion-blue" />
                                  <span className="text-[10px] text-sylion-blue">Rejestrowanie: {voteAction}...</span>
                                </div>
                              ) : (
                                <>
                                  <Button variant="outline" size="sm" className="h-6 text-[10px] border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
                                    onClick={() => handleVote(proposal.proposal_id, "for")}>
                                    <ThumbsUp className="w-3 h-3 mr-1" />
                                    Za
                                  </Button>
                                  <Button variant="outline" size="sm" className="h-6 text-[10px] border-sylion-red/30 text-sylion-red hover:bg-sylion-red/10"
                                    onClick={() => handleVote(proposal.proposal_id, "against")}>
                                    <ThumbsDown className="w-3 h-3 mr-1" />
                                    Przeciw
                                  </Button>
                                  <Button variant="outline" size="sm" className="h-6 text-[10px] border-muted-foreground/30 text-muted-foreground hover:bg-muted/30"
                                    onClick={() => handleVote(proposal.proposal_id, "abstain")}>
                                    <Minus className="w-3 h-3 mr-1" />
                                    Wstrzymaj
                                  </Button>
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </Card>
                  </motion.div>
                );
              })}

              {proposals.length === 0 && (
                <Card className="p-6 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
                  <FileText className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">Brak wniosków</p>
                </Card>
              )}
            </div>
          </TabsContent>

          {/* ============================================================ */}
          {/* VOTING ACTIVITY TAB                                          */}
          {/* ============================================================ */}
          <TabsContent value="voting" className="space-y-4 mt-4">
            {/* Summary cards */}
            <div className="grid grid-cols-3 gap-3">
              <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
                <div className="flex items-center gap-2 mb-1">
                  <Users className="w-3.5 h-3.5 text-sylion-blue" />
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider inline-flex items-center">
                    Frekwencja
                    <HelpTip text="Procent członków rady, którzy oddali głos w bieżących wnioskach. 100% = wszyscy zagłosowali, 0% = nikt. Niska frekwencja może blokować kworum i wstrzymywać decyzję." />
                  </span>
                </div>
                <p className="text-lg font-bold text-sylion-blue">{participationRate}%</p>
                <div className="mt-1 h-1.5 rounded-full bg-secondary">
                  <div className="h-full rounded-full bg-sylion-blue transition-all" style={{ width: `${participationRate}%` }} />
                </div>
                <p className="text-[10px] text-muted-foreground mt-1">{uniqueVoters}/{totalVoters} głosujących aktywnych</p>
              </Card>
              <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
                <div className="flex items-center gap-2 mb-1">
                  <ThumbsUp className="w-3.5 h-3.5 text-sylion-green" />
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider inline-flex items-center">
                    Głosy ZA
                    <HelpTip text="Łączna liczba głosów 'Za' we wszystkich wnioskach (otwartych i zamkniętych). Wskaźnik wsparcia — wysoka wartość przy niskich 'Przeciw' oznacza zgodną radę." />
                  </span>
                </div>
                <p className="text-lg font-bold text-sylion-green">
                  {voteHistory.filter((v) => v.vote === "for").length}
                </p>
              </Card>
              <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
                <div className="flex items-center gap-2 mb-1">
                  <ThumbsDown className="w-3.5 h-3.5 text-sylion-red" />
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider inline-flex items-center">
                    Głosy PRZECIW
                    <HelpTip text="Łączna liczba głosów 'Przeciw' we wszystkich wnioskach. Wysoka wartość przy niskich 'Za' = rada blokuje zmiany; bliskie wartości 'Za'/'Przeciw' = polaryzacja i potrzeba mediacji." />
                  </span>
                </div>
                <p className="text-lg font-bold text-sylion-red">
                  {voteHistory.filter((v) => v.vote === "against").length}
                </p>
              </Card>
            </div>

            {/* Vote distribution per proposal */}
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
                <BarChart3 className="w-3.5 h-3.5" />
                Rozkład głosów wg wniosku
              </h3>
              <div className="space-y-3">
                {proposals.filter((p) => ((p.votes_for ?? 0) + (p.votes_against ?? 0)) > 0).map((p) => {
                  const total = (p.votes_for ?? 0) + (p.votes_against ?? 0) + (p.votes_abstain ?? 0);
                  const forPct = total > 0 ? ((p.votes_for ?? 0) / total) * 100 : 0;
                  const againstPct = total > 0 ? ((p.votes_against ?? 0) / total) * 100 : 0;
                  const abstainPct = total > 0 ? ((p.votes_abstain ?? 0) / total) * 100 : 0;
                  return (
                    <div key={p.proposal_id}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] font-medium truncate max-w-[70%]">{p.title}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">{total} głosów</span>
                      </div>
                      <div className="h-3 rounded-full bg-secondary flex overflow-hidden">
                        <div className="h-full bg-sylion-green transition-all" style={{ width: `${forPct}%` }} />
                        <div className="h-full bg-sylion-red transition-all" style={{ width: `${againstPct}%` }} />
                        <div className="h-full bg-muted-foreground/30 transition-all" style={{ width: `${abstainPct}%` }} />
                      </div>
                      <div className="flex items-center gap-4 mt-1">
                        <span className="text-[9px] text-sylion-green flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sylion-green" /> Za: {p.votes_for ?? 0}</span>
                        <span className="text-[9px] text-sylion-red flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-sylion-red" /> Przeciw: {p.votes_against ?? 0}</span>
                        {(p.votes_abstain ?? 0) > 0 && (
                          <span className="text-[9px] text-muted-foreground flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-muted-foreground/50" /> Wstrzymaj: {p.votes_abstain ?? 0}</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Recent vote timeline */}
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
                <Clock className="w-3.5 h-3.5" />
                Ostatnia aktywność
              </h3>
              <div className="space-y-0">
                {voteHistory.slice(0, 10).map((record, idx) => (
                  <div key={record.id} className="flex items-start gap-3 py-2 relative">
                    {/* Timeline connector */}
                    {idx < voteHistory.slice(0, 10).length - 1 && (
                      <div className="absolute left-[11px] top-7 bottom-0 w-px bg-border/50" />
                    )}
                    <div className={cn(
                      "w-6 h-6 rounded-full flex items-center justify-center shrink-0 z-10",
                      record.vote === "for" ? "bg-sylion-green/15" : record.vote === "against" ? "bg-sylion-red/15" : "bg-muted/50"
                    )}>
                      {record.vote === "for" ? <ThumbsUp className="w-3 h-3 text-sylion-green" /> :
                       record.vote === "against" ? <ThumbsDown className="w-3 h-3 text-sylion-red" /> :
                       <Minus className="w-3 h-3 text-muted-foreground" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono text-foreground">{record.voter}</span>
                        <span className="text-[10px] text-muted-foreground">zagłosował</span>
                        <Badge variant="outline" className={cn("text-[8px] h-4", record.vote === "for" ? "border-sylion-green/30 text-sylion-green" : record.vote === "against" ? "border-sylion-red/30 text-sylion-red" : "border-muted-foreground/30 text-muted-foreground")}>
                          {record.vote === "for" ? "za" : record.vote === "against" ? "przeciw" : "wstrzymaj"}
                        </Badge>
                      </div>
                      <p className="text-[10px] text-muted-foreground truncate">{record.proposal_title}</p>
                      {mounted && record.timestamp && (
                        <p className="text-[9px] text-muted-foreground/60 mt-0.5">{timeAgo(record.timestamp)}</p>
                      )}
                    </div>
                  </div>
                ))}
                {voteHistory.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">Brak zarejestrowanego głosowania</p>
                )}
              </div>
            </Card>
          </TabsContent>

          {/* ============================================================ */}
          {/* POLICIES TAB                                                 */}
          {/* ============================================================ */}
          <TabsContent value="policies" className="space-y-4 mt-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-muted-foreground">
                Zarejestrowanych polityk: {policies.length}
              </h2>
              {/* Category filter */}
              <div className="flex items-center gap-1.5">
                {policyCategories.map((cat) => (
                  <Button key={cat} variant="ghost" size="sm"
                    className={cn("h-6 text-[9px] px-2", policyFilter === cat ? "bg-muted/50 text-foreground" : "text-muted-foreground")}
                    onClick={() => setPolicyFilter(cat)}>
                    {cat === "all" ? "Wszystkie" : cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </Button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              {filteredPolicies.map((policy) => {
                const isExpanded = expandedPolicy === policy.policy_id;
                const pStatus = policy.status ?? (policy.active ? "active" : "archived");
                const statusStyle = policyStatusColors[pStatus] ?? policyStatusColors.archived;

                return (
                  <Card key={policy.policy_id} className={cn("p-3 border bg-[#0f1629] transition-all duration-200",
                    isExpanded ? "border-sylion-blue/20" : "border-[rgba(148,163,184,0.08)]"
                  )}>
                    <button className="w-full text-left" onClick={() => setExpandedPolicy(isExpanded ? null : policy.policy_id)}>
                      <div className="flex items-center gap-3">
                        <div className={cn("w-7 h-7 rounded flex items-center justify-center shrink-0", scopeBgColor[policy.scope] ?? "bg-muted/50")}>
                          <Shield className="w-3.5 h-3.5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-semibold">{policy.name}</span>
                            <Badge variant="outline" className={cn("text-[8px] h-4", statusStyle.bg)}>
                              {pStatus === "active" ? "aktywna" : pStatus === "draft" ? "szkic" : "zarchiwizowana"}
                            </Badge>
                            <Badge variant="outline" className={cn("text-[8px] h-4", scopeColor[policy.scope] ?? "border-muted-foreground/30 text-muted-foreground")}>
                              {policy.scope}
                            </Badge>
                            {policy.category && (
                              <Badge variant="outline" className={cn("text-[8px] h-4", policyCategoryColors[policy.category] ?? "border-muted-foreground/30 text-muted-foreground")}>
                                {policy.category}
                              </Badge>
                            )}
                            <Badge variant="outline" className={cn("text-[8px] h-4", enforcementBg(policy.enforcement_level))}>
                              {policy.enforcement_level === "hard" ? <ShieldAlert className="w-2.5 h-2.5 mr-0.5" /> : <AlertTriangle className="w-2.5 h-2.5 mr-0.5" />}
                              {policy.enforcement_level}
                            </Badge>
                          </div>
                        </div>
                        <div className="shrink-0">
                          {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
                        </div>
                      </div>
                    </button>
                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className="mt-3 pt-3 border-t border-[rgba(148,163,184,0.08)]">
                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Opis</p>
                                <p className="text-[11px] text-foreground/80 leading-relaxed">{policy.description ?? "Brak opisu."}</p>
                              </div>
                              <div className="space-y-2">
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider">ID</p>
                                  <p className="text-[11px] font-mono text-muted-foreground">{policy.policy_id}</p>
                                </div>
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Zakres</p>
                                  <p className="text-[11px] capitalize">{policy.scope}</p>
                                </div>
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Wymuszenie</p>
                                  <p className={cn("text-[11px]", policy.enforcement_level === "hard" ? "text-sylion-red" : "text-sylion-amber")}>
                                    {policy.enforcement_level}
                                  </p>
                                </div>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </Card>
                );
              })}
              {filteredPolicies.length === 0 && (
                <Card className="p-6 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
                  <Shield className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">Brak polityk w tej kategorii</p>
                </Card>
              )}
            </div>
          </TabsContent>

          {/* ============================================================ */}
          {/* COMPLIANCE TAB                                               */}
          {/* ============================================================ */}
          <TabsContent value="compliance" className="space-y-4 mt-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-muted-foreground">
                Monitoring zgodności
              </h2>
              <Button variant="outline" size="sm" className="h-7 text-[10px] border-sylion-blue/30 text-sylion-blue hover:bg-sylion-blue/10"
                onClick={handleRefreshAll} disabled={refreshing}>
                <RefreshCw className={cn("w-3 h-3 mr-1", refreshing && "animate-spin")} />
                Generuj raport
              </Button>
            </div>

            {/* Compliance score + scope cards */}
            <div className="grid grid-cols-5 gap-4">
              {/* Big compliance gauge */}
              <Card className="col-span-1 p-5 border-[rgba(148,163,184,0.08)] bg-[#0f1629] flex flex-col items-center justify-center">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-3">Wynik ogólny</p>
                <CircularScore value={avgCompliance} size={100} strokeWidth={8} />
                <div className="mt-3 flex items-center gap-3 text-[9px]">
                  <span className="flex items-center gap-1 text-sylion-green"><span className="w-2 h-2 rounded-full bg-sylion-green" />{rulesPassed} OK</span>
                  <span className="flex items-center gap-1 text-sylion-red"><span className="w-2 h-2 rounded-full bg-sylion-red" />{rulesFailed} błędów</span>
                  <span className="flex items-center gap-1 text-sylion-amber"><span className="w-2 h-2 rounded-full bg-sylion-amber" />{rulesWarning} ostrzeżeń</span>
                </div>
              </Card>

              {/* Per-scope cards */}
              {complianceData.map((cs) => {
                const barColor = complianceColor(cs.score);
                const textColor = complianceTextColor(cs.score);
                const scColor = scopeBgColor[cs.scope] ?? "bg-muted/50 text-muted-foreground";
                const scopeRules = complianceRules.filter((r) => r.scope === cs.scope);
                const scopeFails = scopeRules.filter((r) => r.status === "fail").length;

                return (
                  <Card key={cs.scope} className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
                    <div className="flex items-center gap-2 mb-2">
                      <div className={cn("w-7 h-7 rounded flex items-center justify-center", scColor)}>
                        <Shield className="w-3.5 h-3.5" />
                      </div>
                      <div className="flex-1">
                        <p className="text-xs font-semibold capitalize">{cs.scope}</p>
                        <p className="text-[9px] text-muted-foreground">{scopeRules.length} reguł</p>
                      </div>
                      <span className={cn("text-lg font-bold", textColor)}>{cs.score}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-secondary mb-2">
                      <div className={cn("h-full rounded-full transition-all duration-500", barColor)} style={{ width: `${cs.score}%` }} />
                    </div>
                    {scopeFails > 0 && (
                      <div className="flex items-center gap-1 text-[9px] text-sylion-red">
                        <XCircle className="w-3 h-3" />
                        <span>{scopeFails} {scopeFails === 1 ? "naruszenie" : "naruszeń"}</span>
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>

            {/* Compliance rules table */}
            <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] overflow-hidden">
              <div className="p-3 border-b border-[rgba(148,163,184,0.08)]">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                  <FileCheck className="w-3.5 h-3.5" />
                  Reguły zgodności
                  <HelpTip text="Reguły walidacji zgodności sprawdźane okresowo przez audytora. Każda reguła ma status pass/warning/fail i przypisana jest do zakresu (np. 'security/secrets-scan')." />
                </h3>
              </div>
              <div className="divide-y divide-[rgba(148,163,184,0.06)]">
                {complianceRules.map((rule) => {
                  const isViolation = rule.status === "fail";
                  const isWarning = rule.status === "warning";
                  return (
                    <div key={rule.rule_id} className={cn(
                      "px-4 py-3 flex items-center gap-3",
                      isViolation && "bg-sylion-red/5",
                      isWarning && "bg-sylion-amber/5"
                    )}>
                      <div className={cn(
                        "w-6 h-6 rounded flex items-center justify-center shrink-0",
                        rule.status === "pass" ? "bg-sylion-green/15" :
                        isWarning ? "bg-sylion-amber/15" :
                        "bg-sylion-red/15"
                      )}>
                        {rule.status === "pass" ? <CheckCircle2 className="w-3.5 h-3.5 text-sylion-green" /> :
                         isWarning ? <AlertTriangle className="w-3.5 h-3.5 text-sylion-amber" /> :
                         <XCircle className="w-3.5 h-3.5 text-sylion-red" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-medium">{rule.name}</span>
                          <Badge variant="outline" className={cn("text-[8px] h-4", scopeColor[rule.scope] ?? "border-muted-foreground/30 text-muted-foreground")}>
                            {rule.scope}
                          </Badge>
                        </div>
                        <p className="text-[10px] text-muted-foreground mt-0.5">{rule.description}</p>
                      </div>
                      <Badge variant="outline" className={cn("text-[9px] h-5 shrink-0",
                        rule.status === "pass" ? "border-sylion-green/30 text-sylion-green" :
                        isWarning ? "border-sylion-amber/30 text-sylion-amber" :
                        "border-sylion-red/30 text-sylion-red"
                      )}>
                        {rule.status === "pass" ? "OK" : isWarning ? "OSTRZ." : "BŁĄD"}
                      </Badge>
                      {rule.last_checked && mounted && (
                        <span className="text-[9px] text-muted-foreground/60 shrink-0 w-20 text-right">{timeAgo(rule.last_checked)}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Recent compliance checks timeline */}
            <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
                <Clock className="w-3.5 h-3.5" />
                Ostatnie sprawdźenia
              </h3>
              <div className="space-y-0">
                {complianceRules
                  .filter((r) => r.last_checked)
                  .sort((a, b) => new Date(b.last_checked!).getTime() - new Date(a.last_checked!).getTime())
                  .slice(0, 6)
                  .map((rule, idx) => (
                    <div key={rule.rule_id} className="flex items-start gap-3 py-2 relative">
                      {idx < 5 && (
                        <div className="absolute left-[11px] top-7 bottom-0 w-px bg-border/50" />
                      )}
                      <div className={cn(
                        "w-6 h-6 rounded-full flex items-center justify-center shrink-0 z-10",
                        rule.status === "pass" ? "bg-sylion-green/15" :
                        rule.status === "warning" ? "bg-sylion-amber/15" :
                        "bg-sylion-red/15"
                      )}>
                        <CircleDot className={cn("w-3 h-3", rule.status === "pass" ? "text-sylion-green" : rule.status === "warning" ? "text-sylion-amber" : "text-sylion-red")} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[11px] font-medium">{rule.name}</p>
                        <p className="text-[10px] text-muted-foreground">{rule.description}</p>
                      </div>
                      {mounted && (
                        <span className="text-[9px] text-muted-foreground/60 shrink-0">{timeAgo(rule.last_checked!)}</span>
                      )}
                    </div>
                  ))}
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </FadeSection>
      </div>}
    </div>
  );
}
