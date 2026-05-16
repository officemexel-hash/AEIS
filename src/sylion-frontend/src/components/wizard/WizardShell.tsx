"use client";

import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ChevronLeft, ChevronRight, Check, Lock } from "lucide-react";
import { cn } from "@/lib/utils";

export interface WizardStepDef {
  id: number;
  title: string;
  description?: string;
  optional?: boolean;
  /** F-019: when present and returns ``passed=false`` users cannot advance
   *  past this step nor jump to later steps via the step nav. */
  gateReason?: string | null;
}

interface Props {
  steps: WizardStepDef[];
  current: number;
  /** F-019: highest step the user has been allowed to reach so far.
   *  Steps with id > maxReachable are locked in the nav. */
  maxReachable?: number;
  onStepChange: (step: number) => void;
  onNext: () => void;
  onPrev: () => void;
  onSkip?: () => void;
  onComplete: () => void;
  children: React.ReactNode;
  canAdvance?: boolean;
  /** Reason shown next to disabled Next when canAdvance=false. */
  blockingReason?: string;
  className?: string;
}

export function WizardShell({
  steps,
  current,
  maxReachable,
  onStepChange,
  onNext,
  onPrev,
  onSkip,
  onComplete,
  children,
  canAdvance = true,
  blockingReason,
  className,
}: Props) {
  const total = steps.length;
  const pct = useMemo(() => Math.round((current / total) * 100), [current, total]);
  const stepDef = steps.find((s) => s.id === current) ?? steps[0];
  const isLast = current === total;
  const reachable = maxReachable ?? current;

  return (
    <div className={cn("mx-auto flex min-h-[80vh] w-full max-w-4xl flex-col gap-6 px-6 py-10", className)}>
      <header className="space-y-2">
        <div className="flex items-center justify-between text-xs uppercase tracking-wide text-muted-foreground">
          <span>Krok {current} z {total}</span>
          <span>{pct}%</span>
        </div>
        <Progress value={pct} />
        <nav className="flex flex-wrap gap-1 pt-2">
          {steps.map((s) => {
            const completed = s.id < current;
            const active = s.id === current;
            const locked = s.id > reachable;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  if (!locked) onStepChange(s.id);
                }}
                disabled={locked}
                title={locked ? "Ukończ wcześniejsze kroki — nie można przeskoczyć." : undefined}
                aria-disabled={locked}
                className={cn(
                  "rounded-md border px-2 py-1 text-[11px] transition",
                  active && "border-sylion-blue/60 bg-sylion-blue/10 text-sylion-blue",
                  completed && !active && "border-sylion-green/40 bg-sylion-green/5 text-sylion-green",
                  locked && "cursor-not-allowed border-border/30 text-muted-foreground/50",
                  !locked && !completed && !active && "border-border/50 text-muted-foreground hover:bg-muted/30",
                )}
                data-testid={`wizard-step-${s.id}`}
                data-locked={locked || undefined}
              >
                {locked ? <Lock className="mr-1 inline h-3 w-3" /> : null}
                {completed && !locked ? <Check className="mr-1 inline h-3 w-3" /> : null}
                {s.id}. {s.title}
              </button>
            );
          })}
        </nav>
      </header>

      <main className="flex-1 rounded-lg border border-border bg-card p-6 shadow-sm">
        <div className="mb-4">
          <h1 className="text-2xl font-semibold tracking-tight">{stepDef.title}</h1>
          {stepDef.description ? (
            <p className="mt-1 text-sm text-muted-foreground">{stepDef.description}</p>
          ) : null}
        </div>
        <div className="space-y-4">{children}</div>
      </main>

      <footer className="flex flex-col gap-2">
        {!canAdvance && blockingReason ? (
          <div
            className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-1.5 text-[11px] text-amber-300"
            data-testid="wizard-blocking-reason"
          >
            <Lock className="mr-1 inline h-3 w-3" />
            {blockingReason}
          </div>
        ) : null}
        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={onPrev} disabled={current === 1}>
            <ChevronLeft className="mr-1 h-4 w-4" />
            Wstecz
          </Button>
          <div className="flex items-center gap-2">
            {stepDef.optional && onSkip ? (
              <Button variant="ghost" onClick={onSkip}>
                Pominę na razie
              </Button>
            ) : null}
            {isLast ? (
              <Button
                onClick={onComplete}
                disabled={!canAdvance}
                title={!canAdvance ? blockingReason : undefined}
              >
                Zakończ konfigurację
                <Check className="ml-1 h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={onNext}
                disabled={!canAdvance}
                title={!canAdvance ? blockingReason : undefined}
              >
                Dalej
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}
