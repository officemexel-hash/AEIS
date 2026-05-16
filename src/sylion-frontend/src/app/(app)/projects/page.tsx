"use client";

import Link from "next/link";
import { useMemo, useState, type ElementType, type MouseEvent } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useHealth, useProjects, useWorkflows, useJobs } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import {
  FolderKanban, AlertTriangle, TrendingUp,
  Shield, GitBranch, Timer, Activity,
  CircleDot, CheckCircle2, XCircle, Pause,
  ArrowRight, Network,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

/* ---------- Project data model ---------- */

type ProjectRisk = "low" | "medium" | "high" | "critical";
type ProjectStatus = "active" | "paused" | "blocked" | "completed";
type GovernanceStatus = "clear" | "pending_review" | "blocked";

interface ProjectEnriched {
  id: string;
  name: string;
  description: string;
  phase: string;
  phase_index: number;
  progress: number;
  risk: ProjectRisk;
  owner: string;
  agents: string[];
  modules: string[];
  source_status: string;
  status: ProjectStatus;
  governance: GovernanceStatus;
  module_deps: number;
  blockers: number;
  confidence: number;
  timeline_start: string;
  timeline_end: string;
  phase_steps: { label: string; done: boolean }[];
}

interface RawProject {
  [key: string]: unknown;
  project_id?: string;
  id?: string;
  plan_id?: string;
  title?: string;
  name?: string;
  description?: string;
  idea?: string;
  goal?: string;
  owner_id?: string;
  owner?: string;
  status?: string;
  source_status?: string;
  phase?: string;
  risk?: string;
  risk_level?: string;
  progress?: number;
  created_at?: unknown;
  emitted_at?: unknown;
  timeline_end?: unknown;
  deadline?: unknown;
  attachments?: unknown[];
  approvals?: Record<string, unknown>;
  canonical_book?: unknown;
  masterplan?: unknown;
  build_authorized_at?: unknown;
  build_pending_ticket_id?: unknown;
  human_gate_session_id?: unknown;
  human_gate_status?: unknown;
  canon_snapshot?: {
    modules?: unknown[];
  };
  worker_plan?: {
    modules?: unknown[];
  };
  council_plan?: {
    members?: unknown[];
  };
  execution_plan?: {
    modules?: unknown[];
    budget_usd?: unknown;
    hard_limit_usd?: unknown;
  };
  modules?: unknown[];
  preferred_stack?: unknown[];
  confidence?: number;
}

const phases = ["idea", "canon", "masterplan", "council", "build", "validate", "stable"];
const FALLBACK_NOW_ISO = new Date().toISOString();
const FALLBACK_NOW_MS = new Date(FALLBACK_NOW_ISO).getTime();

const phaseLabels: Record<string, string> = {
  idea: "pomysł",
  canon: "kanon",
  masterplan: "masterplan",
  council: "rada",
  build: "budowa",
  validate: "walidacja",
  shadow: "shadow",
  stable: "stabilny",
};

const defaultPhaseSteps: Record<string, { label: string; done: boolean }[]> = {
  idea: [
    { label: "Pomysł", done: false },
    { label: "Załączniki", done: false },
    { label: "Intencja", done: false },
  ],
  canon: [
    { label: "Kanon", done: false },
    { label: "Zakres", done: false },
    { label: "Akceptacja", done: false },
  ],
  masterplan: [
    { label: "SoT", done: false },
    { label: "Masterplan", done: false },
    { label: "Budżet", done: false },
    { label: "Rada", done: false },
  ],
  council: [
    { label: "Modele", done: false },
    { label: "Krytyka", done: false },
    { label: "Human Gate", done: false },
    { label: "Decyzja", done: false },
  ],
  build: [
    { label: "Plan", done: false },
    { label: "Build", done: false },
    { label: "Walidacja", done: false },
    { label: "Paczka", done: false },
  ],
  validate: [
    { label: "Testy", done: false },
    { label: "Naprawy", done: false },
    { label: "Gotowość", done: false },
  ],
  shadow: [
    { label: "Shadow", done: false },
    { label: "Monitoring", done: false },
    { label: "Cutover", done: false },
  ],
  stable: [
    { label: "Live", done: true },
    { label: "Monitoring", done: false },
    { label: "Zamknięcie", done: false },
  ],
};

/* ---------- Helpers ---------- */

const riskBg: Record<ProjectRisk, string> = {
  low: "bg-sylion-green/15 text-sylion-green border-sylion-green/20",
  medium: "bg-sylion-amber/15 text-sylion-amber border-sylion-amber/20",
  high: "bg-orange-500/15 text-orange-400 border-orange-400/20",
  critical: "bg-sylion-red/15 text-sylion-red border-sylion-red/20",
};

const riskBar: Record<ProjectRisk, string> = {
  low: "bg-sylion-green",
  medium: "bg-sylion-amber",
  high: "bg-orange-400",
  critical: "bg-sylion-red",
};

const riskLabels: Record<ProjectRisk, string> = {
  low: "niskie",
  medium: "średnie",
  high: "wysokie",
  critical: "krytyczne",
};

const statusIconMap: Record<ProjectStatus, ElementType> = {
  active: CircleDot,
  completed: CheckCircle2,
  blocked: XCircle,
  paused: Pause,
};

const statusColor: Record<ProjectStatus, string> = {
  active: "text-sylion-green",
  completed: "text-primary",
  blocked: "text-sylion-red",
  paused: "text-sylion-amber",
};

const statusLabels: Record<ProjectStatus, string> = {
  active: "aktywny",
  completed: "ukończony",
  blocked: "zablokowany",
  paused: "wstrzymany",
};

const governanceLabels: Record<GovernanceStatus, string> = {
  clear: "czysto",
  pending_review: "wymaga decyzji",
  blocked: "blokada",
};

function confidenceColor(c: number): string {
  if (c >= 0.9) return "text-sylion-green";
  if (c >= 0.7) return "text-sylion-blue";
  if (c >= 0.5) return "text-sylion-amber";
  return "text-sylion-red";
}

function progressColor(p: number): string {
  if (p >= 90) return "bg-sylion-green";
  if (p >= 70) return "bg-sylion-blue";
  if (p >= 40) return "bg-sylion-amber";
  return "bg-sylion-red";
}

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function displayValue(value: unknown): string {
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return String(record.module_id ?? record.id ?? record.name ?? record.title ?? record.role ?? "").trim();
  }
  return String(value ?? "").trim();
}

function uniqueStrings(values: unknown[]): string[] {
  return Array.from(
    new Set(
      values
        .map(displayValue)
        .filter(Boolean),
    ),
  );
}

function listFromProjectsResponse(payload: unknown): RawProject[] {
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    if (Array.isArray(record.projects)) return record.projects as RawProject[];
    if (Array.isArray(record.items)) return record.items as RawProject[];
    if (Array.isArray(record.data)) return record.data as RawProject[];
  }
  return [];
}

function toIsoTimestamp(value: unknown, fallback: string): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    const millis = value < 10_000_000_000 ? value * 1000 : value;
    return new Date(millis).toISOString();
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Date.parse(value);
    if (!Number.isNaN(parsed)) return new Date(parsed).toISOString();
  }
  return fallback;
}

function addDaysIso(dateIso: string, days: number): string {
  const base = Date.parse(dateIso);
  return new Date((Number.isNaN(base) ? FALLBACK_NOW_MS : base) + days * 86_400_000).toISOString();
}

function compactText(value: unknown, fallback = ""): string {
  const text = String(value ?? fallback).replace(/\s+/g, " ").trim();
  if (!text) return fallback;
  return text.length > 180 ? `${text.slice(0, 177)}...` : text;
}

function formatSourceStatus(status: string): string {
  const normalized = status.toLowerCase();
  const labels: Record<string, string> = {
    definition_complete: "definicja gotowa",
    active: "aktywny",
    completed: "ukończony",
    blocked: "zablokowany",
    paused: "wstrzymany",
  };
  return labels[normalized] ?? status.replaceAll("_", " ");
}

function normalizeStatus(raw: RawProject): ProjectStatus {
  const status = String(raw?.status ?? "").toLowerCase();
  if (["completed", "done", "stable", "closed"].includes(status)) return "completed";
  if (["paused", "waiting", "suspended"].includes(status)) return "paused";
  if (["blocked", "failed", "rejected"].includes(status)) return "blocked";
  return "active";
}

function normalizeRisk(raw: RawProject, status: ProjectStatus, blockers: number): ProjectRisk {
  const risk = String(raw?.risk_level ?? raw?.risk ?? "").toLowerCase();
  if (["critical", "krytyczne"].includes(risk)) return "critical";
  if (["high", "wysokie"].includes(risk)) return "high";
  if (["medium", "średnie", "srednie"].includes(risk)) return "medium";
  if (["low", "niskie"].includes(risk)) return "low";
  if (status === "blocked") return "high";
  if (blockers > 0) return "medium";
  return "low";
}

function derivePhase(raw: RawProject): string {
  const explicit = String(raw?.phase ?? "").toLowerCase().trim();
  if (phases.includes(explicit) || explicit === "shadow") return explicit;
  const status = String(raw?.status ?? "").toLowerCase();
  if (["completed", "done", "stable"].includes(status)) return "stable";
  if (raw?.build_authorized_at || status.includes("build")) return "build";
  if (raw?.council_plan || status.includes("council")) return "council";
  if (raw?.masterplan || status.includes("masterplan") || status.includes("definition_complete")) return "masterplan";
  if (raw?.canonical_book || raw?.canon_snapshot) return "canon";
  return "idea";
}

function deriveProgress(raw: RawProject, phase: string, status: ProjectStatus): number {
  if (typeof raw?.progress === "number") return clampPercent(raw.progress);
  if (status === "completed") return 100;

  let score = raw?.project_id || raw?.id ? 12 : 0;
  if (raw?.attachments?.length) score += 8;
  if (raw?.canonical_book || raw?.canon_snapshot) score += 18;
  if (raw?.masterplan) score += 18;
  if (raw?.council_plan?.members?.length) score += 14;
  if (raw?.execution_plan) score += 12;
  if (raw?.build_authorized_at) score += 10;
  if (phase === "validate") score = Math.max(score, 78);
  if (phase === "stable") score = Math.max(score, 92);
  return clampPercent(score);
}

function buildPhaseSteps(raw: RawProject, phase: string, progress: number): { label: string; done: boolean }[] {
  const template = defaultPhaseSteps[phase] ?? defaultPhaseSteps.idea;
  const doneCount = Math.round((progress / 100) * template.length);
  const fieldDone: Record<string, boolean> = {
    Pomysł: Boolean(raw?.idea || raw?.project_id),
    Załączniki: asList(raw?.attachments).length > 0,
    Intencja: Boolean(raw?.idea || raw?.constraints),
    Kanon: Boolean(raw?.canonical_book || raw?.canon_snapshot),
    SoT: Boolean(raw?.canonical_book || raw?.canon_snapshot),
    Zakres: Boolean(raw?.canon_snapshot?.modules?.length || raw?.worker_plan?.modules?.length),
    Masterplan: Boolean(raw?.masterplan),
    Budżet: Boolean(raw?.execution_plan?.budget_usd || raw?.execution_plan?.hard_limit_usd),
    Rada: Boolean(raw?.council_plan?.members?.length),
    Modele: Boolean(raw?.council_plan?.members?.length),
  };
  return template.map((step, index) => ({
    ...step,
    done: fieldDone[step.label] ?? index < doneCount,
  }));
}

function extractModules(raw: RawProject): string[] {
  const canonicalModules = uniqueStrings([
    ...asList(raw?.canon_snapshot?.modules),
    ...asList(raw?.worker_plan?.modules),
  ]);
  if (canonicalModules.length > 0) return canonicalModules;

  const projectionModules = uniqueStrings([
    ...asList(raw?.modules),
    ...asList(raw?.execution_plan?.modules),
  ])
    .filter((moduleName) => !moduleName.includes("::module::"));
  if (projectionModules.length > 0) return projectionModules;

  return uniqueStrings(asList(raw?.preferred_stack));
}

function deriveBlockers(raw: RawProject): number {
  let count = 0;
  const approvals = raw?.approvals && typeof raw.approvals === "object" ? raw.approvals : {};
  count += Object.values(approvals).filter((value) => value === false).length;
  if (raw?.build_pending_ticket_id) count += 1;
  if (raw?.human_gate_session_id && raw?.human_gate_status !== "approved") count += 1;
  return count;
}

function deriveGovernance(raw: RawProject, blockers: number, status: ProjectStatus): GovernanceStatus {
  if (status === "blocked") return "blocked";
  if (blockers > 0 || raw?.build_pending_ticket_id) return "pending_review";
  return "clear";
}

function deriveConfidence(raw: RawProject): number {
  if (typeof raw?.confidence === "number") return Math.max(0, Math.min(1, raw.confidence));
  if (raw?.council_plan?.members?.length && raw?.masterplan && raw?.canonical_book) return 0.78;
  if (raw?.masterplan && raw?.canonical_book) return 0.68;
  return 0.55;
}

function normalizeProject(raw: RawProject): ProjectEnriched {
  const id = String(raw?.project_id ?? raw?.id ?? raw?.plan_id ?? "").trim();
  const safeId = id || String(raw?.title ?? raw?.name ?? "project-untracked")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "project-untracked";
  const blockers = deriveBlockers(raw);
  const status = normalizeStatus(raw);
  const phase = derivePhase(raw);
  const progress = deriveProgress(raw, phase, status);
  const modules = extractModules(raw);
  const createdAt = toIsoTimestamp(raw?.created_at ?? raw?.emitted_at, FALLBACK_NOW_ISO);
  const deadline = toIsoTimestamp(raw?.timeline_end ?? raw?.deadline, addDaysIso(createdAt, phase === "stable" ? 30 : 90));
  const phaseIdx = phases.indexOf(phase);
  const councilMembers = asList(raw?.council_plan?.members);

  return {
    id: safeId,
    name: compactText(raw?.title ?? raw?.name ?? safeId, safeId),
    description: compactText(raw?.description ?? raw?.idea ?? raw?.goal ?? "Projekt utworzony w AEIS"),
    phase,
    phase_index: phaseIdx >= 0 ? phaseIdx : 0,
    progress,
    risk: normalizeRisk(raw, status, blockers),
    owner: compactText(raw?.owner_id ?? raw?.owner ?? "operator", "operator"),
    agents: uniqueStrings(councilMembers.map((member) => {
      if (!member || typeof member !== "object") return "";
      const record = member as Record<string, unknown>;
      return record.role ?? record.model_id;
    })),
    modules,
    source_status: String(raw?.status ?? "active"),
    status,
    governance: deriveGovernance(raw, blockers, status),
    module_deps: modules.length,
    blockers,
    confidence: deriveConfidence(raw),
    timeline_start: createdAt,
    timeline_end: deadline,
    phase_steps: buildPhaseSteps(raw, phase, progress),
  };
}

function formatShortDate(dateIso: string): string {
  return new Date(dateIso).toLocaleDateString("pl-PL", { month: "short", day: "numeric" });
}

/* ---------- Gantt-like timeline ---------- */

function GanttTimeline({ project, allProjects }: { project: ProjectEnriched; allProjects: ProjectEnriched[] }) {
  const allStarts = allProjects.map((p) => new Date(p.timeline_start).getTime());
  const allEnds = allProjects.map((p) => new Date(p.timeline_end).getTime());
  const rangeStart = allStarts.length > 0 ? Math.min(...allStarts) : FALLBACK_NOW_MS;
  const rangeEnd = allEnds.length > 0 ? Math.max(...allEnds) : rangeStart + 30 * 86_400_000;
  const rangeWidth = Math.max(1, rangeEnd - rangeStart);

  const dayToPercent = (dateStr: string) => {
    const d = new Date(dateStr).getTime();
    return Math.max(0, Math.min(100, ((d - rangeStart) / rangeWidth) * 100));
  };

  const leftPct = dayToPercent(project.timeline_start);
  const rawWidthPct = dayToPercent(project.timeline_end) - leftPct;
  const widthPct = Math.max(8, rawWidthPct);
  const progressPct = (project.progress / 100) * widthPct;

  const months: string[] = [];
  const start = new Date(rangeStart);
  const end = new Date(rangeEnd);
  const cur = new Date(start.getFullYear(), start.getMonth(), 1);
  while (cur <= end) {
    months.push(cur.toLocaleDateString("pl-PL", { month: "short", year: "2-digit" }));
    cur.setMonth(cur.getMonth() + 1);
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
        {months.map((month) => (
          <div key={month} className="flex-1 text-center">{month}</div>
        ))}
      </div>
      <div className="relative h-7 rounded bg-secondary/30">
        {months.slice(1).map((_, i) => (
          <div
            key={i}
            className="absolute top-0 bottom-0 w-px bg-[rgba(148,163,184,0.06)]"
            style={{ left: `${((i + 1) / months.length) * 100}%` }}
          />
        ))}
        <div
          className="absolute top-0.5 bottom-0.5 rounded-sm bg-primary/10 border border-primary/15"
          style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
        />
        <motion.div
          className={cn("absolute top-0.5 bottom-0.5 rounded-sm", riskBar[project.risk])}
          initial={{ width: 0 }}
          animate={{ left: `${leftPct}%`, width: `${progressPct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
        <div
          className="absolute top-0.5 bottom-0.5 flex items-center px-2 text-[10px] font-medium text-foreground/80 overflow-hidden whitespace-nowrap"
          style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
        >
          {project.name}
        </div>
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-sylion-amber/60 z-10"
          style={{ left: `${dayToPercent(FALLBACK_NOW_ISO)}%` }}
        >
          <div className="absolute -top-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-sylion-amber" />
        </div>
      </div>
    </div>
  );
}

/* ---------- Dependencies Graph ---------- */

function DependenciesGraph({ project }: { project: ProjectEnriched }) {
  const deps = project.modules;

  return (
    <div className="relative min-h-40">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
        <div className="px-3 py-1.5 rounded-lg bg-primary/15 border border-primary/25 text-xs font-semibold text-primary max-w-[260px] truncate">
          {project.name}
        </div>
      </div>
      {deps.length === 0 && (
        <div className="absolute inset-x-0 bottom-2 text-center text-xs text-muted-foreground">
          Brak jawnych modułów w projekcji projektu.
        </div>
      )}
      {deps.map((dep, i) => {
        const angle = (2 * Math.PI * i) / deps.length - Math.PI / 2;
        const rx = 130;
        const ry = 55;
        const x = 50 + Math.cos(angle) * (rx / 3);
        const y = 50 + Math.sin(angle) * (ry / 1.5);
        return (
          <div key={dep} className="absolute" style={{ left: `${x}%`, top: `${y}%`, transform: "translate(-50%, -50%)" }}>
            <div className="px-2 py-1 rounded bg-[#0f1629] border border-[rgba(148,163,184,0.08)] text-[10px] text-muted-foreground whitespace-nowrap">
              {dep}
            </div>
          </div>
        );
      })}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ overflow: "visible" }}>
        {deps.map((dep, i) => {
          const angle = (2 * Math.PI * i) / deps.length - Math.PI / 2;
          const rx = 130;
          const ry = 55;
          const x = 50 + Math.cos(angle) * (rx / 3);
          const y = 50 + Math.sin(angle) * (ry / 1.5);
          return (
            <motion.line
              key={dep}
              x1="50%" y1="50%" x2={`${x}%`} y2={`${y}%`}
              stroke="rgba(148,163,184,0.12)"
              strokeWidth="1"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.05 * i }}
            />
          );
        })}
      </svg>
    </div>
  );
}

/* ---------- Project Card ---------- */

function ProjectCard({ project, selected, onSelect }: { project: ProjectEnriched; selected: boolean; onSelect: () => void }) {
  const StatusIcon = statusIconMap[project.status] || CircleDot;
  const stopLinkClick = (event: MouseEvent<HTMLAnchorElement>) => event.stopPropagation();

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card
        data-testid={`project-card-${project.id}`}
        className={cn(
          "p-5 cursor-pointer transition-all duration-200",
          "bg-[#0f1629] border-[rgba(148,163,184,0.08)]",
          selected
            ? "border-primary/30 ring-1 ring-primary/10"
            : "hover:border-[rgba(148,163,184,0.18)]",
        )}
        onClick={onSelect}
      >
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center shrink-0", riskBg[project.risk])}>
              <FolderKanban className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-semibold truncate">{project.name}</h3>
              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{project.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <Badge variant="outline" className={cn("text-[10px] border", riskBg[project.risk])}>
              Ryzyko: {riskLabels[project.risk]}
            </Badge>
            <div
              className={cn("w-6 h-6 rounded-full flex items-center justify-center", project.status === "active" ? "bg-sylion-green/15" : "bg-sylion-amber/15")}
              title={statusLabels[project.status]}
            >
              <StatusIcon className={cn("w-3.5 h-3.5", statusColor[project.status])} />
            </div>
          </div>
        </div>

        <div className="mb-3">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] text-muted-foreground">Etap: {phaseLabels[project.phase] ?? project.phase}</span>
            <span className="text-[10px] text-muted-foreground">Stan: {formatSourceStatus(project.source_status)}</span>
          </div>
          <div className="flex items-center gap-1">
            {project.phase_steps.map((step, i) => (
              <div key={`${step.label}-${i}`} className="flex-1 flex flex-col items-center gap-0.5 min-w-0">
                <div className={cn(
                  "w-full h-1 rounded-full",
                  step.done ? "bg-sylion-green" : i === project.phase_steps.findIndex((s) => !s.done) ? "bg-sylion-amber/60" : "bg-secondary/50",
                )} />
                <span className={cn("text-[9px] truncate max-w-full", step.done ? "text-sylion-green" : "text-muted-foreground/60")}>{step.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] text-muted-foreground">Postęp</span>
            <span className={cn("text-base font-bold", project.progress >= 90 ? "text-sylion-green" : project.progress >= 70 ? "text-sylion-blue" : "text-sylion-amber")}>
              {project.progress}%
            </span>
          </div>
          <div className="w-full h-2 rounded-full bg-secondary/50">
            <motion.div
              className={cn("h-full rounded-full", progressColor(project.progress))}
              initial={{ width: 0 }}
              animate={{ width: `${project.progress}%` }}
              transition={{ duration: 0.7, ease: "easeOut" }}
            />
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2">
          <div className="text-center">
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Opiekun</p>
            <p className="text-[11px] font-medium mt-0.5 truncate">{project.owner}</p>
          </div>
          <div className="text-center">
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Moduły</p>
            <p className="text-[11px] font-medium mt-0.5">{project.module_deps}</p>
          </div>
          <div className="text-center">
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Blokady</p>
            <p className={cn("text-[11px] font-medium mt-0.5", project.blockers > 0 ? "text-sylion-amber" : "text-sylion-green")}>
              {project.blockers}
            </p>
          </div>
          <div className="text-center">
            <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Pewność</p>
            <p className={cn("text-[11px] font-medium mt-0.5", confidenceColor(project.confidence))}>
              {(project.confidence * 100).toFixed(0)}%
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between mt-3 pt-3 border-t border-[rgba(148,163,184,0.06)]">
          <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
            <Timer className="w-3 h-3" />
            <span>{formatShortDate(project.timeline_start)} - {formatShortDate(project.timeline_end)}</span>
          </div>
          {project.governance !== "clear" && (
            <Badge variant="outline" className="text-[9px] h-5 border-sylion-amber/20 text-sylion-amber">
              <Shield className="w-2.5 h-2.5 mr-0.5" />
              {governanceLabels[project.governance]}
            </Badge>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-4">
          <Link
            href={`/projects/${project.id}`}
            onClick={stopLinkClick}
            className="inline-flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-semibold text-primary-foreground transition hover:bg-primary/90"
          >
            Otwórz projekt
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          <Link
            href={`/projects/${project.id}/lifecycle`}
            onClick={stopLinkClick}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[rgba(148,163,184,0.16)] px-3 text-xs text-muted-foreground transition hover:text-foreground hover:border-[rgba(148,163,184,0.28)]"
          >
            Cykl życia
          </Link>
          <Link
            href={`/projects/${project.id}/orchestration`}
            onClick={stopLinkClick}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[rgba(148,163,184,0.16)] px-3 text-xs text-muted-foreground transition hover:text-foreground hover:border-[rgba(148,163,184,0.28)]"
          >
            Meta-orkiestracja
          </Link>
        </div>
      </Card>
    </motion.div>
  );
}

/* ---------- Main page ---------- */

export default function ProjectsPage() {
  const { data: health } = useHealth();
  const { data: projectsData, loading: projectsLoading, error: projectsError } = useProjects();
  const { data: workflowsData } = useWorkflows();
  const { data: jobsData } = useJobs();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const backendLive = health.status === "ok";
  const liveProjects = listFromProjectsResponse(projectsData);

  const displayProjects: ProjectEnriched[] = useMemo(() => {
    return liveProjects.map(normalizeProject).filter((project) => project.id);
  }, [liveProjects]);

  const active = displayProjects.filter((p) => p.status === "active").length;
  const completed = displayProjects.filter((p) => p.status === "completed").length;
  const atRisk = displayProjects.filter((p) => p.risk === "high" || p.risk === "critical").length;
  const avgProgress = displayProjects.length > 0
    ? Math.round(displayProjects.reduce((a, b) => a + b.progress, 0) / displayProjects.length)
    : 0;

  const selectedProject = displayProjects.find((p) => p.id === selectedId) ?? null;

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center">
              <FolderKanban className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Projekty</h1>
              <p className="text-sm text-muted-foreground">Realne projekty AEIS z endpointu /api/v1/projects, ich etap, blokady i ścieżki dalszej pracy.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {backendLive && (
              <>
                <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green">
                  {(workflowsData.workflows ?? []).length} workflowy
                </Badge>
                <Badge variant="outline" className="text-[10px] border-sylion-amber/30 text-sylion-amber">
                  {(jobsData.jobs ?? []).length} zadania
                </Badge>
              </>
            )}
          </div>
        </div>
      </motion.div>

      {!backendLive && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="p-4 bg-sylion-red/5 border-sylion-red/20">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-sylion-red/10 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-4 h-4 text-sylion-red" />
              </div>
              <div>
                <p className="text-sm font-medium text-sylion-red">Backend nie odpowiada</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Panel nie może pobrać projektów. Sprawdź usługę API na localhost:3001/api.
                </p>
              </div>
            </div>
          </Card>
        </motion.div>
      )}

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.05 }}>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Card className="relative overflow-hidden p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Aktywne</p>
                <p className="text-2xl font-semibold text-sylion-green">{active}</p>
              </div>
              <div className="w-9 h-9 rounded-lg bg-sylion-green/10 flex items-center justify-center">
                <Activity className="w-4 h-4 text-sylion-green" />
              </div>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-sylion-green/20 to-transparent" />
          </Card>
          <Card className="relative overflow-hidden p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Ukończone</p>
                <p className="text-2xl font-semibold text-primary">{completed}</p>
              </div>
              <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                <CheckCircle2 className="w-4 h-4 text-primary" />
              </div>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
          </Card>
          <Card className="relative overflow-hidden p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Ryzykowne</p>
                <p className="text-2xl font-semibold text-sylion-red">{atRisk}</p>
              </div>
              <div className="w-9 h-9 rounded-lg bg-sylion-red/10 flex items-center justify-center">
                <AlertTriangle className="w-4 h-4 text-sylion-red" />
              </div>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-sylion-red/20 to-transparent" />
          </Card>
          <Card className="relative overflow-hidden p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Średni postęp</p>
                <p className="text-2xl font-semibold text-sylion-blue">{avgProgress}%</p>
              </div>
              <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 flex items-center justify-center">
                <TrendingUp className="w-4 h-4 text-sylion-blue" />
              </div>
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-sylion-blue/20 to-transparent" />
          </Card>
        </div>
      </motion.div>

      {projectsLoading && displayProjects.length === 0 && (
        <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <Activity className="w-4 h-4 animate-pulse text-primary" />
            Pobieram listę projektów z /api/v1/projects...
          </div>
        </Card>
      )}

      {!projectsLoading && displayProjects.length === 0 && (
        <Card className="p-6 bg-[#0f1629] border-dashed border-[rgba(148,163,184,0.18)]" data-testid="projects-empty-state">
          <div className="flex items-start gap-3">
            <Network className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="text-sm font-semibold">Brak projektów w projekcji dashboardu</p>
              <p className="text-sm text-muted-foreground">
                Panel odpytał /api/v1/projects, ale nie dostał listy projektów. {projectsError ? `Błąd: ${projectsError}` : "Utwórz projekt z pierwszego uruchomienia albo odśwież API."}
              </p>
            </div>
          </div>
        </Card>
      )}

      {displayProjects.length > 0 && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {displayProjects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              selected={selectedId === project.id}
              onSelect={() => setSelectedId(selectedId === project.id ? null : project.id)}
            />
          ))}
        </div>
      )}

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}>
        <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <Timer className="w-4 h-4 text-primary" />
            Oś projektów
          </h2>
          <div className="space-y-3">
            {displayProjects.length === 0 ? (
              <p className="text-xs text-muted-foreground">Brak danych do osi czasu.</p>
            ) : (
              displayProjects.map((project, i) => (
                <motion.div
                  key={project.id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: 0.06 * i }}
                >
                  <GanttTimeline project={project} allProjects={displayProjects} />
                </motion.div>
              ))
            )}
          </div>
          <div className="flex items-center gap-1.5 mt-3 text-[10px] text-sylion-amber">
            <div className="w-0.5 h-3 bg-sylion-amber/60 rounded-full" />
            <span>Dzisiaj: {new Date(FALLBACK_NOW_ISO).toLocaleDateString("pl-PL", { month: "short", day: "numeric", year: "numeric" })}</span>
          </div>
        </Card>
      </motion.div>

      <AnimatePresence>
        {selectedProject && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold flex items-center gap-2">
                  <GitBranch className="w-4 h-4 text-primary" />
                  Moduły projektu: {selectedProject.name}
                </h2>
                <Badge variant="outline" className="text-[9px] border-[rgba(148,163,184,0.12)] text-muted-foreground">
                  {selectedProject.module_deps} moduły
                </Badge>
              </div>
              <DependenciesGraph project={selectedProject} />
              <div className="mt-4 pt-3 border-t border-[rgba(148,163,184,0.06)]">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="text-center p-2 rounded-lg bg-secondary/20">
                    <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Etap</p>
                    <p className="text-xs font-semibold mt-0.5">{phaseLabels[selectedProject.phase] ?? selectedProject.phase}</p>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-secondary/20">
                    <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Pewność</p>
                    <p className={cn("text-xs font-semibold mt-0.5", confidenceColor(selectedProject.confidence))}>
                      {(selectedProject.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="text-center p-2 rounded-lg bg-secondary/20">
                    <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Decyzje</p>
                    <p className={cn("text-xs font-semibold mt-0.5", selectedProject.governance === "clear" ? "text-sylion-green" : "text-sylion-amber")}>
                      {governanceLabels[selectedProject.governance]}
                    </p>
                  </div>
                </div>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {!selectedProject && displayProjects.length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}>
          <p className="text-center text-xs text-muted-foreground/60">
            Kliknij kartę projektu, żeby zobaczyć moduły, albo użyj przycisków na karcie, żeby przejść dalej.
          </p>
        </motion.div>
      )}
    </div>
  );
}
