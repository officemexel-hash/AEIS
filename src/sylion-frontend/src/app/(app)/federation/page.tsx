"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/common/HelpTip";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cloud,
  Cpu,
  Globe,
  Laptop,
  Loader2,
  RefreshCw,
  Server,
  Signal,
  Workflow,
  XCircle,
} from "lucide-react";

/* ============================================================
   Typy
   ============================================================ */

interface FederationNode {
  node_id: string;
  name: string;
  kind: string; // full_instance | compute_provider | hybrid
  status: string; // online | offline | degraded | unknown
  base_url: string;
  locality: string; // local | lan | cloud
  tags: string[];
  available_models: string[];
  cost_per_1k_tokens_usd: Record<string, number>;
  last_heartbeat: number; // epoch seconds
  capacity_score: number;
  metadata?: Record<string, unknown>;
}

interface FederationListResponse {
  count: number;
  nodes: FederationNode[];
}

interface FederationHealth {
  status?: string;
  phase?: string;
  total_nodes?: number;
  active_nodes?: number;
  routing_decisions_total?: number;
}

interface RoutingDecisionView {
  chosen_node_id: string | null;
  chosen_model_id: string | null;
  rationale: string;
  candidates: string[];
  rejected: { node_id: string; reason: string }[];
}

const PRIVACY_LEVELS: { id: string; label: string; help: string }[] = [
  {
    id: "any",
    label: "Dowolne (any)",
    help: "Bez ograniczen lokalnosci — wybiera najta?szy/najszybszy node.",
  },
  {
    id: "external_ok",
    label: "Cloud OK (external_ok)",
    help: "Cloud nodes dozwolone, ale local rownie ma szanse jesli ma model.",
  },
  {
    id: "prefer_local",
    label: "Preferuj lokalne (prefer_local)",
    help: "Boost dla local; fallback na lan/cloud gdy brak local.",
  },
  {
    id: "local_only",
    label: "Tylko lokalne (local_only)",
    help: "Twardy filtr — dane musza zostać na local node-ach (np. PII).",
  },
];

/* ============================================================
   Pomocnicze
   ============================================================ */

function formatRelativePl(epochSecs: number, nowSecs: number): string {
  if (!epochSecs || epochSecs <= 0) return "—";
  const diff = Math.max(0, Math.round(nowSecs - epochSecs));
  if (diff < 5) return "teraz";
  if (diff < 60) return `${diff} sek temu`;
  const mins = Math.floor(diff / 60);
  if (mins < 60) return `${mins} min temu`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} godz temu`;
  const days = Math.floor(hours / 24);
  return `${days} dni temu`;
}

function avgCostPer1k(node: FederationNode): number | null {
  const values = Object.values(node.cost_per_1k_tokens_usd || {});
  if (values.length === 0) return null;
  const sum = values.reduce((a, b) => a + b, 0);
  return sum / values.length;
}

function statusPill(status: string): { label: string; color: string; icon: typeof Activity } {
  const s = (status || "").toLowerCase();
  if (s === "online") {
    return {
      label: "online",
      color: "border-sylion-green/40 bg-sylion-green/10 text-sylion-green",
      icon: CheckCircle2,
    };
  }
  if (s === "degraded") {
    return {
      label: "degraded",
      color: "border-sylion-amber/40 bg-sylion-amber/10 text-sylion-amber",
      icon: AlertTriangle,
    };
  }
  if (s === "offline") {
    return {
      label: "offline",
      color: "border-red-400/40 bg-red-400/10 text-red-400",
      icon: XCircle,
    };
  }
  return {
    label: status || "unknown",
    color: "border-border/40 bg-muted/30 text-muted-foreground",
    icon: Activity,
  };
}

function kindPill(kind: string): { label: string; color: string; icon: typeof Cpu } {
  const k = (kind || "").toLowerCase();
  if (k === "full_instance") {
    return {
      label: "Full instance",
      color: "border-sylion-blue/40 bg-sylion-blue/10 text-sylion-blue",
      icon: Server,
    };
  }
  if (k === "compute_provider") {
    return {
      label: "Compute provider",
      color: "border-violet-400/40 bg-violet-400/10 text-violet-400",
      icon: Cpu,
    };
  }
  if (k === "hybrid") {
    return {
      label: "Hybrid",
      color: "border-emerald-400/40 bg-emerald-400/10 text-emerald-400",
      icon: Laptop,
    };
  }
  return {
    label: kind,
    color: "border-border/40 bg-muted/30 text-muted-foreground",
    icon: Cpu,
  };
}

function localityIcon(locality: string): typeof Laptop {
  const l = (locality || "").toLowerCase();
  if (l === "local") return Laptop;
  if (l === "lan") return Globe;
  if (l === "cloud") return Cloud;
  return Globe;
}

/* ============================================================
   Strona
   ============================================================ */

export default function FederationPage() {
  const [nodes, setNodes] = useState<FederationNode[]>([]);
  const [health, setHealth] = useState<FederationHealth | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<number>(Date.now());
  const [now, setNow] = useState<number>(Math.floor(Date.now() / 1000));

  // Routing test form
  const [routeModel, setRouteModel] = useState<string>("qwen2.5:7b");
  const [routePrivacy, setRoutePrivacy] = useState<string>("any");
  const [routeMaxCost, setRouteMaxCost] = useState<string>("");
  const [routeBusy, setRouteBusy] = useState<boolean>(false);
  const [routeDecision, setRouteDecision] = useState<RoutingDecisionView | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);

  /* ---------- Fetch ---------- */
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nodesResp, healthResp] = await Promise.all([
        api.listFederationNodes() as Promise<FederationListResponse>,
        api.getFederationHealth() as Promise<FederationHealth>,
      ]);
      setNodes(Array.isArray(nodesResp?.nodes) ? nodesResp.nodes : []);
      setHealth(healthResp || null);
      setLastRefresh(Date.now());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Nie udało się pobrać federacji.",
      );
      setNodes([]);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Tick every 5s for relative time labels.
  useEffect(() => {
    const id = window.setInterval(() => {
      setNow(Math.floor(Date.now() / 1000));
    }, 5000);
    return () => window.clearInterval(id);
  }, []);

  /* ---------- KPI ---------- */
  const kpis = useMemo(() => {
    const total = nodes.length;
    const online = nodes.filter((n) => (n.status || "").toLowerCase() === "online").length;
    const stale = nodes.filter(
      (n) => n.last_heartbeat > 0 && now - n.last_heartbeat > 60,
    ).length;
    const decisions = health?.routing_decisions_total ?? 0;
    return { total, online, stale, decisions };
  }, [nodes, now, health]);

  /* ---------- Routing test ---------- */
  const handleRoute = useCallback(async () => {
    const model = routeModel.trim();
    if (!model) return;
    setRouteBusy(true);
    setRouteError(null);
    setRouteDecision(null);
    try {
      const max = routeMaxCost.trim() ? Number(routeMaxCost) : null;
      const decision = (await api.routeFederation(
        model,
        routePrivacy,
        max !== null && Number.isFinite(max) ? max : null,
      )) as RoutingDecisionView;
      setRouteDecision(decision);
    } catch (err) {
      setRouteError(
        err instanceof Error ? err.message : "Routing nie powiodl sie.",
      );
    } finally {
      setRouteBusy(false);
    }
  }, [routeModel, routePrivacy, routeMaxCost]);

  const lastRefreshLabel = new Date(lastRefresh).toLocaleTimeString("pl-PL");

  /* ============================================================
     Render
     ============================================================ */
  return (
    <div className="space-y-5 p-6">
      {/* ===== Naglowek ===== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-start justify-between gap-3"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Signal className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight flex items-center">
              Federacja Compute Providers (W17)
              <HelpTip
                text={
                  "Lista wszystkich nodów (Full Instance / Compute Provider / Hybrid). " +
                  "Każdy node wysyła heartbeat co 30s. Routing engine wybiera najta?szy " +
                  "dostepny node respektujac privacy levels."
                }
                side="bottom"
              />
            </h1>
            <p className="text-sm text-muted-foreground">
              Mesh nodów + heartbeaty + deterministic routing.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground font-mono">
            Odświeżono: {lastRefreshLabel}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refresh()}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            )}
            Odśwież
          </Button>
        </div>
      </motion.div>

      {/* ===== Błądy ===== */}
      {error && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <div className="p-3 flex items-center gap-2 text-amber-600">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs">{error}</span>
          </div>
        </Card>
      )}

      {/* ===== KPI ===== */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 space-y-1">
            <div className="flex items-center gap-2 text-[10px] uppercase text-muted-foreground tracking-wider">
              Wszystkie nody
              <HelpTip text="Liczba zarejestrowanych nodów w federacji (oba aktywne i nieaktywne)." />
            </div>
            <div className="text-2xl font-semibold font-mono">{kpis.total}</div>
          </div>
        </Card>
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 space-y-1">
            <div className="flex items-center gap-2 text-[10px] uppercase text-muted-foreground tracking-wider">
              Online
              <HelpTip text="Nody z status=online i swiezym heartbeatem (do 60s)." />
            </div>
            <div className="text-2xl font-semibold font-mono text-sylion-green">
              {kpis.online}
            </div>
          </div>
        </Card>
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 space-y-1">
            <div className="flex items-center gap-2 text-[10px] uppercase text-muted-foreground tracking-wider">
              Stale (heartbeat &gt; 60s)
              <HelpTip text="Nody które nie wysyła?y heartbeat w ostatnich 60 sekundach — wykluczone z routingu." />
            </div>
            <div
              className={cn(
                "text-2xl font-semibold font-mono",
                kpis.stale > 0 ? "text-sylion-amber" : "text-muted-foreground",
              )}
            >
              {kpis.stale}
            </div>
          </div>
        </Card>
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 space-y-1">
            <div className="flex items-center gap-2 text-[10px] uppercase text-muted-foreground tracking-wider">
              Decyzje routingu
              <HelpTip text="??cznie ile razy router odpali? sie od restartu backendu." />
            </div>
            <div className="text-2xl font-semibold font-mono">{kpis.decisions}</div>
          </div>
        </Card>
      </div>

      {/* ===== Tabela nodów ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-sylion-blue" />
            <h3 className="text-sm font-semibold">Nody federacji</h3>
            <HelpTip
              text={
                "Snapshot bieżącego stanu registry. Heartbeaty sa polling-owane co 5s " +
                "tylko po stronie UI (relative time); pelny refresh wykonaj klikajac przycisk."
              }
            />
            <Badge variant="outline" className="font-mono text-[10px]">
              {nodes.length}
            </Badge>
          </div>

          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-10 bg-muted/30 animate-pulse rounded-md border border-border/30"
                />
              ))}
            </div>
          ) : nodes.length === 0 ? (
            <div className="p-8 text-center text-xs text-muted-foreground">
              Brak nodów w federacji. Uruchom <span className="font-mono">deploy_agent</span> na
              dowolnym hoscie żeby zarejestrowa? sie tutaj.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                    <th className="px-2 py-2">Nazwa</th>
                    <th className="px-2 py-2">Typ</th>
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Lokalizacja</th>
                    <th className="px-2 py-2 text-right">Modeli</th>
                    <th className="px-2 py-2 text-right">Sredni koszt /1k</th>
                    <th className="px-2 py-2 text-right">Capacity</th>
                    <th className="px-2 py-2">Heartbeat</th>
                  </tr>
                </thead>
                <tbody>
                  {nodes.map((n) => {
                    const sp = statusPill(n.status);
                    const kp = kindPill(n.kind);
                    const LocIcon = localityIcon(n.locality);
                    const KindIcon = kp.icon;
                    const StatusIcon = sp.icon;
                    const cost = avgCostPer1k(n);
                    const isStale =
                      n.last_heartbeat > 0 && now - n.last_heartbeat > 60;
                    return (
                      <tr
                        key={n.node_id}
                        className="border-t border-border/20 hover:bg-muted/10"
                      >
                        <td className="px-2 py-2">
                          <div className="flex flex-col">
                            <span className="font-medium">{n.name}</span>
                            <span className="text-[10px] font-mono text-muted-foreground truncate max-w-[200px]">
                              {n.node_id}
                            </span>
                          </div>
                        </td>
                        <td className="px-2 py-2">
                          <span
                            className={cn(
                              "inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-mono",
                              kp.color,
                            )}
                          >
                            <KindIcon className="w-3 h-3" />
                            {kp.label}
                          </span>
                        </td>
                        <td className="px-2 py-2">
                          <span
                            className={cn(
                              "inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-mono",
                              sp.color,
                            )}
                          >
                            <StatusIcon className="w-3 h-3" />
                            {sp.label}
                          </span>
                        </td>
                        <td className="px-2 py-2">
                          <span className="inline-flex items-center gap-1 text-[11px]">
                            <LocIcon className="w-3 h-3 text-muted-foreground" />
                            {n.locality}
                          </span>
                        </td>
                        <td className="px-2 py-2 text-right font-mono">
                          {n.available_models?.length ?? 0}
                        </td>
                        <td className="px-2 py-2 text-right font-mono">
                          {cost === null ? (
                            <span className="text-muted-foreground">free</span>
                          ) : (
                            `$${cost.toFixed(5)}`
                          )}
                        </td>
                        <td className="px-2 py-2 text-right font-mono">
                          {n.capacity_score?.toFixed(2) ?? "—"}
                        </td>
                        <td
                          className={cn(
                            "px-2 py-2 font-mono text-[11px]",
                            isStale ? "text-sylion-amber" : "text-muted-foreground",
                          )}
                        >
                          {formatRelativePl(n.last_heartbeat, now)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      {/* ===== Test routing ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Workflow className="w-4 h-4 text-sylion-blue" />
            <h3 className="text-sm font-semibold">Test routing</h3>
            <HelpTip
              text={
                "Symulacja: dla podanego model_id + privacy_level routing engine " +
                "(W17) zwróci który node wygrał i dlaczego. Nie wykonuje żadnego inferensu."
              }
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_1fr_auto] gap-3 items-end">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase text-muted-foreground tracking-wider flex items-center">
                Model ID
                <HelpTip text="Identyfikator modelu — np. qwen2.5:7b, llama3:70b." />
              </label>
              <input
                type="text"
                value={routeModel}
                onChange={(e) => setRouteModel(e.target.value)}
                placeholder="qwen2.5:7b"
                className="w-full rounded-md border border-border/40 bg-black/30 px-3 py-2 text-xs font-mono outline-none focus:border-sylion-blue/40"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase text-muted-foreground tracking-wider flex items-center">
                Privacy level
                <HelpTip text="Pierwszy filtr w routerze — opisuje gdzie wolno wykonac task." />
              </label>
              <select
                value={routePrivacy}
                onChange={(e) => setRoutePrivacy(e.target.value)}
                className="w-full rounded-md border border-border/40 bg-black/30 px-3 py-2 text-xs font-mono outline-none focus:border-sylion-blue/40"
              >
                {PRIVACY_LEVELS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] uppercase text-muted-foreground tracking-wider flex items-center">
                Max koszt USD/1k (opc.)
                <HelpTip text="Twardy cap — nody drozsze niz ten cost beda odrzucone z reason 'koszt > cap'." />
              </label>
              <input
                type="number"
                step="0.001"
                min="0"
                value={routeMaxCost}
                onChange={(e) => setRouteMaxCost(e.target.value)}
                placeholder="0.005"
                className="w-full rounded-md border border-border/40 bg-black/30 px-3 py-2 text-xs font-mono outline-none focus:border-sylion-blue/40"
              />
            </div>
            <Button
              onClick={() => void handleRoute()}
              disabled={routeBusy || !routeModel.trim()}
            >
              {routeBusy ? (
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : (
                <Workflow className="w-3.5 h-3.5 mr-1.5" />
              )}
              Wykonaj routing
            </Button>
          </div>

          {routeError && (
            <div className="flex items-center gap-2 text-amber-600 text-xs">
              <AlertTriangle className="w-4 h-4" />
              <span>{routeError}</span>
            </div>
          )}

          {routeDecision && (
            <div className="space-y-3">
              {/* Wybrany node */}
              <div
                className={cn(
                  "rounded-md border px-3 py-2",
                  routeDecision.chosen_node_id
                    ? "border-sylion-green/40 bg-sylion-green/5"
                    : "border-amber-500/40 bg-amber-500/5",
                )}
              >
                <div className="flex items-center gap-2">
                  {routeDecision.chosen_node_id ? (
                    <CheckCircle2 className="w-4 h-4 text-sylion-green" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-sylion-amber" />
                  )}
                  <span className="text-xs font-semibold">
                    {routeDecision.chosen_node_id
                      ? `Wybrany: ${
                          nodes.find((n) => n.node_id === routeDecision.chosen_node_id)
                            ?.name || routeDecision.chosen_node_id
                        }`
                      : "Brak decyzji"}
                  </span>
                  {routeDecision.chosen_model_id && (
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {routeDecision.chosen_model_id}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-1.5">
                  {routeDecision.rationale}
                </p>
              </div>

              {/* Rejected */}
              {routeDecision.rejected.length > 0 && (
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-semibold">Odrzucone nody</h4>
                    <HelpTip text="Lista nodów które zostaćy odrzucone — każdy z reason po polsku (privacy / model / koszt)." />
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {routeDecision.rejected.length}
                    </Badge>
                  </div>
                  <ul className="text-[11px] text-muted-foreground space-y-1">
                    {routeDecision.rejected.map((r, idx) => {
                      const found = nodes.find((n) => n.node_id === r.node_id);
                      return (
                        <li
                          key={`${r.node_id}-${idx}`}
                          className="border-l-2 border-amber-500/40 pl-2"
                        >
                          <span className="font-mono text-foreground">
                            {found?.name || r.node_id}
                          </span>
                          <span className="text-muted-foreground"> — {r.reason}</span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}

              {/* Candidates */}
              {routeDecision.candidates.length > 0 && (
                <div className="text-[11px] text-muted-foreground">
                  Rozpatrzone nody (po privacy filter):{" "}
                  {routeDecision.candidates
                    .map((id) => nodes.find((n) => n.node_id === id)?.name || id)
                    .join(", ")}
                </div>
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
