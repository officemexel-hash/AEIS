"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Sparkles, X } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const LS_DISMISS_KEY = "sylion.firstrun.dismissed";
const LS_LOCAL_FLAG = "sylion.advisor.onboarding";

/**
 * Top-of-page banner shown until the operator has completed the onboarding
 * wizard. Polls /api/v1/advisor/onboarding/has_completed; falls back to the
 * local-storage onboarding state if the backend is unreachable.
 *
 * Hidden when:
 *   1. backend reports completed=true
 *   2. localStorage onboarding has `phase1_completed_at` or `completed_at` set
 *   3. user has explicitly dismissed the banner this session
 *   4. we are already on /onboarding
 *   5. operator is inside a working module; the banner must not obscure
 *      runtime dashboards or make configured modules look blocked.
 */
export function FirstRunBanner({ pathname }: { pathname: string | null }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const canShowOnPath = !pathname || pathname === "/" || pathname === "/overview" || pathname.startsWith("/onboarding");
    if (!pathname || pathname.startsWith("/onboarding") || !canShowOnPath) {
      queueMicrotask(() => {
        if (!cancelled) setShow(false);
      });
      return () => {
        cancelled = true;
      };
    }

    (async () => {
      // Local dismiss takes precedence per session.
      try {
        if (window.sessionStorage.getItem(LS_DISMISS_KEY) === "1") {
          if (!cancelled) setShow(false);
          return;
        }
      } catch {
        // ignore
      }

      // Local wizard state: Phase 1 or legacy onboarding completion hides it.
      try {
        const raw = window.localStorage.getItem(LS_LOCAL_FLAG);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed?.phase1_completed_at || parsed?.completed_at) {
            if (!cancelled) setShow(false);
            return;
          }
        }
      } catch {
        // ignore
      }

      // Ask the backend.
      try {
        const res = await fetch(`${API_BASE}/api/v1/advisor/onboarding/has_completed`, {
          signal: AbortSignal.timeout(2500),
        });
        if (res.ok) {
          const data = await res.json();
          if (!cancelled) setShow(!data?.completed);
          return;
        }
      } catch {
        // backend unreachable — fall through and show banner
      }
      if (!cancelled) setShow(true);
    })();

    return () => {
      cancelled = true;
    };
  }, [pathname]);

  if (!show) return null;

  return (
    <div
      className="mx-6 mt-4 flex items-start gap-3 rounded-lg border px-4 py-3 text-sm"
      style={{
        backgroundColor: "oklch(0.55 0.2 260 / 8%)",
        borderColor: "oklch(0.55 0.2 260 / 25%)",
        color: "oklch(0.93 0.01 260)",
      }}
      data-testid="firstrun-banner"
      role="region"
      aria-label="Powitanie operatora"
    >
      <Sparkles className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "oklch(0.75 0.15 260)" }} />
      <div className="flex-1">
        <div className="font-medium">Witaj w SYLION AEIS — skonfiguruj Fazę 1.</div>
        <div className="mt-0.5 text-[12px]" style={{ color: "oklch(0.75 0.01 260)" }}>
          8 kroków: system check, tożsamość, storage, security, profil, tutorial,
          hard gate modelu i acceptance. Pełne klucze API, budżety, rada i pierwszy
          projekt są dostępne po zakończeniu tej fazy.
        </div>
      </div>
      <Link
        href="/onboarding"
        className="shrink-0 rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors"
        style={{
          backgroundColor: "oklch(0.55 0.2 260 / 25%)",
          color: "oklch(0.93 0.01 260)",
          border: "1px solid oklch(0.55 0.2 260 / 35%)",
        }}
        data-testid="firstrun-banner-cta"
      >
        Otwórz Fazę 1
      </Link>
      <button
        type="button"
        aria-label="Ukryj komunikat"
        className="shrink-0 rounded-md p-1 text-[oklch(0.55_0.01_260)] transition-colors hover:text-white"
        onClick={() => {
          try {
            window.sessionStorage.setItem(LS_DISMISS_KEY, "1");
          } catch {
            // ignore
          }
          setShow(false);
        }}
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
