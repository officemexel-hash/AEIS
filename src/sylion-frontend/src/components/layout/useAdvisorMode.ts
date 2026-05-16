"use client";

import { useEffect, useState } from "react";

export type AdvisorMode = "operator" | "technical";

const STORAGE_KEY = "sylion.advisor.mode";

function readInitial(): AdvisorMode {
  if (typeof window === "undefined") return "operator";
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    if (v === "technical") return "technical";
  } catch {
    // ignore
  }
  return "operator";
}

/**
 * Shared hook for the operator vs technical UI mode.
 *
 * - Default: operator. Sidebar hides legacy/technical sections.
 * - Switching to `technical` exposes the legacy navigation tree.
 * - State persists in localStorage and broadcasts via a custom event so other
 *   listeners (sidebar, top bar, banner) re-render in lockstep.
 */
export function useAdvisorMode(): {
  mode: AdvisorMode;
  setMode: (next: AdvisorMode) => void;
  toggle: () => void;
} {
  const [mode, setModeState] = useState<AdvisorMode>("operator");

  useEffect(() => {
    setModeState(readInitial());
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<AdvisorMode>).detail;
      if (detail === "operator" || detail === "technical") setModeState(detail);
    };
    window.addEventListener("sylion:advisor-mode", onChange as EventListener);
    return () => window.removeEventListener("sylion:advisor-mode", onChange as EventListener);
  }, []);

  function setMode(next: AdvisorMode) {
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
    window.dispatchEvent(new CustomEvent("sylion:advisor-mode", { detail: next }));
    setModeState(next);
  }

  return {
    mode,
    setMode,
    toggle: () => setMode(mode === "operator" ? "technical" : "operator"),
  };
}
