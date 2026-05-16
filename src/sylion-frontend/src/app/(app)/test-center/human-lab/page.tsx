"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import { Users, ArrowLeft, RefreshCw } from "lucide-react";
import { HelpTip } from "@/components/common/HelpTip";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "";

interface Persona {
  persona_id: string;
  name: string;
  capability_level: string;
  expertise_domains: string[];
  error_proneness: number;
  attention_span_min: number;
  trust_in_ai_baseline: number;
  risk_tolerance: string;
}

interface Scenario {
  scenario_id: string;
  persona_id: string;
  domain: string;
  workflow_steps: { step: string }[];
  decision_points: { d: string }[];
  difficulty: string;
}

interface PersonaResp {
  starter_count: number;
  extended_count: number;
  total_canonical: number;
  loaded_count: number;
  personas: Persona[];
}

interface ScenarioResp {
  total: number;
  domain: string | null;
  domains_canonical: string[];
  scenarios: Scenario[];
}

const CAPABILITY_COLOR: Record<string, string> = {
  beginner: "bg-amber-500/15 text-amber-700",
  intermediate: "bg-blue-500/15 text-blue-700",
  expert: "bg-emerald-500/15 text-emerald-700",
};

const DIFFICULTY_COLOR: Record<string, string> = {
  easy: "bg-emerald-500/15 text-emerald-700",
  medium: "bg-blue-500/15 text-blue-700",
  hard: "bg-rose-500/15 text-rose-700",
};

export default function HumanLabPage() {
  const backendLive =
    ((useHealth().data as { status?: string })?.status === "ok");

  const [personasResp, setPersonasResp] = useState<PersonaResp | null>(null);
  const [scenariosResp, setScenariosResp] = useState<ScenarioResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [domain, setDomain] = useState<string | null>(null);

  const refresh = async () => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    try {
      const [pRes, sRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/test-center/personas`).then((r) =>
          r.ok ? r.json() : Promise.reject(new Error(`personas ${r.status}`)),
        ),
        fetch(
          `${API_BASE}/api/v1/test-center/scenarios${
            domain ? `?domain=${domain}` : ""
          }`,
        ).then((r) =>
          r.ok ? r.json() : Promise.reject(new Error(`scenarios ${r.status}`)),
        ),
      ]);
      setPersonasResp(pRes);
      setScenariosResp(sRes);
    } catch (e: unknown) {
      setError(String((e as Error)?.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendLive, domain]);

  const personas = useMemo(() => personasResp?.personas ?? [], [personasResp]);
  const scenarios = useMemo(() => scenariosResp?.scenarios ?? [], [scenariosResp]);
  const domains = useMemo(() => scenariosResp?.domains_canonical ?? [], [scenariosResp]);

  const scenariosByDomain = useMemo(() => {
    const map: Record<string, number> = {};
    scenarios.forEach((s) => {
      map[s.domain] = (map[s.domain] || 0) + 1;
    });
    return map;
  }, [scenarios]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/test-center"
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users className="w-6 h-6" />
            Laboratorium operatora
            <HelpTip text="Katalog 21 person operatora i 50 scenariuszy testówych. Symuluje realnych pracowników o różnym poziomie wiedzy (beginner/intermediate/expert), tolerancji ryzyka i podatności na błędy. Użyj do ewaluacji UX i komprehensji systemu." />
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
            {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
        </div>
        <Button onClick={refresh} disabled={loading} size="sm" variant="outline">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          <span className="ml-2">Odśwież</span>
        </Button>
      </div>

      {error && (
        <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
          Błąd: {error}
        </Card>
      )}

      <Card className="p-4">
        <div className="flex items-baseline justify-between mb-3">
          <div className="font-semibold flex items-center">
            Persony — {personasResp?.loaded_count ?? "—"} z{" "}
            {personasResp?.total_canonical ?? "—"} kanonicznych
            <HelpTip text="Persony to syntetyczni pracownicy o zdefiniowanych cechach: capability_level (beginner/intermediate/expert), error_proneness (0-1), trust_in_ai_baseline (0-1), attention_span_min, risk_tolerance, expertise_domains. Symulator używa ich w scenariuszach do oceny, czy UI/workflow działa dla różnych typów użytkowników." />
          </div>
          <div className="text-xs text-muted-foreground">
            {personasResp?.starter_count ?? 0} startowych +{" "}
            {personasResp?.extended_count ?? 0} rozszerzonych
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {personas.map((p) => (
            <Card key={p.persona_id} className="p-3">
              <div className="flex items-baseline justify-between">
                <div className="font-mono text-sm font-semibold">{p.name}</div>
                <Badge
                  variant="outline"
                  className={`text-xs ${
                    CAPABILITY_COLOR[p.capability_level] || ""
                  }`}
                >
                  {p.capability_level}
                </Badge>
              </div>
              <div className="text-xs text-muted-foreground mt-1 space-y-0.5">
                <div>
                  error_proneness:{" "}
                  <span className="font-mono">
                    {p.error_proneness.toFixed(2)}
                  </span>
                </div>
                <div>
                  trust_in_ai:{" "}
                  <span className="font-mono">
                    {p.trust_in_ai_baseline.toFixed(2)}
                  </span>
                </div>
                <div>
                  attention_min:{" "}
                  <span className="font-mono">{p.attention_span_min}</span>
                </div>
                <div>
                  risk: <span className="font-mono">{p.risk_tolerance}</span>
                </div>
                {p.expertise_domains.length > 0 && (
                  <div className="pt-1">
                    {p.expertise_domains.map((d) => (
                      <Badge
                        key={d}
                        variant="outline"
                        className="text-[10px] mr-1"
                      >
                        {d}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      </Card>

      <Card className="p-4">
        <div className="flex items-baseline justify-between mb-3">
          <div className="font-semibold flex items-center">
            Scenariusze — {scenariosResp?.total ?? "—"} z 50 kanonicznych
            <HelpTip text="Scenariusz to przepis testówy: persona + domena + sekwencja kroków workflow + punkty decyzyjne + poziom trudności. Filtruj po domenie, żeby zobaczyć scenariusze dla konkretnego obszaru (np. risk, finance, ops). Użyj do batch-runu w Symulacji." />
          </div>
          <div className="flex flex-wrap gap-1 max-w-[60%] justify-end">
            <button
              onClick={() => setDomain(null)}
              className={`text-[10px] px-2 py-0.5 rounded border ${
                !domain ? "bg-primary text-primary-foreground" : ""
              }`}
            >
              wszystkie
            </button>
            {domains.map((d) => (
              <button
                key={d}
                onClick={() => setDomain(d)}
                className={`text-[10px] px-2 py-0.5 rounded border ${
                  domain === d ? "bg-primary text-primary-foreground" : ""
                }`}
              >
                {d} ({scenariosByDomain[d] || 0})
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {scenarios.map((s) => (
            <Card key={s.scenario_id} className="p-3">
              <div className="flex items-baseline justify-between">
                <div className="text-xs font-mono">{s.persona_id}</div>
                <div className="flex gap-1">
                  <Badge variant="outline" className="text-[10px]">
                    {s.domain}
                  </Badge>
                  <Badge
                    variant="outline"
                    className={`text-[10px] ${
                      DIFFICULTY_COLOR[s.difficulty] || ""
                    }`}
                  >
                    {s.difficulty}
                  </Badge>
                </div>
              </div>
              <div className="text-xs mt-2">
                <div className="text-muted-foreground">
                  {s.workflow_steps.length} krokow · {s.decision_points.length}{" "}
                  decyzji
                </div>
                <div className="mt-1 line-clamp-2 text-foreground/80">
                  {s.workflow_steps
                    .slice(0, 3)
                    .map((x) => x.step)
                    .join(" -> ")}
                </div>
              </div>
            </Card>
          ))}
        </div>
      </Card>
    </div>
  );
}
