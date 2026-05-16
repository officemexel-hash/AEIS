"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight } from "lucide-react";
import { useOnboarding } from "@/lib/hooks/advisor";
import { cn } from "@/lib/utils";

interface Props {
  className?: string;
}

export function IncompleteBanner({ className }: Props) {
  const { state } = useOnboarding();
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    queueMicrotask(() => setMounted(true));
  }, []);
  if (!mounted) return null;
  if (state.phase1_completed_at || state.completed_at) return null;

  const total = 8;
  const done = Math.min(state.completed_steps.length, total);

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-md border border-sylion-amber/30 bg-sylion-amber/5 px-3 py-2 text-xs text-sylion-amber",
        className,
      )}
      data-testid="onboarding-incomplete-banner"
      role="alert"
    >
      <AlertCircle className="h-4 w-4 flex-none" />
      <span className="flex-1">
        Faza 1 niekompletna (<span className="font-mono">{done}/{total}</span> kroków).
        Dokończ setup operatora, storage, security i hard gate modelu.
      </span>
      <Link
        href="/onboarding"
        className="inline-flex items-center gap-1 rounded-md border border-sylion-amber/40 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide hover:bg-sylion-amber/10"
      >
        Wznów <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}
