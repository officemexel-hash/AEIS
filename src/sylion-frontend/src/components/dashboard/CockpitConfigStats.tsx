"use client";

import { Key, Cpu, GitBranch, Wrench } from "lucide-react";

interface Props {
  projectCount: number;
}

// Static capability stats — wired to static data until backend exposes /api/v1/advisor/cockpit/overview
const STATS = [
  {
    icon: Key,
    title: "Klucze API",
    desc: "Dodaj, testuj, rotuj i blokuj dostawcę. Sekrety trafiają do Vault.",
    metric: "5",
    metricLabel: "aktywnych dostawców",
    href: "/costs",
  },
  {
    icon: Cpu,
    title: "Modele lokalne",
    desc: "Zdrowie Ollama, benchmark, fallback i kara za niższą pewność.",
    metric: "2",
    metricLabel: "gotowe / 1 brak",
    href: "/costs",
  },
  {
    icon: GitBranch,
    title: "Routing ról",
    desc: "rola × ryzyko × domena × tryb strategiczny → model.",
    metric: "27",
    metricLabel: "aktywnych regul",
    href: "/decisions",
  },
  {
    icon: Wrench,
    title: "Skills",
    desc: "SZKIC → OPUBLIKOWANY → WYCOFANY, testy i powiązanie z projektami.",
    metric: "18",
    metricLabel: "opublikowanych skilli",
    href: "/agents",
  },
];

export function CockpitConfigStats({ projectCount }: Props) {
  return (
    <section>
      <div className="mb-3">
        <h2 className="text-lg font-bold text-white">Modele, klucze API, Skills</h2>
        <p className="text-[11px] text-slate-500">
          Konfiguracja jest czescia trybu operatora, nie tylko trybu technicznego.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {STATS.map((s) => {
          const Icon = s.icon;
          return (
            <a
              key={s.title}
              href={s.href}
              className="group rounded-2xl border border-white/10 bg-white/[0.04] p-4 transition hover:border-[#75a7ff]/30 hover:bg-[#75a7ff]/5"
            >
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#75a7ff]/10">
                  <Icon className="h-4 w-4 text-[#75a7ff]" />
                </div>
                <h4 className="text-sm font-semibold text-white">{s.title}</h4>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-slate-400">{s.desc}</p>
              <div className="mt-3">
                <span className="text-2xl font-black text-white">{s.metric}</span>
                <span className="ml-2 text-[11px] text-slate-500">{s.metricLabel}</span>
              </div>
            </a>
          );
        })}
      </div>
    </section>
  );
}
