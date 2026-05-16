"use client";

import { useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useModules, useEvents, useEvidence, useContracts, useHealth } from "@/lib/api/hooks";
import {
  cn,
  getLifecycleBgColor,
  getRiskBgColor,
  fmtDateTime,
} from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import type { Module, ModuleClass } from "@/lib/types";
import {
  Cpu, Search, X, ChevronRight, Package, FileText,
  Link2, Shield, Clock, Activity, Eye, Zap,
  CheckCircle2, AlertTriangle, ArrowRight, Layers,
  CircleDot, ScrollText,
} from "lucide-react";

/* ============================================================
   Category mapping — maps module_id prefix to display category
   ============================================================ */

const CATEGORY_ORDER = [
  "Core", "Cognitive", "Governance", "Execution", "Security",
  "Monitoring", "Memory", "Quality", "AEIS", "Skills",
  "Cellular", "SDR", "Devices",
] as const;

type Category = (typeof CATEGORY_ORDER)[number];

const prefixToCategory: Record<string, Category> = {
  core: "Core",
  cognitive: "Cognitive",
  governance: "Governance",
  execution: "Execution",
  security: "Security",
  monitoring: "Monitoring",
  memory: "Memory",
  quality: "Quality",
  aeis: "AEIS",
  skills: "Skills",
  cellular: "Cellular",
  sdr: "SDR",
  devices: "Devices",
};

function getCategoryFromModuleId(moduleId: string): Category {
  const prefix = moduleId.split(".")[0].toLowerCase();
  return prefixToCategory[prefix] || "Core";
}

const categoryBgMap: Record<Category, string> = {
  Core: "bg-sylion-blue/15 text-sylion-blue border-sylion-blue/20",
  Cognitive: "bg-indigo-400/15 text-indigo-400 border-indigo-400/20",
  Governance: "bg-cyan-400/15 text-cyan-400 border-cyan-400/20",
  Execution: "bg-violet-400/15 text-violet-400 border-violet-400/20",
  Security: "bg-sylion-green/15 text-sylion-green border-sylion-green/20",
  Monitoring: "bg-emerald-400/15 text-emerald-400 border-emerald-400/20",
  Memory: "bg-pink-400/15 text-pink-400 border-pink-400/20",
  Quality: "bg-lime-400/15 text-lime-400 border-lime-400/20",
  AEIS: "bg-teal-400/15 text-teal-400 border-teal-400/20",
  Skills: "bg-orange-400/15 text-orange-400 border-orange-400/20",
  Cellular: "bg-sky-400/15 text-sky-400 border-sky-400/20",
  SDR: "bg-rose-400/15 text-rose-400 border-rose-400/20",
  Devices: "bg-sylion-amber/15 text-sylion-amber border-sylion-amber/20",
};

const categoryDotMap: Record<Category, string> = {
  Core: "bg-sylion-blue",
  Cognitive: "bg-indigo-400",
  Governance: "bg-cyan-400",
  Execution: "bg-violet-400",
  Security: "bg-sylion-green",
  Monitoring: "bg-emerald-400",
  Memory: "bg-pink-400",
  Quality: "bg-lime-400",
  AEIS: "bg-teal-400",
  Skills: "bg-orange-400",
  Cellular: "bg-sky-400",
  SDR: "bg-rose-400",
  Devices: "bg-sylion-amber",
};

/* ============================================================
   Lifecycle color for the top accent bar
   ============================================================ */

function getLifecycleBarColor(lifecycle: string): string {
  const map: Record<string, string> = {
    stable: "bg-sylion-green/50",
    validate: "bg-sylion-amber/50",
    shadow: "bg-purple-400/50",
    build: "bg-sylion-blue/50",
    draft: "bg-muted-foreground/30",
    deprecated: "bg-sylion-red/50",
  };
  return map[lifecycle] || "bg-muted-foreground/30";
}

/* ============================================================
   Contract state visual config
   ============================================================ */

const contractStateConfig: Record<string, { color: string; icon: React.ElementType }> = {
  frozen: { color: "border-sylion-green/30 text-sylion-green bg-sylion-green/8", icon: CheckCircle2 },
  draft: { color: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/8", icon: Clock },
  breaking: { color: "border-sylion-red/30 text-sylion-red bg-sylion-red/8", icon: AlertTriangle },
};

/* ============================================================
   Module Card
   ============================================================ */

function ModuleCard({
  mod,
  eventCount,
  evidenceCount,
  isSelected,
  onClick,
}: {
  mod: Module;
  eventCount: number;
  evidenceCount: number;
  isSelected: boolean;
  onClick: () => void;
}) {
  const contractState = contractStateConfig[mod.contract_state] || contractStateConfig.draft;
  const ContractIcon = contractState.icon;
  const category = getCategoryFromModuleId(mod.id);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      layout
    >
      <Card
        className={cn(
          "bg-card border-sylion-border card-hover overflow-hidden cursor-pointer transition-shadow",
          isSelected ? "ring-1 ring-primary/40 shadow-lg shadow-primary/5" : "hover:shadow-md"
        )}
        onClick={onClick}
      >
        {/* Top accent bar by lifecycle stage */}
        <div className={cn("h-0.5 w-full", getLifecycleBarColor(mod.lifecycle))} />

        <div className="p-4">
          {/* Row 1: Module ID badge + Kind badge */}
          <div className="flex items-start gap-3">
            <div className={cn(
              "w-9 h-9 rounded-lg flex items-center justify-center shrink-0",
              categoryBgMap[category] || "bg-muted/30 text-muted-foreground"
            )}>
              <Cpu className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold font-mono truncate">{mod.name}</h3>
              <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                <Badge variant="outline" className={cn("text-[9px] h-4", categoryBgMap[category])}>
                  {category}
                </Badge>
                <Badge variant="outline" className={cn("text-[9px] h-4", getLifecycleBgColor(mod.lifecycle))}>
                  {mod.lifecycle}
                </Badge>
              </div>
            </div>
          </div>

          {/* Row 2: Description */}
          <p className="text-xs text-muted-foreground mt-3 line-clamp-2 leading-relaxed">
            {mod.description}
          </p>

          {/* Row 3: Metadata chips */}
          <div className="mt-3 flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <Package className="w-3 h-3" />
              <span>{mod.package}</span>
            </div>
            <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <FileText className="w-3 h-3" />
              <span>{mod.owner_plan}</span>
            </div>
          </div>

          {/* Row 4: Contract + Event/Evidence counts */}
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            <div className={cn("flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] border", contractState.color)}>
              <ContractIcon className="w-2.5 h-2.5" />
              {mod.contract_state}
            </div>
            {eventCount > 0 && (
              <div className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] bg-primary/8 text-primary border border-primary/20">
                <Activity className="w-2.5 h-2.5" />
                {eventCount} event{eventCount !== 1 ? "s" : ""}
              </div>
            )}
            {evidenceCount > 0 && (
              <div className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] bg-sylion-amber/8 text-sylion-amber border border-sylion-amber/20">
                <Eye className="w-2.5 h-2.5" />
                {evidenceCount} evidence
              </div>
            )}
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

/* ============================================================
   Module Detail Panel
   ============================================================ */

function ModuleDetailPanel({
  mod,
  events,
  evidenceEntries,
  contracts,
  onClose,
}: {
  mod: Module;
  events: any[];
  evidenceEntries: any[];
  contracts: any[];
  onClose: () => void;
}) {
  const contractState = contractStateConfig[mod.contract_state] || contractStateConfig.draft;
  const ContractIcon = contractState.icon;
  const category = getCategoryFromModuleId(mod.id);
  const modContracts = contracts.filter(
    (c: any) => c.module_id === mod.id || c.name === mod.name || c.module === mod.id
  );

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
      <Card className="bg-card border-sylion-border overflow-hidden">
        {/* Header */}
        <div className={cn("px-5 py-4 border-b border-sylion-border", categoryBgMap[category] + " bg-opacity-30")}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center", categoryBgMap[category])}>
                <Cpu className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-semibold font-mono">{mod.name}</h2>
                <div className="flex items-center gap-2 mt-0.5">
                  <Badge variant="outline" className={cn("text-[9px] h-4", categoryBgMap[category])}>
                    {category}
                  </Badge>
                  <Badge variant="outline" className={cn("text-[9px] h-4", getLifecycleBgColor(mod.lifecycle))}>
                    {mod.lifecycle}
                  </Badge>
                </div>
              </div>
            </div>
            <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={onClose}>
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div className="p-5 space-y-5 max-h-[calc(100vh-280px)] overflow-y-auto">
          {/* Description */}
          <p className="text-sm text-muted-foreground leading-relaxed">{mod.description}</p>

          {/* Manifest Grid */}
          <div>
            <h4 className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
              <FileText className="w-3 h-3" /> Manifest modułu
              <HelpTip text="Statyczne metadane modułu z manifest.yaml — id, klasa, paczka, plan właściciela, ryzyko." />
            </h4>
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2.5 rounded-md surface-inset">
                <p className="text-[9px] text-muted-foreground">Module ID</p>
                <p className="text-[11px] font-mono font-medium">{mod.id}</p>
              </div>
              <div className="p-2.5 rounded-md surface-inset">
                <p className="text-[9px] text-muted-foreground">Kind</p>
                <p className="text-[11px] font-mono font-medium">{mod.kind}</p>
              </div>
              <div className="p-2.5 rounded-md surface-inset">
                <p className="text-[9px] text-muted-foreground">Package</p>
                <p className="text-[11px]">{mod.package}</p>
              </div>
              <div className="p-2.5 rounded-md surface-inset">
                <p className="text-[9px] text-muted-foreground">Owner Plan</p>
                <p className="text-[11px]">{mod.owner_plan}</p>
              </div>
              <div className="p-2.5 rounded-md surface-inset">
                <p className="text-[9px] text-muted-foreground">Lifecycle</p>
                <Badge variant="outline" className={cn("text-[9px] h-4 mt-0.5", getLifecycleBgColor(mod.lifecycle))}>
                  {mod.lifecycle}
                </Badge>
              </div>
              <div className="p-2.5 rounded-md surface-inset">
                <p className="text-[9px] text-muted-foreground">Risk</p>
                <Badge variant="outline" className={cn("text-[9px] h-4 mt-0.5", getRiskBgColor(mod.risk as "none" | "low" | "medium" | "high" | "critical"))}>
                  {mod.risk}
                </Badge>
              </div>
            </div>
          </div>

          {/* Contract State */}
          <div>
            <h4 className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
              <Shield className="w-3 h-3" /> Stan kontraktu
              <HelpTip text="frozen = bez zmian łamiących, draft = zmiany dozwolone, breaking = wymaga przeglądu rady i nowej wersji." />
            </h4>
            <div className={cn("flex items-center gap-2 px-3 py-2 rounded-lg border", contractState.color)}>
              <ContractIcon className="w-4 h-4" />
              <div>
                <p className="text-xs font-medium capitalize">{mod.contract_state}</p>
                <p className="text-[9px] text-muted-foreground">
                  {mod.contract_state === "frozen"
                    ? "Contract locked -- no breaking changes allowed"
                    : mod.contract_state === "draft"
                    ? "Contract in draft -- changes permitted"
                    : "Breaking changes detected -- requires governance review"}
                </p>
              </div>
            </div>
          </div>

          {/* Dependencies */}
          <div>
            <h4 className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
              <Link2 className="w-3 h-3" /> Zależności ({mod.dependencies.length})
              <HelpTip text="Inne moduły, których ten moduł wymaga do działania. Zmiana zależności wymaga rebuildu i ponownej walidacji." />
            </h4>
            {mod.dependencies.length > 0 ? (
              <div className="space-y-1">
                {mod.dependencies.map((dep) => (
                  <div key={dep} className="flex items-center gap-2 px-2 py-1.5 rounded-md surface-inset">
                    <ArrowRight className="w-3 h-3 text-primary shrink-0" />
                    <span className="text-[11px] font-mono">{dep}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-muted-foreground italic px-2">No external dependencies</p>
            )}
          </div>

          {/* Lifecycle Progress */}
          <div>
            <h4 className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
              <Clock className="w-3 h-3" /> Historia cyklu życia
              <HelpTip text="Postęp modułu przez etapy: draft → build → validate → shadow → dual → cutover → stable. Deprecated to koniec życia." />
            </h4>
            <div className="flex items-center gap-1 flex-wrap">
              {(["draft", "build", "validate", "shadow", "dual", "cutover", "stable", "deprecated"] as const).map((stage, idx) => {
                const stages = ["draft", "build", "validate", "shadow", "dual", "cutover", "stable", "deprecated"];
                const currentIdx = stages.indexOf(mod.lifecycle);
                const isActive = stage === mod.lifecycle;
                const isPast = idx <= currentIdx && currentIdx >= 0;

                if (stage === "deprecated" && mod.lifecycle !== "deprecated") return null;
                if (stage === "dual" && mod.lifecycle !== "dual" && currentIdx < 4) return null;
                if (stage === "cutover" && mod.lifecycle !== "cutover" && currentIdx < 5) return null;

                return (
                  <div key={stage} className="flex items-center gap-1">
                    <div className={cn(
                      "px-2 py-0.5 rounded text-[9px] font-medium",
                      isActive ? getLifecycleBgColor(stage) : isPast ? "bg-primary/8 text-primary" : "bg-secondary/50 text-muted-foreground/40"
                    )}>
                      {stage}
                    </div>
                    {idx < stages.length - 1 && stage !== "deprecated" && (
                      <ChevronRight className="w-2.5 h-2.5 text-muted-foreground/30" />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recent Events */}
          <div>
            <h4 className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
              <Activity className="w-3 h-3" /> Ostatnie zdarze?ia ({events.length})
              <HelpTip text="Strumień zdarzeń event-busa wystartowanych z tego modułu. Pomocne do diagnozy i analizy ruchu." />
            </h4>
            {events.length > 0 ? (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {events.slice(0, 15).map((ev: any, i: number) => (
                  <div key={ev.id || i} className="flex items-start gap-2 px-2.5 py-2 rounded-md surface-inset">
                    <CircleDot className="w-3 h-3 text-primary shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono font-medium truncate">
                          {ev.topic || ev.event_type || "event"}
                        </span>
                        {ev.source_module && (
                          <span className="text-[9px] text-muted-foreground truncate">
                            from {ev.source_module}
                          </span>
                        )}
                      </div>
                      {ev.timestamp && (
                        <p className="text-[9px] text-muted-foreground mt-0.5">
                          {fmtDateTime(ev.timestamp)}
                        </p>
                      )}
                      {ev.payload && (
                        <p className="text-[9px] text-muted-foreground mt-0.5 line-clamp-1">
                          {typeof ev.payload === "string" ? ev.payload : JSON.stringify(ev.payload).slice(0, 120)}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-muted-foreground italic px-2">No events recorded for this module</p>
            )}
          </div>

          {/* Evidence Entries */}
          <div>
            <h4 className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
              <Eye className="w-3 h-3" /> Dowody ({evidenceEntries.length})
              <HelpTip text="Wpisy w kręgosłupie dowodowym powiązane z modułem — artefakty walidacyjne, decyzję D3+, podpisy." />
            </h4>
            {evidenceEntries.length > 0 ? (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {evidenceEntries.slice(0, 10).map((ev: any, i: number) => (
                  <div key={ev.id || ev.evidence_id || i} className="flex items-start gap-2 px-2.5 py-2 rounded-md surface-inset">
                    <ScrollText className="w-3 h-3 text-sylion-amber shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-medium truncate">
                        {ev.title || ev.action || ev.evidence_id || "Evidence entry"}
                      </p>
                      {(ev.timestamp || ev.created_at) && (
                        <p className="text-[9px] text-muted-foreground mt-0.5">
                          {fmtDateTime(ev.timestamp || ev.created_at)}
                        </p>
                      )}
                      {ev.status && (
                        <Badge variant="outline" className={cn(
                          "text-[8px] h-3.5 mt-1",
                          ev.status === "validated" || ev.status === "submitted"
                            ? "bg-sylion-green/8 text-sylion-green border-sylion-green/20"
                            : "bg-sylion-amber/8 text-sylion-amber border-sylion-amber/20"
                        )}>
                          {ev.status}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-muted-foreground italic px-2">No evidence entries for this module</p>
            )}
          </div>

          {/* Contracts */}
          {modContracts.length > 0 && (
            <div>
              <h4 className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1">
                <Shield className="w-3 h-3" /> Kontrakty ({modContracts.length})
                <HelpTip text="Kontrakty proto, których ten moduł jest właścicielem lub konsumentem. Wersjonowane; zmiany breaking wymagają zatwierdzenia." />
              </h4>
              <div className="space-y-1.5">
                {modContracts.map((c: any, i: number) => (
                  <div key={c.name || c.id || i} className="flex items-center gap-2 px-2.5 py-2 rounded-md surface-inset">
                    <Shield className="w-3 h-3 text-primary shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-mono font-medium truncate">{c.name || c.contract_name}</p>
                      {c.version && (
                        <p className="text-[9px] text-muted-foreground">v{c.version}</p>
                      )}
                    </div>
                    {c.state && (
                      <Badge variant="outline" className={cn("text-[8px] h-3.5", contractStateConfig[c.state]?.color || "bg-muted/50 text-muted-foreground")}>
                        {c.state}
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Card>
    </motion.div>
  );
}

/* ============================================================
   Backend module normalizer
   ============================================================ */

function mapBackendModule(raw: Record<string, unknown>): Module {
  const moduleId = (raw.module_id as string) || (raw.id as string) || "";
  const kind = ((raw.module_kind as string) || (raw.kind as string) || "A") as ModuleClass;
  const pkg = raw.package as string || moduleId.split(".")[0] || "core";
  return {
    id: raw.id as string || moduleId,
    name: raw.name as string || moduleId,
    kind,
    package: pkg,
    lifecycle: (raw.lifecycle as Module["lifecycle"]) || "stable",
    owner_plan: (raw.owner_plan as string) || "",
    description: (raw.description as string) || "",
    contract_state: (raw.contract_state as Module["contract_state"]) || "draft",
    dependencies: Array.isArray(raw.dependencies) ? raw.dependencies as string[] : [],
    risk: (raw.risk as Module["risk"]) || "low",
  };
}

/* ============================================================
   Main Page
   ============================================================ */

export default function ModulesPage() {
  const { data: apiHealth } = useHealth();
  const { data: backendModules } = useModules();
  const { data: eventsData } = useEvents();
  const { data: evidenceData } = useEvidence();
  const { data: contractsData } = useContracts();

  const backendLive = apiHealth.status === "ok";

  // Normalize modules from backend
  const modules = useMemo(() => {
    if (backendModules.modules && backendModules.modules.length > 0) {
      return backendModules.modules.map(mapBackendModule);
    }
    return [] as Module[];
  }, [backendModules.modules]);

  const allEvents = eventsData.events || [];
  const allEvidence = evidenceData.entries || [];
  const allContracts = contractsData.contracts || [];

  // Build event/evidence counts per module
  const eventCounts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const ev of allEvents) {
      const src = ev.source_module || ev.module_id || ev.topic?.split(".")[0] || "";
      if (src) map[src] = (map[src] || 0) + 1;
    }
    return map;
  }, [allEvents]);

  const evidenceCounts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const e of allEvidence) {
      const src = e.source_module || e.module_id || e.module || "";
      if (src) map[src] = (map[src] || 0) + 1;
    }
    return map;
  }, [allEvidence]);

  // Filter state
  const [selectedCategory, setSelectedCategory] = useState<Category | "All">("All");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedModuleId, setSelectedModuleId] = useState<string | null>(null);

  // Available categories from actual modules
  const availableCategories = useMemo(() => {
    const cats = new Set<Category>();
    for (const m of modules) cats.add(getCategoryFromModuleId(m.id));
    return CATEGORY_ORDER.filter((c) => cats.has(c));
  }, [modules]);

  // Category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const m of modules) {
      const cat = getCategoryFromModuleId(m.id);
      counts[cat] = (counts[cat] || 0) + 1;
    }
    return counts;
  }, [modules]);

  // Filtered modules
  const filteredModules = useMemo(() => {
    let result = modules;
    if (selectedCategory !== "All") {
      result = result.filter((m) => getCategoryFromModuleId(m.id) === selectedCategory);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(
        (m) =>
          m.name.toLowerCase().includes(q) ||
          m.id.toLowerCase().includes(q) ||
          m.description.toLowerCase().includes(q) ||
          m.owner_plan.toLowerCase().includes(q)
      );
    }
    return result;
  }, [modules, selectedCategory, searchQuery]);

  // Selected module detail
  const selectedModule = useMemo(() => {
    if (!selectedModuleId) return null;
    return modules.find((m) => m.id === selectedModuleId) || null;
  }, [modules, selectedModuleId]);

  // Module events / evidence / contracts
  const moduleEvents = useMemo(() => {
    if (!selectedModule) return [];
    return allEvents.filter(
      (ev: any) =>
        ev.source_module === selectedModule.id ||
        ev.source_module === selectedModule.name ||
        ev.module_id === selectedModule.id
    );
  }, [selectedModule, allEvents]);

  const moduleEvidence = useMemo(() => {
    if (!selectedModule) return [];
    return allEvidence.filter(
      (e: any) =>
        e.source_module === selectedModule.id ||
        e.source_module === selectedModule.name ||
        e.module_id === selectedModule.id ||
        e.module === selectedModule.id
    );
  }, [selectedModule, allEvidence]);

  const moduleContracts = useMemo(() => {
    if (!selectedModule) return [];
    return allContracts.filter(
      (c: any) =>
        c.module_id === selectedModule.id ||
        c.name === selectedModule.name ||
        c.module === selectedModule.id
    );
  }, [selectedModule, allContracts]);

  const handleModuleClick = useCallback((id: string) => {
    setSelectedModuleId((prev) => (prev === id ? null : id));
  }, []);

  // Stats
  const totalModules = modules.length;
  const stableModules = modules.filter((m) => m.lifecycle === "stable").length;
  const buildingModules = modules.filter((m) => m.lifecycle === "build" || m.lifecycle === "validate").length;

  return (
    <div className="space-y-5">
      {/* ---- Header ---- */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <Cpu className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                Eksplorator modułów
                <HelpTip text="Rejestr wszystkich modułów SYLION — id, kategoria, cykl życia, kontrakt, zależności, ryzyko. Filtruj po kategorii lub szukaj po nazwie/ID/opisie." />
              </h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                {totalModules} zarejestrowanych modułów w {availableCategories.length} kategoriach
              </p>
            </div>
            <span className={cn("text-xs px-2.5 py-1 rounded-full ml-2", backendLive ? "bg-sylion-green/10 text-sylion-green" : "bg-sylion-red/10 text-sylion-red")}>
              {backendLive ? "Na żywo" : "Backend offline"}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] border-primary/30 text-primary">
            {filteredModules.length} pokazane
          </Badge>
        </div>
      </div>

      {/* ---- Backend Offline Warning ---- */}
      {!backendLive && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-sylion-red/[0.06] border border-sylion-red/15">
          <AlertTriangle className="w-3.5 h-3.5 text-sylion-red shrink-0" />
          <p className="text-[11px] text-sylion-red">Backend niedostępny — brak danych modułów. Uruchom serwer backendu, aby się połączyć.</p>
        </div>
      )}

      {/* ---- Search Bar ---- */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Szukaj modułów po nazwie, ID, opisie lub planie..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-10 py-2.5 rounded-lg border border-sylion-border bg-card text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/40 focus:border-primary/40 transition-colors"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* ---- Category Filter Chips ---- */}
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant={selectedCategory === "All" ? "default" : "outline"}
            size="sm"
            className="text-[10px] h-7"
            onClick={() => setSelectedCategory("All")}
          >
            Wszystkie ({modules.length})
          </Button>
          {availableCategories.map((cat) => {
            const count = categoryCounts[cat] || 0;
            return (
              <Button
                key={cat}
                variant={selectedCategory === cat ? "default" : "outline"}
                size="sm"
                className={cn(
                  "text-[10px] h-7 gap-1.5",
                  selectedCategory === cat ? "" : "hover:bg-secondary"
                )}
                onClick={() => setSelectedCategory(cat)}
              >
                <span className={cn("w-1.5 h-1.5 rounded-full", categoryDotMap[cat])} />
                {cat} ({count})
              </Button>
            );
          })}
        </div>
      </div>

      {/* ---- Main Content: Grid + Detail Panel ---- */}
      <div className="flex gap-5">
        {/* Module Grid */}
        <div className={cn("transition-all", selectedModule ? "flex-1" : "w-full")}>
          <div className={cn(
            "grid gap-3",
            selectedModule ? "grid-cols-2" : "grid-cols-3"
          )}>
            <AnimatePresence mode="popLayout">
              {filteredModules.map((mod) => (
                <ModuleCard
                  key={mod.id}
                  mod={mod}
                  eventCount={eventCounts[mod.id] || eventCounts[mod.name] || 0}
                  evidenceCount={evidenceCounts[mod.id] || evidenceCounts[mod.name] || 0}
                  isSelected={selectedModuleId === mod.id}
                  onClick={() => handleModuleClick(mod.id)}
                />
              ))}
            </AnimatePresence>
          </div>

          {filteredModules.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Search className="w-8 h-8 mb-3 opacity-30" />
              <p className="text-sm font-medium">Nie znaleziono modułów</p>
              <p className="text-xs mt-1">Spróbuj zmienić wyszukiwanie lub filtr kategorii</p>
            </div>
          )}
        </div>

        {/* Detail Panel */}
        <AnimatePresence>
          {selectedModule && (
            <div className="w-[420px] shrink-0">
              <ModuleDetailPanel
                mod={selectedModule}
                events={moduleEvents}
                evidenceEntries={moduleEvidence}
                contracts={moduleContracts}
                onClose={() => setSelectedModuleId(null)}
              />
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
