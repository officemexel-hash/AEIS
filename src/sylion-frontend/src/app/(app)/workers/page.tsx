"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

import { useWorkers, useTopologies, useHealth } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn, fmtDateTime } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Server, Plus, Activity, Zap, AlertTriangle,
  Clock, Cpu, HardDrive, RefreshCw, ArrowRight, X,
  Globe, Layers, Loader2, Folder, Users,
} from "lucide-react";

/* ============================================================ */

const getErrorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "Unexpected worker fleet API error";

export default function WorkersPage() {
  const { data: health } = useHealth();
  const {
    data: workersData,
    loading: workersLoading,
    error: workersError,
    refresh: refreshWorkers,
  } = useWorkers();
  const {
    data: topologiesData,
    loading: topologiesLoading,
    error: topologiesError,
    refresh: refreshTopologies,
  } = useTopologies();

  const workers = Array.isArray(workersData?.workers) ? workersData.workers : [];
  const topologies = Array.isArray(topologiesData?.topologies) ? topologiesData.topologies : [];
  const backendLive = health?.status === "ok";

  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);
  const [showRegister, setShowRegister] = useState(false);
  const [registerForm, setRegisterForm] = useState({ name: "", host: "localhost", capacity: "3", tags: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // FE-9.3 — Workers per-project view
  const [viewMode, setViewMode] = useState<"all" | "per-project">("all");
  const [projects, setProjects] = useState<Array<{ project_id: string; title?: string; name?: string; status?: string }>>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [projectsError, setProjectsError] = useState<string | null>(null);

  useEffect(() => {
    if (viewMode !== "per-project" || !backendLive) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await api.listProjects();
        if (cancelled) return;
        const list = Array.isArray(data?.projects) ? data.projects : Array.isArray(data) ? data : [];
        setProjects(list);
        if (list.length > 0 && !selectedProjectId) {
          setSelectedProjectId(list[0].project_id);
        }
        setProjectsError(null);
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "Nie udało się pobrać listy projektów";
        setProjectsError(msg.includes("404") ? "Endpoint /api/v1/projects nie odpowiada" : msg);
      }
    })();
    return () => { cancelled = true; };
  }, [viewMode, backendLive, selectedProjectId]);

  // FE-9.3 — workers assigned to selected project (best-effort filter on tags / project_id field)
  const projectWorkers = useMemo(() => {
    if (!selectedProjectId) return [] as any[];
    return workers.filter((w: any) => {
      if (w.project_id === selectedProjectId) return true;
      if (Array.isArray(w.tags) && w.tags.includes(`project:${selectedProjectId}`)) return true;
      if (Array.isArray(w.assigned_projects) && w.assigned_projects.includes(selectedProjectId)) return true;
      return false;
    });
  }, [workers, selectedProjectId]);

  const surfaceLoading = workersLoading && topologiesLoading && workers.length === 0 && topologies.length === 0;
  const isRefreshing = busy === "refresh";

  const stats = useMemo(() => {
    const active = workers.filter((w: any) => w.status === "active").length;
    const offline = workers.filter((w: any) => w.status === "offline").length;
    const totalCap = workers.reduce((s: number, w: any) => s + (w.capacity || 0), 0);
    const totalLoad = workers.reduce((s: number, w: any) => s + (w.assigned_modules?.length || 0), 0);
    return { active, offline, totalCap, totalLoad, count: workers.length };
  }, [workers]);

  const selectedWorker = useMemo(() =>
    workers.find((w: any) => w.worker_id === selectedWorkerId) || null
  , [workers, selectedWorkerId]);

  const handleRefresh = useCallback(() => {
    setActionError(null);
    setBusy("refresh");
    refreshWorkers();
    refreshTopologies();
    window.setTimeout(() => {
      setBusy((current) => (current === "refresh" ? null : current));
    }, 600);
  }, [refreshTopologies, refreshWorkers]);

  const handleRegister = useCallback(async () => {
    if (!registerForm.name.trim()) return;
    setActionError(null);
    setBusy("register");
    try {
      await api.registerWorker({
        name: registerForm.name,
        host: registerForm.host || "localhost",
        capacity: parseInt(registerForm.capacity) || 3,
        tags: registerForm.tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      setRegisterForm({ name: "", host: "localhost", capacity: "3", tags: "" });
      setShowRegister(false);
      refreshWorkers();
    } catch (e) {
      setActionError(getErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }, [registerForm, refreshWorkers]);

  const handleHeartbeat = useCallback(async (id: string) => {
    setActionError(null);
    setBusy(`hb-${id}`);
    try {
      await api.heartbeatWorker(id);
      refreshWorkers();
    } catch (e) {
      setActionError(getErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }, [refreshWorkers]);

  const handleDelete = useCallback(async (id: string) => {
    if (!confirm("Usunąć tego wykonawcę?")) return;
    setActionError(null);
    setBusy(`del-${id}`);
    try {
      await api.deleteWorker(id);
      setSelectedWorkerId(null);
      refreshWorkers();
    } catch (e) {
      setActionError(getErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }, [refreshWorkers]);

  const handleRebalance = useCallback(async () => {
    setActionError(null);
    setBusy("rebalance");
    try {
      await api.rebalanceAssignments();
      refreshWorkers();
      refreshTopologies();
    } catch (e) {
      setActionError(getErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }, [refreshTopologies, refreshWorkers]);

  const statusColor = (s: string) => {
    if (s === "active") return "bg-sylion-green/15 text-sylion-green border-sylion-green/20";
    if (s === "offline") return "bg-sylion-red/15 text-sylion-red border-sylion-red/20";
    if (s === "draining") return "bg-sylion-amber/15 text-sylion-amber border-sylion-amber/20";
    return "bg-muted text-muted-foreground border-muted";
  };

  const loadPct = (w: any) => {
    const cap = w.capacity || 1;
    const load = w.assigned_modules?.length || 0;
    return Math.min(100, Math.round((load / cap) * 100));
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
            <Server className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Flota wykonawców
              <HelpTip text="Pula procesów wykonujących zadania (kompilacja, deploy, testy, code-gen). Autoskalowanie; każdy wykonawca ma role + limit zadań + budżet czasowy. Topologia widoczna poniżej." />
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Rozproszona orkiestracja buildów — wykonawcy, przydziały i topologia
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {backendLive && (
            <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green">
              <span className="w-1.5 h-1.5 rounded-full bg-sylion-green mr-1.5 pulse-glow-green" />
              NA ŻYWO
            </Badge>
          )}
          <Button size="sm" variant="outline" onClick={handleRefresh} disabled={!!busy}>
            {isRefreshing ? (
              <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5 mr-1" />
            )}
            Odśwież
          </Button>
          <Button size="sm" variant="outline" onClick={() => setShowRegister((s) => !s)}>
            <Plus className="w-3.5 h-3.5 mr-1" />
            Zarejestruj wykonawcę
          </Button>
          <Button size="sm" variant="outline" onClick={handleRebalance} disabled={!!busy}>
            <RefreshCw className={cn("w-3.5 h-3.5 mr-1", busy === "rebalance" && "animate-spin")} />
            Rebalansuj
          </Button>
        </div>
      </div>

      {actionError && (
        <Card className="border-sylion-red/20 bg-sylion-red/5 p-4" aria-live="polite">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 text-sylion-red" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-sylion-red">Operacja wykonawcy nieudana</p>
              <p className="text-sm text-muted-foreground">{actionError}</p>
            </div>
          </div>
        </Card>
      )}

      {surfaceLoading && (
        <Card className="border-sylion-border p-6" aria-live="polite">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Ładowanie floty wykonawców...
          </div>
        </Card>
      )}

      {!surfaceLoading && workersError && workers.length === 0 && (
        <Card className="border-sylion-red/20 bg-sylion-red/5 p-5" aria-live="polite">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium text-sylion-red">Flota wykonawców niedostępna</p>
              <p className="text-sm text-muted-foreground">{workersError}</p>
            </div>
            <Button size="sm" variant="outline" onClick={handleRefresh} disabled={!!busy}>
              Ponów
            </Button>
          </div>
        </Card>
      )}

      {/* Register form */}
      <AnimatePresence>
        {showRegister && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <Card className="p-4 bg-card border-sylion-border">
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="text-[10px] text-muted-foreground mb-1 block">
                    Nazwa wykonawcy
                    <HelpTip text="Czytelna nazwa wykonawcy (np. build-worker-01). Używana w widokach operatora i logach." />
                  </label>
                  <input placeholder="Nazwa wykonawcy" value={registerForm.name} onChange={(e) => setRegisterForm((f) => ({ ...f, name: e.target.value }))} className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50" />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground mb-1 block">
                    Host
                    <HelpTip text="Hostname lub adres IP, na którym działa wykonawca. Domyślnie localhost — dla worker'ów rozproszonych podaj VPS / DNS." />
                  </label>
                  <input placeholder="Host" value={registerForm.host} onChange={(e) => setRegisterForm((f) => ({ ...f, host: e.target.value }))} className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50" />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground mb-1 block">
                    Pojemność
                    <HelpTip text="Maksymalna liczba zadań współbieżnych dla tego wykonawcy. Zacznij od 3 i skaluj zależnie od CPU/RAM." />
                  </label>
                  <input placeholder="Pojemność" type="number" value={registerForm.capacity} onChange={(e) => setRegisterForm((f) => ({ ...f, capacity: e.target.value }))} className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50" />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground mb-1 block">
                    Tagi (oddzielone przecinkami)
                    <HelpTip text="Etykiety routingu — np. 'gpu', 'docker', 'fast'. Scheduler kieruje zadania do wykonawców z pasującymi tagami." />
                  </label>
                  <input placeholder="Tagi (oddzielone przecinkami)" value={registerForm.tags} onChange={(e) => setRegisterForm((f) => ({ ...f, tags: e.target.value }))} className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50" />
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-3">
                <Button size="sm" variant="ghost" onClick={() => setShowRegister(false)}><X className="w-3.5 h-3.5 mr-1" /> Anuluj</Button>
                <Button size="sm" onClick={handleRegister} disabled={!!busy || !registerForm.name.trim()}>
                  <Plus className="w-3.5 h-3.5 mr-1" /> Zarejestruj
                </Button>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-3">
        <Card className="p-4 bg-card border-sylion-border"><p className="text-[10px] text-muted-foreground uppercase tracking-wider">Wykonawcy<HelpTip text="Łączna liczba zarejestrowanych wykonawców (online + offline)." /></p><p className="text-2xl font-semibold mt-1">{stats.count}</p></Card>
        <Card className="p-4 bg-card border-sylion-border"><p className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1"><Activity className="w-3 h-3 text-sylion-green" /> Aktywni<HelpTip text="Wykonawcy aktualnie odpowiadający na heartbeat. Mogą przyjmować zadania." /></p><p className="text-2xl font-semibold mt-1 text-sylion-green">{stats.active}</p></Card>
        <Card className="p-4 bg-card border-sylion-border"><p className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-sylion-red" /> Offline<HelpTip text="Wykonawcy bez ostatniego heartbeatu. Nie otrzymują nowych zadań — zaplanuj diagnozę." /></p><p className="text-2xl font-semibold mt-1 text-sylion-red">{stats.offline}</p></Card>
        <Card className="p-4 bg-card border-sylion-border"><p className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1"><Cpu className="w-3 h-3 text-sylion-blue" /> Pojemność<HelpTip text="Łączna pojemność (równoległe zadania) wszystkich wykonawców. Limit górny dla schedulera." /></p><p className="text-2xl font-semibold mt-1 text-sylion-blue">{stats.totalCap}</p></Card>
        <Card className="p-4 bg-card border-sylion-border"><p className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center gap-1"><Zap className="w-3 h-3 text-sylion-amber" /> Obciążenie<HelpTip text="Aktualnie wykonywane zadania / pojemność. Wartości >80% sygnalizują, że warto dorzucić wykonawców." /></p><p className="text-2xl font-semibold mt-1">{stats.totalLoad} <span className="text-xs text-muted-foreground">/ {stats.totalCap}</span></p></Card>
      </div>

      {/* FE-9.3 — view mode tabs */}
      <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as "all" | "per-project")}>
        <div className="flex items-center gap-2">
          <TabsList data-testid="workers-view-tabs">
            <TabsTrigger value="all" className="text-xs" data-testid="workers-tab-all">
              <Users className="w-3 h-3" />
              Wszyscy wykonawcy
            </TabsTrigger>
            <TabsTrigger value="per-project" className="text-xs" data-testid="workers-tab-per-project">
              <Folder className="w-3 h-3" />
              Per projekt
            </TabsTrigger>
          </TabsList>
          <HelpTip text="Wszyscy: globalna pula wykonawcow. Per projekt: wykonawcy przypisani do wybranego projektu — konfiguracja w panelu /projects/{id}/orchestration > Dispatch Agent?w." />
        </div>
        <TabsContent value="per-project" className="mt-4 space-y-3" data-testid="workers-per-project-panel">
          <Card className="p-4 bg-card border-sylion-border">
            <div className="flex items-center gap-3">
              <label className="text-[10px] text-muted-foreground">
                Projekt
                <HelpTip text="Wybierz projekt aby zobaczyć liste wykonawcow przypisanych. Lista projektów jest pobierana z /api/v1/projects." />
              </label>
              <select
                data-testid="workers-project-selector"
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="flex h-9 min-w-[280px] rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                disabled={projects.length === 0}
              >
                {projects.length === 0 ? (
                  <option value="">{projectsError || "Brak projektów"}</option>
                ) : (
                  projects.map((p) => (
                    <option key={p.project_id} value={p.project_id}>
                      {p.title || p.name || p.project_id}
                      {p.status ? ` [${p.status}]` : ""}
                    </option>
                  ))
                )}
              </select>
              {projectsError && (
                <span className="text-[10px] text-sylion-amber flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" /> {projectsError}
                </span>
              )}
            </div>
          </Card>

          {selectedProjectId && projectWorkers.length === 0 && (
            <Card className="p-6 bg-card border-dashed border-sylion-border/80" data-testid="workers-empty-per-project">
              <div className="flex items-start gap-3">
                <Folder className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="text-sm font-semibold">Brak workerów przypisanych do projektu</p>
                  <p className="text-sm text-muted-foreground">
                    Skonfiguruj w <code className="text-[10px] bg-muted px-1 py-0.5 rounded">/projects/{selectedProjectId}/orchestration</code> panel Dispatch Agent?w.
                  </p>
                </div>
              </div>
            </Card>
          )}

          {selectedProjectId && projectWorkers.length > 0 && (
            <div className="grid grid-cols-3 gap-3" data-testid="workers-per-project-grid">
              {projectWorkers.map((w: any) => (
                <Card key={w.worker_id} className="p-4 bg-card border-sylion-border">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <HardDrive className="w-4 h-4 text-primary" />
                      <div>
                        <p className="text-sm font-medium">{w.name}</p>
                        <p className="text-[10px] text-muted-foreground font-mono">{w.worker_id}</p>
                      </div>
                    </div>
                    <Badge variant="outline" className={cn("text-[10px] capitalize", statusColor(w.status))}>
                      {w.status}
                    </Badge>
                  </div>
                  <div className="mt-2 text-[10px] text-muted-foreground">
                    {w.assigned_modules?.length ?? 0}/{w.capacity} zada?
                  </div>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
        <TabsContent value="all" className="mt-4">
          {/* "all" view content rendered below in original layout */}
        </TabsContent>
      </Tabs>

      {workers.length === 0 && viewMode === "all" && (
        <Card className="p-8 bg-card border-dashed border-sylion-border/80">
          <div className="max-w-xl">
            <p className="text-sm font-semibold">Brak zarejestrowanych wykonawców</p>
            <p className="text-sm text-muted-foreground mt-1">
              Zarejestruj pierwszego wykonawcę, aby umożliwić rozproszone przydziały buildów, kontrole heartbeatu i planowanie topologii.
            </p>
            <div className="flex items-center gap-2 mt-4">
              <Button size="sm" onClick={() => setShowRegister(true)}>
                <Plus className="w-3.5 h-3.5 mr-1" />
                Zarejestruj pierwszego wykonawcę
              </Button>
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <ArrowRight className="w-3 h-3" />
                Zacznij od lokalnego hosta z pojemnością 3, potem skaluj.
              </span>
            </div>
          </div>
        </Card>
      )}

      {/* Workers grid */}
      {workers.length > 0 && viewMode === "all" && (
        <div className="grid grid-cols-3 gap-3">
          {workers.map((w: any) => {
            const pct = loadPct(w);
            const isSelected = selectedWorkerId === w.worker_id;
            return (
              <Card
                key={w.worker_id}
                className={cn(
                  "p-4 bg-card border-sylion-border cursor-pointer transition-all hover:border-primary/30",
                  isSelected && "ring-1 ring-primary/40 border-primary/30"
                )}
                onClick={() => setSelectedWorkerId(isSelected ? null : w.worker_id)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <HardDrive className="w-4 h-4 text-primary" />
                    <div>
                      <p className="text-sm font-medium">{w.name}</p>
                      <p className="text-[10px] text-muted-foreground font-mono">{w.worker_id}</p>
                    </div>
                  </div>
                  <Badge variant="outline" className={cn("text-[10px] capitalize", statusColor(w.status))}>
                    {w.status}
                  </Badge>
                </div>
                <div className="mt-3 space-y-1">
                  <div className="flex justify-between text-[10px] text-muted-foreground">
                    <span>Load {pct}%</span>
                    <span>{w.assigned_modules?.length ?? 0}/{w.capacity}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div
                      className={cn("h-full rounded-full", pct > 90 ? "bg-sylion-red" : pct > 60 ? "bg-sylion-amber" : "bg-sylion-green")}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2 text-[10px] text-muted-foreground">
                  <Globe className="w-3 h-3" /> {w.host}
                  {w.last_heartbeat && (
                    <span className="ml-auto"><Clock className="w-3 h-3 inline mr-0.5" />{fmtDateTime(w.last_heartbeat)}</span>
                  )}
                </div>
                {w.tags?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {w.tags.map((t: string) => (
                      <Badge key={t} variant="secondary" className="text-[8px] h-4">{t}</Badge>
                    ))}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Selected worker detail */}
      <AnimatePresence>
        {selectedWorker && viewMode === "all" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}>
            <Card className="p-5 bg-card border-sylion-border">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold">{selectedWorker.name}</h3>
                  <p className="text-xs text-muted-foreground font-mono">{selectedWorker.worker_id}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" onClick={() => handleHeartbeat(selectedWorker.worker_id)} disabled={!!busy}>
                    <Activity className={cn("w-3.5 h-3.5 mr-1", busy === `hb-${selectedWorker.worker_id}` && "animate-pulse")} />
                    Heartbeat
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => handleDelete(selectedWorker.worker_id)} disabled={!!busy}>
                    <X className="w-3.5 h-3.5 mr-1" /> Usuń
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-4 gap-4 mt-4 text-sm">
                <div><span className="text-muted-foreground text-xs">Host<HelpTip text="Adres / hostname, na którym działa proces wykonawcy." /></span><p>{selectedWorker.host}</p></div>
                <div><span className="text-muted-foreground text-xs">Pojemność<HelpTip text="Limit zadań współbieżnych, które ten wykonawca obsłuży." /></span><p>{selectedWorker.capacity}</p></div>
                <div><span className="text-muted-foreground text-xs">Limit budżetu<HelpTip text="Górny limit kosztu (USD) dla tego wykonawcy w bieżącym okresie." /></span><p>${selectedWorker.budget_limit?.toFixed?.(2) ?? "0.00"}</p></div>
                <div><span className="text-muted-foreground text-xs">Wydany budżet<HelpTip text="Skumulowany koszt zadań przypisanych temu wykonawcy w bieżącym okresie." /></span><p>${selectedWorker.budget_spent?.toFixed?.(2) ?? "0.00"}</p></div>
              </div>

              {selectedWorker.assigned_modules?.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                    Przypisane moduły
                    <HelpTip text="Moduły aktualnie obsługiwane przez tego wykonawcę. Rozdział kontrolowany przez scheduler." />
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {selectedWorker.assigned_modules.map((m: string) => (
                      <Badge key={m} variant="outline" className="text-[10px]">{m}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Topologies */}
      {viewMode === "all" && (
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
            Topologie buildów
            <HelpTip text="Wygenerowane konfiguracje topologii — które wykonawcy obsługują które moduły. Rebalansuj, aby przygenerować nowe rozkłady przy zmianie pojemności lub awariach." />
          </h3>
          {topologiesLoading && topologies.length > 0 && (
            <span className="text-xs text-muted-foreground">Odświeżanie listy topologii...</span>
          )}
        </div>

        {topologiesError && topologies.length === 0 ? (
          <Card className="border-sylion-amber/20 bg-sylion-amber/5 p-4" aria-live="polite">
            <div className="space-y-1">
              <p className="text-sm font-medium text-sylion-amber">Dane topologii niedostępne</p>
              <p className="text-sm text-muted-foreground">{topologiesError}</p>
            </div>
          </Card>
        ) : topologiesLoading && topologies.length === 0 ? (
          <Card className="border-sylion-border p-4" aria-live="polite">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Ładowanie topologii...
            </div>
          </Card>
        ) : topologies.length === 0 ? (
          <Card className="border-dashed border-sylion-border p-4">
            <p className="text-sm font-medium">Brak wygenerowanych topologii</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Rebalansuj wykonawców lub wygeneruj dane topologii w pipeline, aby uzupełnić tę sekcję.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {topologies.map((t: any) => (
              <Card key={t.topology_id} className="p-4 bg-card border-sylion-border">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-primary" />
                  <div>
                    <p className="text-sm font-medium">{t.name}</p>
                    <p className="text-[10px] text-muted-foreground font-mono">{t.topology_id}</p>
                  </div>
                  <Badge variant="outline" className="text-[10px] ml-auto capitalize">{t.status}</Badge>
                </div>
                {t.config?.servers && (
                  <p className="text-xs text-muted-foreground mt-2">{t.config.servers.length} serwer(ów)</p>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
      )}
    </div>
  );
}
