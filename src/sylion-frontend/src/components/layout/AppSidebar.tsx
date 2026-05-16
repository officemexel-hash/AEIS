"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useSidebar } from "@/components/layout/SidebarContext";
import { useAdvisorMode } from "@/components/layout/useAdvisorMode";
import { advisorApi, DEFAULT_OPERATOR_ID } from "@/lib/api/advisor";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Lightbulb,
  Wrench,
  BookOpen,
  FolderKanban,
  Users,
  Boxes,
  Shield,
  ShieldAlert,
  FileCheck,
  FileLock,
  Bell,
  GitBranch,
  Activity,
  ScrollText,
  Gauge,
  RefreshCw,
  Brain,
  RotateCcw,
  Settings,
  PanelLeftClose,
  PanelLeft,
  Smartphone,
  DollarSign,
  Radio,
  Signal,
  Rocket,
  Columns2,
  ShieldCheck,
  GitCompare,
  AlertTriangle,
  HeartPulse,
  ChevronDown,
  Zap,
  TestTube,
  Package,
  ClipboardCheck,
  Link2,
  LinkIcon,
  KeyRound,
  Search,
  Fingerprint,
  Compass,
  Sparkles,
  Settings2,
  MessageSquare,
  HelpCircle,
  Terminal,
  Database,
  UserCog,
  AppWindow,
  Server,
  type LucideIcon,
} from "lucide-react";

type NavItem = { href: string; label: string; icon: LucideIcon };

// ---------------------------------------------------------------------------
// Operator-mode nav: 4 sections, all Polish.
// ---------------------------------------------------------------------------

const advisorItems: NavItem[] = [
  { href: "/advisor/cockpit", label: "Centrum dowodzenia", icon: Sparkles },
  { href: "/advisor", label: "Doradca na żywo", icon: Compass },
  { href: "/dashboard/operator-monitor", label: "Monitor projektów", icon: Activity },
  { href: "/onboarding", label: "Pierwsze uruchomienie", icon: Sparkles },
];

const projectItems: NavItem[] = [
  { href: "/projects", label: "Projekty", icon: FolderKanban },
  { href: "/project-start", label: "Start projektu", icon: Rocket },
  { href: "/council-to-ksiega", label: "Deliberacja i Księga", icon: BookOpen },
  { href: "/planning", label: "Planowanie", icon: ClipboardCheck },
  { href: "/execution-start", label: "Start wykonania", icon: Activity },
  { href: "/idea-vault", label: "Skarbiec pomysłów", icon: Lightbulb },
];

const fundingItems: NavItem[] = [
  { href: "/funding", label: "Doradca grantów", icon: DollarSign },
];

const decisionItems: NavItem[] = [
  { href: "/decisions", label: "Decyzje", icon: GitBranch },
  { href: "/governance", label: "Rada", icon: Users },
  { href: "/human-gate", label: "Bramka człowieka", icon: ShieldAlert },
  { href: "/evidence", label: "Pakiety dowodowe", icon: FileCheck },
  { href: "/audit", label: "Ścieżka audytu", icon: FileLock },
];

const testingItems: NavItem[] = [
  { href: "/test-center", label: "Centrum testów (W14)", icon: TestTube },
];

const configItems: NavItem[] = [
  { href: "/settings/advisor", label: "Ustawienia doradcy", icon: Settings },
  { href: "/ai-models", label: "Modele AI", icon: Brain },
  { href: "/workspace-defaults", label: "Domyślny obszar pracy", icon: Settings2 },
  { href: "/coherence-guard", label: "Strażnik spójności", icon: ShieldCheck },
  { href: "/cost-guard", label: "Strażnik kosztów", icon: DollarSign },
  { href: "/security-guard", label: "Strażnik bezpieczeństwa", icon: ShieldAlert },
  { href: "/quality-guard", label: "Strażnik jakości", icon: TestTube },
  { href: "/provenance-guard", label: "Strażnik pochodzenia", icon: FileLock },
  { href: "/templates-setup", label: "Szablony", icon: Package },
  { href: "/environments", label: "Środowiska", icon: Server },
  { href: "/skills", label: "Umiejętności", icon: Wrench },
  { href: "/budget", label: "Budżet modeli", icon: DollarSign },
  { href: "/secrets", label: "Klucze API", icon: KeyRound },
];

const helpItems: NavItem[] = [
  { href: "/faq", label: "Pomoc i FAQ", icon: HelpCircle },
];

const aeisV2Items: NavItem[] = [
  { href: "/v2/admin", label: "Przegląd administracyjny", icon: Gauge },
  { href: "/architecture-layers", label: "Warstwy AEIS (W1-W19)", icon: Boxes },
  { href: "/ontology", label: "Ontologia (W15)", icon: Database },
  { href: "/apps-builder", label: "Kreator aplikacji (W16)", icon: AppWindow },
  { href: "/terminal", label: "Terminal (W18)", icon: Terminal },
  { href: "/role-catalog", label: "Katalog ról (W7)", icon: UserCog },
  { href: "/federation", label: "Federacja (W17)", icon: Signal },
  { href: "/policy", label: "Polityki systemu (W19)", icon: Shield },
];

const orchestrationItems: NavItem[] = [
  { href: "/orchestration/llm-routing", label: "Trasy LLM", icon: Brain },
  { href: "/orchestration/council-rules", label: "Reguły rady", icon: Users },
  { href: "/orchestration/auditor", label: "Audytor", icon: ShieldCheck },
  { href: "/orchestration/fixer", label: "Naprawiacze", icon: Wrench },
  { href: "/orchestration/dispatch", label: "Rozdział pracy", icon: GitBranch },
  { href: "/orchestration/tests", label: "Katalog testów", icon: TestTube },
  { href: "/orchestration/teams", label: "Zespoły", icon: Users },
  { href: "/orchestration/event-map", label: "Mapa eventów", icon: Activity },
  { href: "/orchestration/conversations", label: "Rozmowy AI", icon: MessageSquare },
];

const operatorTestingItems: NavItem[] = [
  ...testingItems,
  { href: "/test-center/theater", label: "Teatr modeli", icon: Users },
];

const operatorConfigItems: NavItem[] = [
  ...configItems.slice(0, 4),
  { href: "/guards", label: "Panel strażników", icon: Shield },
  ...configItems.slice(4, 10),
  { href: "/environments/theater", label: "Teatr środowisk", icon: Activity },
  ...configItems.slice(10),
];

// ---------------------------------------------------------------------------
// Technical-mode nav: legacy structure (advanced operators).
// ---------------------------------------------------------------------------

const technicalCore: NavItem[] = [
  { href: "/overview", label: "Przegląd", icon: LayoutDashboard },
  { href: "/pipeline", label: "Linia wykonania", icon: Rocket },
  { href: "/workspace", label: "Obszar pracy AI", icon: Columns2 },
  { href: "/agents", label: "Agenci", icon: Users },
  { href: "/modules", label: "Moduły", icon: Boxes },
  { href: "/health", label: "Zdrowie systemu", icon: Activity },
  { href: "/contracts", label: "Kontrakty", icon: ScrollText },
  { href: "/performance", label: "Wydajność", icon: Gauge },
  { href: "/devices", label: "Urządzenia", icon: Smartphone },
  { href: "/costs", label: "Koszty", icon: DollarSign },
  { href: "/sdr", label: "Laboratorium SDR", icon: Radio },
  { href: "/cellular", label: "Laboratorium sieci komórkowej", icon: Signal },
  { href: "/rebuild", label: "Odbudowa", icon: RefreshCw },
  { href: "/autonomy", label: "Autonomia", icon: Brain },
  { href: "/lifecycle", label: "Cykl życia", icon: RotateCcw },
  { href: "/book", label: "Księga systemu", icon: BookOpen },
];

const technicalOps: NavItem[] = [
  { href: "/anomalies", label: "Anomalie", icon: Activity },
  { href: "/sla", label: "Monitor SLA", icon: ShieldCheck },
  { href: "/drift", label: "Dryf konfiguracji", icon: GitCompare },
  { href: "/risk", label: "Ryzyko", icon: AlertTriangle },
  { href: "/healing", label: "Samonaprawa", icon: HeartPulse },
  { href: "/capacity", label: "Pojemność", icon: Gauge },
  { href: "/circuits", label: "Bezpieczniki", icon: Zap },
  { href: "/golden-tests", label: "Testy złote", icon: TestTube },
  { href: "/gates", label: "Bramki zarządzania", icon: Shield },
  { href: "/bundles", label: "Pakiety", icon: Package },
  { href: "/evaluator", label: "Ewaluator", icon: ClipboardCheck },
  { href: "/integrations", label: "Integracje", icon: Link2 },
];

const technicalSecurity: NavItem[] = [
  { href: "/auth", label: "Uwierzytelnianie", icon: Fingerprint },
  { href: "/roles", label: "Role", icon: Users },
  { href: "/notifications", label: "Powiadomienia", icon: Bell },
  { href: "/connectors", label: "Konektory", icon: LinkIcon },
  { href: "/security-scan", label: "Skan bezpieczeństwa", icon: Search },
];

// ---------------------------------------------------------------------------
// Mode-aware colors
// ---------------------------------------------------------------------------

function useModeColors(isOperator: boolean) {
  return {
    sidebarBg: isOperator ? "oklch(0.13 0.005 280)" : "oklch(0.11 0.005 240)",
    sectionHeaderColor: isOperator ? "oklch(0.6 0.08 260)" : "oklch(0.4 0.01 260)",
    itemTextColor: isOperator ? "oklch(0.52 0.01 260)" : "oklch(0.48 0.01 260)",
    itemActiveTextColor: "oklch(0.93 0.01 260)",
    itemActiveIconColor: isOperator ? "oklch(0.6 0.18 260)" : "oklch(0.55 0.2 260)",
    itemIconColor: isOperator ? "oklch(0.5 0.01 260)" : "oklch(0.45 0.01 260)",
    activeGlow: "linear-gradient(180deg, oklch(0.55 0.2 260), oklch(0.45 0.25 240))",
    activeBgOperator: "linear-gradient(90deg, oklch(0.55 0.2 260 / 12%), oklch(0.45 0.25 240 / 4%))",
    activeBgTechnical: "linear-gradient(90deg, oklch(0.55 0.2 260 / 6%), transparent)",
    activeBorder: isOperator ? "1px solid oklch(0.55 0.2 260 / 20%)" : "none",
    itemFontSize: isOperator ? "text-[14px]" : "text-[12px]",
    itemIconSize: isOperator ? "w-[18px] h-[18px]" : "w-4 h-4",
    sectionIconSize: isOperator ? "w-[14px] h-[14px]" : "w-[13px] h-[13px]",
    itemPy: isOperator ? "py-2.5" : "py-2",
    navGap: isOperator ? "space-y-1" : "space-y-0.5",
    sectionPt: isOperator ? "pt-4" : "pt-3",
  };
}

// ---------------------------------------------------------------------------
// Renderer
// ---------------------------------------------------------------------------

export function AppSidebar() {
  const pathname = usePathname();
  const { collapsed, toggle } = useSidebar();
  const { mode } = useAdvisorMode();
  const isOperator = mode === "operator";
  const colors = useModeColors(isOperator);

  const [advisorOpen, setAdvisorOpen] = useState(true);
  const [projectsOpen, setProjectsOpen] = useState(true);
  const [fundingOpen, setFundingOpen] = useState(true);
  const [decisionsOpen, setDecisionsOpen] = useState(true);
  const [testingOpen, setTestingOpen] = useState(true);
  const [configOpen, setConfigOpen] = useState(true);
  const [orchestOpen, setOrchestOpen] = useState(true);
  const [helpOpen, setHelpOpen] = useState(true);
  const [aeisV2Open, setAeisV2Open] = useState(true);
  const [techOpen, setTechOpen] = useState(false);
  const [techCoreOpen, setTechCoreOpen] = useState(true);
  const [techOpsOpen, setTechOpsOpen] = useState(true);
  const [techSecOpen, setTechSecOpen] = useState(true);
  const [fundingEnabled, setFundingEnabled] = useState(true);

  useEffect(() => {
    let cancelled = false;
    advisorApi
        .listPreferences(DEFAULT_OPERATOR_ID)
      .then((r) => {
        if (cancelled) return;
        const entry = r.preferences.find((p) => p.preference_key === "funding_advisor_enabled");
        setFundingEnabled(entry ? Boolean(entry.preference_value) : true);
      })
      .catch(() => {
        if (cancelled) return;
        setFundingEnabled(true);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  return (
    <motion.aside
      className="fixed left-0 top-0 z-40 h-screen flex flex-col border-r transition-colors duration-300"
      style={{
        backgroundColor: colors.sidebarBg,
        borderRightColor: "rgba(148,163,184,0.08)",
      }}
      animate={{ width: collapsed ? 64 : 256 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
      {/* Logo */}
      <div
        className={cn(
          "flex items-center border-b shrink-0 h-16 transition-colors duration-300",
          collapsed ? "justify-center px-0" : "gap-3 px-5"
        )}
        style={{ borderBottomColor: "rgba(148,163,184,0.08)" }}
      >
        <motion.div
          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
          style={{
            background:
              "linear-gradient(135deg, oklch(0.55 0.2 260), oklch(0.45 0.25 240))",
            boxShadow: "0 0 20px oklch(0.55 0.2 260 / 20%)",
          }}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <span className="font-bold text-sm" style={{ color: "oklch(0.98 0 0)" }}>
            S
          </span>
        </motion.div>
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.18 }}
              className="overflow-hidden whitespace-nowrap"
            >
              <div
                className="text-sm font-semibold tracking-wide"
                style={{ color: "oklch(0.93 0.01 260)" }}
              >
                SYLION AEIS
              </div>
              <div
                className={cn(
                  "tracking-widest uppercase transition-colors duration-300",
                  isOperator ? "text-[11px]" : "text-[10px]"
                )}
                style={{ color: isOperator ? "oklch(0.55 0.12 260)" : "oklch(0.5 0.01 260)" }}
              >
                {isOperator ? "Tryb operatora" : "Tryb techniczny"}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2 overflow-y-auto overflow-x-hidden">
        <ul className={cn("px-2", colors.navGap)}>
          {/* Advisor (zawsze widoczny) */}
          <SectionHeader
            label="Doradca"
            icon={Compass}
            collapsed={collapsed}
            open={advisorOpen}
            onToggle={() => setAdvisorOpen((v) => !v)}
            isOperator={isOperator}
            colors={colors}
          />
          <SectionItems
            items={advisorItems}
            pathname={pathname}
            collapsed={collapsed}
            open={advisorOpen}
            isOperator={isOperator}
            colors={colors}
          />

          {isOperator && (
            <>
              <SectionHeader
                label="Projekty"
                icon={FolderKanban}
                collapsed={collapsed}
                open={projectsOpen}
                onToggle={() => setProjectsOpen((v) => !v)}
                isOperator={isOperator}
                colors={colors}
              />
              <SectionItems
                items={projectItems}
                pathname={pathname}
                collapsed={collapsed}
                open={projectsOpen}
                isOperator={isOperator}
                colors={colors}
              />

              {fundingEnabled && (
                <>
                  <SectionHeader
                    label="Finansowanie"
                    icon={DollarSign}
                    collapsed={collapsed}
                    open={fundingOpen}
                    onToggle={() => setFundingOpen((v) => !v)}
                    isOperator={isOperator}
                    colors={colors}
                  />
                  <SectionItems
                    items={fundingItems}
                    pathname={pathname}
                    collapsed={collapsed}
                    open={fundingOpen}
                    isOperator={isOperator}
                    colors={colors}
                  />
                </>
              )}

              <SectionHeader
                label="Decyzje"
                icon={GitBranch}
                collapsed={collapsed}
                open={decisionsOpen}
                onToggle={() => setDecisionsOpen((v) => !v)}
                isOperator={isOperator}
                colors={colors}
              />
              <SectionItems
                items={decisionItems}
                pathname={pathname}
                collapsed={collapsed}
                open={decisionsOpen}
                isOperator={isOperator}
                colors={colors}
              />

              <SectionHeader
                label="Testowanie i wydania"
                icon={TestTube}
                collapsed={collapsed}
                open={testingOpen}
                onToggle={() => setTestingOpen((v) => !v)}
                isOperator={isOperator}
                colors={colors}
              />
              <SectionItems
                items={operatorTestingItems}
                pathname={pathname}
                collapsed={collapsed}
                open={testingOpen}
                isOperator={isOperator}
                colors={colors}
              />

              <SectionHeader
                label="Konfiguracja"
                icon={Settings}
                collapsed={collapsed}
                open={configOpen}
                onToggle={() => setConfigOpen((v) => !v)}
                isOperator={isOperator}
                colors={colors}
              />
              <SectionItems
                items={operatorConfigItems}
                pathname={pathname}
                collapsed={collapsed}
                open={configOpen}
                isOperator={isOperator}
                colors={colors}
              />

              <SectionHeader
                label="Orkiestracja"
                icon={Settings2}
                collapsed={collapsed}
                open={orchestOpen}
                onToggle={() => setOrchestOpen((v) => !v)}
                isOperator={isOperator}
                colors={colors}
              />
              <SectionItems
                items={orchestrationItems}
                pathname={pathname}
                collapsed={collapsed}
                open={orchestOpen}
                isOperator={isOperator}
                colors={colors}
              />

              {/* Tryb techniczny — zwijany w trybie operatora */}
              <SectionHeader
                label="Tryb techniczny"
                icon={Wrench}
                collapsed={collapsed}
                open={techOpen}
                onToggle={() => setTechOpen((v) => !v)}
                isOperator={isOperator}
                colors={colors}
              />
              <SectionItems
                items={technicalCore.slice(0, 6)}
                pathname={pathname}
                collapsed={collapsed}
                open={techOpen}
                isOperator={isOperator}
                colors={colors}
              />
            </>
          )}

          {/* AEIS v2 — zawsze widoczne moduły fazy 0: W7, W15, W18 */}
          <SectionHeader
            label="AEIS v2"
            icon={Sparkles}
            collapsed={collapsed}
            open={aeisV2Open}
            onToggle={() => setAeisV2Open((v) => !v)}
            isOperator={isOperator}
            colors={colors}
          />
          <SectionItems
            items={aeisV2Items}
            pathname={pathname}
            collapsed={collapsed}
            open={aeisV2Open}
            isOperator={isOperator}
            colors={colors}
          />

          {/* Wsparcie — always visible */}
          <SectionHeader
            label="Wsparcie"
            icon={HelpCircle}
            collapsed={collapsed}
            open={helpOpen}
            onToggle={() => setHelpOpen((v) => !v)}
            isOperator={isOperator}
            colors={colors}
          />
          <SectionItems
            items={helpItems}
            pathname={pathname}
            collapsed={collapsed}
            open={helpOpen}
            isOperator={isOperator}
            colors={colors}
          />

          {!isOperator && (
            <>
              <SectionHeader
                label="Rdzeń"
                icon={LayoutDashboard}
                collapsed={collapsed}
                open={techCoreOpen}
                onToggle={() => setTechCoreOpen((v) => !v)}
                isOperator={isOperator}
                colors={colors}
              />
              <SectionItems
                items={technicalCore}
                pathname={pathname}
                collapsed={collapsed}
                open={techCoreOpen}
                isOperator={isOperator}
                colors={colors}
              />

              <SectionHeader
                label="Operacje"
                icon={Activity}
                collapsed={collapsed}
                open={techOpsOpen}
                onToggle={() => setTechOpsOpen((v) => !v)}
                isOperator={isOperator}
                colors={colors}
              />
              <SectionItems
                items={technicalOps}
                pathname={pathname}
                collapsed={collapsed}
                open={techOpsOpen}
                isOperator={isOperator}
                colors={colors}
              />

              <SectionHeader
                label="Bezpieczeństwo"
                icon={Shield}
                collapsed={collapsed}
                open={techSecOpen}
                onToggle={() => setTechSecOpen((v) => !v)}
                isOperator={isOperator}
                colors={colors}
              />
              <SectionItems
                items={technicalSecurity}
                pathname={pathname}
                collapsed={collapsed}
                open={techSecOpen}
                isOperator={isOperator}
                colors={colors}
              />
            </>
          )}
        </ul>
      </nav>

      {/* Bottom section */}
      <div
        className="shrink-0 border-t px-2 py-2 space-y-0.5"
        style={{ borderTopColor: "rgba(148,163,184,0.08)" }}
      >
        <button
          onClick={toggle}
          className={cn(
            "flex items-center w-full rounded-lg transition-colors duration-150 cursor-pointer",
            colors.itemFontSize,
            collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5"
          )}
          style={{ color: "oklch(0.48 0.01 260)" }}
          aria-label={collapsed ? "Rozwiń menu" : "Zwiń menu"}
        >
          <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
            {collapsed ? (
              <PanelLeft className="w-[18px] h-[18px] shrink-0" />
            ) : (
              <PanelLeftClose className="w-[18px] h-[18px] shrink-0" />
            )}
          </motion.div>
          <AnimatePresence initial={false}>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                transition={{ duration: 0.15 }}
                className="whitespace-nowrap"
              >
                Zwiń
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>
    </motion.aside>
  );
}

function SectionHeader({
  label,
  icon: Icon,
  collapsed,
  open,
  onToggle,
  isOperator,
  colors,
}: {
  label: string;
  icon: LucideIcon;
  collapsed: boolean;
  open: boolean;
  onToggle: () => void;
  isOperator: boolean;
  colors: ReturnType<typeof useModeColors>;
}) {
  return (
    <li className={cn("pb-1", colors.sectionPt)}>
      <button
        onClick={onToggle}
        className={cn(
          "flex items-center w-full rounded-lg uppercase tracking-widest transition-colors duration-150 cursor-pointer",
          isOperator ? "text-[11px] font-semibold" : "text-[10px]",
          collapsed ? "justify-center px-0 py-1.5" : "gap-2 px-3 py-1.5"
        )}
        style={{ color: colors.sectionHeaderColor }}
      >
        <Icon className={cn("shrink-0", colors.sectionIconSize)} />
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
              className="flex-1 text-left"
            >
              {label}
            </motion.span>
          )}
        </AnimatePresence>
        {!collapsed && (
          <motion.div animate={{ rotate: open ? 0 : -90 }} transition={{ duration: 0.15 }}>
            <ChevronDown className="w-[14px] h-[14px] shrink-0" />
          </motion.div>
        )}
      </button>
    </li>
  );
}

function SectionItems({
  items,
  pathname,
  collapsed,
  open,
  isOperator,
  colors,
}: {
  items: NavItem[];
  pathname: string | null;
  collapsed: boolean;
  open: boolean;
  isOperator: boolean;
  colors: ReturnType<typeof useModeColors>;
}) {
  return (
    <AnimatePresence initial={false}>
      {(open || collapsed) && (
        <>
          {items.map((item) => {
            const active =
              pathname === item.href ||
              (item.href !== "/overview" && pathname?.startsWith(item.href + "/"));
            return (
              <motion.li
                key={item.href}
                initial={false}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="overflow-hidden"
              >
                <Link
                  href={item.href}
                  className={cn(
                    "relative flex items-center rounded-lg transition-all duration-200 group",
                    collapsed ? "justify-center px-0" : "gap-3 px-3",
                    colors.itemPy
                  )}
                  style={{
                    color: active ? colors.itemActiveTextColor : colors.itemTextColor,
                    background: active
                      ? isOperator
                        ? colors.activeBgOperator
                        : colors.activeBgTechnical
                      : "transparent",
                    border: active ? colors.activeBorder : "1px solid transparent",
                  }}
                >
                  {active && (
                    <motion.div
                      layoutId="sidebar-active-glow"
                      className="absolute left-0 top-1 bottom-1 w-[3px] rounded-r-full"
                      style={{
                        background: colors.activeGlow,
                        boxShadow:
                          "0 0 12px oklch(0.55 0.2 260 / 40%), 0 0 24px oklch(0.55 0.2 260 / 15%)",
                      }}
                      transition={{ type: "spring", stiffness: 350, damping: 30 }}
                    />
                  )}
                  <item.icon
                    className={cn("shrink-0 relative z-10 transition-colors duration-150", colors.itemIconSize)}
                    style={{
                      color: active ? colors.itemActiveIconColor : colors.itemIconColor,
                    }}
                  />
                  <AnimatePresence initial={false}>
                    {!collapsed && (
                      <motion.span
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -6 }}
                        transition={{ duration: 0.15 }}
                        className={cn(
                          "relative z-10 whitespace-nowrap",
                          colors.itemFontSize,
                          active && "font-medium"
                        )}
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </Link>
              </motion.li>
            );
          })}
        </>
      )}
    </AnimatePresence>
  );
}
