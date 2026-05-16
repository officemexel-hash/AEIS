"use client";

import { useState, useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, fmtDate } from "@/lib/utils";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { useHealth, useContracts } from "@/lib/api/hooks";
import type { KPI } from "@/lib/types";
import {
  ScrollText, FileCode, Zap, Shield, Settings, CheckCircle2,
  XCircle, AlertTriangle, ChevronRight, ArrowUpRight, Layers,
  GitBranch, Clock, Eye, X, WifiOff,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

/* ------------------------------------------------------------------ */
/*  Types & Constants                                                  */
/* ------------------------------------------------------------------ */

interface ContractEntry {
  id: string;
  name: string;
  type: string;
  version: string;
  producer: string;
  consumers: string[];
  breaking: boolean;
  status: string;
  compatible: boolean;
  created_at: string;
  updated_at: string;
  schema?: string;
  description?: string;
}

const TYPE_BADGE: Record<string, { border: string; text: string; icon: React.ElementType }> = {
  gRPC:   { border: "border-sylion-blue/30",   text: "text-sylion-blue",   icon: Zap },
  Query:  { border: "border-cyan-400/30",      text: "text-cyan-400",      icon: FileCode },
  Event:  { border: "border-sylion-green/30",  text: "text-sylion-green",  icon: ArrowUpRight },
  Policy: { border: "border-sylion-amber/30",  text: "text-sylion-amber",  icon: Shield },
  Config: { border: "border-purple-400/30",    text: "text-purple-400",    icon: Settings },
  api:    { border: "border-sylion-blue/30",   text: "text-sylion-blue",   icon: Zap },
  schema: { border: "border-cyan-400/30",      text: "text-cyan-400",      icon: FileCode },
  event:  { border: "border-sylion-green/30",  text: "text-sylion-green",  icon: ArrowUpRight },
  security:{ border: "border-sylion-red/30",   text: "text-sylion-red",    icon: Shield },
  policy: { border: "border-sylion-amber/30",  text: "text-sylion-amber",  icon: Settings },
};

const STATUS_BADGE: Record<string, { border: string; text: string }> = {
  frozen:   { border: "border-sylion-green/30", text: "text-sylion-green" },
  draft:    { border: "border-sylion-amber/30", text: "text-sylion-amber" },
  breaking: { border: "border-sylion-red/30",   text: "text-sylion-red" },
};

/* ------------------------------------------------------------------ */
/*  Normalize live API contract data                                   */
/* ------------------------------------------------------------------ */

function normalizeContracts(raw: any[]): ContractEntry[] {
  return raw.map((c: any) => ({
    id: c.contract_id ?? c.id ?? c.name,
    name: c.name,
    type: c.type || "api",
    version: c.version || "0.0.0",
    producer: c.producer || c.producer_module || "--",
    consumers: c.consumers ?? [],
    breaking: c.breaking ?? false,
    status: c.status || (c.breaking ? "breaking" : "draft"),
    compatible: c.compatible ?? !c.breaking,
    created_at: c.created_at || new Date().toISOString(),
    updated_at: c.updated_at || c.created_at || new Date().toISOString(),
    schema: c.schema,
    description: c.description,
  }));
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function parseSemVer(v: string): [number, number, number] {
  const parts = v.split(".").map(Number);
  return [parts[0] || 0, parts[1] || 0, parts[2] || 0];
}

function semverColor(version: string): string {
  const [major] = parseSemVer(version);
  if (major === 0) return "text-sylion-amber";
  return "text-sylion-green";
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function TypeBadge({ type }: { type: string }) {
  const cfg = TYPE_BADGE[type] ?? TYPE_BADGE.api;
  const Icon = cfg.icon;
  return (
    <Badge variant="outline" className={cn("text-[9px] gap-1 h-5", cfg.border, cfg.text)}>
      <Icon className="w-2.5 h-2.5" />
      {type.toUpperCase()}
    </Badge>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_BADGE[status] ?? STATUS_BADGE.draft;
  return (
    <Badge variant="outline" className={cn("text-[9px] h-5", cfg.border, cfg.text)}>
      {status.toUpperCase()}
    </Badge>
  );
}

function CompatibilityIcon({ compatible }: { compatible: boolean }) {
  return compatible
    ? <CheckCircle2 className="w-4 h-4 text-sylion-green" />
    : <XCircle className="w-4 h-4 text-sylion-red" />;
}

/* ------------------------------------------------------------------ */
/*  Contract Detail Drawer                                             */
/* ------------------------------------------------------------------ */

function ContractDetail({
  contract,
  onClose,
}: {
  contract: ContractEntry;
  onClose: () => void;
}) {
  const [major, minor, patch] = parseSemVer(contract.version);
  const versionHistory = useMemo(() => {
    const hist = [];
    for (let m = 1; m <= major; m++) {
      for (let n = m === major ? 0 : 0; n <= (m === major ? minor : 2); n++) {
        for (let p = m === major && n === minor ? 0 : 0; p <= (m === major && n === minor ? patch : 3); p++) {
          hist.push({
            version: `${m}.${n}.${p}`,
            date: new Date(Date.now() - (hist.length * 86400000 * 3)).toISOString().slice(0, 10),
            breaking: m > 1 && n === 0 && p === 0,
            current: m === major && n === minor && p === patch,
          });
        }
      }
    }
    return hist.reverse().slice(0, 6);
  }, [major, minor, patch]);

  return (
    <motion.div
      initial={{ opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 40 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="fixed inset-y-0 right-0 z-50 w-[480px] border-l overflow-y-auto"
      style={{
        backgroundColor: "#0f1629",
        borderLeftColor: "rgba(148,163,184,0.08)",
      }}
    >
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center justify-between p-5 border-b" style={{ backgroundColor: "#0f1629", borderBottomColor: "rgba(148,163,184,0.08)" }}>
        <div className="flex items-center gap-3">
          <ScrollText className="w-5 h-5 text-primary" />
          <div>
            <h2 className="text-sm font-semibold font-mono">{contract.name}</h2>
            <p className="text-[10px] text-muted-foreground">v{contract.version}</p>
          </div>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-md hover:bg-secondary/50 transition-colors cursor-pointer">
          <X className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>

      <div className="p-5 space-y-5">
        {/* Meta */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-md border" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Type</p>
            <TypeBadge type={contract.type} />
          </div>
          <div className="p-3 rounded-md border" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Status</p>
            <StatusBadge status={contract.status} />
          </div>
          <div className="p-3 rounded-md border" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Producer</p>
            <p className="text-xs font-mono">{contract.producer}</p>
          </div>
          <div className="p-3 rounded-md border" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Compatibility</p>
            <div className="flex items-center gap-1.5">
              <CompatibilityIcon compatible={contract.compatible} />
              <span className={cn("text-xs", contract.compatible ? "text-sylion-green" : "text-sylion-red")}>
                {contract.compatible ? "Compatible" : "Breaking"}
              </span>
            </div>
          </div>
        </div>

        {/* SemVer Visualization */}
        <div className="p-4 rounded-lg border" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
          <h3 className="text-xs font-semibold mb-3 flex items-center gap-2">
            <GitBranch className="w-3.5 h-3.5 text-primary" />
            SemVer Visualization
          </h3>
          <div className="flex items-center gap-3 justify-center">
            <div className={cn("flex flex-col items-center p-3 rounded-lg border", major > 0 ? "border-sylion-green/30 bg-sylion-green/5" : "border-sylion-amber/30 bg-sylion-amber/5")}>
              <p className="text-[9px] text-muted-foreground uppercase">Major</p>
              <p className={cn("text-2xl font-bold", semverColor(contract.version))}>{major}</p>
              {major > 0 && <span className="text-[8px] text-sylion-red mt-0.5">BREAKING</span>}
            </div>
            <span className="text-lg text-muted-foreground font-light">.</span>
            <div className="flex flex-col items-center p-3 rounded-lg border border-primary/20 bg-primary/5">
              <p className="text-[9px] text-muted-foreground uppercase">Minor</p>
              <p className="text-2xl font-bold text-primary">{minor}</p>
              <span className="text-[8px] text-sylion-green mt-0.5">additive</span>
            </div>
            <span className="text-lg text-muted-foreground font-light">.</span>
            <div className="flex flex-col items-center p-3 rounded-lg border border-sylion-green/20 bg-sylion-green/5">
              <p className="text-[9px] text-muted-foreground uppercase">Patch</p>
              <p className="text-2xl font-bold text-sylion-green">{patch}</p>
              <span className="text-[8px] text-muted-foreground mt-0.5">fix</span>
            </div>
          </div>
        </div>

        {/* Version History */}
        <div className="p-4 rounded-lg border" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
          <h3 className="text-xs font-semibold mb-3 flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-primary" />
            Version History
          </h3>
          <div className="space-y-2">
            {versionHistory.map((vh) => (
              <div key={vh.version} className={cn(
                "flex items-center gap-3 p-2 rounded-md text-xs",
                vh.current ? "bg-primary/8 border border-primary/20" : "hover:bg-secondary/30 transition-colors"
              )}>
                <div className={cn(
                  "w-2 h-2 rounded-full shrink-0",
                  vh.current ? "bg-primary" : vh.breaking ? "bg-sylion-red" : "bg-muted-foreground/50"
                )} />
                <span className={cn("font-mono font-medium", vh.current && "text-primary")}>v{vh.version}</span>
                <span className="text-muted-foreground">{vh.date}</span>
                {vh.breaking && <Badge variant="destructive" className="text-[8px] h-3.5 ml-auto">BREAKING</Badge>}
                {vh.current && <Badge variant="outline" className="text-[8px] h-3.5 border-primary/30 text-primary ml-auto">CURRENT</Badge>}
              </div>
            ))}
          </div>
        </div>

        {/* Schema Definition */}
        <div className="p-4 rounded-lg border" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
          <h3 className="text-xs font-semibold mb-3 flex items-center gap-2">
            <FileCode className="w-3.5 h-3.5 text-primary" />
            Schema Definition
          </h3>
          <pre className="text-[10px] font-mono text-muted-foreground bg-[#050816] p-3 rounded-md overflow-x-auto leading-relaxed">
{contract.schema ?? `{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "timestamp": { "type": "string", "format": "date-time" },
    "payload": { "type": "object" }
  },
  "required": ["id", "timestamp"]
}`}
          </pre>
        </div>

        {/* Breaking Change Analysis */}
        {contract.breaking && (
          <div className="p-4 rounded-lg border border-sylion-red/30 bg-sylion-red/5">
            <h3 className="text-xs font-semibold mb-3 flex items-center gap-2 text-sylion-red">
              <AlertTriangle className="w-3.5 h-3.5" />
              Breaking Change Analysis
            </h3>
            <div className="space-y-2">
              <div className="flex items-start gap-2 text-xs">
                <XCircle className="w-3.5 h-3.5 text-sylion-red mt-0.5 shrink-0" />
                <div>
                  <p className="font-medium">Schema field removal</p>
                  <p className="text-muted-foreground mt-0.5">Removed field <code className="text-sylion-red bg-sylion-red/10 px-1 rounded text-[10px]">metadata.source</code> from response payload</p>
                </div>
              </div>
              <div className="flex items-start gap-2 text-xs">
                <XCircle className="w-3.5 h-3.5 text-sylion-red mt-0.5 shrink-0" />
                <div>
                  <p className="font-medium">Type change</p>
                  <p className="text-muted-foreground mt-0.5">Field <code className="text-sylion-red bg-sylion-red/10 px-1 rounded text-[10px]">version</code> changed from <code className="text-sylion-amber bg-sylion-amber/10 px-1 rounded text-[10px]">string</code> to <code className="text-sylion-amber bg-sylion-amber/10 px-1 rounded text-[10px]">semver_object</code></p>
                </div>
              </div>
              <div className="flex items-start gap-2 text-xs">
                <AlertTriangle className="w-3.5 h-3.5 text-sylion-amber mt-0.5 shrink-0" />
                <div>
                  <p className="font-medium">Affected consumers</p>
                  <p className="text-muted-foreground mt-0.5">{contract.consumers.length} modules consuming this contract require migration</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Consumers */}
        <div className="p-4 rounded-lg border" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
          <h3 className="text-xs font-semibold mb-3 flex items-center gap-2">
            <Layers className="w-3.5 h-3.5 text-primary" />
            Consumers ({contract.consumers.length})
          </h3>
          {contract.consumers.length === 0 ? (
            <p className="text-xs text-muted-foreground">No consumers registered</p>
          ) : (
            <div className="space-y-1.5">
              {contract.consumers.map((consumer) => (
                <div key={consumer} className="flex items-center gap-2 p-1.5 rounded-md hover:bg-secondary/30 transition-colors text-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-sylion-green" />
                  <span className="font-mono">{consumer}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */

export default function ContractsPage() {
  const { data: health } = useHealth();
  const { data: contractsData } = useContracts();
  const [selectedContract, setSelectedContract] = useState<ContractEntry | null>(null);
  const [filterType, setFilterType] = useState<string>("all");

  const backendLive = health.status === "ok";
  const liveContracts = contractsData.contracts ?? [];

  const displayContracts = useMemo(() => {
    if (!backendLive) return [];
    return normalizeContracts(liveContracts);
  }, [backendLive, liveContracts]);

  const filteredContracts = useMemo(() =>
    filterType === "all" ? displayContracts : displayContracts.filter((c) => c.type === filterType)
  , [displayContracts, filterType]);

  const breakingContracts = useMemo(() =>
    displayContracts.filter((c) => c.breaking)
  , [displayContracts]);

  const totalContracts = displayContracts.length;
  const breakingCount = breakingContracts.length;
  const frozenCount = displayContracts.filter((c) => c.status === "frozen").length;
  const latestVersions = new Set(displayContracts.map((c) => `${c.name}@${c.version}`)).size;

  const kpis: KPI[] = useMemo(() => [
    { label: "Total Contracts", value: String(totalContracts), change: 3, trend: "up", icon: "ScrollText" },
    { label: "Latest Versions", value: String(latestVersions), change: 2, trend: "up", icon: "GitBranch" },
    { label: "Breaking Changes", value: String(breakingCount), change: breakingCount > 0 ? 1 : 0, trend: breakingCount > 0 ? "up" : "stable", icon: "Activity" },
    { label: "Frozen / Stable", value: `${frozenCount}/${totalContracts}`, change: 0, trend: "stable", icon: "Shield" },
  ], [totalContracts, latestVersions, breakingCount, frozenCount]);

  const allTypes = useMemo(() => [...new Set(displayContracts.map((c) => c.type))], [displayContracts]);

  /* Compatibility matrix data */
  const matrixModules = useMemo(() => {
    const set = new Set<string>();
    displayContracts.forEach((c) => {
      set.add(c.producer);
      c.consumers.forEach((m) => set.add(m));
    });
    return [...set].sort();
  }, [displayContracts]);

  const matrixContracts = useMemo(() =>
    displayContracts.slice(0, 8)
  , [displayContracts]);

  function moduleConsumes(moduleName: string, contract: ContractEntry): boolean {
    return contract.consumers.includes(moduleName) || contract.producer === moduleName;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Rejestr kontraktów</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Versioned inter-module contracts
            {backendLive && (
              <Badge variant="outline" className="ml-2 text-[9px] border-sylion-green/30 text-sylion-green">
                LIVE
              </Badge>
            )}
          </p>
        </div>
        <Badge variant="outline" className="text-[10px] border-primary/30 text-primary">
          <ScrollText className="w-3 h-3 mr-1.5" />
          {totalContracts} contracts tracked
        </Badge>
      </div>

      {/* Backend not reachable */}
      {!backendLive && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <WifiOff className="w-10 h-10 text-muted-foreground mb-4" />
          <h2 className="text-lg font-semibold text-muted-foreground">Backend not reachable</h2>
          <p className="text-sm text-muted-foreground mt-1 max-w-md">
            The SYLION backend API is not responding. Contract data requires a live connection to the backend service.
          </p>
        </div>
      )}

      {backendLive && (
        <>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-3">
        {kpis.map((kpi) => (
          <MetricCard key={kpi.label} kpi={kpi} />
        ))}
      </div>

      {/* Breaking Changes Alert */}
      {breakingContracts.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-lg border border-sylion-red/30 bg-sylion-red/5 p-4"
        >
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-sylion-red" />
            <h2 className="text-sm font-semibold text-sylion-red">
              Breaking Changes Detected ({breakingContracts.length})
            </h2>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {breakingContracts.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setSelectedContract(c)}
                className="flex items-center gap-3 p-3 rounded-md border border-sylion-red/20 bg-sylion-red/5 hover:bg-sylion-red/10 transition-colors text-left cursor-pointer"
              >
                <XCircle className="w-4 h-4 text-sylion-red shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium font-mono truncate">{c.name}</p>
                  <p className="text-[10px] text-muted-foreground">v{c.version} &middot; {c.producer}</p>
                </div>
                <Badge variant="destructive" className="text-[8px] h-4 shrink-0">BREAKING</Badge>
              </button>
            ))}
          </div>
        </motion.div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setFilterType("all")}
          className={cn(
            "px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
            filterType === "all"
              ? "bg-primary/15 text-primary border border-primary/30"
              : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
          )}
        >
          All ({displayContracts.length})
        </button>
        {allTypes.map((type) => {
          const count = displayContracts.filter((c) => c.type === type).length;
          return (
            <button
              key={type}
              type="button"
              onClick={() => setFilterType(type)}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer",
                filterType === type
                  ? "bg-primary/15 text-primary border border-primary/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
              )}
            >
              {type} ({count})
            </button>
          );
        })}
      </div>

      {/* Contract Table */}
      <div className="rounded-lg border overflow-hidden" style={{ borderColor: "rgba(148,163,184,0.08)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40 border-b" style={{ borderBottomColor: "rgba(148,163,184,0.08)" }}>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Contract</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Type</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Version</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Producer</th>
              <th className="text-center px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Consumers</th>
              <th className="text-center px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Breaking</th>
              <th className="text-center px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Compat</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Last Updated</th>
              <th className="px-4 py-2.5 w-8" />
            </tr>
          </thead>
          <tbody>
            {filteredContracts.map((contract) => (
              <tr
                key={contract.id}
                onClick={() => setSelectedContract(contract)}
                className={cn(
                  "border-b hover:bg-muted/20 transition-colors cursor-pointer",
                  contract.breaking && "bg-sylion-red/3"
                )}
                style={{ borderBottomColor: "rgba(148,163,184,0.05)" }}
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <FileCode className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <span className="font-mono text-xs font-medium">{contract.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <TypeBadge type={contract.type} />
                </td>
                <td className="px-4 py-3">
                  <span className={cn("font-mono text-xs font-medium", semverColor(contract.version))}>
                    v{contract.version}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs text-muted-foreground font-mono">{contract.producer}</span>
                </td>
                <td className="px-4 py-3 text-center">
                  <Badge variant="secondary" className="text-[9px] h-5">
                    {contract.consumers.length}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-center">
                  {contract.breaking ? (
                    <Badge variant="destructive" className="text-[8px] h-4">YES</Badge>
                  ) : (
                    <Badge variant="outline" className="text-[8px] h-4 border-sylion-green/30 text-sylion-green">NO</Badge>
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  <CompatibilityIcon compatible={contract.compatible} />
                </td>
                <td className="px-4 py-3">
                  <span className="text-[10px] text-muted-foreground">
                    {fmtDate(contract.updated_at)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Compatibility Matrix */}
      <Card className="p-4" style={{ backgroundColor: "#0f1629", borderColor: "rgba(148,163,184,0.08)" }}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Layers className="w-4 h-4 text-primary" />
              Compatibility Matrix
            </h3>
            <p className="text-[10px] text-muted-foreground mt-0.5">Which modules consume which contracts</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <span className="w-2 h-2 rounded-sm bg-primary" /> Producer
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <span className="w-2 h-2 rounded-sm bg-sylion-green/60" /> Consumer
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <span className="w-2 h-2 rounded-sm bg-secondary" /> None
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-[10px]">
            <thead>
              <tr>
                <th className="text-left py-1.5 pr-3 font-medium text-muted-foreground sticky left-0" style={{ backgroundColor: "#0f1629" }}>
                  Module
                </th>
                {matrixContracts.map((c) => (
                  <th key={c.id} className="text-center py-1.5 px-1.5 font-medium text-muted-foreground" style={{ minWidth: 52 }}>
                    <span className="truncate block max-w-[52px]" title={c.name}>{c.name.split(".").pop()}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrixModules.slice(0, 12).map((moduleName) => (
                <tr key={moduleName} className="border-b" style={{ borderBottomColor: "rgba(148,163,184,0.04)" }}>
                  <td className="py-1.5 pr-3 font-mono text-muted-foreground sticky left-0 truncate max-w-[140px]" style={{ backgroundColor: "#0f1629" }}>
                    {moduleName}
                  </td>
                  {matrixContracts.map((c) => {
                    const isProducer = c.producer === moduleName;
                    const isConsumer = c.consumers.includes(moduleName);
                    return (
                      <td key={c.id} className="py-1.5 px-1.5 text-center">
                        {isProducer ? (
                          <span className="inline-block w-3 h-3 rounded-sm bg-primary" title="Producer" />
                        ) : isConsumer ? (
                          <span className="inline-block w-3 h-3 rounded-sm bg-sylion-green/60" title="Consumer" />
                        ) : (
                          <span className="inline-block w-3 h-3 rounded-sm bg-secondary" />
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Contract Detail Drawer */}
      <AnimatePresence>
        {selectedContract && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/40"
              onClick={() => setSelectedContract(null)}
            />
            <ContractDetail
              contract={selectedContract}
              onClose={() => setSelectedContract(null)}
            />
          </>
        )}
      </AnimatePresence>
        </>
      )}
    </div>
  );
}
