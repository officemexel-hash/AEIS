"use client";

import { CheckCircle2, Clock, AlertOctagon, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProjectLifecycleState } from "@/lib/api/advisor";

const PHASE_PL: Record<string, string> = {
  H01: "Konfiguracja modeli",
  H02: "API providers",
  H03: "Budzet",
  H04: "Intake pomyslu",
  H05: "Model SoT",
  H06: "Formacja Rady",
  H07: "Polityka autonomii",
  H08: "Szkic SoT",
  H09: "Masterplan",
  H10: "Topologia runtime",
  H11: "Skalowanie VPS",
  H12: "Dobor Skills",
  H13: "Deploy produkcyjny",
  H14: "Testy",
  H15: "Human Gate",
  H16: "Finalna akceptacja",
};

const STATUS_STYLE: Record<
  string,
  { cls: string; icon: React.ComponentType<{ className?: string }> }
> = {
  approved: { cls: "border-[#40d987]/30 bg-[#40d987]/10 text-[#40d987]", icon: CheckCircle2 },
  in_progress: { cls: "border-[#75a7ff]/40 bg-[#75a7ff]/10 text-[#75a7ff]", icon: Loader2 },
  pending: { cls: "border-white/10 bg-white/[0.03] text-slate-400", icon: Clock },
  blocked: { cls: "border-[#ff5f7a]/35 bg-[#ff5f7a]/10 text-[#ff5f7a]", icon: AlertOctagon },
};

interface Props {
  lifecycle: ProjectLifecycleState;
  projectName?: string;
  currentPhase?: number;
}

export function CockpitLifecycleStrip({ lifecycle, projectName, currentPhase }: Props) {
  return (
    <section
      className="rounded-2xl border border-white/10 p-5"
      style={{ background: "linear-gradient(180deg,rgba(17,24,39,.92),rgba(10,14,25,.92))" }}
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-white">
            Lifecycle projektu
            {projectName ? <span className="ml-2 text-slate-400">— {projectName}</span> : null}
          </h2>
          <p className="text-[11px] text-slate-500">16 faz projektu z aktywnymi hookami Advisora.</p>
        </div>
        {currentPhase != null ? (
          <span className="rounded-full border border-[#f6c177]/25 bg-[#f6c177]/10 px-3 py-1 text-[11px] text-[#f6c177]">
            faza {currentPhase}/16
          </span>
        ) : null}
      </div>

      <div className="flex gap-2 overflow-x-auto pb-2">
        {lifecycle.phases.map((phase) => {
          const style = STATUS_STYLE[phase.status] ?? STATUS_STYLE.pending;
          const Icon = style.icon;
          const label = PHASE_PL[phase.hook_id] ?? phase.hook_id;
          const shortId = phase.hook_id.replace("H0", "").replace("H1", "1");
          return (
            <div
              key={phase.hook_id}
              className={cn(
                "flex min-w-[110px] flex-col rounded-xl border p-3 transition",
                style.cls,
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] opacity-60">{phase.hook_id}</span>
                <Icon
                  className={cn(
                    "h-3.5 w-3.5 opacity-80",
                    phase.status === "in_progress" && "animate-spin",
                  )}
                />
              </div>
              <span className="mt-1.5 text-[11px] font-semibold leading-tight">{label}</span>
              <span className="mt-1 text-[10px] opacity-60">{phase.status}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
