"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { BackendErrorBanner } from "@/components/advisor/BackendErrorBanner";
import { PhaseTimeline } from "@/components/advisor/PhaseTimeline";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useProjectLifecycle } from "@/lib/hooks/advisor";
import type { ProjectLifecyclePhase } from "@/lib/api/advisor";
import { Search, Activity } from "lucide-react";
import { LifecycleHeader } from "./_components/LifecycleHeader";
import { LifecycleFlowChart } from "./_components/LifecycleFlowChart";
import { ActiveCardsPanel } from "./_components/ActiveCardsPanel";
import { PhaseDetailModal } from "./_components/PhaseDetailModal";
import { LifecycleQuickActions } from "./_components/LifecycleQuickActions";
import { OperatorNextStepsPanel } from "./_components/OperatorNextStepsPanel";
import { EmptyState } from "./_components/EmptyState";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function ProjectLifecyclePage() {
  const params = useParams<{ projectId: string }>();
  const projectId = String(params?.projectId ?? "");

  const { lifecycle, source, loading, refresh } = useProjectLifecycle(projectId || null);

  const [selectedHookId, setSelectedHookId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [kickoffing, setKickoffing] = useState(false);
  const [kickoffMessage, setKickoffMessage] = useState("");
  const [cardsRefreshNonce, setCardsRefreshNonce] = useState(0);
  const searchRef = useRef<HTMLInputElement | null>(null);

  const phases: ProjectLifecyclePhase[] = useMemo(() => lifecycle?.phases ?? [], [lifecycle]);

  const filteredPhases = useMemo(() => {
    if (!search.trim()) return phases;
    const q = search.toLowerCase();
    return phases.filter(
      (phase) => phase.hook_id.toLowerCase().includes(q) || phase.hook_event_type.toLowerCase().includes(q),
    );
  }, [phases, search]);

  const selectedPhase = useMemo(() => {
    if (!selectedHookId) return null;
    return phases.find((phase) => phase.hook_id === selectedHookId) ?? null;
  }, [phases, selectedHookId]);

  const handlePhaseClick = useCallback(
    (hookId: string) => {
      setSelectedHookId(hookId);
      setModalOpen(true);
    },
    [],
  );

  const handleCardActionComplete = useCallback(() => {
    void refresh();
    setCardsRefreshNonce((value) => value + 1);
  }, [refresh]);

  const handleNextPhase = useCallback(() => {
    if (phases.length === 0) return;
    const currentIndex = selectedHookId
      ? phases.findIndex((phase) => phase.hook_id === selectedHookId)
      : -1;
    const nextIndex = currentIndex < 0 ? 0 : Math.min(currentIndex + 1, phases.length - 1);
    setSelectedHookId(phases[nextIndex].hook_id);
  }, [phases, selectedHookId]);

  const handlePrevPhase = useCallback(() => {
    if (phases.length === 0) return;
    const currentIndex = selectedHookId
      ? phases.findIndex((phase) => phase.hook_id === selectedHookId)
      : -1;
    const prevIndex = currentIndex <= 0 ? 0 : currentIndex - 1;
    setSelectedHookId(phases[prevIndex].hook_id);
  }, [phases, selectedHookId]);

  const focusSearch = useCallback(() => {
    searchRef.current?.focus();
  }, []);

  const runKickoff = useCallback(async () => {
    if (!projectId || kickoffing) return;
    setKickoffing(true);
    setKickoffMessage("");
    try {
      const response = await fetch(`${API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/kickoff`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`kickoff HTTP ${response.status}`);
      }
      const payload = await response.json();
      const kickoff = payload?.kickoff ?? {};
      const kickoffStatus = String(kickoff.status ?? "");
      const plannedTopics = Array.isArray(kickoff.planned_topics) ? kickoff.planned_topics.length : 0;
      const created = Number(kickoff.cards_created ?? 0);
      const existingTopics = Array.isArray(kickoff.existing_topics)
        ? kickoff.existing_topics.length
        : Array.isArray(kickoff.existing_topics_before)
          ? kickoff.existing_topics_before.length
          : 0;
      setKickoffMessage(
        kickoffStatus === "queued"
          ? `Kickoff zakolejkowany (${plannedTopics} tematów). Karty pojawią się po zakończeniu pracy modeli.`
          : kickoffStatus === "already_running"
            ? `Kickoff już działa w tle (${plannedTopics} tematów).`
            : kickoff.skipped
              ? `Kickoff już istnieje (${existingTopics} tematów).`
              : `Kickoff wyemitował ${created} kart.`,
      );
      await refresh();
      setCardsRefreshNonce((value) => value + 1);
    } catch (err) {
      setKickoffMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setKickoffing(false);
    }
  }, [kickoffing, projectId, refresh]);

  const status = useMemo(() => {
    if (!lifecycle) return { approved: 0, in_progress: 0, pending: 0, blocked: 0 };
    return phases.reduce(
      (acc, phase) => {
        acc[phase.status] = (acc[phase.status] ?? 0) + 1;
        return acc;
      },
      { approved: 0, in_progress: 0, pending: 0, blocked: 0 } as Record<string, number>,
    );
  }, [lifecycle, phases]);

  return (
    <div className="space-y-4" data-testid="lifecycle-dashboard" data-project-id={projectId}>
      <BackendErrorBanner source={source} />
      <LifecycleHeader lifecycle={lifecycle} projectId={projectId} />

      <LifecycleQuickActions
        onNext={handleNextPhase}
        onPrev={handlePrevPhase}
        onFocusSearch={focusSearch}
      />

      <Card className="flex flex-wrap items-center justify-between gap-2 bg-card p-3">
        <div>
          <p className="text-xs font-semibold">Kickoff projektu</p>
          <p className="text-[11px] text-muted-foreground">
            Emituje brakujące karty lifecycle AdvisorEngine dla projektów istniejących albo importowanych.
          </p>
          {kickoffMessage ? (
            <p className="mt-1 text-[11px] text-muted-foreground" data-testid="kickoff-result">
              {kickoffMessage}
            </p>
          ) : null}
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void runKickoff()}
          disabled={!projectId || kickoffing}
          data-testid="run-project-kickoff"
        >
          {kickoffing ? "Uruchamianie kickoff..." : "Uruchom kickoff"}
        </Button>
      </Card>

      <div className="grid grid-cols-4 gap-2">
        <StatusTile label="Zatwierdzone" value={status.approved} accent="text-sylion-green" />
        <StatusTile label="W toku" value={status.in_progress} accent="text-sylion-blue" />
        <StatusTile label="Zablokowane" value={status.blocked} accent="text-sylion-red" />
        <StatusTile label="Oczekujące" value={status.pending} accent="text-muted-foreground" />
      </div>

      {!loading && (!lifecycle || phases.length === 0) ? (
        <EmptyState projectId={projectId} />
      ) : (
        <>
          <Card className="bg-card p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <Activity className="h-4 w-4 text-primary" />
                Oś 16 faz
              </h2>
              <label className="relative w-56">
                <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  ref={searchRef}
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Filtruj fazy, np. H08 lub SoT"
                  data-testid="lifecycle-search"
                  className="h-7 w-full rounded-md border border-border bg-background pl-7 pr-2 text-[11px] outline-none focus:ring-2 focus:ring-sylion-blue/40"
                />
              </label>
            </div>

            {lifecycle ? (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
                <PhaseTimeline
                  lifecycle={{ ...lifecycle, phases: filteredPhases }}
                  selected={selectedHookId ?? undefined}
                  onPhaseClick={handlePhaseClick}
                />
                {filteredPhases.length === 0 && search ? (
                  <p className="mt-2 text-center text-[11px] text-muted-foreground">
                    Brak faz pasujących do <span className="font-mono">{search}</span>
                  </p>
                ) : null}
              </motion.div>
            ) : null}
          </Card>

          <OperatorNextStepsPanel
            phases={phases}
            projectId={projectId}
            onOpenPhase={handlePhaseClick}
          />

          {lifecycle ? (
            <LifecycleFlowChart
              lifecycle={lifecycle}
              onPhaseClick={handlePhaseClick}
              selected={selectedHookId ?? undefined}
            />
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            <ActiveCardsPanel key={`cards-${projectId}-${cardsRefreshNonce}`} projectId={projectId} />
            <Card className="bg-card p-4" data-testid="phase-summary-card">
              <header className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold">Wybrana faza</h3>
                {selectedPhase ? (
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {selectedPhase.hook_id}
                  </Badge>
                ) : null}
              </header>
              {selectedPhase ? (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground font-mono">
                    {selectedPhase.hook_event_type}
                  </p>
                  <p className="text-xs">
                    Status:{" "}
                    <span className="font-medium capitalize">
                      {statusLabel(selectedPhase.status)}
                    </span>
                  </p>
                  <p className="text-xs">
                    Karty: <span className="font-mono">{selectedPhase.cards?.length ?? 0}</span>
                  </p>
                  <button
                    type="button"
                    className="rounded bg-sylion-blue/10 px-2 py-1 text-[11px] text-sylion-blue hover:bg-sylion-blue/20"
                    onClick={() => setModalOpen(true)}
                    data-testid="open-phase-modal"
                  >
                    Otworz szczegoly
                  </button>
                </div>
              ) : (
                <p className="py-6 text-center text-xs text-muted-foreground">
                  Wybierz fazę z osi albo uzyj <kbd className="font-mono">j</kbd> /{" "}
                  <kbd className="font-mono">k</kbd>, aby nawigowac.
                </p>
              )}
            </Card>
          </div>
        </>
      )}

      <PhaseDetailModal
        phase={selectedPhase}
        open={modalOpen}
        onOpenChange={setModalOpen}
        onActionComplete={handleCardActionComplete}
      />
    </div>
  );
}

function StatusTile({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <Card className="bg-card p-3">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${accent}`}>{value}</p>
    </Card>
  );
}

function statusLabel(status: string): string {
  if (status === "approved") return "zatwierdzone";
  if (status === "in_progress") return "w toku";
  if (status === "blocked") return "zablokowane";
  return "oczekuje";
}
