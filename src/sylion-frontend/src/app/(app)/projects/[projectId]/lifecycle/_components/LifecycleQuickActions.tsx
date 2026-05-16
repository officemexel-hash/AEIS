"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Keyboard, ChevronLeft, ChevronRight, Search, HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  onNext: () => void;
  onPrev: () => void;
  onFocusSearch?: () => void;
  className?: string;
}

const SHORTCUTS = [
  { keys: ["j"], description: "Nastepna faza" },
  { keys: ["k"], description: "Poprzednia faza" },
  { keys: ["/"], description: "Fokus na wyszukiwarke" },
  { keys: ["?"], description: "Pokaz lub ukryj pomoc" },
];

export function LifecycleQuickActions({ onNext, onPrev, onFocusSearch, className }: Props) {
  const [overlayOpen, setOverlayOpen] = useState(false);

  useEffect(() => {
    function handler(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      if (event.key === "j") {
        event.preventDefault();
        onNext();
      } else if (event.key === "k") {
        event.preventDefault();
        onPrev();
      } else if (event.key === "/") {
        event.preventDefault();
        onFocusSearch?.();
      } else if (event.key === "?") {
        event.preventDefault();
        setOverlayOpen((v) => !v);
      } else if (event.key === "Escape") {
        setOverlayOpen(false);
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onNext, onPrev, onFocusSearch]);

  return (
    <Card
      className={cn("flex flex-wrap items-center justify-between gap-2 bg-card p-2", className)}
      data-testid="lifecycle-quick-actions"
    >
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="sm"
          onClick={onPrev}
          className="h-7 gap-1 px-2 text-[11px]"
          data-testid="qa-prev"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          k
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onNext}
          className="h-7 gap-1 px-2 text-[11px]"
          data-testid="qa-next"
        >
          j
          <ChevronRight className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onFocusSearch}
          className="h-7 gap-1 px-2 text-[11px]"
          data-testid="qa-search"
        >
          <Search className="h-3.5 w-3.5" />/
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setOverlayOpen((v) => !v)}
          className="h-7 gap-1 px-2 text-[11px]"
          data-testid="qa-help"
        >
          <HelpCircle className="h-3.5 w-3.5" />?
        </Button>
      </div>
      <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
        <Keyboard className="h-3 w-3" />
        Szybkie akcje lifecycle
      </span>

      {overlayOpen ? (
        <div
          className="fixed inset-0 z-40 flex items-end justify-end bg-black/30 p-6 sm:items-center sm:justify-center"
          role="dialog"
          aria-modal="true"
          onClick={() => setOverlayOpen(false)}
          data-testid="lifecycle-quick-actions-overlay"
        >
          <Card
            className="w-full max-w-sm space-y-2 bg-popover p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold">Skr?ty klawiaturowe</h4>
              <span className="text-[10px] text-muted-foreground">esc zamyka</span>
            </div>
            <ul className="space-y-1.5">
              {SHORTCUTS.map((shortcut) => (
                <li
                  key={shortcut.description}
                  className="flex items-center justify-between rounded border border-border/40 bg-muted/10 px-2 py-1 text-xs"
                >
                  <span>{shortcut.description}</span>
                  <span className="flex gap-1">
                    {shortcut.keys.map((k) => (
                      <kbd
                        key={k}
                        className="rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10px]"
                      >
                        {k}
                      </kbd>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      ) : null}
    </Card>
  );
}
