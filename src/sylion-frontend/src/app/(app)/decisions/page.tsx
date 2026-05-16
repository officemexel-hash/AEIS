"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useHealth, useDecisionGates, useDecisionAuditLog, useCompliance } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn, fmtDateTime } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Zap,
  Activity,
  ListChecks,
  FileText,
  ChevronDown,
  ChevronRight,
  Search,
  RefreshCw,
  BarChart3,
  Eye,
  ArrowRight,
  GitBranch,
  GitMerge,
  Layers,
  Network,
  AlertCircle,
  Play,
  X,
  ArrowDown,
  ExternalLink,
  RotateCcw,
  Siren,
  Sparkles,
  Code2,
  ChevronUp,
  WifiOff,
} from "lucide-react";

/* ============================================================
   Decision Gates Dashboard — Full Rewrite
   Code-aware decision tracking with cascade analysis
   ============================================================ */

/* ---------- Types ---------- */

interface DecisionSnapshot {
  snapshot_id: string;
  decision_id: string;
  gate_id?: string;
  session_id?: string;
  pipeline_run_id?: string;
  decision_class: string;
  choice_made: string;
  choice_id?: string;
  consequences?: Record<string, unknown>;
  module_states?: Record<string, unknown>;
  active_contracts?: string[];
  codebase_hash?: string;
  is_active: boolean;
  superseded_by?: string;
  impact_radius?: number;
  created_at: string;
  dependency_ids?: string[];
  pipeline_context?: Record<string, unknown>;
}

interface CascadeEvent {
  event_id: string;
  source_snapshot_id: string;
  affected_snapshot_id: string;
  cascade_type: "invalidated" | "needs_review" | "warning" | "auto_adapted";
  message: string;
  requires_human: boolean;
  acknowledged: boolean;
  action_taken?: string;
  created_at: string;
}

interface GateEntry {
  gate_id: string;
  description?: string;
  criteria?: string[];
  status?: "pass" | "fail" | "pending" | "warning";
  auto?: boolean;
  scope?: string;
  last_evaluated?: string;
  evaluations?: GateEvaluation[];
}

interface GateEvaluation {
  gate_id: string;
  result: "pass" | "fail" | "pending" | "warning";
  context?: string;
  timestamp?: string;
  details?: Record<string, unknown>;
}

/* ---------- Decision class colors ---------- */

const dcColors: Record<string, string> = {
  D0: "text-muted-foreground",
  D1: "text-sylion-blue",
  D2: "text-sylion-green",
  D3: "text-sylion-amber",
  D4: "text-sylion-red",
  D5: "text-purple-400",
};

const dcBgColors: Record<string, string> = {
  D0: "bg-muted/30 text-muted-foreground",
  D1: "bg-sylion-blue/15 text-sylion-blue",
  D2: "bg-sylion-green/15 text-sylion-green",
  D3: "bg-sylion-amber/15 text-sylion-amber",
  D4: "bg-sylion-red/15 text-sylion-red",
  D5: "bg-purple-500/15 text-purple-400",
};

const cascadeTypeColors: Record<string, string> = {
  invalidated: "text-sylion-red",
  needs_review: "text-sylion-amber",
  warning: "text-yellow-400",
  auto_adapted: "text-sylion-green",
};

const cascadeTypeBg: Record<string, string> = {
  invalidated: "bg-sylion-red/15 text-sylion-red",
  needs_review: "bg-sylion-amber/15 text-sylion-amber",
  warning: "bg-yellow-500/15 text-yellow-400",
  auto_adapted: "bg-sylion-green/15 text-sylion-green",
};

const timelineDotColors: Record<string, string> = {
  active: "bg-sylion-green",
  superseded: "bg-sylion-amber",
  invalidated: "bg-sylion-red",
};

/* ---------- Backend-only empty states ---------- */

const complianceScopes = [
  { value: "evidence", label: "Evidence" },
  { value: "governance", label: "Governance" },
  { value: "contract", label: "Contract" },
  { value: "security", label: "Security" },
  { value: "performance", label: "Performance" },
  { value: "full", label: "Full System" },
];

/* ---------- Helpers ---------- */

function getDCBadge(cls: string) {
  return (
    <Badge variant="outline" className={cn("text-[9px] h-5 font-mono", dcBgColors[cls] ?? "bg-muted/30")}>
      {cls}
    </Badge>
  );
}

function getStatusForSnapshot(s: DecisionSnapshot): "active" | "superseded" | "invalidated" {
  if (!s.is_active && s.superseded_by) return "superseded";
  if (!s.is_active) return "invalidated";
  return "active";
}

/* ============================================================
   Page Component
   ============================================================ */

export default function DecisionsPage() {
  const { data: health } = useHealth();
  const { data: gatesData, refresh: refreshGates } = useDecisionGates();
  const { data: auditData } = useDecisionAuditLog();
  const backendLive = health.status === "ok";

  const [activeTab, setActiveTab] = useState("chain");
  const [snapshots, setSnapshots] = useState<DecisionSnapshot[]>([]);
  const [cascadeEvents, setCascadeEvents] = useState<CascadeEvent[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState<DecisionSnapshot | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());
  const [expandedTimelineModules, setExpandedTimelineModules] = useState<Set<string>>(new Set());
  const [complianceScope, setComplianceScope] = useState("full");
  const [evaluatingGate, setEvaluatingGate] = useState<string | null>(null);
  const [evaluateResult, setEvaluateResult] = useState<{ gate_id: string; result: string } | null>(null);
  const [timelineFilter, setTimelineFilter] = useState<string>("");
  const [diffId1, setDiffId1] = useState("");
  const [diffId2, setDiffId2] = useState("");
  const [cascadeImpactSnapshot, setCascadeImpactSnapshot] = useState<string>("");
  const [simulatingChange, setSimulatingChange] = useState(false);
  const [simInput, setSimInput] = useState("");
  const [changeSnapshotId, setChangeSnapshotId] = useState<string | null>(null);
  const [changeInput, setChangeInput] = useState("");

  // Fetch live snapshots and cascade events when backend is live
  useEffect(() => {
    if (!backendLive) return;
    api.listDecisionSnapshots().then((r) => {
      if (r.snapshots?.length) setSnapshots(r.snapshots);
    }).catch(() => {});
    api.listCascadeEvents().then((r) => {
      if (r.events?.length) setCascadeEvents(r.events);
    }).catch(() => {});
  }, [backendLive]);

  // Gates from hook data
  const rawGates = gatesData.gates ?? [];
  const gates: GateEntry[] = useMemo(() =>
    rawGates.map((g: any) => ({
      gate_id: g.gate_id ?? g.id ?? "",
      description: g.description ?? "",
      criteria: g.criteria ?? [],
      status: g.status ?? "pending",
      auto: g.auto ?? g.automated ?? false,
      scope: g.scope ?? "",
      last_evaluated: g.last_evaluated ?? g.updated_at ?? "",
      evaluations: g.evaluations ?? [],
    })),
    [rawGates]
  );

  const { data: complianceData } = useCompliance(complianceScope);

  // Stats
  const activeCount = snapshots.filter((s) => s.is_active).length;
  const cascadeAlertCount = cascadeEvents.filter((e) => e.requires_human && !e.acknowledged).length;
  const cleanCount = snapshots.filter((s) => {
    const relatedCascades = cascadeEvents.filter(
      (e) => e.source_snapshot_id === s.snapshot_id && e.cascade_type === "invalidated"
    );
    return relatedCascades.length === 0;
  }).length;
  const compliancePct = snapshots.length > 0 ? Math.round((cleanCount / snapshots.length) * 100) : 0;

  // Active chain — build dependency tree
  const activeSnapshots = useMemo(() => snapshots.filter((s) => s.is_active), [snapshots]);
  const chainNodes = useMemo(() => {
    const nodes: DecisionSnapshot[] = [];
    const visited = new Set<string>();
    const addNode = (snap: DecisionSnapshot) => {
      if (visited.has(snap.snapshot_id)) return;
      visited.add(snap.snapshot_id);
      const deps = (snap.dependency_ids ?? []).map((id) => snapshots.find((s) => s.snapshot_id === id)).filter(Boolean) as DecisionSnapshot[];
      for (const dep of deps) addNode(dep);
      nodes.push(snap);
    };
    for (const snap of activeSnapshots) addNode(snap);
    return nodes;
  }, [activeSnapshots, snapshots]);

  // Timeline entries sorted by date
  const timelineEntries = useMemo(() => {
    let entries = [...snapshots].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    if (timelineFilter) {
      entries = entries.filter((s) => s.decision_class === timelineFilter);
    }
    return entries;
  }, [snapshots, timelineFilter]);

  // Cascade impact tree for selected snapshot
  const cascadeImpactTree = useMemo(() => {
    if (!cascadeImpactSnapshot) return null;
    const root = snapshots.find((s) => s.snapshot_id === cascadeImpactSnapshot);
    if (!root) return null;
    const children = cascadeEvents
      .filter((e) => e.source_snapshot_id === cascadeImpactSnapshot)
      .map((e) => {
        const affected = snapshots.find((s) => s.snapshot_id === e.affected_snapshot_id);
        const grandchildren = cascadeEvents
          .filter((ce) => ce.source_snapshot_id === e.affected_snapshot_id)
          .map((ce) => ({ event: ce, snapshot: snapshots.find((s) => s.snapshot_id === ce.affected_snapshot_id) ?? null }));
        return { event: e, snapshot: affected ?? null, children: grandchildren };
      });
    return { snapshot: root, children };
  }, [cascadeImpactSnapshot, snapshots, cascadeEvents]);

  // Diff calculation
  const snapshotDiff = useMemo(() => {
    if (!diffId1 || !diffId2) return null;
    const s1 = snapshots.find((s) => s.snapshot_id === diffId1);
    const s2 = snapshots.find((s) => s.snapshot_id === diffId2);
    if (!s1 || !s2) return null;
    const ms1 = s1.module_states ?? {};
    const ms2 = s2.module_states ?? {};
    const allKeys = new Set([...Object.keys(ms1), ...Object.keys(ms2)]);
    const moduleChanges: { key: string; old: string; new: string; type: "added" | "removed" | "modified" | "unchanged" }[] = [];
    for (const k of allKeys) {
      const v1 = String(ms1[k] ?? "");
      const v2 = String(ms2[k] ?? "");
      if (v1 === v2) moduleChanges.push({ key: k, old: v1, new: v2, type: "unchanged" });
      else if (!v1) moduleChanges.push({ key: k, old: "", new: v2, type: "added" });
      else if (!v2) moduleChanges.push({ key: k, old: v1, new: "", type: "removed" });
      else moduleChanges.push({ key: k, old: v1, new: v2, type: "modified" });
    }
    const c1 = new Set(s1.active_contracts ?? []);
    const c2 = new Set(s2.active_contracts ?? []);
    const contractsAdded = [...c2].filter((c) => !c1.has(c));
    const contractsRemoved = [...c1].filter((c) => !c2.has(c));
    const contractsUnchanged = [...c1].filter((c) => c2.has(c));
    return { s1, s2, moduleChanges, contractsAdded, contractsRemoved, contractsUnchanged };
  }, [diffId1, diffId2, snapshots]);

  // Filtered gates by search
  const filteredGates = useMemo(() => {
    if (!searchQuery.trim()) return gates;
    const q = searchQuery.toLowerCase();
    return gates.filter(
      (g) =>
        g.gate_id.toLowerCase().includes(q) ||
        (g.description ?? "").toLowerCase().includes(q) ||
        (g.scope ?? "").toLowerCase().includes(q)
    );
  }, [gates, searchQuery]);

  // Handlers
  const handleEvaluate = useCallback(async (gateId: string) => {
    setEvaluatingGate(gateId);
    setEvaluateResult(null);
    try {
      const result = await api.evaluateGate(gateId, { triggered_by: "dashboard" });
      setEvaluateResult({ gate_id: result.gate_id, result: result.result });
      refreshGates();
    } catch {
      setEvaluateResult({ gate_id: gateId, result: "error" });
    } finally {
      setEvaluatingGate(null);
    }
  }, [refreshGates]);

  const handleOpenDetail = useCallback((snap: DecisionSnapshot) => {
    setSelectedSnapshot(snap);
    setDetailOpen(true);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setDetailOpen(false);
    setSelectedSnapshot(null);
    setChangeSnapshotId(null);
    setChangeInput("");
  }, []);

  const handleAckCascade = useCallback(async (eventId: string) => {
    try {
      await api.acknowledgeCascade(eventId, "Acknowledged from dashboard");
      setCascadeEvents((prev) => prev.map((e) => e.event_id === eventId ? { ...e, acknowledged: true, action_taken: "Acknowledged from dashboard" } : e));
    } catch {
      setEvaluateResult({ gate_id: eventId, result: "error" });
    }
  }, []);

  const handleChangeDecision = useCallback(async () => {
    if (!changeSnapshotId || !changeInput.trim()) return;
    setSimulatingChange(true);
    try {
      const result = await api.changeDecision(changeSnapshotId, { new_choice: changeInput });
      if (result.new_snapshot) {
        setSnapshots((prev) => [...prev.filter((s) => s.snapshot_id !== result.new_snapshot.snapshot_id), result.new_snapshot]);
      }
      if (result.cascade_events?.length) {
        setCascadeEvents((prev) => [...prev, ...result.cascade_events]);
      }
      setChangeSnapshotId(null);
      setChangeInput("");
    } catch {
      setEvaluateResult({ gate_id: changeSnapshotId, result: "error" });
    } finally {
      setSimulatingChange(false);
    }
  }, [changeSnapshotId, changeInput]);

  const toggleModules = useCallback((id: string, set: React.Dispatch<React.SetStateAction<Set<string>>>) => {
    set((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Upstream/downstream for detail panel
  const upstreamDecisions = useMemo(() => {
    if (!selectedSnapshot) return [];
    return (selectedSnapshot.dependency_ids ?? [])
      .map((id) => snapshots.find((s) => s.snapshot_id === id))
      .filter(Boolean) as DecisionSnapshot[];
  }, [selectedSnapshot, snapshots]);

  const downstreamDecisions = useMemo(() => {
    if (!selectedSnapshot) return [];
    return snapshots.filter((s) => (s.dependency_ids ?? []).includes(selectedSnapshot.snapshot_id));
  }, [selectedSnapshot, snapshots]);

  const relatedCascades = useMemo(() => {
    if (!selectedSnapshot) return [];
    return cascadeEvents.filter(
      (e) => e.source_snapshot_id === selectedSnapshot.snapshot_id || e.affected_snapshot_id === selectedSnapshot.snapshot_id
    );
  }, [selectedSnapshot, cascadeEvents]);

  /* ---------- Backend unreachable ---------- */
  if (!backendLive) {
    return (
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
              <Shield className="w-4 h-4 text-sylion-blue" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Bramy decyzyjne</h1>
              <p className="text-sm text-muted-foreground">Śledzenie decyzji z analizą kaskadową</p>
            </div>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Bramy decyzyjne, migawki i analiza kaskadowa wymagają działającego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => { refreshGates(); }}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  /* ============================================================
     Sub-components
     ============================================================ */

  function StatCard({ label, value, icon: Icon, color, tipText }: { label: string; value: string | number; icon: React.ElementType; color: string; tipText?: string }) {
    return (
      <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
        <div className="flex items-center justify-between mb-1">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
            {label}
            {tipText && <HelpTip text={tipText} />}
          </p>
          <Icon className={cn("w-3.5 h-3.5", color)} />
        </div>
        <p className={cn("text-2xl font-semibold", color)}>{value}</p>
      </Card>
    );
  }

  function ChainNode({ snap, depth }: { snap: DecisionSnapshot; depth: number }) {
    const relatedCascadesForNode = cascadeEvents.filter((e) => e.source_snapshot_id === snap.snapshot_id && !e.acknowledged);
    const status = getStatusForSnapshot(snap);

    return (
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: depth * 0.05 }}
        className="relative"
      >
        {depth > 0 && (
          <div className="absolute left-0 top-0 bottom-0 w-px bg-border" style={{ left: "-24px" }}>
            <div className="absolute top-1/2 -left-1 w-2 h-px bg-border" />
          </div>
        )}
        <Card
          className="p-3 bg-[#0f1629] border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.16)] transition-all cursor-pointer"
          onClick={() => handleOpenDetail(snap)}
        >
          <div className="flex items-center gap-2 mb-1.5">
            {getDCBadge(snap.decision_class)}
            <span className={cn("w-2 h-2 rounded-full", timelineDotColors[status])} />
            <span className="text-[11px] font-medium truncate flex-1">{snap.choice_made}</span>
            {snap.impact_radius != null && (
              <Badge variant="outline" className="text-[8px] h-4 border-border text-muted-foreground">
                <Network className="w-2.5 h-2.5 mr-1" />
                {snap.impact_radius}
              </Badge>
            )}
            {relatedCascadesForNode.length > 0 && (
              <Badge variant="outline" className="text-[8px] h-4 border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5">
                <AlertTriangle className="w-2.5 h-2.5 mr-1" />
                {relatedCascadesForNode.length}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-3 text-[9px] text-muted-foreground">
            <span className="font-mono">{snap.snapshot_id}</span>
            <span>{fmtDateTime(snap.created_at)}</span>
            {snap.codebase_hash && (
              <span className="flex items-center gap-1">
                <Code2 className="w-2.5 h-2.5" />
                {snap.codebase_hash}
              </span>
            )}
          </div>
        </Card>
      </motion.div>
    );
  }

  function TimelineEntry({ snap, idx, isLast }: { snap: DecisionSnapshot; idx: number; isLast: boolean }) {
    const status = getStatusForSnapshot(snap);
    const isExpanded = expandedTimelineModules.has(snap.snapshot_id);

    return (
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: idx * 0.03 }}
        className="relative flex gap-4"
      >
        <div className="flex flex-col items-center w-10 shrink-0">
          <motion.div
            className={cn("w-2.5 h-2.5 rounded-full z-10 mt-2", timelineDotColors[status])}
            animate={status === "invalidated" ? { scale: [1, 1.3, 1] } : {}}
            transition={{ repeat: Infinity, duration: 2 }}
          />
          {!isLast && <div className="w-0.5 flex-1 bg-border min-h-[28px]" />}
        </div>

        <div
          className="flex-1 mb-1.5 py-2.5 px-3 rounded-md bg-[#0f1629] border border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.16)] transition-all cursor-pointer"
          onClick={() => handleOpenDetail(snap)}
        >
          <div className="flex items-center gap-2 mb-1">
            {getDCBadge(snap.decision_class)}
            <Badge variant="outline" className={cn("text-[8px] h-4", status === "active" ? "border-sylion-green/30 text-sylion-green bg-sylion-green/5" : status === "superseded" ? "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5" : "border-sylion-red/30 text-sylion-red bg-sylion-red/5")}>
              {status}
            </Badge>
            <span className="text-[11px] font-medium truncate flex-1">{snap.choice_made}</span>
            <span className="text-[9px] text-muted-foreground font-mono shrink-0">
              {fmtDateTime(snap.created_at)}
            </span>
          </div>

          <div className="flex items-center gap-3 text-[9px] text-muted-foreground mb-1">
            {snap.gate_id && <span className="font-mono">gate: {snap.gate_id}</span>}
            {snap.codebase_hash && (
              <span className="flex items-center gap-1">
                <Code2 className="w-2.5 h-2.5" />
                {snap.codebase_hash}
              </span>
            )}
            {snap.impact_radius != null && <span>impact: {snap.impact_radius}</span>}
          </div>

          {snap.superseded_by && (
            <div className="flex items-center gap-1 text-[9px] text-sylion-amber mt-1">
              <ArrowRight className="w-2.5 h-2.5" />
              <span>Zastąpione przez {snap.superseded_by}</span>
            </div>
          )}

          {snap.consequences && Object.keys(snap.consequences).length > 0 && (
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {Object.entries(snap.consequences).map(([k, v]) => (
                <span key={k} className="text-[8px] px-1.5 py-0.5 rounded bg-muted/30 text-muted-foreground font-mono">
                  {k}: {String(v)}
                </span>
              ))}
            </div>
          )}

          {/* Cascade events from this decision */}
          {cascadeEvents.filter((e) => e.source_snapshot_id === snap.snapshot_id).length > 0 && (
            <div className="mt-2 space-y-1">
              {cascadeEvents.filter((e) => e.source_snapshot_id === snap.snapshot_id).map((e) => (
                <div key={e.event_id} className={cn("flex items-center gap-1.5 text-[8px] px-2 py-1 rounded", cascadeTypeBg[e.cascade_type])}>
                  <AlertCircle className="w-2.5 h-2.5" />
                  <span>{e.message}</span>
                  {e.requires_human && !e.acknowledged && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-4 text-[7px] ml-auto px-1"
                      onClick={(ev) => { ev.stopPropagation(); handleAckCascade(e.event_id); }}
                    >
                      Ack
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Module states expandable */}
          {snap.module_states && Object.keys(snap.module_states).length > 0 && (
            <div className="mt-2">
              <button
                className="flex items-center gap-1 text-[8px] text-muted-foreground hover:text-foreground transition-colors"
                onClick={(ev) => { ev.stopPropagation(); toggleModules(snap.snapshot_id, setExpandedTimelineModules); }}
              >
                {isExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
                Stany modułów
              </button>
              <AnimatePresence>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <pre className="text-[8px] text-muted-foreground bg-muted/20 rounded p-2 mt-1 font-mono overflow-x-auto">
                      {JSON.stringify(snap.module_states, null, 2)}
                    </pre>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </motion.div>
    );
  }

  function CascadeImpactNode({ event, snapshot, depth }: { event: CascadeEvent; snapshot: DecisionSnapshot | null; depth: number }) {
    return (
      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: depth * 0.08 }}
        className="ml-6 mt-2"
      >
        <div className="flex items-center gap-2">
          <ArrowDown className={cn("w-3 h-3", cascadeTypeColors[event.cascade_type])} />
          <Card className={cn("flex-1 p-2.5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]", event.cascade_type === "invalidated" && "border-sylion-red/20")}>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="outline" className={cn("text-[8px] h-4", cascadeTypeBg[event.cascade_type])}>
                {event.cascade_type.replace("_", " ")}
              </Badge>
              {event.requires_human && (
                <Badge variant="outline" className="text-[8px] h-4 border-sylion-red/30 text-sylion-red bg-sylion-red/5">
                  WYMAGANA DECYZJA CZŁOWIEKA
                </Badge>
              )}
              {snapshot && (
                <span className="text-[9px] font-mono text-muted-foreground">{snapshot.snapshot_id}</span>
              )}
            </div>
            <p className="text-[10px] text-muted-foreground">{event.message}</p>
            {snapshot && (
              <p className="text-[9px] text-muted-foreground mt-1">
                Decyzja: {snapshot.choice_made}
              </p>
            )}
            {event.requires_human && !event.acknowledged && (
              <Button
                variant="outline"
                size="sm"
                className="h-5 text-[8px] mt-2 border-sylion-amber/30 text-sylion-amber hover:bg-sylion-amber/10"
                onClick={() => handleAckCascade(event.event_id)}
              >
                Potwierdź
              </Button>
            )}
            {event.acknowledged && (
              <span className="text-[8px] text-sylion-green mt-1 block">Potwierdzone</span>
            )}
          </Card>
        </div>
      </motion.div>
    );
  }

  function CascadeImpactTab() {
    return (
      <div className="mt-4 space-y-4">
        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <div className="flex items-center gap-3 mb-3">
            <Layers className="w-4 h-4 text-sylion-amber" />
            <h3 className="text-xs font-medium">Wybierz decyzję do analizy wpływu</h3>
          </div>
          <select
            value={cascadeImpactSnapshot}
            onChange={(e) => setCascadeImpactSnapshot(e.target.value)}
            className="w-full h-8 rounded-md border border-[rgba(148,163,184,0.08)] bg-card text-[11px] text-foreground focus:outline-none focus:border-sylion-blue/40"
          >
            <option value="">-- Wybierz migawkę --</option>
            {snapshots.map((s) => (
              <option key={s.snapshot_id} value={s.snapshot_id}>
                [{s.decision_class}] {s.snapshot_id} - {s.choice_made.slice(0, 50)}
              </option>
            ))}
          </select>
        </Card>

        {cascadeImpactTree && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
              <div className="flex items-center gap-3 mb-3">
                <GitBranch className="w-4 h-4 text-sylion-green" />
                <h3 className="text-xs font-medium">Drzewo efektów kaskadowych</h3>
                <Badge variant="outline" className="text-[8px] h-4 border-border text-muted-foreground">
                  Root: {cascadeImpactTree.snapshot.snapshot_id}
                </Badge>
              </div>

              {/* Root node */}
              <Card className="p-3 bg-[#0f1629] border-sylion-blue/20">
                <div className="flex items-center gap-2 mb-1">
                  {getDCBadge(cascadeImpactTree.snapshot.decision_class)}
                  <span className="text-[11px] font-medium">{cascadeImpactTree.snapshot.choice_made}</span>
                </div>
                <div className="text-[9px] text-muted-foreground">
                  {cascadeImpactTree.snapshot.snapshot_id} | {fmtDateTime(cascadeImpactTree.snapshot.created_at)}
                </div>
              </Card>

              {/* Children */}
              {cascadeImpactTree.children.length === 0 && (
                <div className="ml-6 mt-3 text-[10px] text-muted-foreground">
                  Brak zdarzeń kaskadowych z tej decyzji.
                </div>
              )}
              {cascadeImpactTree.children.map((child) => (
                <div key={child.event.event_id}>
                  <CascadeImpactNode event={child.event} snapshot={child.snapshot} depth={1} />
                  {child.children.map((gc) => (
                    <CascadeImpactNode key={gc.event.event_id} event={gc.event} snapshot={gc.snapshot} depth={2} />
                  ))}
                </div>
              ))}
            </Card>
          </motion.div>
        )}

        {/* Simulate Change */}
        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <div className="flex items-center gap-3 mb-3">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <h3 className="text-xs font-medium">Symuluj zmianę</h3>
            <span className="text-[9px] text-muted-foreground">Podgląd efektów kaskadowych przed zatwierdzeniem</span>
          </div>
          <div className="flex gap-2">
            <select
              value={simInput ? snapshots.find((s) => s.snapshot_id)?.snapshot_id ?? "" : ""}
              onChange={(e) => {}}
              className="h-7 rounded-md border border-[rgba(148,163,184,0.08)] bg-card text-[10px] text-foreground flex-1 focus:outline-none"
              disabled
            >
              <option value="">Najpierw wybierz migawkę...</option>
            </select>
            <input
              type="text"
              placeholder="Wprowadź nowy wybór do symulacji..."
              value={simInput}
              onChange={(e) => setSimInput(e.target.value)}
              className="flex-1 h-7 rounded-md border border-[rgba(148,163,184,0.08)] bg-card text-[10px] text-foreground px-3 focus:outline-none focus:border-sylion-blue/40"
            />
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-[9px] border-sylion-blue/30 text-sylion-blue hover:bg-sylion-blue/10"
              disabled={!simInput.trim()}
              onClick={() => {
                // Simulate: show what would be affected based on dependency graph
                alert("Simulation would show cascade preview here. Connect to backend for full simulation.");
              }}
            >
              Symuluj
            </Button>
          </div>
        </Card>

        {/* Pending cascade events */}
        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <div className="flex items-center gap-3 mb-3">
            <Siren className="w-4 h-4 text-sylion-red" />
            <h3 className="text-xs font-medium">Oczekujące alerty kaskadowe</h3>
            <Badge variant="outline" className="text-[8px] h-4 border-sylion-red/30 text-sylion-red bg-sylion-red/5">
              {cascadeEvents.filter((e) => e.requires_human && !e.acknowledged).length} oczekujących
            </Badge>
          </div>
          <div className="space-y-2">
            {cascadeEvents.filter((e) => e.requires_human && !e.acknowledged).length === 0 ? (
              <p className="text-[10px] text-muted-foreground">Brak oczekujących alertów. Wszystkie kaskady obsłużone.</p>
            ) : (
              cascadeEvents.filter((e) => e.requires_human && !e.acknowledged).map((e) => (
                <div key={e.event_id} className="flex items-start gap-3 p-2 rounded bg-muted/20">
                  <AlertTriangle className={cn("w-3.5 h-3.5 mt-0.5 shrink-0", cascadeTypeColors[e.cascade_type])} />
                  <div className="flex-1">
                    <p className="text-[10px] text-foreground">{e.message}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="outline" className={cn("text-[8px] h-4", cascadeTypeBg[e.cascade_type])}>
                        {e.cascade_type.replace("_", " ")}
                      </Badge>
                      <span className="text-[8px] text-muted-foreground font-mono">{e.source_snapshot_id} {"->"} {e.affected_snapshot_id}</span>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-5 text-[8px] shrink-0 border-sylion-green/30 text-sylion-green hover:bg-sylion-green/10"
                    onClick={() => handleAckCascade(e.event_id)}
                  >
                    Potwierdź
                  </Button>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    );
  }

  function SnapshotDiffTab() {
    const diffColor = (type: "added" | "removed" | "modified" | "unchanged") => {
      if (type === "added") return "bg-sylion-green/10 text-sylion-green";
      if (type === "removed") return "bg-sylion-red/10 text-sylion-red";
      if (type === "modified") return "bg-sylion-amber/10 text-sylion-amber";
      return "";
    };

    return (
      <div className="mt-4 space-y-4">
        <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <div className="flex items-center gap-3 mb-3">
            <GitMerge className="w-4 h-4 text-sylion-blue" />
            <h3 className="text-xs font-medium">Porównaj migawki</h3>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[9px] text-muted-foreground uppercase tracking-wider block mb-1">Migawka A</label>
              <select
                value={diffId1}
                onChange={(e) => setDiffId1(e.target.value)}
                className="w-full h-8 rounded-md border border-[rgba(148,163,184,0.08)] bg-card text-[10px] text-foreground focus:outline-none focus:border-sylion-blue/40"
              >
                <option value="">-- Wybierz --</option>
                {snapshots.map((s) => (
                  <option key={s.snapshot_id} value={s.snapshot_id}>
                    [{s.decision_class}] {s.snapshot_id}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[9px] text-muted-foreground uppercase tracking-wider block mb-1">Migawka B</label>
              <select
                value={diffId2}
                onChange={(e) => setDiffId2(e.target.value)}
                className="w-full h-8 rounded-md border border-[rgba(148,163,184,0.08)] bg-card text-[10px] text-foreground focus:outline-none focus:border-sylion-blue/40"
              >
                <option value="">-- Wybierz --</option>
                {snapshots.map((s) => (
                  <option key={s.snapshot_id} value={s.snapshot_id}>
                    [{s.decision_class}] {s.snapshot_id}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </Card>

        {snapshotDiff && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            {/* Header comparison */}
            <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Migawka A</p>
                  <p className="text-[11px] font-medium">{snapshotDiff.s1.choice_made}</p>
                  <div className="flex items-center gap-2 mt-1">
                    {getDCBadge(snapshotDiff.s1.decision_class)}
                    <span className="text-[9px] text-muted-foreground font-mono">{snapshotDiff.s1.codebase_hash}</span>
                  </div>
                </div>
                <div>
                  <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Migawka B</p>
                  <p className="text-[11px] font-medium">{snapshotDiff.s2.choice_made}</p>
                  <div className="flex items-center gap-2 mt-1">
                    {getDCBadge(snapshotDiff.s2.decision_class)}
                    <span className="text-[9px] text-muted-foreground font-mono">{snapshotDiff.s2.codebase_hash}</span>
                  </div>
                </div>
              </div>
            </Card>

            {/* Module state changes */}
            <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
              <div className="flex items-center gap-2 mb-3">
                <Layers className="w-3.5 h-3.5 text-muted-foreground" />
                <h3 className="text-xs font-medium">Zmiany stanów modułów</h3>
              </div>
              <div className="space-y-1.5">
                {snapshotDiff.moduleChanges
                  .filter((c) => c.type !== "unchanged")
                  .map((c) => (
                    <div key={c.key} className={cn("flex items-center gap-3 px-3 py-1.5 rounded text-[10px]", diffColor(c.type))}>
                      <span className="font-mono w-24 shrink-0">{c.key}</span>
                      <span className="flex-1 truncate">{c.type === "added" ? `(new) ${c.new}` : c.type === "removed" ? `(removed) ${c.old}` : `${c.old} -> ${c.new}`}</span>
                      <Badge variant="outline" className={cn("text-[7px] h-3.5 shrink-0", diffColor(c.type))}>
                        {c.type}
                      </Badge>
                    </div>
                  ))}
                {snapshotDiff.moduleChanges.every((c) => c.type === "unchanged") && (
                  <p className="text-[10px] text-muted-foreground">Brak zmian stanów modułów między migawkami.</p>
                )}
              </div>
            </Card>

            {/* Contract changes */}
            <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                <h3 className="text-xs font-medium">Zmiany kontraktów</h3>
              </div>
              <div className="space-y-1.5">
                {snapshotDiff.contractsUnchanged.map((c) => (
                  <div key={c} className="flex items-center gap-2 px-3 py-1 text-[10px] text-muted-foreground">
                    <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30" />
                    <span className="font-mono">{c}</span>
                    <span className="text-[8px]">bez zmian</span>
                  </div>
                ))}
                {snapshotDiff.contractsAdded.map((c) => (
                  <div key={c} className="flex items-center gap-2 px-3 py-1 text-[10px] text-sylion-green bg-sylion-green/5 rounded">
                    <span className="w-1.5 h-1.5 rounded-full bg-sylion-green" />
                    <span className="font-mono">{c}</span>
                    <Badge variant="outline" className="text-[7px] h-3.5 border-sylion-green/30 text-sylion-green">dodano</Badge>
                  </div>
                ))}
                {snapshotDiff.contractsRemoved.map((c) => (
                  <div key={c} className="flex items-center gap-2 px-3 py-1 text-[10px] text-sylion-red bg-sylion-red/5 rounded">
                    <span className="w-1.5 h-1.5 rounded-full bg-sylion-red" />
                    <span className="font-mono">{c}</span>
                    <Badge variant="outline" className="text-[7px] h-3.5 border-sylion-red/30 text-sylion-red">usunięto</Badge>
                  </div>
                ))}
                {snapshotDiff.contractsAdded.length === 0 && snapshotDiff.contractsRemoved.length === 0 && (
                  <p className="text-[10px] text-muted-foreground">Brak zmian kontraktów.</p>
                )}
              </div>
            </Card>
          </motion.div>
        )}

        {!snapshotDiff && diffId1 && diffId2 && (
          <Card className="p-6 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
            <p className="text-[11px] text-muted-foreground">Wybierz dwie różne migawki do porównania.</p>
          </Card>
        )}
      </div>
    );
  }

  function GatesTab() {
    return (
      <div className="mt-4 space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Szukaj bram po ID, opisie lub zakresie..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-8 rounded-md border border-[rgba(148,163,184,0.06)] bg-card pl-9 pr-3 text-[11px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-sylion-blue/40"
          />
        </div>
        <div className="space-y-3">
          {filteredGates.length === 0 ? (
            <Card className="p-8 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
              <Shield className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">Nie znaleziono bram</p>
            </Card>
          ) : (
            filteredGates.map((gate) => {
              const RIcon = gate.status === "pass" ? CheckCircle2 : gate.status === "fail" ? XCircle : gate.status === "warning" ? AlertTriangle : Clock;
              const color = gate.status === "pass" ? "text-sylion-green" : gate.status === "fail" ? "text-sylion-red" : "text-sylion-amber";
              const bgColor = gate.status === "pass" ? "bg-sylion-green/10" : gate.status === "fail" ? "bg-sylion-red/10" : "bg-sylion-amber/10";
              const badgeColor = gate.status === "pass" ? "border-sylion-green/30 text-sylion-green bg-sylion-green/5" : gate.status === "fail" ? "border-sylion-red/30 text-sylion-red bg-sylion-red/5" : "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5";
              const expanded = evaluateResult?.gate_id === gate.gate_id;

              return (
                <Card key={gate.gate_id} className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.16)] transition-colors">
                  <div className="flex items-start gap-3">
                    <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center shrink-0", bgColor)}>
                      <RIcon className={cn("w-4 h-4", color)} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-[9px] h-5 font-mono border-border">{gate.gate_id}</Badge>
                        <Badge variant="outline" className={cn("text-[8px] h-4", badgeColor)}>{gate.status}</Badge>
                        {gate.auto !== undefined && (
                          <Badge variant="outline" className={cn("text-[8px] h-4", gate.auto ? "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5" : "border-purple-400/30 text-purple-400 bg-purple-400/5")}>
                            {gate.auto ? "AUTO" : "MANUAL"}
                          </Badge>
                        )}
                        {gate.scope && <span className="text-[9px] text-muted-foreground uppercase tracking-wider">{gate.scope}</span>}
                      </div>
                      <p className="text-[11px] text-muted-foreground">{gate.description}</p>
                    </div>
                    <Button variant="ghost" size="sm" className="h-6 text-[9px] shrink-0" disabled={evaluatingGate === gate.gate_id} onClick={() => handleEvaluate(gate.gate_id)}>
                      {evaluatingGate === gate.gate_id ? <RefreshCw className="w-3 h-3 animate-spin mr-1" /> : <Zap className="w-3 h-3 mr-1" />}
                      Oceń
                    </Button>
                  </div>
                  {gate.criteria && gate.criteria.length > 0 && (
                    <div className="mt-3 pl-11">
                      <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1.5">Kryteria</p>
                      {gate.criteria.map((c, i) => (
                        <div key={i} className="flex items-center gap-2 text-[10px]">
                          <ArrowRight className="w-2.5 h-2.5 text-muted-foreground shrink-0" />
                          <span className="text-muted-foreground">{c}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {gate.last_evaluated && (
                    <div className="mt-3 pl-11 flex items-center gap-1.5 text-[9px] text-muted-foreground">
                      <Clock className="w-2.5 h-2.5" />
                      <span>Ostatnio oceniano: {fmtDateTime(gate.last_evaluated)}</span>
                    </div>
                  )}
                  {expanded && evaluateResult && (
                    <div className={cn("mt-3 ml-11 px-3 py-2 rounded-md text-[10px]", evaluateResult.result === "pass" ? "bg-sylion-green/10 text-sylion-green" : evaluateResult.result === "fail" ? "bg-sylion-red/10 text-sylion-red" : "bg-sylion-amber/10 text-sylion-amber")}>
                      Wynik oceny: {evaluateResult.result}
                    </div>
                  )}
                </Card>
              );
            })
          )}
        </div>
      </div>
    );
  }

  /* ============================================================
     Detail Panel (slide-in from right)
     ============================================================ */

  function DetailPanel() {
    if (!selectedSnapshot) return null;
    const status = getStatusForSnapshot(selectedSnapshot);
    const isExpanded = expandedModules.has(selectedSnapshot.snapshot_id);

    return (
      <AnimatePresence>
        {detailOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/40 z-40"
              onClick={handleCloseDetail}
            />

            {/* Panel */}
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 250 }}
              className="fixed right-0 top-0 bottom-0 w-[480px] bg-[#0a0f1e] border-l border-[rgba(148,163,184,0.08)] z-50 overflow-y-auto"
            >
              <div className="p-5">
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Eye className="w-4 h-4 text-sylion-blue" />
                    <h2 className="text-sm font-semibold">Szczegóły decyzji</h2>
                  </div>
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={handleCloseDetail}>
                    <X className="w-3.5 h-3.5" />
                  </Button>
                </div>

                {/* Main info */}
                <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    {getDCBadge(selectedSnapshot.decision_class)}
                    <Badge variant="outline" className={cn("text-[8px] h-4", status === "active" ? "border-sylion-green/30 text-sylion-green" : status === "superseded" ? "border-sylion-amber/30 text-sylion-amber" : "border-sylion-red/30 text-sylion-red")}>
                      {status}
                    </Badge>
                  </div>
                  <p className="text-[12px] font-medium mb-2">{selectedSnapshot.choice_made}</p>

                  <div className="grid grid-cols-2 gap-2 text-[9px] text-muted-foreground">
                    <div><span className="uppercase tracking-wider">ID migawki</span><p className="font-mono mt-0.5">{selectedSnapshot.snapshot_id}</p></div>
                    <div><span className="uppercase tracking-wider">ID decyzji</span><p className="font-mono mt-0.5">{selectedSnapshot.decision_id}</p></div>
                    {selectedSnapshot.gate_id && <div><span className="uppercase tracking-wider">Brama</span><p className="font-mono mt-0.5">{selectedSnapshot.gate_id}</p></div>}
                    {selectedSnapshot.session_id && <div><span className="uppercase tracking-wider">Sesja</span><p className="font-mono mt-0.5">{selectedSnapshot.session_id}</p></div>}
                    <div><span className="uppercase tracking-wider">Utworzono</span><p className="mt-0.5">{fmtDateTime(selectedSnapshot.created_at)}</p></div>
                    {selectedSnapshot.codebase_hash && <div><span className="uppercase tracking-wider">Hash kodu</span><p className="font-mono mt-0.5">{selectedSnapshot.codebase_hash}</p></div>}
                    {selectedSnapshot.impact_radius != null && <div><span className="uppercase tracking-wider">Promień wpływu</span><p className="mt-0.5">{selectedSnapshot.impact_radius} modułów</p></div>}
                    {selectedSnapshot.superseded_by && <div><span className="uppercase tracking-wider">Zastąpione przez</span><p className="font-mono mt-0.5 text-sylion-amber">{selectedSnapshot.superseded_by}</p></div>}
                  </div>
                </Card>

                {/* Module States */}
                {selectedSnapshot.module_states && Object.keys(selectedSnapshot.module_states).length > 0 && (
                  <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] mb-4">
                    <button
                      className="flex items-center gap-2 w-full text-left"
                      onClick={() => toggleModules(selectedSnapshot.snapshot_id, setExpandedModules)}
                    >
                      {isExpanded ? <ChevronDown className="w-3 h-3 text-muted-foreground" /> : <ChevronRight className="w-3 h-3 text-muted-foreground" />}
                      <Layers className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="text-xs font-medium">Stany modułów w momencie decyzji</span>
                    </button>
                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                          <pre className="text-[8px] text-muted-foreground bg-muted/20 rounded p-2 mt-2 font-mono overflow-x-auto">
                            {JSON.stringify(selectedSnapshot.module_states, null, 2)}
                          </pre>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </Card>
                )}

                {/* Upstream dependencies */}
                {upstreamDecisions.length > 0 && (
                  <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] mb-4">
                    <div className="flex items-center gap-2 mb-2">
                      <ArrowRight className="w-3.5 h-3.5 text-sylion-blue rotate-180" />
                      <span className="text-xs font-medium">Zależności wyżej w łańcuchu</span>
                    </div>
                    <div className="space-y-1.5">
                      {upstreamDecisions.map((dep) => (
                        <div
                          key={dep.snapshot_id}
                          className="flex items-center gap-2 px-2 py-1.5 rounded bg-muted/20 cursor-pointer hover:bg-muted/30 transition-colors"
                          onClick={() => handleOpenDetail(dep)}
                        >
                          {getDCBadge(dep.decision_class)}
                          <span className="text-[10px] truncate flex-1">{dep.choice_made}</span>
                          <span className="text-[8px] text-muted-foreground font-mono">{dep.snapshot_id}</span>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {/* Downstream dependents */}
                {downstreamDecisions.length > 0 && (
                  <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] mb-4">
                    <div className="flex items-center gap-2 mb-2">
                      <ArrowDown className="w-3.5 h-3.5 text-sylion-green" />
                      <span className="text-xs font-medium">Zależności niżej w łańcuchu</span>
                    </div>
                    <div className="space-y-1.5">
                      {downstreamDecisions.map((dep) => (
                        <div
                          key={dep.snapshot_id}
                          className="flex items-center gap-2 px-2 py-1.5 rounded bg-muted/20 cursor-pointer hover:bg-muted/30 transition-colors"
                          onClick={() => handleOpenDetail(dep)}
                        >
                          {getDCBadge(dep.decision_class)}
                          <span className="text-[10px] truncate flex-1">{dep.choice_made}</span>
                          <span className="text-[8px] text-muted-foreground font-mono">{dep.snapshot_id}</span>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {/* Cascade Events */}
                {relatedCascades.length > 0 && (
                  <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] mb-4">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-3.5 h-3.5 text-sylion-amber" />
                      <span className="text-xs font-medium">Zdarzenia kaskadowe</span>
                    </div>
                    <div className="space-y-1.5">
                      {relatedCascades.map((ce) => (
                        <div key={ce.event_id} className={cn("px-2 py-1.5 rounded text-[9px]", cascadeTypeBg[ce.cascade_type])}>
                          <p>{ce.message}</p>
                          <span className="text-[7px] opacity-70">{ce.source_snapshot_id} {"->"} {ce.affected_snapshot_id}</span>
                          {ce.acknowledged && <span className="block text-[7px] mt-0.5 opacity-70">Potwierdzone</span>}
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {/* Change Decision */}
                {selectedSnapshot.is_active && (
                  <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)] mb-4">
                    <div className="flex items-center gap-2 mb-3">
                      <RotateCcw className="w-3.5 h-3.5 text-sylion-amber" />
                      <span className="text-xs font-medium">Zmień decyzję</span>
                    </div>
                    {changeSnapshotId === selectedSnapshot.snapshot_id ? (
                      <div className="space-y-2">
                        <input
                          type="text"
                          placeholder="Wprowadź nową decyzję..."
                          value={changeInput}
                          onChange={(e) => setChangeInput(e.target.value)}
                          className="w-full h-7 rounded-md border border-[rgba(148,163,184,0.08)] bg-card text-[10px] text-foreground px-3 focus:outline-none focus:border-sylion-amber/40"
                        />
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-6 text-[9px] border-sylion-amber/30 text-sylion-amber hover:bg-sylion-amber/10"
                            disabled={!changeInput.trim() || simulatingChange}
                            onClick={handleChangeDecision}
                          >
                            {simulatingChange ? <RefreshCw className="w-3 h-3 animate-spin mr-1" /> : <Play className="w-3 h-3 mr-1" />}
                            Potwierdź zmianę
                          </Button>
                          <Button variant="ghost" size="sm" className="h-6 text-[9px]" onClick={() => { setChangeSnapshotId(null); setChangeInput(""); }}>
                            Anuluj
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-[9px] border-sylion-amber/30 text-sylion-amber hover:bg-sylion-amber/10"
                        onClick={() => setChangeSnapshotId(selectedSnapshot.snapshot_id)}
                      >
                        <RotateCcw className="w-3 h-3 mr-1" />
                        Zmień decyzję
                      </Button>
                    )}
                  </Card>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    );
  }

  /* ============================================================
     Render
     ============================================================ */

  return (
    <div className="space-y-6">
      {/* HEADER */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Shield className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Decyzje
              <HelpTip text="Log wszystkich decyzji rady AEIS — kto/co/kiedy zdecydowało, z jakimi argumentami, przy jakich kosztach. Pełna ścieżka audytu (append-only). Filtruj po projekcie/poziomie/rezultacie." />
            </h1>
            <p className="text-sm text-muted-foreground">Śledzenie decyzji z analizą kaskadową</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" className="h-7 text-[10px]" onClick={() => { refreshGates(); }}>
            <RefreshCw className="w-3 h-3 mr-1" />
            Odśwież
          </Button>
          {cascadeAlertCount > 0 && (
            <Badge variant="outline" className="text-[10px] border-sylion-red/30 text-sylion-red bg-sylion-red/5">
              <Siren className="w-3 h-3 mr-1" />
              {cascadeAlertCount} Alert{cascadeAlertCount !== 1 ? "y" : ""}
            </Badge>
          )}
          <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green">
            <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-sylion-green" />
            NA ŻYWO
          </Badge>
        </div>
      </div>

      {/* STATS */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Łącznie decyzji" value={snapshots.length} icon={ListChecks} color="text-foreground" tipText="Wszystkie zarejestrowane migawki decyzji (aktywne + zastąpione + unieważnione)." />
        <StatCard label="Aktywne decyzję" value={activeCount} icon={CheckCircle2} color="text-sylion-green" tipText="Migawki obecnie obowiązujące — wpływające na konfigurację i moduły." />
        <StatCard label="Alerty kaskadowe" value={cascadeAlertCount} icon={AlertTriangle} color={cascadeAlertCount > 0 ? "text-sylion-red" : "text-sylion-green"} tipText="Niepotwierdzone zdarze?ia kaskadowe wymagające decyzji człowieka." />
        <StatCard label="Wynik zgodności" value={`${compliancePct}%`} icon={BarChart3} color={compliancePct >= 80 ? "text-sylion-green" : compliancePct >= 50 ? "text-sylion-amber" : "text-sylion-red"} tipText="Procent decyzji bez konfliktów kaskadowych. <80% wymaga przeglądu rady." />
      </div>

      {/* TABS */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <HelpTip text="Aktywny łańcuch: graf zależności obecnych decyzji. Oś czasu: kronika wszystkich decyzji. Efekty kaskadowe: kto blokuje kogo. Diff: porównaj dwie migawki. Bramy: kontrole D0-D5." />
        <TabsList>
          <TabsTrigger value="chain" className="text-[11px]">
            <GitBranch className="w-3 h-3 mr-1" />
            Aktywny łańcuch
          </TabsTrigger>
          <TabsTrigger value="timeline" className="text-[11px]">
            <Activity className="w-3 h-3 mr-1" />
            Oś czasu
          </TabsTrigger>
          <TabsTrigger value="cascade" className="text-[11px]">
            <Layers className="w-3 h-3 mr-1" />
            Efekty kaskadowe
          </TabsTrigger>
          <TabsTrigger value="diff" className="text-[11px]">
            <GitMerge className="w-3 h-3 mr-1" />
            Diff migawek
          </TabsTrigger>
          <TabsTrigger value="gates" className="text-[11px]">
            <Shield className="w-3 h-3 mr-1" />
            Bramy
          </TabsTrigger>
        </TabsList>

        {/* ACTIVE CHAIN TAB */}
        <TabsContent value="chain">
          <div className="mt-4">
            {chainNodes.length === 0 ? (
              <Card className="p-8 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
                <GitBranch className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">Brak aktywnego łańcucha decyzji</p>
              </Card>
            ) : (
              <div className="space-y-2 pl-6">
                {chainNodes.map((snap) => (
                  <ChainNode key={snap.snapshot_id} snap={snap} depth={0} />
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* TIMELINE TAB */}
        <TabsContent value="timeline">
          <div className="mt-4 space-y-4">
            {/* Filters */}
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-muted-foreground uppercase tracking-wider">Filtruj według klasy:</span>
              <div className="flex gap-1.5">
                {["", "D0", "D1", "D2", "D3", "D4", "D5"].map((cls) => (
                  <Button
                    key={cls}
                    variant={timelineFilter === cls ? "default" : "outline"}
                    size="sm"
                    className={cn(
                      "h-5 text-[8px] px-2",
                      timelineFilter === cls
                        ? cls ? dcBgColors[cls] + " border-transparent" : "bg-sylion-blue/20 border-sylion-blue/40 text-sylion-blue"
                        : "border-border text-muted-foreground"
                    )}
                    onClick={() => setTimelineFilter(cls)}
                  >
                    {cls || "Wszystkie"}
                  </Button>
                ))}
              </div>
            </div>

            {/* Timeline */}
            {timelineEntries.length === 0 ? (
              <Card className="p-8 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
                <Activity className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">Brak historii decyzji</p>
              </Card>
            ) : (
              <div className="relative space-y-0">
                {timelineEntries.map((snap, idx) => (
                  <TimelineEntry key={snap.snapshot_id} snap={snap} idx={idx} isLast={idx === timelineEntries.length - 1} />
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* CASCADE IMPACT TAB */}
        <TabsContent value="cascade">
          <CascadeImpactTab />
        </TabsContent>

        {/* SNAPSHOT DIFF TAB */}
        <TabsContent value="diff">
          <SnapshotDiffTab />
        </TabsContent>

        {/* GATES TAB */}
        <TabsContent value="gates">
          <GatesTab />
        </TabsContent>
      </Tabs>

      {/* DETAIL PANEL */}
      <DetailPanel />
    </div>
  );
}
