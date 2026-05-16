"use client";

import { useAdvisorMode } from "@/components/layout/useAdvisorMode";
import { Wrench, UserCog } from "lucide-react";
import { motion } from "framer-motion";

/**
 * Operator vs Technical mode toggle. Lives in the TopCommandBar so it is
 * always visible. Persists via localStorage (sylion.advisor.mode).
 *
 * Polish labels by default:
 *   - "Operator" — tryb operatora (sidebar pokazuje sekcje Doradca/Projekty/Decyzje/Konfiguracja)
 *   - "Techniczny" — tryb techniczny (pełen legacy nav)
 */
export function ModeSwitcher() {
  const { mode, setMode } = useAdvisorMode();
  const isOperator = mode === "operator";

  return (
    <div
      className="inline-flex items-center gap-0 rounded-lg p-0.5 text-[11px] transition-colors duration-300"
      style={{
        backgroundColor: isOperator ? "oklch(0.14 0.01 280 / 60%)" : "oklch(0.12 0.005 240 / 60%)",
        border: isOperator
          ? "1px solid oklch(0.55 0.15 260 / 20%)"
          : "1px solid oklch(0.5 0.08 240 / 15%)",
      }}
      data-testid="mode-switcher"
      role="group"
      aria-label="Tryb interfejsu"
    >
      <button
        type="button"
        onClick={() => setMode("operator")}
        aria-pressed={isOperator}
        className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-all duration-200 cursor-pointer"
        style={{
          color: isOperator ? "oklch(0.93 0.01 260)" : "oklch(0.5 0.01 260)",
          backgroundColor: isOperator ? "oklch(0.55 0.18 260 / 25%)" : "transparent",
          border: isOperator ? "1px solid oklch(0.55 0.18 260 / 30%)" : "1px solid transparent",
        }}
        data-mode="operator"
        title="Tryb operatora — uproszczony interfejs dla codziennej pracy"
      >
        <UserCog className="w-3.5 h-3.5" />
        <span className="font-medium">Operator</span>
        {isOperator && (
          <motion.span
            layoutId="mode-switcher-dot"
            className="w-1 h-1 rounded-full ml-0.5"
            style={{ backgroundColor: "oklch(0.65 0.15 260)" }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
          />
        )}
      </button>
      <button
        type="button"
        onClick={() => setMode("technical")}
        aria-pressed={!isOperator}
        className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-all duration-200 cursor-pointer"
        style={{
          color: !isOperator ? "oklch(0.93 0.01 260)" : "oklch(0.5 0.01 260)",
          backgroundColor: !isOperator ? "oklch(0.6 0.14 45 / 25%)" : "transparent",
          border: !isOperator ? "1px solid oklch(0.65 0.16 45 / 30%)" : "1px solid transparent",
        }}
        data-mode="technical"
        title="Tryb techniczny — pełen dostęp dla deweloperów"
      >
        <Wrench className="w-3.5 h-3.5" />
        <span className="font-medium">Techniczny</span>
        {!isOperator && (
          <motion.span
            layoutId="mode-switcher-dot"
            className="w-1 h-1 rounded-full ml-0.5"
            style={{ backgroundColor: "oklch(0.75 0.14 45)" }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
          />
        )}
      </button>
    </div>
  );
}
