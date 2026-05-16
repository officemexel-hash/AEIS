"use client";

import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  rationale?: string;
  onApply: () => void;
  className?: string;
}

export function SmartDefault({ label, rationale, onApply, className }: Props) {
  return (
    <button
      type="button"
      onClick={onApply}
      className={cn(
        "group flex w-full items-start gap-3 rounded-md border border-sylion-blue/30 bg-sylion-blue/5 px-3 py-2.5 text-left transition hover:bg-sylion-blue/10",
        className,
      )}
    >
      <Sparkles className="mt-0.5 h-4 w-4 flex-none text-sylion-blue" />
      <div className="flex-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-sylion-blue">Doradca sugeruje</p>
        <p className="mt-0.5 text-sm font-medium">{label}</p>
        {rationale ? <p className="mt-1 text-xs text-muted-foreground">{rationale}</p> : null}
      </div>
      <span className="self-center text-[11px] font-medium text-sylion-blue underline-offset-2 group-hover:underline">
        zastosuj
      </span>
    </button>
  );
}
