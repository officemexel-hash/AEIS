"use client";

import { Gauge, Timer, DollarSign } from "lucide-react";
import { SmartDefault } from "./SmartDefault";
import { cn } from "@/lib/utils";

export interface QSCWeights {
  quality: number;
  speed: number;
  cost: number;
}

export interface Step7Values {
  quality_speed_cost?: QSCWeights;
}

export const DEFAULT_QSC: QSCWeights = { quality: 0.4, speed: 0.3, cost: 0.3 };

const TOLERANCE = 0.001;

export function isValidQSC(w: QSCWeights | undefined): boolean {
  if (!w) return false;
  const sum = w.quality + w.speed + w.cost;
  return Math.abs(sum - 1) <= TOLERANCE;
}

function rebalance(prev: QSCWeights, key: keyof QSCWeights, value: number): QSCWeights {
  const v = Math.max(0, Math.min(1, value));
  const others = (["quality", "speed", "cost"] as const).filter((k) => k !== key);
  const remaining = 1 - v;
  const prevOthersSum = prev[others[0]] + prev[others[1]];
  if (prevOthersSum <= 0) {
    const half = remaining / 2;
    return { ...prev, [key]: v, [others[0]]: half, [others[1]]: half } as QSCWeights;
  }
  const r0 = (prev[others[0]] / prevOthersSum) * remaining;
  const r1 = remaining - r0;
  return { ...prev, [key]: v, [others[0]]: r0, [others[1]]: r1 } as QSCWeights;
}

interface Props {
  values: Step7Values;
  onChange: (patch: Step7Values) => void;
}

const ROWS: Array<{ key: keyof QSCWeights; label: string; icon: typeof Gauge; tone: string; hint: string }> = [
  { key: "quality", label: "Jakość", icon: Gauge, tone: "text-sylion-blue", hint: "Wyżej = dokładniejsi sędziowie i większa Rada." },
  { key: "speed", label: "Prędkość", icon: Timer, tone: "text-sylion-amber", hint: "Wyżej = więcej równoległości, krótszy czas, mniejsza Rada." },
  { key: "cost", label: "Koszt", icon: DollarSign, tone: "text-sylion-green", hint: "Wyżej = silniejsza preferencja tanich modeli i ciaśniejsze limity." },
];

export function Step7QualitySpeedCost({ values, onChange }: Props) {
  const w = values.quality_speed_cost ?? DEFAULT_QSC;
  const sum = w.quality + w.speed + w.cost;
  const valid = isValidQSC(w);

  const update = (k: keyof QSCWeights, v: number) => {
    const next = rebalance(w, k, v);
    onChange({ quality_speed_cost: next });
  };
  const nudge = (k: keyof QSCWeights, delta: number) => {
    update(k, w[k] + delta);
  };

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        Dostosuj kompromis — przesunięcie jednego suwaka automatycznie równoważy pozostałe,
        żeby suma pozostała równa 1.0.
      </p>

      <div className="space-y-4" data-testid="step7-sliders">
        {ROWS.map((row) => {
          const Icon = row.icon;
          const v = w[row.key];
          return (
            <div key={row.key} className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className={cn("flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide", row.tone)}>
                  <Icon className="h-3.5 w-3.5" />
                  {row.label}
                </span>
                <span className="font-mono text-sm tabular-nums">{(v * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={v}
                onChange={(e) => update(row.key, parseFloat(e.target.value))}
                onInput={(e) => update(row.key, parseFloat(e.currentTarget.value))}
                className="w-full accent-sylion-blue"
                data-testid={`step7-${row.key}`}
                aria-label={`${row.label} - waga`}
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => nudge(row.key, -0.05)}
                  disabled={v <= 0}
                  className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted/30 disabled:cursor-not-allowed disabled:opacity-40"
                  data-testid={`step7-${row.key}-dec`}
                >
                  -
                </button>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={Math.round(v * 100)}
                  onChange={(e) => update(row.key, parseFloat(e.target.value) / 100)}
                  className="w-20 rounded-md border border-border bg-background px-2 py-1 text-center text-xs font-mono outline-none focus:border-sylion-blue/60"
                  data-testid={`step7-${row.key}-number`}
                  aria-label={`${row.label} - waga procentowa`}
                />
                <button
                  type="button"
                  onClick={() => nudge(row.key, 0.05)}
                  disabled={v >= 1}
                  className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted/30 disabled:cursor-not-allowed disabled:opacity-40"
                  data-testid={`step7-${row.key}-inc`}
                >
                  +
                </button>
                <span className="text-[11px] text-muted-foreground">
                  precyzyjna kontrola procentowa
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground">{row.hint}</p>
            </div>
          );
        })}
      </div>

      <div
        className={cn(
          "rounded-md border px-3 py-2 text-xs",
          valid
            ? "border-sylion-green/30 bg-sylion-green/5 text-sylion-green"
            : "border-sylion-red/30 bg-sylion-red/5 text-sylion-red",
        )}
        data-testid="step7-sum"
      >
        Suma: <span className="font-mono">{sum.toFixed(2)}</span>
        {valid ? " — zbalansowane" : " — musi wynosić 1.00"}
      </div>

      <SmartDefault
        label="Reset do 0.40 / 0.30 / 0.30 (Jakość / Prędkość / Koszt)"
        rationale="Domyślne ustawieńie z master spec — lekki priorytet jakości bez spalania budżetu."
        onApply={() => onChange({ quality_speed_cost: { ...DEFAULT_QSC } })}
      />
    </div>
  );
}
