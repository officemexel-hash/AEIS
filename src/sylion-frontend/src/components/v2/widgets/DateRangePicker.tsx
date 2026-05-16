"use client";

/**
 * SYLION AEIS v2 — W16 G2 widget: DateRangePicker.
 *
 * Dwa natywne `<input type="date">` + szybkie presety: Dziś, 7 dni, 30 dni,
 * Ten miesiąc, Własny. Operator klika preset → start/end ustawiane
 * programatycznie. Brak zewnętrznej biblioteki kalendarza.
 */

import { useMemo } from "react";
import { Calendar } from "lucide-react";
import { Card } from "@/components/ui/card";
import { HelpTip } from "@/components/common/HelpTip";
import { cn } from "@/lib/utils";

export type DateRangePreset = "today" | "7d" | "30d" | "this_month" | "custom";

export interface DateRangePickerProps {
  value: { start: string; end: string };
  onChange: (value: { start: string; end: string }) => void;
  presets?: DateRangePreset[];
  helpText?: string;
}

const PRESET_LABEL_PL: Record<DateRangePreset, string> = {
  today: "Dziś",
  "7d": "7 dni",
  "30d": "30 dni",
  this_month: "Ten miesiąc",
  custom: "Własny",
};

const DEFAULT_PRESETS: DateRangePreset[] = [
  "today",
  "7d",
  "30d",
  "this_month",
  "custom",
];

const INPUT_CLS =
  "rounded-md border border-foreground/15 bg-background px-2 py-1.5 text-sm outline-none transition focus:border-sylion-blue/60 focus:ring-1 focus:ring-sylion-blue/40";

function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function rangeForPreset(
  preset: DateRangePreset,
  current: { start: string; end: string },
): { start: string; end: string } {
  const now = new Date();
  const today = isoDate(now);
  if (preset === "today") return { start: today, end: today };
  if (preset === "7d") {
    const start = new Date(now);
    start.setDate(start.getDate() - 6);
    return { start: isoDate(start), end: today };
  }
  if (preset === "30d") {
    const start = new Date(now);
    start.setDate(start.getDate() - 29);
    return { start: isoDate(start), end: today };
  }
  if (preset === "this_month") {
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    return { start: isoDate(start), end: today };
  }
  // custom — preserve current values; if empty, default to today
  return {
    start: current.start || today,
    end: current.end || today,
  };
}

function detectActivePreset(
  value: { start: string; end: string },
  presets: DateRangePreset[],
): DateRangePreset | null {
  for (const p of presets) {
    if (p === "custom") continue;
    const r = rangeForPreset(p, value);
    if (r.start === value.start && r.end === value.end) return p;
  }
  return presets.includes("custom") ? "custom" : null;
}

export function DateRangePicker({
  value,
  onChange,
  presets = DEFAULT_PRESETS,
  helpText,
}: DateRangePickerProps) {
  const activePreset = useMemo(
    () => detectActivePreset(value, presets),
    [value, presets],
  );

  function handleStart(e: React.ChangeEvent<HTMLInputElement>): void {
    onChange({ ...value, start: e.target.value });
  }

  function handleEnd(e: React.ChangeEvent<HTMLInputElement>): void {
    onChange({ ...value, end: e.target.value });
  }

  function handlePreset(preset: DateRangePreset): void {
    onChange(rangeForPreset(preset, value));
  }

  return (
    <Card size="sm" className="flex flex-col gap-2 px-3 py-3" data-slot="date-range-picker">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        <Calendar className="h-3 w-3" />
        Zakres dat
        {helpText && <HelpTip text={helpText} />}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1 text-xs text-muted-foreground">
          Od
          <input
            type="date"
            value={value.start}
            onChange={handleStart}
            className={INPUT_CLS}
            aria-label="Data początkowa"
          />
        </label>
        <label className="flex items-center gap-1 text-xs text-muted-foreground">
          Do
          <input
            type="date"
            value={value.end}
            onChange={handleEnd}
            className={INPUT_CLS}
            aria-label="Data końcowa"
          />
        </label>
      </div>

      <div className="flex flex-wrap gap-1">
        {presets.map((preset) => {
          const active = preset === activePreset;
          return (
            <button
              key={preset}
              type="button"
              onClick={() => handlePreset(preset)}
              className={cn(
                "rounded-full border px-2 py-0.5 text-[11px] transition",
                active
                  ? "border-sylion-blue/60 bg-sylion-blue/10 text-foreground"
                  : "border-foreground/10 text-muted-foreground hover:border-foreground/30 hover:text-foreground",
              )}
              aria-pressed={active}
            >
              {PRESET_LABEL_PL[preset]}
            </button>
          );
        })}
      </div>
    </Card>
  );
}
