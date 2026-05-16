"use client";

import { Sparkles } from "lucide-react";
import { SmartDefault } from "./SmartDefault";
import { cn } from "@/lib/utils";

export const STEP1_GOALS = [
  { id: "ship_software", label: "Szybciej tworzyć oprogramowanie" },
  { id: "win_grants", label: "Zdobywać finansowanie i granty" },
  { id: "control_costs", label: "Kontrolować koszty LLM i infrastruktury" },
  { id: "audit_governance", label: "Utrzymać audyt i governance" },
  { id: "research", label: "Prowadzić projekty badawcze" },
  { id: "ops", label: "Obsługiwać systemy produkcyjne" },
];

export const STEP1_CADENCES = [
  { id: "daily", label: "Codziennie" },
  { id: "weekly", label: "Co tydzień" },
  { id: "occasional", label: "Sporadycznie / na żądanie" },
];

export interface Step1Values {
  operator_name?: string;
  goals?: string[];
  usage_cadence?: string;
}

interface Props {
  values: Step1Values;
  onChange: (patch: Step1Values) => void;
}

export function Step1Welcome({ values, onChange }: Props) {
  const goals = values.goals ?? [];
  const toggleGoal = (id: string) => {
    const next = goals.includes(id) ? goals.filter((g) => g !== id) : [...goals, id];
    onChange({ goals: next });
  };

  const advisorName = values.operator_name?.trim() ? null : "Operator";
  const advisorGoals = goals.length === 0 ? ["ship_software", "control_costs"] : null;
  const advisorCadence = values.usage_cadence ? null : "weekly";

  return (
    <div className="space-y-5">
      <div className="rounded-md border border-sylion-blue/20 bg-sylion-blue/5 p-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-sylion-blue" />
          <span className="text-xs font-semibold uppercase tracking-wide text-sylion-blue">
            Witaj
          </span>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Dopasujmy Doradcę AEIS do Twojego sposobu pracy. Każdy krok pokazuje
          sugerowane ustawieńie domyślne — możesz je przyjąć jednym kliknięciem albo zmienić.
        </p>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Nazwa operatora
        </label>
        <input
          type="text"
          value={values.operator_name ?? ""}
          onChange={(e) => onChange({ operator_name: e.target.value })}
          placeholder="Jak Doradca ma się do Ciebie zwracać?"
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none transition focus:border-sylion-blue/60"
          data-testid="step1-name"
        />
        {advisorName ? (
          <SmartDefault
            label={`Użyj „${advisorName}”`}
            rationale="Tymczasowa nazwa operatora; możesz ją później zmienić w ustawieńiach."
            onApply={() => onChange({ operator_name: advisorName })}
          />
        ) : null}
      </div>

      <div className="space-y-2">
        <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Główne cele (wybór wielokrotny)
        </label>
        <div className="grid grid-cols-2 gap-2" data-testid="step1-goals">
          {STEP1_GOALS.map((g) => {
            const active = goals.includes(g.id);
            return (
              <button
                key={g.id}
                type="button"
                onClick={() => toggleGoal(g.id)}
                className={cn(
                  "rounded-md border px-3 py-2 text-left text-sm transition",
                  active
                    ? "border-sylion-blue/60 bg-sylion-blue/10 text-sylion-blue"
                    : "border-border hover:bg-muted/30",
                )}
                data-testid={`step1-goal-${g.id}`}
                data-active={active}
              >
                {g.label}
              </button>
            );
          })}
        </div>
        {advisorGoals ? (
          <SmartDefault
            label="Szybciej tworzyć oprogramowanie + kontrolować koszty"
            rationale="Większość operatorów zaczyna od tych celów; kolejne możesz włączyć później w Ustawienia → Doradca."
            onApply={() => onChange({ goals: advisorGoals })}
          />
        ) : null}
      </div>

      <div className="space-y-2">
        <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Jak często będziesz używać SYLION?
        </label>
        <div className="flex gap-2" data-testid="step1-cadence">
          {STEP1_CADENCES.map((c) => {
            const active = values.usage_cadence === c.id;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => onChange({ usage_cadence: c.id })}
                className={cn(
                  "flex-1 rounded-md border px-3 py-2 text-sm transition",
                  active
                    ? "border-sylion-blue/60 bg-sylion-blue/10 text-sylion-blue"
                    : "border-border hover:bg-muted/30",
                )}
                data-testid={`step1-cadence-${c.id}`}
                data-active={active}
              >
                {c.label}
              </button>
            );
          })}
        </div>
        {advisorCadence ? (
          <SmartDefault
            label="Co tydzień"
            rationale="Ustawia rytm podsumowań i częstotliwość aktualizacji uczenia miękkiego."
            onApply={() => onChange({ usage_cadence: advisorCadence })}
          />
        ) : null}
      </div>
    </div>
  );
}
