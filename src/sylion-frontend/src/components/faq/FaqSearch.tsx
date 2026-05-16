"use client";

import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface FaqSearchProps {
  value: string;
  onChange: (v: string) => void;
  resultCount?: number;
}

export function FaqSearch({ value, onChange, resultCount }: FaqSearchProps) {
  return (
    <div className="relative">
      <div className="relative flex items-center">
        <Search
          className="absolute left-3 w-4 h-4 pointer-events-none"
          style={{ color: "oklch(0.5 0.01 260)" }}
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Szukaj w FAQ..."
          className={cn(
            "w-full rounded-lg border pl-9 pr-9 py-2.5 text-sm outline-none transition-colors duration-150",
            "placeholder:text-[oklch(0.45_0.01_260)]"
          )}
          style={{
            backgroundColor: "oklch(0.16 0.005 280)",
            borderColor: value ? "oklch(0.55 0.15 260 / 40%)" : "rgba(148,163,184,0.1)",
            color: "oklch(0.93 0.01 260)",
          }}
        />
        {value && (
          <button
            onClick={() => onChange("")}
            className="absolute right-3 rounded transition-colors duration-150"
            style={{ color: "oklch(0.5 0.01 260)" }}
            aria-label="Wyczysc wyszukiwanie"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {value && (
        <p className="mt-1.5 text-xs" style={{ color: "oklch(0.5 0.01 260)" }}>
          {resultCount === 0
            ? "Brak wyników"
            : `${resultCount} ${resultCount === 1 ? "wynik" : "wyników"}`}
        </p>
      )}
    </div>
  );
}
