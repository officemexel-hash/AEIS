"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { HelpCircle, X } from "lucide-react";
import { FAQ_ENTRIES } from "@/data/faq-entries";

export function HelpHint({ contextKey }: { contextKey: string }) {
  const entries = FAQ_ENTRIES.filter((e) => e.contextHints.includes(contextKey));
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  if (entries.length === 0) return null;

  return (
    <div ref={ref} className="relative inline-flex items-center">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center justify-center w-5 h-5 rounded-full transition-colors duration-150"
        style={{ color: open ? "oklch(0.6 0.15 260)" : "oklch(0.45 0.01 260)" }}
        aria-label="Pomoc kontekstowa"
        aria-expanded={open}
      >
        <HelpCircle className="w-4 h-4" />
      </button>

      {open && (
        <div
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-80 rounded-lg border shadow-xl"
          style={{
            backgroundColor: "oklch(0.15 0.005 280)",
            borderColor: "rgba(148,163,184,0.12)",
            boxShadow: "0 8px 32px oklch(0 0 0 / 40%)",
          }}
        >
          <div
            className="flex items-center justify-between px-3 py-2 border-b"
            style={{ borderBottomColor: "rgba(148,163,184,0.08)" }}
          >
            <span
              className="text-[11px] uppercase tracking-widest font-semibold"
              style={{ color: "oklch(0.52 0.01 260)" }}
            >
              Pomoc kontekstowa
            </span>
            <button
              onClick={() => setOpen(false)}
              style={{ color: "oklch(0.45 0.01 260)" }}
              aria-label="Zamknij"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="p-3 space-y-3">
            {entries.map((e) => (
              <div key={e.id}>
                <p className="text-sm font-medium mb-0.5" style={{ color: "oklch(0.88 0.01 260)" }}>
                  {e.question}
                </p>
                <p className="text-xs leading-relaxed mb-1" style={{ color: "oklch(0.55 0.01 260)" }}>
                  {e.shortAnswer}
                </p>
                <Link
                  href={`/faq#${e.id}`}
                  className="text-xs font-medium"
                  style={{ color: "oklch(0.6 0.15 260)" }}
                  onClick={() => setOpen(false)}
                >
                  Zobacz pelna odpowiedz →
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
