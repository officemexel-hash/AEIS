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
  GitBranch,
  Undo2,
  Plus,
  CheckCircle2,
  Circle,
  WifiOff,
  RotateCcw,
  Clock,
  MousePointerClick,
} from "lucide-react";

/* -------------------------------------------------------------------------- */
/*  Types                                                                     */
/* -------------------------------------------------------------------------- */

interface HGChoice {
  choice_id: string;
  label: string;
  description: string;
  consequences: string;
}

interface HGDecision {
  node_id: string;
  context: string;
  phase: string;
  choices: HGChoice[];
}

interface HGTreeNode {
  node_id: string;
  label: string;
  phase: string;
  parent_id: string | null;
  children: HGTreeNode[];
  status: "current" | "visited" | "superseded";
  chosen_choice_id?: string;
}

interface HGHistoryEntry {
  node_id: string;
  phase: string;
  label: string;
  timestamp: number;
}

interface HGSession {
  session_id: string;
  title: string;
  description: string;
  created_at: number;
}

/* -------------------------------------------------------------------------- */
/*  Component                                                                 */
/* -------------------------------------------------------------------------- */

export function HumanGatePanel() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";

  const [sessions, setSessions] = useState<HGSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [currentDecision, setCurrentDecision] = useState<HGDecision | null>(null);
  const [tree, setTree] = useState<HGTreeNode | null>(null);
  const [history, setHistory] = useState<HGHistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [choosing, setChoosing] = useState<string | null>(null);

  /* ---- Convert flat API tree response to nested HGTreeNode ---- */
  function buildTree(apiTree: { nodes: any[]; edges: any[]; current_node_id: string } | null): HGTreeNode | null {
    if (!apiTree || !apiTree.nodes || apiTree.nodes.length === 0) return null;
    const nodeMap = new Map<string, HGTreeNode>();
    const childMap = new Map<string, HGTreeNode[]>();

    for (const n of apiTree.nodes) {
      const status = n.node_id === apiTree.current_node_id ? "current" : n.status === "decided" ? "visited" : n.status === "superseded" ? "superseded" : "visited";
      const treeNode: HGTreeNode = {
        node_id: n.node_id,
        label: n.title || n.context || "",
        phase: n.phase || "",
        parent_id: n.parent_node_id || null,
        children: [],
        status,
        chosen_choice_id: n.parent_choice_id || undefined,
      };
      nodeMap.set(n.node_id, treeNode);
      if (n.parent_node_id) {
        const siblings = childMap.get(n.parent_node_id) || [];
        siblings.push(treeNode);
        childMap.set(n.parent_node_id, siblings);
      }
    }

    for (const [, children] of childMap) {
      for (const child of children) {
        const parent = nodeMap.get(child.parent_id!);
        if (parent) parent.children.push(child);
      }
    }

    // Root is the node with no parent
    for (const n of nodeMap.values()) {
      if (!n.parent_id) return n;
    }
    return null;
  }

  /* ---- Fetch sessions on mount ---- */
  useEffect(() => {
    if (!backendLive) return;
    api.listHumanGateSessions()
      .then((d: any) => setSessions(d.sessions ?? []))
      .catch(() => {});
  }, [backendLive]);

  /* ---- Load tree, history, current decision when session changes ---- */
  const loadSessionData = useCallback(async (sessionId: string) => {
    setLoading(true);
    try {
      const [treeRes, histRes, decRes] = await Promise.all([
        api.getHumanGateTree(sessionId).catch(() => ({ nodes: [], edges: [], current_node_id: "" })),
        api.getHumanGateHistory(sessionId).catch(() => ({ history: [] })),
        api.getHumanGateCurrentDecision(sessionId).catch(() => null),
      ]);
      setTree(buildTree(treeRes));
      setHistory(histRes.history ?? []);
      setCurrentDecision(decRes);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    if (activeSessionId && backendLive) {
      loadSessionData(activeSessionId);
    } else {
      setTree(null);
      setHistory([]);
      setCurrentDecision(null);
    }
  }, [activeSessionId, backendLive, loadSessionData]);

  /* ---- Create new session ---- */
  const createSession = async () => {
    if (!backendLive) return;
    setLoading(true);
    try {
      const result = await api.createHumanGateSession(
        "Decision Session",
        "Interactive decision tree"
      );
      if (result.session_id) {
        setActiveSessionId(result.session_id);
        const d = await api.listHumanGateSessions();
        setSessions(d.sessions ?? []);
      }
    } catch {}
    setLoading(false);
  };

  /* ---- Make a choice ---- */
  const makeChoice = async (nodeId: string, choiceId: string) => {
    if (!activeSessionId) return;
    setChoosing(choiceId);
    try {
      await api.makeHumanGateChoice(nodeId, choiceId);
      await loadSessionData(activeSessionId);
    } catch {}
    setChoosing(null);
  };

  /* ---- Undo last choice ---- */
  const undoLast = async () => {
    if (!activeSessionId) return;
    setLoading(true);
    try {
      await api.undoHumanGateChoice(activeSessionId);
      await loadSessionData(activeSessionId);
    } catch {}
    setLoading(false);
  };

  /* ---- Rollback to a specific node ---- */
  const rollbackTo = async (nodeId: string) => {
    if (!activeSessionId) return;
    setLoading(true);
    try {
      await api.rollbackHumanGateTo(activeSessionId, nodeId);
      await loadSessionData(activeSessionId);
    } catch {}
    setLoading(false);
  };

  /* ---- Backend offline ---- */
  if (!backendLive) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <WifiOff className="w-8 h-8 text-sylion-red/50 mb-3" />
        <p className="text-xs text-muted-foreground">Backend niedostępny</p>
      </div>
    );
  }

  /* ---- No active session: session picker ---- */
  if (!activeSessionId) {
    return (
      <div className="h-full flex flex-col p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-primary/60" />
            <span className="text-xs font-semibold">Human Gate</span>
          </div>
          <Button size="sm" onClick={createSession} disabled={loading}>
            {loading ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <Plus className="w-3.5 h-3.5 mr-1.5" />
            )}
            New Session
          </Button>
        </div>

        {sessions.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center">
            <GitBranch className="w-8 h-8 text-primary/20 mb-3" />
            <p className="text-xs text-muted-foreground mb-1">No decision sessions</p>
            <p className="text-[10px] text-muted-foreground/60">
              Create a session to start making decisions
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto space-y-1">
            {sessions.map((s) => (
              <button
                key={s.session_id}
                onClick={() => setActiveSessionId(s.session_id)}
                className="w-full text-left px-3 py-2.5 rounded-lg border border-[rgba(148,163,184,0.06)] bg-card hover:bg-muted/20 transition-colors"
              >
                <p className="text-[11px] font-medium truncate">
                  {s.title || s.session_id.slice(0, 12)}
                </p>
                {s.description && (
                  <p className="text-[10px] text-muted-foreground truncate mt-0.5">
                    {s.description}
                  </p>
                )}
                <p className="text-[9px] text-muted-foreground/50 mt-1">
                  {s.created_at
                    ? new Date(s.created_at * 1000).toLocaleString()
                    : ""}
                </p>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  /* ---- Active session ---- */
  const activeSession = sessions.find((s) => s.session_id === activeSessionId);

  return (
    <div className="flex h-full">
      {/* ===== Left: Decision card + history ===== */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-[rgba(148,163,184,0.06)]">
        {/* Session header */}
        <div className="px-4 pt-3 pb-2 border-b border-[rgba(148,163,184,0.06)] flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setActiveSessionId(null)}
              className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
            >
              <RotateCcw className="w-3 h-3" />
            </button>
            <span className="text-[11px] font-semibold truncate">
              {activeSession?.title || activeSessionId.slice(0, 16)}
            </span>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {history.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-[10px] px-2"
                onClick={undoLast}
                disabled={loading}
              >
                <Undo2 className="w-3 h-3 mr-1" />
                Undo last
              </Button>
            )}
          </div>
        </div>

        {/* Decision area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading && !currentDecision ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-5 h-5 text-muted-foreground animate-spin" />
            </div>
          ) : currentDecision ? (
            <>
              {/* Phase badge */}
              <div className="flex items-center gap-2 mb-1">
                <Badge
                  variant="outline"
                  className="text-[9px] border-primary/30 text-primary"
                >
                  {currentDecision.phase}
                </Badge>
              </div>

              {/* Context */}
              <p className="text-xs leading-relaxed text-foreground mb-3">
                {currentDecision.context}
              </p>

              {/* Choices */}
              <div className="space-y-2">
                {currentDecision.choices.map((choice) => (
                  <Card
                    key={choice.choice_id}
                    className="p-3 bg-card border-[rgba(148,163,184,0.06)] hover:border-primary/20 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-[11px] font-semibold mb-1">
                          {choice.label}
                        </p>
                        {choice.description && (
                          <p className="text-[10px] text-muted-foreground leading-relaxed mb-1.5">
                            {choice.description}
                          </p>
                        )}
                        {choice.consequences && (
                          <p className="text-[10px] text-sylion-amber/80 leading-relaxed">
                            {choice.consequences}
                          </p>
                        )}
                      </div>
                      <Button
                        size="sm"
                        className="h-7 text-[10px] px-3 shrink-0"
                        onClick={() =>
                          makeChoice(currentDecision.node_id, choice.choice_id)
                        }
                        disabled={choosing !== null}
                      >
                        {choosing === choice.choice_id ? (
                          <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                        ) : (
                          <MousePointerClick className="w-3 h-3 mr-1" />
                        )}
                        Choose
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <CheckCircle2 className="w-8 h-8 text-sylion-green/40 mb-3" />
              <p className="text-xs text-muted-foreground mb-1">
                Decision tree complete
              </p>
              <p className="text-[10px] text-muted-foreground/60">
                All decisions have been made for this session
              </p>
            </div>
          )}
        </div>

        {/* History timeline */}
        {history.length > 0 && (
          <div className="border-t border-[rgba(148,163,184,0.06)] max-h-[40%] overflow-y-auto">
            <div className="px-4 pt-2 pb-1">
              <span className="text-[9px] font-medium text-muted-foreground uppercase tracking-wider">
                Decision History
              </span>
            </div>
            <div className="px-4 pb-3 space-y-0">
              {history.map((entry, i) => {
                const isLast = i === history.length - 1;
                return (
                  <div key={entry.node_id} className="flex gap-2.5">
                    {/* Łącznik osi czasu */}
                    <div className="flex flex-col items-center">
                      <div
                        className={cn(
                          "w-2.5 h-2.5 rounded-full shrink-0 mt-1.5",
                          isLast
                            ? "bg-sylion-green"
                            : "bg-muted-foreground/30"
                        )}
                      />
                      {!isLast && (
                        <div className="w-px flex-1 bg-[rgba(148,163,184,0.08)]" />
                      )}
                    </div>
                    {/* Entry content */}
                    <button
                      onClick={() => rollbackTo(entry.node_id)}
                      className={cn(
                        "flex-1 text-left py-1.5 px-2 rounded-md transition-colors mb-0.5",
                        "hover:bg-muted/20",
                        isLast ? "opacity-100" : "opacity-70"
                      )}
                      title="Click to rollback to this decision"
                    >
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className="text-[8px] h-4 px-1.5"
                        >
                          {entry.phase}
                        </Badge>
                        <span className="text-[10px] font-medium">
                          {entry.label}
                        </span>
                      </div>
                      {entry.timestamp > 0 && (
                        <p className="text-[9px] text-muted-foreground/50 mt-0.5">
                          <Clock className="w-2.5 h-2.5 inline mr-0.5 -mt-px" />
                          {new Date(entry.timestamp * 1000).toLocaleTimeString()}
                        </p>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ===== Right: Decision tree diagram ===== */}
      <div className="w-[45%] shrink-0 flex flex-col bg-[#050816]/50">
        <div className="px-4 pt-3 pb-2 border-b border-[rgba(148,163,184,0.06)]">
          <span className="text-[9px] font-medium text-muted-foreground uppercase tracking-wider">
            Decision Tree
          </span>
        </div>
        <div className="flex-1 overflow-auto p-4">
          {tree ? (
            <TreeNode node={tree} depth={0} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full">
              <GitBranch className="w-8 h-8 text-muted-foreground/20 mb-3" />
              <p className="text-[10px] text-muted-foreground/60">
                {loading ? "Loading tree..." : "No tree data yet"}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Tree Visualization (CSS-based recursive)                                  */
/* -------------------------------------------------------------------------- */

function TreeNode({ node, depth }: { node: HGTreeNode; depth: number }) {
  const hasChildren = node.children && node.children.length > 0;

  const statusStyles: Record<string, string> = {
    current: "bg-primary text-primary-foreground ring-2 ring-primary/40",
    visited: "bg-sylion-green/20 text-sylion-green border border-sylion-green/30",
    superseded:
      "bg-muted/20 text-muted-foreground/40 border border-[rgba(148,163,184,0.06)]",
  };

  return (
    <div className="flex flex-col">
      {/* Node badge */}
      <div className="flex items-center gap-2">
        <div
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[9px] font-medium",
            statusStyles[node.status] || statusStyles.superseded
          )}
        >
          {node.status === "current" ? (
            <Circle className="w-2 h-2 fill-current" />
          ) : node.status === "visited" ? (
            <CheckCircle2 className="w-2.5 h-2.5" />
          ) : (
            <Circle className="w-2 h-2" />
          )}
          <span className="truncate max-w-[120px]">{node.label || node.node_id.slice(0, 8)}</span>
        </div>
        {node.phase && (
          <Badge
            variant="outline"
            className={cn(
              "text-[8px] h-4 px-1.5",
              node.status === "superseded" && "opacity-40"
            )}
          >
            {node.phase}
          </Badge>
        )}
      </div>

      {/* Children */}
      {hasChildren && (
        <div className="ml-4 border-l border-[rgba(148,163,184,0.08)] pl-4 mt-1 space-y-1">
          {node.children.map((child) => (
            <div key={child.node_id} className="relative">
              {/* Horizontal connector */}
              <div
                className={cn(
                  "absolute left-[-16px] top-3 w-4 border-t",
                  child.status === "visited"
                    ? "border-sylion-green/30"
                    : child.status === "current"
                    ? "border-primary/30"
                    : "border-[rgba(148,163,184,0.06)] border-dashed"
                )}
              />
              <TreeNode node={child} depth={depth + 1} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
