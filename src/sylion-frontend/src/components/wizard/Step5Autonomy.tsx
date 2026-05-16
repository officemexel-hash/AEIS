"use client";

import { Hand, Sparkles, Zap } from "lucide-react";
import { SmartDefault } from "./SmartDefault";
import { cn } from "@/lib/utils";

export type AutonomyLevel = "manual" | "suggest" | "auto";

export interface Step5Values {
  autonomy_level?: AutonomyLevel;
}

const OPTIONS: Array<{
  id: AutonomyLevel;
  label: string;
  desc: string;
  icon: typeof Hand;
  tone: string;
}> = [
  {
    id: "manual",
    label: "Ręcznie",
    desc: "Doradca proponuje; operator klika każdą akcję D1+. Maksymalna kontrola, najwolniejszy rytm.",
    icon: Hand,
    tone: "border-sylion-blue/30 bg-sylion-blue/5 text-sylion-blue",
  },
  {
    id: "suggest",
    label: "Sugestie",
    desc: "Doradca proponuje ranking rekomendacji i alternatyw. Operator akceptuje, modyfikuje albo odrzuca. Zalecane dla większości operatorów.",
    icon: Sparkles,
    tone: "border-sylion-amber/30 bg-sylion-amber/5 text-sylion-amber",
  },
  {
    id: "auto",
    label: "Automatycznie",
    desc: "Doradca sam stosuje decyzję D0/D1 i proponuje D2+. D3+ zawsze zatrzymuje się na HumanGate.",
    icon: Zap,
    tone: "border-sylion-green/30 bg-sylion-green/5 text-sylion-green",
  },
];

interface Props {
  values: Step5Values;
  onChange: (patch: Step5Values) => void;
}

export function Step5Autonomy({ values, onChange }: Props) {
  const advisorPick = values.autonomy_level ? null : "suggest";

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        Domyślne zachowanie dla nowych projektów. Decyzje D3+ zawsze wymagają zgody człowieka
        i Evidence Pack niezależnie od tego ustawieńia.
      </p>

      <div className="space-y-2" data-testid="step5-autonomy">
        {OPTIONS.map((o) => {
          const Icon = o.icon;
          const active = values.autonomy_level === o.id;
          return (
            <button
              key={o.id}
              type="button"
              onClick={() => onChange({ autonomy_level: o.id })}
              className={cn(
                "flex w-full items-start gap-3 rounded-md border px-3 py-3 text-left transition",
                active
                  ? "border-sylion-blue/60 bg-sylion-blue/10"
                  : "border-border hover:bg-muted/30",
              )}
              data-testid={`step5-${o.id}`}
              data-active={active}
            >
              <div
                className={cn(
                  "flex h-9 w-9 flex-none items-center justify-center rounded-md border",
                  o.tone,
                )}
              >
                <Icon className="h-4 w-4" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold">{o.label}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{o.desc}</p>
              </div>
            </button>
          );
        })}
      </div>

      {advisorPick ? (
        <SmartDefault
          label="Sugestie"
          rationale="Najlepszy balans autonomii i bezpieczeństwa; operator zachowuje klik decyzyjny, ale nie musi sam przygotowywać kontekstu."
          onApply={() => onChange({ autonomy_level: advisorPick })}
        />
      ) : null}
    </div>
  );
}
