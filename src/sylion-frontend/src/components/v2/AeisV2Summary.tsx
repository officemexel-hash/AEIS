"use client";

/**
 * SYLION AEIS v2 — Operator overview summary panel.
 *
 * Top-of-dashboard glance card for the v2 plane (W15-W19): pulls 4 KPIs
 * in parallel from existing v2 endpoints and renders a responsive grid
 * + quick-jump links to the dedicated v2 pages.
 *
 * Endpoints (all read-only, no backend changes):
 *   - GET /api/v1/ontology/types     -> count            (W15 manifests)
 *   - GET /api/v1/federation/health  -> active_nodes,
 *                                       total_nodes,
 *                                       routing_decisions_total (W17)
 *   - GET /api/v1/apps               -> count            (W16 apps)
 *
 * Refresh cadence: initial fetch on mount + setInterval every 30s.
 * Errors per-endpoint do NOT cascade — Promise.allSettled isolates them.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { request } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  AppWindow,
  Brain,
  Database,
  Signal,
  ArrowRight,
} from "lucide-react";

/* ============================================================
   Types — mirror the shape the four endpoints already return
   ============================================================ */

interface OntologyTypesResponse {
  count?: number;
  types?: unknown[];
}

interface FederationHealthResponse {
  active_nodes?: number;
  total_nodes?: number;
  routing_decisions_total?: number;
}

interface AppsListResponse {
  count?: number;
  apps?: unknown[];
}

type KpiState = "loading" | "ok" | "zero" | "error";

interface KpiData {
  value: number | null;
  subtitle: string;
  state: KpiState;
}

interface SummaryState {
  ontology: KpiData;
  federationNodes: KpiData;
  routingDecisions: KpiData;
  apps: KpiData;
}

const INITIAL: KpiData = {
  value: null,
  subtitle: "",
  state: "loading",
};

const REFRESH_MS = 30_000;

/* ============================================================
   Single KPI card — variant of v2/widgets/KpiCard tuned for
   the operator overview (status dot + subtitle + icon block).
   ============================================================ */

function StatusDot({ state }: { state: KpiState }) {
  const cls =
    state === "ok"
      ? "bg-emerald-400"
      : state === "zero"
      ? "bg-amber-400"
      : state === "error"
      ? "bg-red-400"
      : "bg-muted-foreground/40 animate-pulse";
  return <span className={cn("w-2 h-2 rounded-full shrink-0", cls)} />;
}

interface SummaryKpiProps {
  label: string;
  data: KpiData;
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
}

function SummaryKpi({ label, data, icon: Icon, iconColor, iconBg }: SummaryKpiProps) {
  const isError = data.state === "error";
  const display =
    data.state === "loading"
      ? "..."
      : isError || data.value === null
      ? "—"
      : data.value.toLocaleString("pl-PL");
  const tooltip = isError ? "Endpoint nieosięgalny" : undefined;

  return (
    <Card
      className="rounded-xl p-4 transition-all duration-300"
      style={{
        background: "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
        borderColor: "rgba(148,163,184,0.06)",
      }}
      title={tooltip}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <StatusDot state={data.state} />
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider truncate">
              {label}
            </p>
          </div>
          <p
            className={cn(
              "text-2xl font-bold tabular-nums",
              isError ? "text-red-400" : "text-foreground",
            )}
          >
            {display}
          </p>
          <p className="text-[10px] text-muted-foreground/70 mt-1 truncate">
            {data.subtitle || " "}
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

const QUICK_LINKS: { href: string; label: string; icon: React.ElementType; color: string }[] = [
  { href: "/ontology", label: "Ontologia (W15)", icon: Database, color: "#A855F7" },
  { href: "/federation", label: "Federacja (W17)", icon: Signal, color: "#2F6BFF" },
  { href: "/apps-builder", label: "Apps Builder (W16)", icon: AppWindow, color: "#17C964" },
  { href: "/policy", label: "Polityka (W19)", icon: Brain, color: "#F59E0B" },
];

export function AeisV2Summary() {
  const [state, setState] = useState<SummaryState>({
    ontology: INITIAL,
    federationNodes: INITIAL,
    routingDecisions: INITIAL,
    apps: INITIAL,
  });

  useEffect(() => {
    let cancelled = false;

    const toKpi = (
      value: number | undefined,
      subtitle: string,
    ): KpiData => {
      if (typeof value !== "number" || Number.isNaN(value)) {
        return { value: null, subtitle, state: "error" };
      }
      return {
        value,
        subtitle,
        state: value > 0 ? "ok" : "zero",
      };
    };

    const fetchAll = async () => {
      const results = await Promise.allSettled([
        request<OntologyTypesResponse>("/api/v1/ontology/types"),
        request<FederationHealthResponse>("/api/v1/federation/health"),
        request<AppsListResponse>("/api/v1/apps"),
      ]);
      if (cancelled) return;

      const [ontologyRes, federationRes, appsRes] = results;

      const ontology: KpiData =
        ontologyRes.status === "fulfilled"
          ? toKpi(ontologyRes.value?.count, "manifesty W15")
          : { value: null, subtitle: "manifesty W15", state: "error" };

      let federationNodes: KpiData;
      let routingDecisions: KpiData;
      if (federationRes.status === "fulfilled") {
        const h = federationRes.value ?? {};
        const total =
          typeof h.total_nodes === "number" && !Number.isNaN(h.total_nodes)
            ? h.total_nodes
            : 0;
        federationNodes = toKpi(h.active_nodes, `z ${total} lacznie`);
        routingDecisions = toKpi(h.routing_decisions_total, "decyzji od startu");
      } else {
        federationNodes = { value: null, subtitle: "z 0 lacznie", state: "error" };
        routingDecisions = {
          value: null,
          subtitle: "decyzji od startu",
          state: "error",
        };
      }

      const apps: KpiData =
        appsRes.status === "fulfilled"
          ? toKpi(appsRes.value?.count, "kompozycji W16")
          : { value: null, subtitle: "kompozycji W16", state: "error" };

      setState({ ontology, federationNodes, routingDecisions, apps });
    };

    void fetchAll();
    const id = window.setInterval(() => {
      void fetchAll();
    }, REFRESH_MS);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <div className="space-y-3">
      {/* KPI grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <SummaryKpi
          label="Object Types"
          data={state.ontology}
          icon={Database}
          iconColor="#A855F7"
          iconBg="rgba(168,85,247,0.08)"
        />
        <SummaryKpi
          label="Federation Nodes"
          data={state.federationNodes}
          icon={Signal}
          iconColor="#2F6BFF"
          iconBg="rgba(47,107,255,0.08)"
        />
        <SummaryKpi
          label="Routing Decisions"
          data={state.routingDecisions}
          icon={Brain}
          iconColor="#F59E0B"
          iconBg="rgba(245,158,11,0.08)"
        />
        <SummaryKpi
          label="Apps Available"
          data={state.apps}
          icon={AppWindow}
          iconColor="#17C964"
          iconBg="rgba(23,201,100,0.08)"
        />
      </div>

      {/* See more — quick-jump links */}
      <div className="flex flex-wrap gap-2">
        {QUICK_LINKS.map((link) => {
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              className="group inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[11px] transition-colors hover:bg-white/[0.03]"
              style={{
                background: "rgba(15,22,41,0.6)",
                borderColor: "rgba(148,163,184,0.08)",
              }}
            >
              <Icon className="w-3.5 h-3.5" style={{ color: link.color }} />
              <span className="text-foreground">{link.label}</span>
              <ArrowRight className="w-3 h-3 text-muted-foreground/40 group-hover:text-muted-foreground transition-colors" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export default AeisV2Summary;
