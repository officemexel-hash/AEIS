"use client";

import { ArrowRight } from "lucide-react";

const NODES = [
  {
    title: "Planner",
    desc: "Rozbija cel na zadania, proponuje warianty i Masterplan.",
  },
  {
    title: "Workers",
    desc: "Wykonuja taski zgodnie ze Skills i zakresem uprawnien.",
  },
  {
    title: "Verifier",
    desc: "SprawdŹa kontrakt wyj?cia, testy i wymagania runtime.",
  },
  {
    title: "Critic",
    desc: "Szuka bledow, luk, ryzyk i brakujacych dowodow.",
  },
  {
    title: "Council / HG",
    desc: "Glosowanie, sentinels, Evidence Pack, decyzja operatora.",
  },
];

export function CockpitAgentFlow() {
  return (
    <div
      className="rounded-2xl border border-white/10 p-5"
      style={{ background: "linear-gradient(180deg,rgba(17,24,39,.92),rgba(10,14,25,.92))" }}
    >
      <h3 className="mb-1 text-base font-bold text-white">Przepływ kontroli agentow</h3>
      <p className="mb-4 text-[11px] text-slate-500">
        Agenci nie komunikuj? się niejawnie — każdy krok ma event, kontrakt wyj?cia i audyt.
      </p>
      <div className="flex flex-wrap items-stretch gap-2">
        {NODES.map((node, i) => (
          <div key={node.title} className="flex items-center gap-2">
            <div className="min-w-[120px] rounded-xl border border-[#75a7ff]/18 bg-[#75a7ff]/8 p-3">
              <div className="text-sm font-semibold text-white">{node.title}</div>
              <div className="mt-1 text-[11px] leading-relaxed text-slate-400">{node.desc}</div>
            </div>
            {i < NODES.length - 1 ? (
              <ArrowRight className="h-4 w-4 flex-none text-slate-600" />
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
