"use client";

import { usePathname, useRouter } from "next/navigation";
import { useSidebar } from "@/components/layout/SidebarContext";
import { useAdvisorMode } from "@/components/layout/useAdvisorMode";
import {
  Search,
  ChevronDown,
  Zap,
  ShieldAlert,
  LogOut,
  User,
  Settings,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ModeSwitcher } from "@/components/layout/ModeSwitcher";
import { ModeBadge } from "@/components/layout/ModeBadge";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";

type InstanceMode = "NORMAL" | "INCIDENT" | "REBUILD";

const modeConfig: Record<
  InstanceMode,
  { label: string; color: string; bg: string }
> = {
  NORMAL: {
    label: "NORMALNY",
    color: "oklch(0.65 0.18 150)",
    bg: "oklch(0.65 0.18 150 / 12%)",
  },
  INCIDENT: {
    label: "INCYDENT",
    color: "oklch(0.6 0.22 25)",
    bg: "oklch(0.6 0.22 25 / 12%)",
  },
  REBUILD: {
    label: "ODBUDOWA",
    color: "oklch(0.72 0.16 55)",
    bg: "oklch(0.72 0.16 55 / 12%)",
  },
};

const pageTitles: Record<string, string> = {
  "/advisor": "Doradca na żywo",
  "/onboarding": "Pierwsze uruchomienie",
  "/dashboard/operator-monitor": "Monitor projektów",
  "/projects": "Projekty",
  "/project-start": "Start projektu",
  "/council-to-ksiega": "Deliberacja i Księga",
  "/planning": "Planowanie",
  "/execution-start": "Start wykonania",
  "/architecture-layers": "Warstwy AEIS W1-W19",
  "/idea-vault": "Skarbiec pomysłów",
  "/funding": "Granty i finansowanie",
  "/decisions": "Decyzje",
  "/governance": "Rada",
  "/human-gate": "Bramka człowieka",
  "/evidence": "Pakiety dowodowe",
  "/evidence-spine": "Kręgosłup dowodowy",
  "/audit": "Ścieżka audytu",
  "/settings/advisor": "Ustawienia doradcy",
  "/ai-models": "Modele AI",
  "/workspace-defaults": "Domyślny obszar pracy",
  "/coherence-guard": "Strażnik spójności",
  "/cost-guard": "Strażnik kosztów",
  "/security-guard": "Strażnik bezpieczeństwa",
  "/quality-guard": "Strażnik jakości",
  "/provenance-guard": "Strażnik pochodzenia",
  "/templates-setup": "Szablony",
  "/environments": "Środowiska",
  "/skills": "Umiejętności",
  "/budget": "Budżet modeli",
  "/secrets": "Klucze API",
  "/overview": "Przegląd techniczny",
  "/book": "Księga",
  "/agents": "Agenci",
  "/modules": "Moduły",
  "/health": "Zdrowie systemu",
  "/contracts": "Kontrakty",
  "/performance": "Wydajność",
  "/rebuild": "Odbudowa",
  "/autonomy": "Autonomia",
  "/lifecycle": "Cykl życia",
  "/orchestration/llm-routing": "Trasy LLM",
  "/orchestration/council-rules": "Reguły rady",
  "/orchestration/auditor": "Audytor",
  "/orchestration/fixer": "Naprawiacze",
  "/orchestration/dispatch": "Rozdział pracy",
  "/orchestration/tests": "Katalog testów",
  "/orchestration/teams": "Zespoły",
  "/orchestration/event-map": "Mapa eventów",
  "/orchestration/conversations": "Rozmowy AI",
};

function getPageTitle(pathname: string | null): string {
  if (!pathname) return "SYLION";
  if (pageTitles[pathname]) return pageTitles[pathname];
  const parent = "/" + pathname.split("/").filter(Boolean)[0];
  return pageTitles[parent] ?? "SYLION";
}

export function TopCommandBar() {
  const pathname = usePathname();
  const router = useRouter();

  // F-bug-dropdown: dropdown items (Profil/Preferencje/Wyloguj) had no
  // handlers and felt dead. Wire them up to existing routes; logout
  // clears any local session token and routes back to /onboarding which
  // is the canonical entry point for re-auth.
  const handleProfile = () => router.push("/settings/profile");
  const handlePreferences = () => router.push("/settings");
  const handleLogout = () => {
    try {
      // Best-effort cleanup of any client-side session state. Backend
      // session is HTTP-only cookie or stateless — nothing to nuke here.
      window.localStorage.removeItem("sylion-session");
      window.localStorage.removeItem("sylion-mode");
      window.sessionStorage.clear();
    } catch {
      /* localStorage may be unavailable in SSR or strict mode */
    }
    router.push("/onboarding");
  };
  const { collapsed } = useSidebar();
  const { mode } = useAdvisorMode();
  const isOperator = mode === "operator";

  const modeState: InstanceMode = "NORMAL";
  const modeCfg = modeConfig[modeState];
  const activeAgents = 4;
  const governanceAlerts = 0;
  const pageTitle = getPageTitle(pathname);

  return (
    <header
      className={cn(
        "fixed top-0 right-0 z-30 h-14 flex items-center justify-between px-5 border-b transition-colors duration-300",
        isOperator ? "operator-topbar" : "technical-topbar"
      )}
      style={{
        left: collapsed ? 64 : 256,
        backgroundColor: isOperator ? "oklch(0.13 0.005 280)" : "oklch(0.11 0.005 240)",
        borderBottomColor: "rgba(148,163,184,0.08)",
      }}
    >
      {/* Left: mode badge + breadcrumb / page title */}
      <div className="flex items-center gap-3 min-w-0">
        <ModeBadge />

        <span
          className="text-[11px] tracking-wider uppercase transition-colors duration-300"
          style={{ color: isOperator ? "oklch(0.45 0.01 260)" : "oklch(0.4 0.01 260)" }}
        >
          SYLION AEIS
        </span>
        <span style={{ color: "oklch(0.25 0.01 260)" }}>/</span>
        <span
          className={cn(
            "font-medium truncate transition-colors duration-300",
            isOperator ? "text-sm" : "text-[13px]"
          )}
          style={{ color: "oklch(0.88 0.01 260)" }}
        >
          {pageTitle}
        </span>
        <HelpTip
          className="ml-0 h-4 w-4 border-muted-foreground/30"
          size={13}
          text={`Jesteś na ekranie: ${pageTitle}. Ten HelpTip opisuje aktualną powierzchnię dashboardu; szczegółowe kółka z pytajnikiem przy sekcjach wyjaśniają konkretne akcje i ryzyka.`}
        />
      </div>

      {/* Center: search bar (cmd+K style placeholder) */}
      <div
        className="hidden md:flex items-center gap-2 rounded-lg px-3 py-1.5 w-72 lg:w-80 border cursor-default select-none transition-colors duration-300"
        style={{
          backgroundColor: isOperator
            ? "oklch(0.14 0.005 280 / 60%)"
            : "oklch(0.12 0.005 240 / 60%)",
          borderColor: "rgba(148,163,184,0.08)",
        }}
      >
        <Search
          className="w-3.5 h-3.5 shrink-0"
          style={{ color: "oklch(0.45 0.01 260)" }}
        />
        <span
          className="text-xs truncate"
          style={{ color: "oklch(0.4 0.01 260)" }}
        >
          Szukaj modułów, agentów, decyzji…
        </span>
        <kbd
          className="ml-auto text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0"
          style={{
            color: "oklch(0.4 0.01 260)",
            backgroundColor: isOperator
              ? "oklch(0.16 0.005 280)"
              : "oklch(0.14 0.005 240)",
            border: "1px solid rgba(148,163,184,0.08)",
          }}
        >
          {typeof navigator !== "undefined" &&
          /Mac|iPhone/.test(navigator.userAgent)
            ? "\u2318K"
            : "Ctrl+K"}
        </kbd>
      </div>

      {/* Right section */}
      <div className="flex items-center gap-2.5">
        <ModeSwitcher />

        {/* Instance mode badge */}
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold tracking-wider uppercase"
          style={{
            color: modeCfg.color,
            backgroundColor: modeCfg.bg,
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ backgroundColor: modeCfg.color }}
          />
          {modeCfg.label}
        </span>

        {/* System status dot */}
        <div className="relative flex items-center justify-center w-5 h-5">
          <span
            className="absolute w-2 h-2 rounded-full animate-ping"
            style={{
              backgroundColor: "oklch(0.65 0.18 150 / 40%)",
            }}
          />
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: "oklch(0.65 0.18 150)" }}
          />
        </div>

        {/* Active agents chip */}
        <span
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium"
          style={{
            color: "oklch(0.55 0.2 260)",
            backgroundColor: "oklch(0.55 0.2 260 / 10%)",
            border: "1px solid oklch(0.55 0.2 260 / 15%)",
          }}
        >
          <Zap className="w-3 h-3" />
          {activeAgents}
        </span>

        {/* Governance alerts */}
        {governanceAlerts > 0 ? (
          <span
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium"
            style={{
              color: "oklch(0.72 0.16 55)",
              backgroundColor: "oklch(0.72 0.16 55 / 10%)",
              border: "1px solid oklch(0.72 0.16 55 / 15%)",
            }}
          >
            <ShieldAlert className="w-3 h-3" />
            {governanceAlerts}
          </span>
        ) : (
          <span
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium"
            style={{
              color: "oklch(0.48 0.01 260)",
              backgroundColor: isOperator
                ? "oklch(0.14 0.005 280)"
                : "oklch(0.12 0.005 240)",
              border: "1px solid rgba(148,163,184,0.08)",
            }}
          >
            <ShieldAlert className="w-3 h-3" />
            0
          </span>
        )}

        {/* Separator */}
        <div
          className="h-5 w-px mx-0.5"
          style={{ backgroundColor: "rgba(148,163,184,0.08)" }}
        />

        {/* Operator avatar dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger className="flex items-center gap-2 cursor-pointer rounded-md px-1.5 py-1 transition-colors hover:bg-white/5 outline-none">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold"
              style={{
                background:
                  "linear-gradient(135deg, oklch(0.55 0.2 260 / 25%), oklch(0.45 0.25 240 / 15%))",
                color: "oklch(0.75 0.15 260)",
                border: "1px solid oklch(0.55 0.2 260 / 20%)",
              }}
            >
              OP
            </div>
            <ChevronDown
              className="w-3 h-3"
              style={{ color: "oklch(0.45 0.01 260)" }}
            />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            sideOffset={8}
            className="w-48"
            style={{
              backgroundColor: "#0a0f1e",
              border: "1px solid rgba(148,163,184,0.1)",
            }}
          >
            <div className="px-2 py-1.5">
              <div
                className="text-sm font-medium"
                style={{ color: "oklch(0.88 0.01 260)" }}
              >
                Operator
              </div>
              <div
                className="text-[11px]"
                style={{ color: "oklch(0.45 0.01 260)" }}
              >
                operator@sylion.local
              </div>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleProfile}>
              <User className="w-4 h-4 mr-2" />
              Profil
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handlePreferences}>
              <Settings className="w-4 h-4 mr-2" />
              Preferencje
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onClick={handleLogout}>
              <LogOut className="w-4 h-4 mr-2" />
              Wyloguj
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
