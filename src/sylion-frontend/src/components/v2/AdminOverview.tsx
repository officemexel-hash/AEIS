"use client";

/**
 * SYLION AEIS v2 — operator admin overview.
 *
 * Sprint 4 deliverable. Sits at /v2/admin and surfaces the v2 plane's
 * health + canary state at a glance:
 *
 *   - W19 evaluator status (enabled flag + canary percent)
 *   - W19 render outcomes (allow/deny/skipped/error)
 *   - W19 deny rate (denies / renders)
 *   - Audit chain integrity per module (size + violations)
 *   - Adapter bus circuit-breaker state per adapter
 *
 * Data source: GET /api/v1/metrics/v2 — plain-text Prometheus
 * exposition. We parse the lines we care about with a tiny
 * line-by-line tokenizer so we don't need a Prometheus client lib.
 *
 * Refresh cadence: 30s. Errors surface as a single inline banner so
 * the operator sees if the metrics endpoint is unreachable.
 */

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  Shield,
  Sliders,
  Activity,
  AlertTriangle,
  Cpu,
  Zap,
} from "lucide-react";

const METRICS_URL =
  (process.env.NEXT_PUBLIC_API_URL || "") +
  "/api/v1/metrics/v2";

const REFRESH_MS = 30_000;

/* ============================================================
   Tiny Prometheus-text parser.

   Supports the subset we emit:
     metric_name 42
     metric_name{label="value",other="x"} 42

   Skips HELP / TYPE / blank lines and unparseable inputs.
   ============================================================ */

interface Sample {
  name: string;
  labels: Record<string, string>;
  value: number;
}

function parsePromText(text: string): Sample[] {
  const out: Sample[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const m = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+(\S+)$/);
    if (!m) continue;
    const [, name, labelStr, valueStr] = m;
    const value = Number(valueStr);
    if (!Number.isFinite(value)) continue;
    const labels: Record<string, string> = {};
    if (labelStr) {
      // labels are comma-separated key="value" pairs
      const parts = labelStr.match(/(\w+)="((?:\\.|[^"\\])*)"/g) || [];
      for (const p of parts) {
        const lm = p.match(/^(\w+)="((?:\\.|[^"\\])*)"$/);
        if (!lm) continue;
        labels[lm[1]] = lm[2].replace(/\\"/g, '"').replace(/\\\\/g, "\\");
      }
    }
    out.push({ name, labels, value });
  }
  return out;
}

function pickFirst(samples: Sample[], name: string): number | null {
  const s = samples.find((x) => x.name === name);
  return s ? s.value : null;
}

function sumByName(samples: Sample[], name: string): number {
  return samples
    .filter((s) => s.name === name)
    .reduce((acc, s) => acc + s.value, 0);
}

function sumByNameWhere(
  samples: Sample[],
  name: string,
  predicate: (labels: Record<string, string>) => boolean,
): number {
  return samples
    .filter((s) => s.name === name && predicate(s.labels))
    .reduce((acc, s) => acc + s.value, 0);
}

/* ============================================================
   Aggregation — derive the 9 dashboard KPIs from the samples.
   ============================================================ */

interface DashboardKpis {
  w19EvaluatorEnabled: number | null;
  w19RolloutPercent: number | null;
  w19RendersTotal: number;
  w19DeniesTotal: number;
  w19DenyRatePct: number; // 0..100
  auditChainTotalRows: number;
  auditChainViolationsTotal: number;
  adapterBusCircuitsOpen: number;
  adapterBusFailuresTotal: number;
}

function buildKpis(samples: Sample[]): DashboardKpis {
  const renders = sumByName(samples, "sylion_v2_w19_renders_total");
  const denies = sumByName(samples, "sylion_v2_w19_denies_total");
  return {
    w19EvaluatorEnabled: pickFirst(samples, "sylion_v2_w19_evaluator_enabled"),
    w19RolloutPercent: pickFirst(samples, "sylion_v2_w19_rollout_percent"),
    w19RendersTotal: renders,
    w19DeniesTotal: denies,
    w19DenyRatePct: renders > 0 ? (denies / renders) * 100 : 0,
    auditChainTotalRows: sumByName(samples, "sylion_v2_audit_chain_size"),
    auditChainViolationsTotal: sumByName(
      samples,
      "sylion_v2_audit_chain_violations_total",
    ),
    adapterBusCircuitsOpen: sumByNameWhere(
      samples,
      "adapter_bus_circuit_state",
      (l) => l.state === "open",
    ),
    adapterBusFailuresTotal: sumByName(samples, "adapter_bus_failures_total"),
  };
}

/* ============================================================
   Status helpers — paint each KPI by the operator-relevant
   threshold per W19 production runbook §4.
   ============================================================ */

type Severity = "ok" | "warn" | "alert" | "muted";

function denyRateSeverity(pct: number): Severity {
  if (pct === 0) return "ok";
  if (pct < 5) return "warn";
  return "alert";
}

function violationsSeverity(n: number): Severity {
  if (n === 0) return "ok";
  return "alert"; // any > 0 is page-DPO territory
}

function circuitsSeverity(n: number): Severity {
  if (n === 0) return "ok";
  return "warn";
}

function severityCls(s: Severity): string {
  switch (s) {
    case "ok":
      return "bg-emerald-400";
    case "warn":
      return "bg-amber-400";
    case "alert":
      return "bg-red-400";
    default:
      return "bg-muted-foreground/40 animate-pulse";
  }
}

/* ============================================================
   KPI card — small, dense, dot + value + footnote.
   ============================================================ */

interface KpiCardProps {
  label: string;
  value: string;
  footnote: string;
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
  severity: Severity;
}

function KpiCard({
  label,
  value,
  footnote,
  icon: Icon,
  iconColor,
  iconBg,
  severity,
}: KpiCardProps) {
  return (
    <Card
      className="rounded-xl p-4"
      style={{
        background:
          "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
        borderColor: "rgba(148,163,184,0.06)",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span
              className={cn(
                "w-2 h-2 rounded-full shrink-0",
                severityCls(severity),
              )}
            />
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider truncate">
              {label}
            </p>
          </div>
          <p
            className={cn(
              "text-2xl font-bold tabular-nums",
              severity === "alert" ? "text-red-400" : "text-foreground",
            )}
          >
            {value}
          </p>
          <p className="text-[10px] text-muted-foreground/70 mt-1 truncate">
            {footnote || " "}
          </p>
        </div>
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: iconBg }}
        >
          <Icon className="w-5 h-5" style={{ color: iconColor }} />
        </div>
      </div>
    </Card>
  );
}

/* ============================================================
   Main component
   ============================================================ */

export function AdminOverview() {
  const [samples, setSamples] = useState<Sample[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchOnce = async () => {
      try {
        const res = await fetch(METRICS_URL, {
          headers: { Accept: "text/plain" },
        });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const text = await res.text();
        if (cancelled) return;
        setSamples(parsePromText(text));
        setError(null);
        setLastRefreshAt(new Date());
      } catch (e) {
        if (cancelled) return;
        setError((e as Error).message || "fetch failed");
      }
    };

    void fetchOnce();
    const id = window.setInterval(() => {
      void fetchOnce();
    }, REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const kpis: DashboardKpis | null = useMemo(
    () => (samples ? buildKpis(samples) : null),
    [samples],
  );

  const lastRefresh = lastRefreshAt
    ? lastRefreshAt.toLocaleTimeString("pl-PL", { hour12: false })
    : "—";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-muted-foreground">
          AEIS v2 — Admin Overview
        </h2>
        <p className="text-[10px] text-muted-foreground/60">
          /api/v1/metrics/v2 · odswiezone {lastRefresh}
        </p>
      </div>

      {error ? (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-red-500/30 bg-red-500/5 text-red-300 text-xs">
          <AlertTriangle className="w-4 h-4" />
          <span>Bledy fetch: {error}</span>
        </div>
      ) : null}

      {kpis ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <KpiCard
            label="W19 Evaluator"
            value={
              kpis.w19EvaluatorEnabled === null
                ? "—"
                : kpis.w19EvaluatorEnabled === 1
                  ? "ON"
                  : "OFF"
            }
            footnote={
              kpis.w19EvaluatorEnabled === 1
                ? "feature flag aktywny"
                : "feature flag wylaczony"
            }
            icon={Shield}
            iconColor="#F59E0B"
            iconBg="rgba(245,158,11,0.08)"
            severity={
              kpis.w19EvaluatorEnabled === 1 ? "ok" : "muted"
            }
          />
          <KpiCard
            label="Canary Rollout"
            value={
              kpis.w19RolloutPercent === null
                ? "—"
                : `${kpis.w19RolloutPercent}%`
            }
            footnote="staged dial 0/1/5/25/50/100"
            icon={Sliders}
            iconColor="#2F6BFF"
            iconBg="rgba(47,107,255,0.08)"
            severity={
              kpis.w19RolloutPercent === null
                ? "muted"
                : kpis.w19RolloutPercent === 0
                  ? "muted"
                  : "ok"
            }
          />
          <KpiCard
            label="W19 Renders"
            value={kpis.w19RendersTotal.toLocaleString("pl-PL")}
            footnote={`${kpis.w19DeniesTotal} deny (${kpis.w19DenyRatePct.toFixed(1)}%)`}
            icon={Activity}
            iconColor="#A855F7"
            iconBg="rgba(168,85,247,0.08)"
            severity={denyRateSeverity(kpis.w19DenyRatePct)}
          />
          <KpiCard
            label="Audit Chain Rows"
            value={kpis.auditChainTotalRows.toLocaleString("pl-PL")}
            footnote="laczenie wszystkich modulow"
            icon={Activity}
            iconColor="#17C964"
            iconBg="rgba(23,201,100,0.08)"
            severity="ok"
          />
          <KpiCard
            label="Audit Violations"
            value={kpis.auditChainViolationsTotal.toLocaleString("pl-PL")}
            footnote={
              kpis.auditChainViolationsTotal === 0
                ? "wszystkie chains clean"
                : "uruchom DPO runbook"
            }
            icon={AlertTriangle}
            iconColor="#EF4444"
            iconBg="rgba(239,68,68,0.08)"
            severity={violationsSeverity(kpis.auditChainViolationsTotal)}
          />
          <KpiCard
            label="Open Circuits"
            value={kpis.adapterBusCircuitsOpen.toLocaleString("pl-PL")}
            footnote={`${kpis.adapterBusFailuresTotal} failures total`}
            icon={Cpu}
            iconColor="#F59E0B"
            iconBg="rgba(245,158,11,0.08)"
            severity={circuitsSeverity(kpis.adapterBusCircuitsOpen)}
          />
        </div>
      ) : (
        <div className="text-xs text-muted-foreground">
          <Zap className="w-3 h-3 inline mr-1 animate-pulse" />
          Pobieranie metryk...
        </div>
      )}
    </div>
  );
}

export default AdminOverview;
