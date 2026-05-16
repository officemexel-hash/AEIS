"use client";

import Link from "next/link";
import type { ComponentType } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { DecisionCardBody, ProjectLifecyclePhase } from "@/lib/api/advisor";
import { ArrowRight, CheckCircle2, CircleDot, FileText, Scale, Sparkles } from "lucide-react";

interface Props {
  phases: ProjectLifecyclePhase[];
  projectId: string;
  onOpenPhase: (hookId: string) => void;
}

const WORKFLOW_HOOKS = ["H04", "H06", "H12"] as const;

export function OperatorNextStepsPanel({ phases, projectId, onOpenPhase }: Props) {
  const phaseByHook = new Map(phases.map((phase) => [phase.hook_id, phase]));
  const intake = phaseByHook.get("H04");
  const council = phaseByHook.get("H06");
  const skills = phaseByHook.get("H12");
  const readyForOrchestration = WORKFLOW_HOOKS.every(
    (hookId) => phaseByHook.get(hookId)?.status === "approved",
  );
  const activeWorkflowPhase = WORKFLOW_HOOKS.map((hookId) => phaseByHook.get(hookId)).find(
    (phase): phase is ProjectLifecyclePhase => Boolean(phase && phase.status === "in_progress"),
  );
  const blockingWorkflowPhase = WORKFLOW_HOOKS.map((hookId) => phaseByHook.get(hookId)).find(
    (phase): phase is ProjectLifecyclePhase => Boolean(phase && phase.status !== "approved"),
  );

  return (
    <section
      className="rounded-lg border border-sylion-blue/25 bg-sylion-blue/5 p-4"
      data-testid="operator-next-steps"
    >
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <CircleDot className="h-4 w-4 text-sylion-blue" />
            <h2 className="text-sm font-semibold">Co dalej z projektem</h2>
            <Badge variant="outline" className={cn("text-[10px]", readyForOrchestration ? "border-sylion-green/30 text-sylion-green" : "border-sylion-blue/30 text-sylion-blue")}>
              {readyForOrchestration ? "gotowe do meta-orkiestracji" : "czeka na decyzję"}
            </Badge>
          </div>
          <p className="mt-1 max-w-3xl text-xs text-muted-foreground">
            Tu widać ścieżkę operatora po pierwszym uruchomieniu: intake, skład Rady, skille i kolejny ekran pracy.
          </p>
        </div>
        {readyForOrchestration ? (
          <Link href={`/projects/${encodeURIComponent(projectId)}/orchestration`} data-testid="lifecycle-go-next">
            <Button size="lg" className="h-10 min-w-[260px] gap-2 px-4 text-sm">
              Idź dalej do meta-orkiestracji
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        ) : activeWorkflowPhase ? (
          <Button
            size="lg"
            onClick={() => onOpenPhase(activeWorkflowPhase.hook_id)}
            className="h-10 min-w-[260px] gap-2 px-4 text-sm"
            data-testid="lifecycle-go-next"
          >
            Idź dalej: {activeWorkflowPhase.hook_id}
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        ) : blockingWorkflowPhase ? (
          <Button
            size="lg"
            variant="outline"
            onClick={() => onOpenPhase(blockingWorkflowPhase.hook_id)}
            className="h-10 min-w-[260px] gap-2 px-4 text-sm"
            data-testid="lifecycle-go-next"
          >
            Sprawdź następny krok: {blockingWorkflowPhase.hook_id}
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        ) : null}
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <WorkflowStep
          icon={FileText}
          title="Pomysł"
          phase={intake}
          fallback="Najpierw przyjmij pomysł i dane z załączników."
          approvedLabel="Pomysł przyjęty"
          activeLabel="Przejrzyj intake"
          onOpenPhase={onOpenPhase}
        />
        <WorkflowStep
          icon={Scale}
          title="Skład Rady"
          phase={council}
          fallback="System powinien pokazać propozycję Rady do akceptacji."
          approvedLabel="Rekomendacja Rady zaakceptowana"
          activeLabel="Zaakceptuj lub zmień Radę"
          onOpenPhase={onOpenPhase}
        />
        <WorkflowStep
          icon={Sparkles}
          title="Skille"
          phase={skills}
          fallback="System powinien pokazać sugerowane skille i uzasadnienie."
          approvedLabel="Skille zaakceptowane"
          activeLabel="Zaakceptuj lub zmień skille"
          onOpenPhase={onOpenPhase}
        />
      </div>

      {readyForOrchestration ? (
        <div className="mt-3 flex flex-col gap-3 rounded-md border border-sylion-green/25 bg-sylion-green/5 px-3 py-3 text-xs text-sylion-green md:flex-row md:items-center md:justify-between">
          <p>
            Intake, Rada i skille są zatwierdzone. Następny logiczny krok to meta-orkiestracja projektu: tam sprawdźisz realny skład Rady, budżet, autonomię i uruchomisz pełny Council V10 przed dalszą pracą.
          </p>
          <Link
            href={`/projects/${encodeURIComponent(projectId)}/orchestration`}
            data-testid="lifecycle-go-next-inline"
          >
            <Button size="sm" className="min-w-[220px] gap-1.5">
              Idź dalej
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      ) : blockingWorkflowPhase ? (
        <div
          className="mt-3 rounded-md border border-sylion-amber/25 bg-sylion-amber/5 px-3 py-2 text-xs text-sylion-amber"
          data-testid="lifecycle-next-blocker"
        >
          Następny krok jest zablokowany przez fazę {blockingWorkflowPhase.hook_id}: {statusLabel(blockingWorkflowPhase.status)}.
        </div>
      ) : null}
    </section>
  );
}

function WorkflowStep({
  icon: Icon,
  title,
  phase,
  fallback,
  approvedLabel,
  activeLabel,
  onOpenPhase,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  phase?: ProjectLifecyclePhase;
  fallback: string;
  approvedLabel: string;
  activeLabel: string;
  onOpenPhase: (hookId: string) => void;
}) {
  const card = phase?.cards?.[0] ?? null;
  const body = card?.body as Partial<DecisionCardBody> | undefined;
  const status = phase?.status ?? "pending";
  const isApproved = status === "approved";
  const isActive = status === "in_progress";
  const summary = compactText(
    body?.recommendation || card?.header.rationale || fallback,
    210,
  );

  return (
    <div className="rounded-md border border-border/50 bg-background/45 p-3" data-testid={`workflow-step-${phase?.hook_id ?? title}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className={cn("h-4 w-4 shrink-0", isApproved ? "text-sylion-green" : isActive ? "text-sylion-blue" : "text-muted-foreground")} />
          <div className="min-w-0">
            <p className="text-xs font-semibold">{title}</p>
            <p className="font-mono text-[10px] text-muted-foreground">{phase?.hook_id ?? "brak fazy"}</p>
          </div>
        </div>
        <Badge variant="outline" className={cn("shrink-0 text-[10px]", statusBadgeClass(status))}>
          {statusLabel(status)}
        </Badge>
      </div>

      <p className="mt-2 min-h-12 text-xs leading-relaxed text-muted-foreground">{summary}</p>

      <div className="mt-3 flex items-center justify-between gap-2">
        <span className={cn("inline-flex items-center gap-1 text-[11px]", isApproved ? "text-sylion-green" : isActive ? "text-sylion-blue" : "text-muted-foreground")}>
          {isApproved ? <CheckCircle2 className="h-3.5 w-3.5" /> : <CircleDot className="h-3.5 w-3.5" />}
          {isApproved ? approvedLabel : isActive ? activeLabel : "Oczekuje na kartę"}
        </span>
        {phase ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 gap-1 px-2 text-[11px]"
            onClick={() => onOpenPhase(phase.hook_id)}
            data-testid={`open-workflow-phase-${phase.hook_id}`}
          >
            Szczegóły
            <ArrowRight className="h-3 w-3" />
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function compactText(value: string, maxLength: number): string {
  const normalized = String(value || "").replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength).trimEnd()}...`;
}

function statusLabel(status: string): string {
  if (status === "approved") return "zatwierdzone";
  if (status === "in_progress") return "w toku";
  if (status === "blocked") return "zablokowane";
  return "oczekuje";
}

function statusBadgeClass(status: string): string {
  if (status === "approved") return "border-sylion-green/30 text-sylion-green";
  if (status === "in_progress") return "border-sylion-blue/30 text-sylion-blue";
  if (status === "blocked") return "border-sylion-red/30 text-sylion-red";
  return "border-muted-foreground/30 text-muted-foreground";
}
