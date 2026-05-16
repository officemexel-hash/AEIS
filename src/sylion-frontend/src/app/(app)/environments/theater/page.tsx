"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  Cloud,
  Cpu,
  DollarSign,
  GitBranch,
  Layers,
  Network,
  Play,
  RefreshCw,
  RotateCcw,
  Server,
  ShieldCheck,
  SlidersHorizontal,
  Wifi,
  WifiOff,
  Wrench,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HelpTip } from "@/components/common/HelpTip";
import { api } from "@/lib/api/client";
import { cn, fmtDateTime } from "@/lib/utils";

type Actor = {
  id: string;
  name: string;
  role: string;
  kind: string;
  status: string;
  details?: Record<string, any>;
};

type Edge = {
  source: string;
  target: string;
  kind: string;
};

type TheaterSnapshot = {
  type: string;
  as_of: number;
  summary: Record<string, any>;
  topology: {
    actors: Actor[];
    edges: Edge[];
  };
  local_scan?: Record<string, any>;
  acceptance?: {
    hard_blocks?: any[];
    soft_warnings?: any[];
  };
  network?: Record<string, any>;
  costs?: Record<string, any>;
};

type Scenario = {
  id: string;
  label: string;
  description: string;
  topology: string;
  local_workers: number;
  vps_workers: number;
  environments: number;
  max_parallel_workers: number;
  max_monthly_vps_eur: number;
  allow_paid_vps: boolean;
  duration_seconds: number;
  risk: string;
  speed: string;
  cost: string;
};

const SCENARIOS: Scenario[] = [
  {
    id: "slow-local",
    label: "Wolno i tanio",
    description: "Jedno środowisko lokalne, jeden worker, zero płatnego VPS. Dobre do taniej pracy nocnej i walidacji małych zadań.",
    topology: "local-first",
    local_workers: 1,
    vps_workers: 0,
    environments: 1,
    max_parallel_workers: 1,
    max_monthly_vps_eur: 0,
    allow_paid_vps: false,
    duration_seconds: 90,
    risk: "niski",
    speed: "niska",
    cost: "0 EUR VPS",
  },
  {
    id: "balanced-local",
    label: "Zbalansowane lokalnie",
    description: "Dwa do trzech środowisk i umiarkowana równoległość. Domyślny tryb dla testów AEIS bez kosztów chmury.",
    topology: "local-first",
    local_workers: 3,
    vps_workers: 0,
    environments: 3,
    max_parallel_workers: 3,
    max_monthly_vps_eur: 0,
    allow_paid_vps: false,
    duration_seconds: 120,
    risk: "średni",
    speed: "średnia",
    cost: "0 EUR VPS",
  },
  {
    id: "burst-supervised",
    label: "Szybko pod nadzorem",
    description: "Wysoka równoległość lokalna z możliwością przygotowania płatnego VPS, ale bez faktycznego deployu i bez automatycznego wydawania pieniędzy.",
    topology: "hybrid-supervised",
    local_workers: 8,
    vps_workers: 2,
    environments: 5,
    max_parallel_workers: 8,
    max_monthly_vps_eur: 25,
    allow_paid_vps: false,
    duration_seconds: 180,
    risk: "wysoki",
    speed: "wysoka",
    cost: "limit 25 EUR, wymaga Human Gate",
  },
];

const STATUS_CLASS: Record<string, string> = {
  working: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  idle: "border-slate-500/40 bg-slate-500/10 text-slate-200",
  degraded: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  blocked: "border-rose-500/40 bg-rose-500/10 text-rose-200",
};

const KIND_ICON: Record<string, any> = {
  host: Cpu,
  environment: Server,
  provider: Cloud,
  cli: GitBranch,
  port: Activity,
  network: Network,
  cost: DollarSign,
  guard: ShieldCheck,
};

const KIND_LABEL: Record<string, string> = {
  host: "host",
  environment: "środowisko",
  provider: "provider",
  cli: "CLI",
  port: "port",
  network: "sieć",
  cost: "koszt",
  guard: "guard",
};

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    working: "pracuje",
    idle: "gotowe",
    degraded: "uwaga",
    blocked: "blokada",
    configured: "skonfigurowane",
  };
  return labels[status] ?? status;
}

function edgeLabel(kind: string) {
  const labels: Record<string, string> = {
    listens_on: "nasłuchuje",
    tool_detected: "wykryto CLI",
    runs_environment: "uruchamia",
    provisions: "provisionuje",
    uses_network_policy: "polityka sieci",
    reports_cost: "raport kosztu",
    guards: "pilnuje",
  };
  return labels[kind] ?? kind.replaceAll("_", " ");
}

function formatMoney(summary: Record<string, any>) {
  const usd = Number(summary.monthly_cost_usd || 0);
  const eur = Number(summary.monthly_cost_eur || 0);
  if (eur > 0) return `${eur.toFixed(2)} EUR`;
  return `${usd.toFixed(2)} USD`;
}

function formatFinding(item: any) {
  if (typeof item === "string") return item.replaceAll("_", " ");
  if (!item || typeof item !== "object") return String(item ?? "");
  const code = item.code || item.id || item.kind || item.type || "finding";
  const message = item.message || item.reason || item.description || item.title || "";
  const detail = item.detail || item.status || item.value || "";
  return [code, message, detail].filter(Boolean).join(" - ").replaceAll("_", " ");
}

function actorPosition(actor: Actor, actors: Actor[], width: number, height: number) {
  const cx = width / 2;
  const cy = height / 2;
  const ring = actor.kind === "host" ? 0 : actor.kind === "environment" ? 1 : 2;
  if (ring === 0) return { x: cx, y: cy };
  const ringActors = actors.filter((item) => (item.kind === "environment" ? 1 : item.kind === "host" ? 0 : 2) === ring);
  const ringIndex = ringActors.findIndex((item) => item.id === actor.id);
  const count = Math.max(ringActors.length, 1);
  const radius = ring === 1 ? Math.min(width, height) * 0.26 : Math.min(width, height) * 0.42;
  const angle = (ringIndex / count) * Math.PI * 2 - Math.PI / 2;
  return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
}

function TopologyGraph({ actors, edges }: { actors: Actor[]; edges: Edge[] }) {
  const width = 900;
  const height = 520;
  const positions = useMemo(() => {
    const map: Record<string, { x: number; y: number }> = {};
    actors.forEach((actor) => {
      map[actor.id] = actorPosition(actor, actors, width, height);
    });
    return map;
  }, [actors]);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="min-h-[420px] w-full">
      <circle cx={width / 2} cy={height / 2} r={Math.min(width, height) * 0.26} className="fill-none stroke-primary/10" />
      <circle cx={width / 2} cy={height / 2} r={Math.min(width, height) * 0.42} className="fill-none stroke-primary/10" />
      {edges.map((edge, index) => {
        const source = positions[edge.source];
        const target = positions[edge.target];
        if (!source || !target) return null;
        return (
          <g key={`${edge.source}-${edge.target}-${edge.kind}-${index}`}>
            <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} className="stroke-primary/25" strokeWidth="1.5" />
            <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 4} textAnchor="middle" className="fill-muted-foreground text-[9px]">
              {edgeLabel(edge.kind)}
            </text>
          </g>
        );
      })}
      {actors.map((actor) => {
        const pos = positions[actor.id];
        const Icon = KIND_ICON[actor.kind] ?? Activity;
        const blocked = actor.status === "blocked";
        const degraded = actor.status === "degraded";
        const fill = blocked ? "#7f1d1d" : degraded ? "#78350f" : actor.kind === "host" ? "#1d4ed8" : "#0f172a";
        const stroke = blocked ? "#fb7185" : degraded ? "#fbbf24" : "#60a5fa";
        return (
          <g key={actor.id}>
            <circle cx={pos.x} cy={pos.y} r="36" fill={fill} stroke={stroke} strokeWidth="2" />
            <foreignObject x={pos.x - 12} y={pos.y - 30} width="24" height="24">
              <Icon className="h-6 w-6 text-white" />
            </foreignObject>
            <text x={pos.x} y={pos.y + 8} textAnchor="middle" className="fill-white text-[10px] font-semibold">
              {actor.name.length > 18 ? `${actor.name.slice(0, 17)}...` : actor.name}
            </text>
            <text x={pos.x} y={pos.y + 23} textAnchor="middle" className="fill-slate-300 text-[9px]">
              {statusLabel(actor.status)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="border-sylion-border bg-card p-4">
      <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </Card>
  );
}

export default function EnvironmentTheaterPage() {
  const [snapshot, setSnapshot] = useState<TheaterSnapshot | null>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [selectedScenarioId, setSelectedScenarioId] = useState("balanced-local");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [interval, setIntervalSeconds] = useState(3);
  const [autoScan, setAutoScan] = useState(true);
  const [actionLog, setActionLog] = useState<string[]>([]);
  const [diagnostic, setDiagnostic] = useState<any | null>(null);
  const [acceptance, setAcceptance] = useState<any | null>(null);
  const [cleanupPlan, setCleanupPlan] = useState<any | null>(null);

  const selectedScenario = SCENARIOS.find((item) => item.id === selectedScenarioId) ?? SCENARIOS[1];

  const addLog = useCallback((message: string) => {
    setActionLog((prev) => [`${new Date().toLocaleTimeString("pl-PL")} - ${message}`, ...prev].slice(0, 12));
  }, []);

  const load = useCallback(async () => {
    try {
      setError("");
      const [theater, projectRows] = await Promise.all([
        api.getEnvironmentTheater(autoScan),
        api.listProjectStartProjects().catch(() => ({ projects: [] })),
      ]);
      const rows = Array.isArray(projectRows.projects) ? projectRows.projects : [];
      setSnapshot(theater);
      setProjects(rows);
      if (!selectedProjectId && rows[0]?.project_id) setSelectedProjectId(rows[0].project_id);
    } catch (err: any) {
      setError(err?.message || "Nie udało się pobrać teatru środowisk.");
    } finally {
      setLoading(false);
    }
  }, [autoScan, selectedProjectId]);

  useEffect(() => {
    const initial = window.setTimeout(() => void load(), 0);
    const timer = window.setInterval(() => void load(), interval * 1000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [interval, load]);

  const runAction = async (name: string, fn: () => Promise<any>, success: string) => {
    setBusy(name);
    setError("");
    try {
      const result = await fn();
      addLog(success);
      await load();
      return result;
    } catch (err: any) {
      const message = err?.message || String(err);
      setError(message);
      addLog(`Błąd: ${message}`);
      return null;
    } finally {
      setBusy("");
    }
  };

  const scanLocal = () =>
    runAction(
      "scan",
      () => api.scanLocalEnvironment({ auto_create_local_dev: true, deep_scan: true }),
      "Wykonano głęboki skan lokalnego hosta i odświeżono katalog środowisk.",
    );

  const acceptLocal = () =>
    runAction(
      "accept",
      () => api.acceptLocalDevEnvironment({ display_name: "Lokalne środowisko developerskie AEIS", purpose: "development", notes: "Zatwierdzone z teatru środowisk." }),
      "Lokalne środowisko developerskie zatwierdzone przez operatora.",
    );

  const addProviders = () =>
    runAction(
      "providers",
      () => api.addDetectedEnvironmentProviders(),
      "Dodano wykrytych providerów CLI do katalogu, jeśli byli dostępni.",
    );

  const runDiagnostic = async () => {
    const result = await runAction(
      "diagnostic",
      () => api.runEnvironmentNetworkDiagnostic({ environment_id: "" }),
      "Diagnostyka sieci środowisk zakończona.",
    );
    if (result) setDiagnostic(result);
  };

  const runAcceptance = async () => {
    const result = await runAction(
      "acceptance",
      () => api.runEnvironmentAcceptanceTest("apps_internal"),
      "Acceptance test W5 środowisk zakończony.",
    );
    if (result) setAcceptance(result);
  };

  const buildCleanupPlan = async () => {
    const result = await runAction(
      "cleanup",
      () => api.createEnvironmentBulkCleanupPlan({ inactive_days: 14, purposes: ["development", "staging"], include_tags: [], exclude_tags: ["protected"] }),
      "Utworzono bezpieczny plan sprzątania środowisk w trybie plan-only.",
    );
    if (result) setCleanupPlan(result);
  };

  const createEdgeLab = () =>
    runAction(
      "edge",
      () => api.createEdgeEnvironmentDevice({
        display_name: `AEIS Edge Lab ${Date.now().toString().slice(-4)}`,
        owner: "operator",
        location: "local lab",
        device_type: "mini_pc",
        architecture: "x86_64",
        ram_gb: 16,
        storage_gb: 256,
        pairing_method: "ssh",
        hostname: "edge-lab.local",
        ssh_port: 22,
        ssh_username: "aeis",
        capabilities: ["linux", "ssh", "docker", "local-runtime"],
        auto_update_policy: "manual",
        sync_strategy: "pull",
      }),
      "Dodano przykładowe środowisko edge lab do katalogu.",
    );

  const applyScenario = () =>
    runAction(
      "scenario",
      async () => {
        if (!selectedProjectId) throw new Error("Najpierw wybierz projekt.");
        return api.updateExecutionRuntimeConfiguration(selectedProjectId, {
          operator_id: "operator",
          approved: true,
          notes: `Konfiguracja z teatru środowisk: ${selectedScenario.label}`,
          topology: selectedScenario.topology,
          local_workers: selectedScenario.local_workers,
          vps_workers: selectedScenario.vps_workers,
          environments: selectedScenario.environments,
          max_parallel_workers: selectedScenario.max_parallel_workers,
          max_monthly_vps_eur: selectedScenario.max_monthly_vps_eur,
          allow_paid_vps: selectedScenario.allow_paid_vps,
          apply_to_next_build: true,
        });
      },
      `Zapisano konfigurację runtime projektu: ${selectedScenario.label}.`,
    );

  const spawnSmokeWorkers = () =>
    runAction(
      "workers",
      async () => {
        if (!selectedProjectId) throw new Error("Najpierw wybierz projekt.");
        return api.liveSpawnExecutionWorkers(selectedProjectId, {
          operator_id: "operator",
          approved: true,
          notes: `Test dymny środowisk: ${selectedScenario.label}`,
          workers_limit: Math.min(selectedScenario.local_workers, 8),
          duration_seconds: selectedScenario.duration_seconds,
          mode: "environment-theater-smoke",
          allow_docker_run: false,
        });
      },
      "Uruchomiono kontrolowany test dymny workerów bez Docker run i bez VPS deploy.",
    );

  const stopSmokeWorkers = () =>
    runAction(
      "stop-workers",
      async () => {
        if (!selectedProjectId) throw new Error("Najpierw wybierz projekt.");
        return api.stopExecutionLiveWorkers(selectedProjectId, { operator_id: "operator", approved: true, notes: "Stop z teatru środowisk." });
      },
      "Zatrzymano live workerów dla wybranego projektu.",
    );

  const actors = snapshot?.topology?.actors ?? [];
  const edges = snapshot?.topology?.edges ?? [];
  const summary = snapshot?.summary ?? {};
  const environments = actors.filter((actor) => actor.kind === "environment");
  const providers = actors.filter((actor) => actor.kind === "provider" || actor.kind === "cli");
  const hardBlocks = snapshot?.acceptance?.hard_blocks ?? [];
  const warnings = snapshot?.acceptance?.soft_warnings ?? [];
  const timeline = [
    { label: "Skan hosta", status: snapshot?.local_scan ? "gotowe" : "oczekuje", detail: "porty, CLI, Docker, Ollama, zasoby lokalne" },
    { label: "Katalog środowisk", status: environments.length > 0 ? "gotowe" : "oczekuje", detail: `${environments.length} środowisk w topologii` },
    { label: "Providerzy", status: providers.length > 0 ? "gotowe" : "uwaga", detail: `${providers.length} kont i narzędzi CLI` },
    { label: "Human Gate", status: hardBlocks.length > 0 ? "blokada" : "gotowe", detail: hardBlocks.length ? `${hardBlocks.length} blokad` : "brak twardych blokad" },
    { label: "Test runtime", status: diagnostic || acceptance ? "gotowe" : "oczekuje", detail: "diagnostyka, acceptance, test workerów" },
  ];

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex items-start gap-3">
          <Link href="/environments" className="mt-2 text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold">
              <Network className="h-6 w-6" />
              Teatr środowisk
              <HelpTip text="Live-view pracy środowisk AEIS: host lokalny, porty, providerzy, CLI, środowiska, sieć, koszt i Human Gate runtime. Panel pozwala symulować wariant wolno/tanio, zbalansowany i szybki pod nadzorem bez produkcyjnego deployu." />
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              W5 runtime: środowiska, providerzy, porty, workerzy, koszt, Human Gate i scenariusze wykonania projektu.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={cn("text-xs", error ? "border-rose-500/40 text-rose-200" : "border-emerald-500/40 text-emerald-200")}>
            {error ? <WifiOff className="mr-1 h-3 w-3" /> : <Wifi className="mr-1 h-3 w-3" />}
            {error ? "OFFLINE" : "LIVE POLLING"}
          </Badge>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            interwał
            <select value={interval} onChange={(event) => setIntervalSeconds(Number(event.target.value))} className="rounded-md border border-sylion-border bg-background px-2 py-1 text-xs">
              <option value={1}>1s</option>
              <option value={3}>3s</option>
              <option value={5}>5s</option>
              <option value={10}>10s</option>
            </select>
          </label>
          <label className="flex items-center gap-2 rounded-md border border-sylion-border px-2 py-1 text-xs text-muted-foreground">
            <input type="checkbox" checked={autoScan} onChange={(event) => setAutoScan(event.target.checked)} />
            auto-skan
          </label>
          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={cn("mr-1 h-3.5 w-3.5", loading && "animate-spin")} />
            Odśwież
          </Button>
        </div>
      </div>

      {error && <Card className="border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">{error}</Card>}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <Metric label="Środowiska" value={summary.active_environments ?? environments.length} />
        <Metric label="Aktorzy" value={summary.actor_count ?? actors.length} />
        <Metric label="Relacje" value={summary.edge_count ?? edges.length} />
        <Metric label="Zajęte porty" value={summary.busy_ports ?? 0} />
        <Metric label="Koszt miesięczny" value={formatMoney(summary)} />
      </div>

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="font-semibold">Topologia pracy środowisk</div>
            <Badge variant="outline" className="text-[10px]">
              {snapshot?.as_of ? fmtDateTime(snapshot.as_of * 1000) : "ładowanie"}
            </Badge>
          </div>
          <TopologyGraph actors={actors} edges={edges} />
          <div className="mt-2 text-xs text-muted-foreground">
            Środek: host lokalny. Pierścień wewnętrzny: środowiska. Pierścień zewnętrzny: providerzy, CLI, porty, sieć, koszt i bramki.
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 font-semibold">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            Sterowanie scenariuszem
          </div>
          <label className="grid gap-1 text-xs text-muted-foreground">
            Projekt
            <select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)} className="h-9 rounded-md border border-sylion-border bg-background px-2 text-xs">
              <option value="">Wybierz projekt</option>
              {projects.slice(0, 30).map((project) => (
                <option key={project.project_id} value={project.project_id}>
                  {project.name || project.project_id}
                </option>
              ))}
            </select>
          </label>

          <div className="mt-4 grid gap-2">
            {SCENARIOS.map((scenario) => (
              <button
                key={scenario.id}
                type="button"
                onClick={() => setSelectedScenarioId(scenario.id)}
                className={cn(
                  "rounded-lg border p-3 text-left transition-colors hover:border-primary/50",
                  selectedScenarioId === scenario.id ? "border-primary/60 bg-primary/10" : "border-sylion-border bg-background",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold">{scenario.label}</span>
                  <Badge variant="outline" className="text-[9px]">{scenario.speed}</Badge>
                </div>
                <p className="mt-1 text-[10px] text-muted-foreground">{scenario.description}</p>
                <div className="mt-2 grid grid-cols-3 gap-1 text-[10px] text-muted-foreground">
                  <span>{scenario.local_workers} local</span>
                  <span>{scenario.environments} env</span>
                  <span>{scenario.cost}</span>
                </div>
              </button>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2">
            <Button size="sm" className="h-8 text-xs" onClick={() => void applyScenario()} disabled={busy === "scenario" || !selectedProjectId}>
              <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
              Zastosuj
            </Button>
            <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => void spawnSmokeWorkers()} disabled={busy === "workers" || !selectedProjectId}>
              <Play className="mr-1 h-3.5 w-3.5" />
              Test workerów
            </Button>
            <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => void stopSmokeWorkers()} disabled={busy === "stop-workers" || !selectedProjectId}>
              <RotateCcw className="mr-1 h-3.5 w-3.5" />
              Stop
            </Button>
            <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => void runAcceptance()} disabled={busy === "acceptance"}>
              <ShieldCheck className="mr-1 h-3.5 w-3.5" />
              W5 test
            </Button>
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="border-sylion-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 font-semibold">
            <Layers className="h-4 w-4 text-primary" />
            Oś pracy środowisk
          </div>
          <div className="space-y-3">
            {timeline.map((item, index) => (
              <div key={item.label} className="grid grid-cols-[28px_1fr] gap-3">
                <div className="flex flex-col items-center">
                  <div className={cn("flex h-7 w-7 items-center justify-center rounded-full border text-[10px]", item.status === "blokada" ? "border-rose-500/40 text-rose-200" : item.status === "uwaga" ? "border-amber-500/40 text-amber-200" : "border-emerald-500/40 text-emerald-200")}>
                    {index + 1}
                  </div>
                  {index < timeline.length - 1 && <div className="h-8 w-px bg-sylion-border" />}
                </div>
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs font-semibold">{item.label}</div>
                    <Badge variant="outline" className="text-[9px]">{item.status}</Badge>
                  </div>
                  <div className="mt-1 text-[10px] text-muted-foreground">{item.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 font-semibold">
            <Wrench className="h-4 w-4 text-primary" />
            Akcje bezpieczne
          </div>
          <div className="grid gap-2">
            <Button variant="outline" size="sm" className="h-8 justify-start text-xs" onClick={() => void scanLocal()} disabled={busy === "scan"}>
              <RefreshCw className="mr-2 h-3.5 w-3.5" />
              Głęboki skan lokalny
            </Button>
            <Button variant="outline" size="sm" className="h-8 justify-start text-xs" onClick={() => void acceptLocal()} disabled={busy === "accept"}>
              <CheckCircle2 className="mr-2 h-3.5 w-3.5" />
              Zatwierdź local dev
            </Button>
            <Button variant="outline" size="sm" className="h-8 justify-start text-xs" onClick={() => void addProviders()} disabled={busy === "providers"}>
              <Cloud className="mr-2 h-3.5 w-3.5" />
              Dodaj wykrytych providerów
            </Button>
            <Button variant="outline" size="sm" className="h-8 justify-start text-xs" onClick={() => void runDiagnostic()} disabled={busy === "diagnostic"}>
              <Network className="mr-2 h-3.5 w-3.5" />
              Diagnostyka sieci
            </Button>
            <Button variant="outline" size="sm" className="h-8 justify-start text-xs" onClick={() => void buildCleanupPlan()} disabled={busy === "cleanup"}>
              <DollarSign className="mr-2 h-3.5 w-3.5" />
              Plan sprzątania kosztów
            </Button>
            <Button variant="outline" size="sm" className="h-8 justify-start text-xs" onClick={() => void createEdgeLab()} disabled={busy === "edge"}>
              <Cpu className="mr-2 h-3.5 w-3.5" />
              Dodaj edge lab
            </Button>
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 font-semibold">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Blokady i ostrzeżenia
          </div>
          <div className="space-y-2">
            {hardBlocks.length === 0 && warnings.length === 0 ? (
              <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-200">
                Brak blokad środowiskowych.
              </div>
            ) : (
              [...hardBlocks.map((item) => ({ item, level: "blokada" })), ...warnings.map((item) => ({ item, level: "uwaga" }))].map((entry, index) => (
                <div key={`${entry.level}-${index}`} className="rounded-md border border-sylion-border bg-background p-3 text-xs">
                  <Badge variant="outline" className={cn("mb-2 text-[9px]", entry.level === "blokada" ? "border-rose-500/40 text-rose-200" : "border-amber-500/40 text-amber-200")}>
                    {entry.level}
                  </Badge>
                  <div className="text-muted-foreground">{formatFinding(entry.item)}</div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card className="border-sylion-border bg-card p-4">
          <div className="mb-3 font-semibold">Macierz aktorów runtime</div>
          <div className="grid gap-2 md:grid-cols-2">
            {actors.map((actor) => {
              const Icon = KIND_ICON[actor.kind] ?? Activity;
              return (
                <div key={actor.id} className="rounded-md border border-sylion-border bg-background p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex min-w-0 items-start gap-2">
                      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <div className="min-w-0">
                        <div className="truncate text-xs font-semibold">{actor.name}</div>
                        <div className="text-[10px] text-muted-foreground">{KIND_LABEL[actor.kind] ?? actor.kind} / {actor.role}</div>
                      </div>
                    </div>
                    <Badge variant="outline" className={cn("text-[9px]", STATUS_CLASS[actor.status] ?? STATUS_CLASS.idle)}>
                      {statusLabel(actor.status)}
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2 font-semibold">
            <Zap className="h-4 w-4 text-primary" />
            Wyniki testów i log operatora
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="space-y-2">
              <div className="rounded-md border border-sylion-border bg-background p-3">
                <div className="text-[10px] uppercase text-muted-foreground">Diagnostyka sieci</div>
                <div className="mt-2 text-xs">{diagnostic ? `${diagnostic.diagnostics?.length ?? 0} sprawdzeń` : "nie uruchomiono w tej sesji"}</div>
              </div>
              <div className="rounded-md border border-sylion-border bg-background p-3">
                <div className="text-[10px] uppercase text-muted-foreground">Acceptance W5</div>
                <div className="mt-2 text-xs">{acceptance ? (acceptance.status || acceptance.result || "zakończony") : "nie uruchomiono w tej sesji"}</div>
              </div>
              <div className="rounded-md border border-sylion-border bg-background p-3">
                <div className="text-[10px] uppercase text-muted-foreground">Plan cleanup</div>
                <div className="mt-2 text-xs">{cleanupPlan?.plan ? `${cleanupPlan.plan.candidates?.length ?? 0} kandydatów, oszczędność ${cleanupPlan.plan.estimated_monthly_savings_usd ?? 0} USD` : "brak planu"}</div>
              </div>
            </div>
            <div className="rounded-md border border-sylion-border bg-background p-3">
              <div className="mb-2 text-[10px] uppercase text-muted-foreground">Ostatnie akcje</div>
              <div className="space-y-2 text-[10px] text-muted-foreground">
                {actionLog.length === 0 ? <div>Brak akcji w tej sesji.</div> : actionLog.map((item) => <div key={item}>{item}</div>)}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
