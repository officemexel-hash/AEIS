"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity, ArrowRight, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api/client";

type GuardEntry = {
  guard_id?: string;
  id?: string;
  name?: string;
  status?: string;
  description?: string;
};

const guardLinks = [
  { href: "/coherence-guard", label: "Straznik spojnosci" },
  { href: "/cost-guard", label: "Straznik kosztow" },
  { href: "/security-guard", label: "Straznik bezpiecze?stwa" },
  { href: "/quality-guard", label: "Strażnik jakości" },
  { href: "/provenance-guard", label: "Straznik pochodzenia" },
];

export default function GuardsPage() {
  const [suite, setSuite] = useState<GuardEntry[]>([]);
  const [panel, setPanel] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [suiteData, panelData] = await Promise.all([
          api.listGuardSuite(),
          api.getGuardSuiteAggregatedPanel(),
        ]);
        if (cancelled) return;
        setSuite(Array.isArray(suiteData?.guards) ? suiteData.guards : []);
        setPanel(panelData ?? null);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Nie udało się pobrać panelu straznikow.");
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const status = error ? "błąd" : suite.length > 0 ? "live" : "oczekuje";

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-white/10 bg-[#0f1629] p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-400/10 ring-1 ring-emerald-400/20">
              <ShieldCheck className="h-5 w-5 text-emerald-300" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-white">Panel strażników AEIS</h1>
              <p className="mt-1 text-sm text-slate-400">
                Zbiorczy widok strażników: koszty, bezpieczeństwo, jakość, pochodzenie i spójność.
              </p>
            </div>
          </div>
          <span className="rounded-md border border-white/10 px-2 py-1 text-[11px] uppercase text-slate-300">
            {status}
          </span>
        </div>
        {error ? (
          <p className="mt-3 rounded-md border border-red-400/25 bg-red-400/10 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        ) : null}
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {guardLinks.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="group rounded-xl border border-white/10 bg-[#101827] p-4 transition hover:border-emerald-300/40"
          >
            <div className="flex items-center justify-between gap-2">
              <Activity className="h-4 w-4 text-emerald-300" />
              <ArrowRight className="h-4 w-4 text-slate-500 transition group-hover:text-emerald-300" />
            </div>
            <p className="mt-3 text-sm font-medium text-white">{item.label}</p>
          </Link>
        ))}
      </section>

      <section className="rounded-xl border border-white/10 bg-[#0f1629] p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Statusy runtime</h2>
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {suite.map((guard) => {
            const id = guard.guard_id ?? guard.id ?? guard.name ?? "guard";
            return (
              <div key={id} className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-white">{guard.name ?? id}</p>
                  <span className="rounded bg-emerald-400/10 px-2 py-0.5 text-[10px] text-emerald-300">
                    {guard.status ?? "ready"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{guard.description ?? id}</p>
              </div>
            );
          })}
          {suite.length === 0 && !error ? (
            <p className="text-sm text-slate-500">Brak wpis?w guard suite albo backend nie zwróci? listy.</p>
          ) : null}
        </div>
      </section>

      <section className="rounded-xl border border-white/10 bg-[#0f1629] p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Panel zbiorczy API</h2>
        <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-black/30 p-3 text-xs text-slate-300">
          {JSON.stringify(panel ?? {}, null, 2)}
        </pre>
      </section>
    </div>
  );
}
