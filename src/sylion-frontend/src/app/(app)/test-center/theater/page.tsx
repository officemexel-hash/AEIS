"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import {
  Activity, ArrowLeft, Cpu, Shield, Wrench, Wifi, WifiOff,
} from "lucide-react";
import { HelpTip } from "@/components/common/HelpTip";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || (API_BASE ? API_BASE.replace(/^http/, "ws") : "");

function resolveWsUrl(path: string) {
  if (WS_BASE) return `${WS_BASE}${path}`;
  if (typeof window === "undefined") return path;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const localFrontend =
    ["localhost", "127.0.0.1"].includes(window.location.hostname) &&
    window.location.port === "3001";
  const host = localFrontend ? "127.0.0.1:8010" : window.location.host;
  return `${protocol}//${host}${path}`;
}

interface Actor {
  id: string;
  name: string;
  role: string;
  status: string;
  kind: string;
  severity?: string;
  d_level?: string;
}
interface Edge {
  source: string;
  target: string;
  kind: string;
}
interface Topology {
  actors: Actor[];
  edges: Edge[];
  as_of: number;
}
interface GuardianStatus {
  name: string;
  health: string;
  alerts_24h: number;
  last_alert_at: number;
}
interface LocalModel {
  name: string;
  status: string;
  tasks_today: number;
  cost_usd: number;
}

interface Snapshot {
  type: string;
  topology?: Topology;
  guardians?: GuardianStatus[];
  locals?: LocalModel[];
}

const HEALTH_COLOR: Record<string, string> = {
  GREEN: "bg-green-500/15 text-green-700",
  YELLOW: "bg-amber-500/15 text-amber-700",
  RED: "bg-red-500/15 text-red-700",
};

const STATUS_COLOR: Record<string, string> = {
  working: "bg-blue-500/15 text-blue-700",
  idle: "bg-gray-500/15 text-gray-700",
  blocked: "bg-red-500/15 text-red-700",
  open: "bg-blue-500/15 text-blue-700",
  reproduced: "bg-amber-500/15 text-amber-700",
  repairing: "bg-purple-500/15 text-purple-700",
};

// Lay out actors on a circle around the centre. Models occupy the inner
// triangle, tasks/findings the outer ring. Returns absolute SVG coords.
function computeLayout(actors: Actor[], width: number, height: number) {
  const cx = width / 2;
  const cy = height / 2;
  const innerR = Math.min(width, height) * 0.18;
  const outerR = Math.min(width, height) * 0.42;

  const models = actors.filter((a) => a.kind === "model");
  const tasks = actors.filter((a) => a.kind !== "model");

  const positions: Record<string, { x: number; y: number }> = {};
  models.forEach((a, i) => {
    const angle = (i / Math.max(models.length, 1)) * Math.PI * 2 - Math.PI / 2;
    positions[a.id] = {
      x: cx + Math.cos(angle) * innerR,
      y: cy + Math.sin(angle) * innerR,
    };
  });
  tasks.forEach((a, i) => {
    const angle = (i / Math.max(tasks.length, 1)) * Math.PI * 2;
    positions[a.id] = {
      x: cx + Math.cos(angle) * outerR,
      y: cy + Math.sin(angle) * outerR,
    };
  });
  return { positions, cx, cy, innerR, outerR };
}

export default function AgentTheaterPage() {
  const healthStatus = (useHealth().data as { status?: string })?.status;
  const backendChecking = healthStatus === "unknown";
  const backendLive = healthStatus === "ok" || backendChecking;

  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [wsState, setWsState] = useState<
    "connecting" | "open" | "closed" | "error"
  >("closed");
  const [interval, setIntervalSeconds] = useState<number>(2);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadRestSnapshot = async () => {
    if (!backendLive) return;
    try {
      const [topology, guardians, locals] = await Promise.all([
        fetch(`${API_BASE}/api/v1/agent-theater/topology`).then((r) =>
          r.ok ? r.json() : Promise.reject(new Error(`topology ${r.status}`)),
        ),
        fetch(`${API_BASE}/api/v1/agent-theater/guardians`).then((r) =>
          r.ok ? r.json() : Promise.reject(new Error(`guardians ${r.status}`)),
        ),
        fetch(`${API_BASE}/api/v1/agent-theater/locals`).then((r) =>
          r.ok ? r.json() : Promise.reject(new Error(`locals ${r.status}`)),
        ),
      ]);
      setSnapshot({
        type: "snapshot",
        topology: {
          actors: topology.actors ?? [],
          edges: topology.edges ?? [],
          as_of: topology.as_of ?? Date.now() / 1000,
        },
        guardians,
        locals,
      });
    } catch {
      // WebSocket remains the primary channel; REST fallback is best-effort.
    }
  };

  const connect = () => {
    if (!backendLive) return;
    if (reconnectRef.current) {
      clearTimeout(reconnectRef.current);
      reconnectRef.current = null;
    }
    setWsState("connecting");
    try {
      const ws = new WebSocket(resolveWsUrl("/ws/agent-theater"));
      wsRef.current = ws;
      ws.onopen = () => {
        setWsState("open");
        ws.send(
          JSON.stringify({ type: "set_interval", seconds: interval }),
        );
      };
      ws.onmessage = (ev) => {
        try {
          const msg: Snapshot = JSON.parse(ev.data);
          if (msg.type === "snapshot") setSnapshot(msg);
        } catch {
          // ignore
        }
      };
      ws.onclose = () => {
        setWsState("closed");
        void loadRestSnapshot();
        // auto-reconnect after 3s
        reconnectRef.current = setTimeout(connect, 3000);
      };
      ws.onerror = () => {
        setWsState("error");
        void loadRestSnapshot();
      };
    } catch {
      setWsState("error");
      void loadRestSnapshot();
      reconnectRef.current = setTimeout(connect, 3000);
    }
  };

  useEffect(() => {
    connect();
    void loadRestSnapshot();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendLive]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (wsState !== "open" || (snapshot?.topology?.actors.length ?? 0) === 0) {
        void loadRestSnapshot();
      }
    }, interval * 1000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendLive, interval, wsState, snapshot?.topology?.actors.length]);

  // Push interval changes to server
  useEffect(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "set_interval", seconds: interval }));
    }
  }, [interval]);

  const topology = snapshot?.topology || null;
  const guardians = snapshot?.guardians || [];
  const locals = snapshot?.locals || [];

  // SVG layout
  const SVG_W = 720;
  const SVG_H = 480;
  const layout = useMemo(
    () => computeLayout(topology?.actors || [], SVG_W, SVG_H),
    [topology?.actors],
  );

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/test-center"
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Activity className="w-6 h-6" />
            Teatr modeli i agentów
            <HelpTip text="Live-view aktualnej topologii modeli LLM, agentów, otwartych findingów i zadań w systemie. Pokazuje kto z kim pracuje, relacje works_on, status guardów i lokalnych modeli. Aktualizowane co N sekund przez WebSocket." />
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
            {healthStatus === "ok" ? "LIVE" : backendChecking ? "SPRAWDZAM API" : "OFFLINE"}
          </Badge>
          {wsState === "open" ? (
            <Badge
              variant="outline"
              className="text-xs bg-emerald-500/15 text-emerald-700"
            >
              <Wifi className="w-3 h-3 inline mr-1" />
              Strumień WS
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="text-xs bg-amber-500/15 text-amber-700"
            >
              <WifiOff className="w-3 h-3 inline mr-1" />
              {wsState}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs">
          <label className="text-muted-foreground flex items-center" htmlFor="theater-interval">
            interwał
            <HelpTip text="Co ile sekund WebSocket wysyła nowy snapshot topologii. Mniej = świeższe dane, ale więcej ruchu sieciowego i CPU. Domyślnie 2s wystarcza dla większości zastosowań. 1s używaj przy aktywnym debugowaniu, 10s przy samym monitoringu." />
          </label>
          <select
            id="theater-interval"
            value={interval}
            onChange={(e) => setIntervalSeconds(Number(e.target.value))}
            className="text-xs px-2 py-1 border rounded font-mono"
          >
            <option value={1}>1s</option>
            <option value={2}>2s</option>
            <option value={5}>5s</option>
            <option value={10}>10s</option>
          </select>
          <Button
            onClick={() => {
              void loadRestSnapshot();
              connect();
            }}
            disabled={wsState === "connecting"}
            size="sm"
            variant="outline"
          >
            Połącz ponownie
          </Button>
        </div>
      </div>

      {/* Topologia — graf SVG */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="font-semibold flex items-center gap-2">
            <Cpu className="w-4 h-4" />
            Topologia — kto nad czym pracuje
            <HelpTip text="Wizualizacja systemu: pierścień wewnętrzny = modele LLM i role Rady, pierścień zewnętrzny = otwarte findingi i zadania. Krawędzie pokazują relacje works_on. Kolor wskazuje severity, czerwony oznacza P0/P1." />
          </div>
          <Badge variant="outline" className="text-xs">
            {topology?.actors.length || 0} aktorów /{" "}
            {topology?.edges.length || 0} krawędzi
          </Badge>
        </div>

        <div className="overflow-auto">
          <svg
            viewBox={`0 0 ${SVG_W} ${SVG_H}`}
            width={SVG_W}
            height={SVG_H}
            className="bg-muted/30 rounded border"
          >
            {/* concentric guides */}
            <circle
              cx={layout.cx}
              cy={layout.cy}
              r={layout.innerR}
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.08}
              strokeDasharray="4 4"
            />
            <circle
              cx={layout.cx}
              cy={layout.cy}
              r={layout.outerR}
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.08}
              strokeDasharray="4 4"
            />

            {/* edges */}
            {(topology?.edges || []).map((e, i) => {
              const s = layout.positions[e.source];
              const t = layout.positions[e.target];
              if (!s || !t) return null;
              return (
                <line
                  key={`e_${i}`}
                  x1={s.x}
                  y1={s.y}
                  x2={t.x}
                  y2={t.y}
                  stroke="currentColor"
                  strokeOpacity={0.4}
                  strokeWidth={1.5}
                />
              );
            })}

            {/* nodes */}
            {(topology?.actors || []).map((a) => {
              const p = layout.positions[a.id];
              if (!p) return null;
              const isModel = a.kind === "model";
              const r = isModel ? 26 : 16;
              const fill = isModel
                ? "rgba(59,130,246,0.2)"
                : a.severity === "P0" || a.severity === "P1"
                ? "rgba(239,68,68,0.25)"
                : "rgba(168,162,158,0.25)";
              const stroke = isModel
                ? "rgb(59,130,246)"
                : a.severity === "P0" || a.severity === "P1"
                ? "rgb(239,68,68)"
                : "rgb(120,113,108)";
              return (
                <g key={a.id}>
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={r}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={2}
                  />
                  <text
                    x={p.x}
                    y={p.y + (isModel ? 4 : 32)}
                    textAnchor="middle"
                    fontSize={isModel ? 11 : 9}
                    fontFamily="monospace"
                    fill="currentColor"
                  >
                    {(isModel ? a.name : a.id.slice(0, 14)).slice(0, 18)}
                  </text>
                  {isModel && (
                    <text
                      x={p.x}
                      y={p.y + 18}
                      textAnchor="middle"
                      fontSize={8}
                      fontFamily="monospace"
                      fill="currentColor"
                      opacity={0.6}
                    >
                      {a.role}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        <div className="text-xs text-muted-foreground mt-2">
          Pierścień wewnętrzny: modele i agenci · pierścień zewnętrzny: otwarte findingi i zadania · krawędzie:
          relacje works_on
        </div>
      </Card>

      {/* Szczegóły aktorów */}
      <Card className="p-4">
        <div className="font-semibold mb-3 flex items-center">
          Szczegóły aktorów
          <HelpTip text="Lista wszystkich aktorów w topologii (modele, agenci, findingi i zadania) z ich statusem i atrybutami. Dla findingów widać severity P0-P4 i poziom decyzyjny D0-D5." />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {(topology?.actors || []).map((a) => (
            <div key={a.id} className="border rounded p-3 text-sm">
              <div className="flex items-center justify-between">
                <div className="font-mono text-xs truncate" title={a.id}>
                  {a.kind === "model" ? a.name : a.id.slice(0, 30)}
                </div>
                <Badge
                  variant="outline"
                  className={`text-xs ${STATUS_COLOR[a.status] || ""}`}
                >
                  {a.status}
                </Badge>
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                rola: <span className="font-mono">{a.role}</span>
              </div>
              {a.severity && (
                <div className="text-xs mt-1">
                  <Badge variant="outline" className="text-xs">
                    {a.severity}
                  </Badge>
                  <Badge variant="outline" className="text-xs ml-1">
                    {a.d_level}
                  </Badge>
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Guardians */}
      <Card className="p-4">
        <div className="font-semibold flex items-center gap-2 mb-3">
          <Shield className="w-4 h-4" />
          13 strażników
          <HelpTip text="13 wyspecjalizowanych agentów nadzorczych pilnujących różnych aspektów systemu (security, cost, drift, integrity, secrets, etc.). Health: GREEN=OK, YELLOW=ostrzeżenia, RED=alarmy. Liczba alertów w ciągu 24h pokazuje rzeczywistą intensywność." />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {guardians.map((g) => (
            <div
              key={g.name}
              className="flex items-center justify-between text-sm py-1 px-2 rounded border"
            >
              <span className="font-mono text-xs truncate">{g.name}</span>
              <div className="flex items-center gap-2">
                {g.alerts_24h > 0 && (
                  <span className="text-xs text-amber-600">
                    {g.alerts_24h}/24h
                  </span>
                )}
                <Badge
                  variant="outline"
                  className={`text-xs ${HEALTH_COLOR[g.health] || ""}`}
                >
                  {g.health}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Modele lokalne */}
      <Card className="p-4">
        <div className="font-semibold flex items-center gap-2 mb-3">
          <Wrench className="w-4 h-4" />
          Modele lokalne (ollama)
          <HelpTip text="Modele uruchamiane lokalnie przez ollama - bez kosztu API, ale ograniczona moc. Status pokazuje czy aktualnie pracuje (working) czy bezczynny (idle). tasks_today = liczba zadań dzisiaj. Cost_usd zwykle 0 dla lokalnych." />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          {locals.map((m) => (
            <div key={m.name} className="border rounded p-2 text-sm">
              <div className="font-mono text-xs">{m.name}</div>
              <div className="flex items-center justify-between mt-1">
                <Badge
                  variant="outline"
                  className={`text-xs ${STATUS_COLOR[m.status] || ""}`}
                >
                  {m.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {m.tasks_today} zadań
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {topology && (
        <div className="text-xs text-muted-foreground text-right">
          stan na {new Date(topology.as_of * 1000).toLocaleTimeString()}
          {wsState === "open"
            ? ` · push WS co ${interval}s`
            : " · oczekiwanie na WS..."}
        </div>
      )}
    </div>
  );
}
