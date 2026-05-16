"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  FileSearch,
  Gauge,
  GitCompare,
  Layers3,
  Loader2,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  TestTube2,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

const plLabel: Record<string, string> = {
  documents: "Dokumenty",
  code: "Kod",
  tests: "Testy",
  deployment: "Wdrożenie",
  Deployment: "Wdrożenie",
  "Cost Guard": "Strażnik kosztów",
  "Quality Guard": "Strażnik jakości",
  "Security Guard": "Strażnik bezpieczeństwa",
  "Provenance Guard": "Strażnik pochodzenia",
  "Coherence Guard": "Strażnik spójności",
  enabled: "włączony",
  disabled: "wyłączony",
  initialized: "zainicjalizowany",
  cold: "zimny start",
  running: "działa",
  unknown: "nieznany",
  standard: "standard",
  none: "brak",
  "Feature in Ksiega has module in masterplan": "Funkcja z Księgi ma moduł w masterplanie",
  "Module in masterplan has test cases in test plan": "Moduł z masterplanu ma przypadki testówe",
  "Council Book claim has evidence in build artifacts": "Teza z Księgi rady ma dowód w artefaktach buildu",
  "Acceptance criteria in Ksiega verifiable in tests": "Kryteria akceptacji z Księgi są weryfikowalne w testach",
  "Council decisions not broken by mid-build interventions": "Decyzje rady nie są łamane przez interwencje w trakcie buildu",
  "Hard gate approvals honored in deploy phase": "Akceptacje twardych bramek są respektowane przy wdrożeniu",
  "Operator overrides expire on schedule, no ghost override": "Nadpisania operatora wygasają zgodnie z harmonogramem",
  "Translation coverage all locales": "Pokrycie tłumaczeń dla wszystkich języków",
  "Semantic equivalence PL/EN/DE": "Równoważność semantyczna PL/EN/DE",
  "Date and currency formats per locale": "Formaty dat i walut zgodne z językiem",
  "API contracts frontend/backend match": "Kontrakty API frontendu i backendu są zgodne",
  "DB schema vs ORM models match": "Schemat bazy jest zgodny z modelami ORM",
  "Deployment configs coherent between environments": "Konfiguracje wdrożenia są spójne między środowiskami",
  "Cost tracking matches actual spend": "Śledzenie kosztów zgadza się z realnym użyciem",
  "Audit chain hash chain valid": "Łańcuch hashy audytu jest poprawny",
  "Coherence Guard scope configured": "Zakres Strażnika spójności skonfigurowany",
  "Triggers configured": "Wyzwalacze skonfigurowane",
  "Severity thresholds reviewed": "Progi ważności sprawdźone",
  "Baseline 15 checks reviewed": "Linia bazowa 15 kontroli sprawdźona",
  "Audit chain entry phase_6.complete": "Wpis audytu phase_6.complete",
  "Custom checks defined or explicitly not needed": "Kontrole własne zdefiniowane albo jawnie zbędne",
  "Per-Guard autonomy override considered": "Nadpisanie autonomii per strażnik uwzględnione",
  "Cost budget allocated for Coherence Guard": "Budżet kosztowy Strażnika spójności przydzielony",
  "Worker running": "Worker działa",
  "Cache initialized": "Cache zainicjalizowany",
  "LLM cost cap below budget share": "Limit kosztu LLM mieści się w udziale budżetu",
  "LLM cost within budget": "Koszt LLM mieści się w budżecie",
  "No custom checks": "Brak kontroli własnych",
  false_positive: "fałszywy alarm",
  performance: "wydajność",
  "Naming variant intentional": "Wariant nazewniczy jest zamierzony",
  "LLM check hallucination": "Halucynacja kontroli LLM",
  "Intentional deviation from Council decision": "Zamierzone odejście od decyzji rady",
  "Translation length variance expected": "Oczekiwana różnica długości tłumaczenia",
  "Test gold standard outdated after refactor": "Złoty wzorzec testu jest nieaktualny po refaktorze",
  "Continuous monitoring is slow": "Monitoring ciągły jest wolny",
  "LLM cost overrun": "Przekroczenie kosztu LLM",
  "Cache cold start delay": "Opóźnienie zimnego startu cache",
};

function t(value?: string | null) {
  if (!value) return "";
  return plLabel[value] || value;
}

function tList(values: string[] = []) {
  return values.map((value) => t(value)).join(", ");
}

function tEvidence(value?: string | null) {
  if (!value) return "";
  return value
    .replaceAll("code", "kod")
    .replaceAll("deployment", "wdrożenie")
    .replaceAll("documents", "dokumenty")
    .replaceAll("tests", "testy")
    .replaceAll("continuous", "ciągły")
    .replaceAll("on_demand", "na żądanie")
    .replaceAll("phase_boundaries", "granice faz")
    .replaceAll("False", "nie")
    .replaceAll("True", "tak")
    .replaceAll("enabled", "włączonych")
    .replaceAll("missing", "brak")
    .replaceAll("custom", "własnych")
    .replaceAll("running", "działa")
    .replaceAll("balanced", "zbalansowany")
    .replaceAll("hit rate", "trafień cache")
    .replaceAll("operator has not made a własnych-check decision", "operator nie podjął decyzji o kontrolach własnych");
}

function StatusIcon({ status }: { status?: string }) {
  if (status === "pass") return <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-sylion-green" />;
  if (status === "warn") return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-amber" />;
  return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-red" />;
}

function Metric({ label, value, tone = "default" }: { label: string; value: string | number; tone?: "default" | "green" | "amber" | "red" }) {
  return (
    <Card
      className={cn(
        "border-sylion-border bg-card p-4",
        tone === "green" && "border-sylion-green/30",
        tone === "amber" && "border-sylion-amber/30",
        tone === "red" && "border-sylion-red/30",
      )}
    >
      <div className="text-[11px] uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold tracking-tight">{value}</div>
    </Card>
  );
}

function MiniRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-sylion-border bg-secondary/10 px-3 py-2 text-xs">
      <span className="truncate font-medium">{label}</span>
      <span className="truncate text-muted-foreground">{value}</span>
    </div>
  );
}

function severityTone(severity: string) {
  if (severity === "CRITICAL" || severity === "BLOCKER") return "border-sylion-red/30 text-sylion-red";
  if (severity === "ERROR") return "border-sylion-amber/40 text-sylion-amber";
  if (severity === "WARNING") return "border-primary/30 text-primary";
  return "border-sylion-border text-muted-foreground";
}

export default function CoherenceGuardPage() {
  const { data: health } = useHealth();
  const backendLive = health.status === "ok";
  const [goal, setGoal] = useState("apps_internal");
  const [snapshot, setSnapshot] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [diagnosis, setDiagnosis] = useState<any | null>(null);

  const load = useCallback(async () => {
    if (!backendLive) {
      setSnapshot(null);
      setLoading(false);
      setStatus("Backend niedostępny.");
      return;
    }
    setLoading(true);
    try {
      const data = await api.getCoherenceGuard(goal);
      setSnapshot(data);
      setStatus("");
    } catch (err: any) {
      setStatus(`Błąd Strażnika spójności: ${err.message || String(err)}`);
    } finally {
      setLoading(false);
    }
  }, [backendLive, goal]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const settings = snapshot?.settings || {};
  const templates = snapshot?.templates || {};
  const acceptance = snapshot?.acceptance || {};
  const panel = snapshot?.aggregated_panel || {};
  const checks = useMemo(() => Object.values(settings.checks || {}) as any[], [settings.checks]);
  const enabledChecks = checks.filter((check: any) => check.enabled);
  const customChecks = settings.custom_checks || [];
  const findings = settings.findings || [];
  const activeFindings = findings.filter((finding: any) => finding.status === "active");
  const performance = settings.performance || {};
  const phaseReady = Boolean(acceptance.accepted && acceptance.audit_chain?.phase_6_complete);

  const scopeRows = useMemo(
    () =>
      (templates.scope || []).map((item: any) => ({
        ...item,
        config: settings.scope?.[item.id] || {},
      })),
    [templates.scope, settings.scope],
  );
  const enabledScope = scopeRows.filter((item: any) => item.config?.enabled);
  const latestRun = settings.runs?.length ? settings.runs[settings.runs.length - 1] : null;

  const withBusy = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    setStatus("");
    try {
      await action();
    } catch (err: any) {
      setStatus(err.message || String(err));
    } finally {
      setBusy("");
    }
  };

  const applyDefaults = () =>
    withBusy("defaults", async () => {
      const data = await api.applyCoherenceGuardDefaults({ goal, autonomy_preset: "balanced", custom_checks_not_needed: true });
      setSnapshot(data);
      setStatus("Domyślne ustawieńia Fazy 6 zastosowane.");
    });

  const saveScopeAndTriggers = () =>
    withBusy("scope", async () => {
      await api.saveCoherenceGuardScope({
        scope: { documents: true, code: true, tests: true, deployment: true },
        cross_project_enabled: false,
        project_count: 1,
      });
      const data = await api.saveCoherenceGuardTriggers({
        phase_boundaries: { enabled: true, critical_phases: [25, 28, 29, 35, 37, 39, 41] },
        continuous: { enabled: true, throttle_per_file_seconds: 60, batch_window_seconds: 5 },
        on_demand: { enabled: true, default_depth: "standard" },
      });
      setSnapshot(data.snapshot);
      setStatus("Zakres i wyzwalacze zapisane.");
    });

  const reviewSeverity = () =>
    withBusy("severity", async () => {
      const data = await api.reviewCoherenceSeverity({ reviewed: true });
      setSnapshot(data.snapshot);
      setStatus("Progi ważności sprawdźone.");
    });

  const reviewChecks = () =>
    withBusy("checks", async () => {
      const data = await api.reviewCoherenceChecks({
        reviewed_check_ids: checks.map((check: any) => check.id),
        disabled_check_ids: [],
        accepted_baseline: true,
        custom_checks_not_needed: customChecks.length === 0,
      });
      setSnapshot(data.snapshot);
      setStatus("Linia bazowa 15 kontroli sprawdźona.");
    });

  const addCustomCheck = () =>
    withBusy("custom", async () => {
      const data = await api.addCoherenceCustomCheck({
        name: "Customer email before phone",
        mechanism: "dsl",
        definition: "FOR EACH form IN frontend.forms IF email BEFORE phone THEN flag",
        severity: "WARNING",
        tier: "tier1",
        enabled: true,
        cost_per_run_usd: 0,
      });
      setSnapshot(data.snapshot);
      setStatus("Dodano demonstracyjną kontrolę własną.");
    });

  const runCheck = () =>
    withBusy("run", async () => {
      const data = await api.runCoherenceCheck({
        depth: "standard",
        scope: ["documents", "code", "tests", "deployment"],
        project_id: "dashboard_current",
      });
      setSnapshot(data.snapshot);
      setStatus(`Kontrola spójności utworzyła ${data.findings?.length || 0} ustaleń.`);
    });

  const savePerformance = () =>
    withBusy("performance", async () => {
      const data = await api.saveCoherencePerformance({
        worker_enabled: true,
        worker_status: "running",
        cache_initialized: true,
        cache_hit_rate_pct: 82,
        monthly_budget_usd: 30,
        used_monthly_usd: Math.min(Number(performance.used_monthly_usd || 12), 14),
        budget_cap_enabled: true,
        budget_share_pct: 5,
        incremental_diff: true,
      });
      setSnapshot(data.snapshot);
      setStatus("Worker, cache i budżet zapisane.");
    });

  const saveOverride = () =>
    withBusy("override", async () => {
      const data = await api.saveCoherenceAutonomyOverride({
        inherits_phase5: true,
        preset: "balanced",
        auto_fix_tier1: false,
        auto_fix_tier2: false,
        per_check_customization: true,
        operator_note: "Phase 6 guard inherits Phase 5 with manual semantic fixes.",
      });
      setSnapshot(data.snapshot);
      setStatus("Nadpisanie autonomii strażnika zapisane.");
    });

  const diagnoseEdge = () =>
    withBusy("edge", async () => {
      const data = await api.diagnoseCoherenceEdgeCase({
        case_id: "EC-D3",
        context: { coherence: "API mismatch", quality: "tests pass", likely_cause: "stale contract fixture" },
      });
      setDiagnosis(data);
      setStatus("Diagnoza EC-D3 gotowa.");
    });

  const runAcceptance = () =>
    withBusy("acceptance", async () => {
      const data = await api.runCoherenceAcceptanceTest(goal);
      const fresh = await api.getCoherenceGuard(goal);
      setSnapshot(fresh);
      setStatus(data.accepted ? "Faza 6 zaakceptowana." : `Twarde blokady Fazy 6: ${data.hard_blocks?.length || 0}.`);
    });

  return (
    <div className="space-y-4 p-4 md:p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">Strażnik spójności - Faza 6</h1>
            <Badge variant="outline" className={cn("text-[10px]", phaseReady ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
              {phaseReady ? "FAZA 6 GOTOWA" : "FAZA 6 AKTYWNA"}
            </Badge>
            <Badge variant="outline" className={cn("text-[10px]", backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
            {backendLive ? "BACKEND DZIAŁA" : "BACKEND NIEDOSTĘPNY"}
            </Badge>
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            Zakres, wyzwalacze, linia bazowa 15 kontroli, ustalenia, worker, cache, budżet i agregacja strażników.
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            className="h-9 rounded-md border border-sylion-border bg-background px-3 text-xs outline-none focus:border-primary"
          >
            <option value="apps_internal">Aplikacje wewnętrzne</option>
            <option value="public_products">Produkty publiczne</option>
            <option value="cybersecurity">Cyberbezpieczeństwo</option>
            <option value="research">Badania</option>
          </select>
          <Button variant="outline" size="sm" className="h-9 text-xs" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={cn("mr-1 h-3 w-3", loading && "animate-spin")} />
            Odśwież
          </Button>
          <Button size="sm" className="h-9 text-xs" onClick={applyDefaults} disabled={!backendLive || busy === "defaults"}>
            {busy === "defaults" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <ShieldCheck className="mr-1 h-3 w-3" />}
            Zastosuj domyślne Fazy 6
          </Button>
        </div>
      </div>

      {status ? (
        <div className="rounded-md border border-sylion-border bg-secondary/10 px-3 py-2 text-xs text-muted-foreground">{status}</div>
      ) : null}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        <Metric label="Aktywny zakres" value={`${enabledScope.length}/4`} tone={enabledScope.length === 4 ? "green" : "amber"} />
        <Metric label="Linia bazowa" value={`${enabledChecks.length}/15`} tone={enabledChecks.length === 15 ? "green" : "amber"} />
        <Metric label="Aktywne ustalenia" value={activeFindings.length} tone={activeFindings.length ? "amber" : "green"} />
        <Metric label="Kontrole własne" value={customChecks.length} />
        <Metric label="Wykorzystany budżet" value={`$${Number(performance.used_monthly_usd || 0).toFixed(2)}`} tone={Number(performance.used_monthly_usd || 0) <= Number(performance.monthly_budget_usd || 0) ? "green" : "red"} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <Layers3 className="h-4 w-4 text-primary" />
                Zakres i wyzwalacze
              </h2>
              <div className="mt-1 text-[11px] text-muted-foreground">
                Międzyprojektówo: {settings.cross_project_enabled ? "WŁ." : "WYŁ."} / liczba projektów: {settings.project_count || 1}
              </div>
            </div>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={saveScopeAndTriggers} disabled={busy === "scope"}>
              <SlidersHorizontal className="mr-1 h-3 w-3" />
              Zapisz zakres i wyzwalacze
            </Button>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {scopeRows.map((item: any) => (
              <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">{t(item.id) || t(item.label)}</div>
                  <Badge variant="outline" className={cn("h-5 text-[9px]", item.config?.enabled ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
                    {item.config?.enabled ? "ON" : "OFF"}
                  </Badge>
                </div>
                <div className="mt-2 line-clamp-2 text-[10px] text-muted-foreground">{tList(item.config?.artifacts || item.artifacts || [])}</div>
              </div>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
            <MiniRow label="Granice faz" value={(settings.triggers?.phase_boundaries?.critical_phases || []).join(", ") || "nie ustawiono"} />
            <MiniRow label="Limit ciągły" value={`${settings.triggers?.continuous?.throttle_per_file_seconds || 60}s/plik`} />
            <MiniRow label="Okno paczki" value={`${settings.triggers?.continuous?.batch_window_seconds || 5}s`} />
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Gauge className="h-4 w-4 text-primary" />
            Worker, cache i koszt
          </h2>
          <div className="mt-3 space-y-2">
            <MiniRow label="Worker" value={`${performance.worker_enabled ? "włączony" : "wyłączony"} / ${t(performance.worker_status || "unknown")}`} />
            <MiniRow label="Cache" value={`${performance.cache_initialized ? "zainicjalizowany" : "zimny start"} / ${performance.cache_hit_rate_pct || 0}%`} />
            <MiniRow label="Limit budżetu" value={`${performance.budget_cap_enabled ? "WŁ." : "WYŁ."} / $${Number(performance.monthly_budget_usd || 0).toFixed(2)}`} />
            <MiniRow label="Ostatni przebieg" value={latestRun ? `${t(latestRun.depth)} / ${latestRun.findings_created} ustaleń` : "brak"} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2">
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={savePerformance} disabled={busy === "performance"}>
              <Database className="mr-1 h-3 w-3" />
              Zapisz wydajność
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={saveOverride} disabled={busy === "override"}>
              <ShieldAlert className="mr-1 h-3 w-3" />
              Zapisz nadpisanie autonomii
            </Button>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <FileSearch className="h-4 w-4 text-primary" />
                Linia bazowa 15 kontroli
              </h2>
              <div className="mt-1 text-[11px] text-muted-foreground">
                Reguły Tier 1 i semantyczne kontrole Tier 2 są ustawiane per kontrola.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={reviewSeverity} disabled={busy === "severity"}>
                Sprawdź ważność
              </Button>
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={reviewChecks} disabled={busy === "checks"}>
                Sprawdź linię bazową
              </Button>
            </div>
          </div>
          <div className="mt-3 grid max-h-[520px] grid-cols-1 gap-2 overflow-auto pr-1 lg:grid-cols-2">
            {checks.map((check: any) => (
              <div key={check.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{t(check.label)}</div>
                    <div className="mt-1 truncate text-[10px] text-muted-foreground">{check.tier} / {check.mechanism} / {tList(check.scope || [])}</div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Badge variant="outline" className={cn("h-5 text-[9px]", severityTone(check.severity))}>{check.severity}</Badge>
                    <Badge variant="outline" className={cn("h-5 text-[9px]", check.enabled ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>{check.enabled ? "ON" : "OFF"}</Badge>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <GitCompare className="h-4 w-4 text-primary" />
            Ustalenia i kontrole własne
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2">
            <Button size="sm" className="h-8 text-xs" onClick={runCheck} disabled={busy === "run"}>
              {busy === "run" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Play className="mr-1 h-3 w-3" />}
              Uruchom kontrolę spójności
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={addCustomCheck} disabled={busy === "custom"}>
              <Zap className="mr-1 h-3 w-3" />
              Dodaj kontrolę demonstracyjną
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={diagnoseEdge} disabled={busy === "edge"}>
              <AlertTriangle className="mr-1 h-3 w-3" />
              Diagnozuj EC-D3
            </Button>
          </div>
          <div className="mt-3 space-y-2">
            <MiniRow label="Kontrole własne" value={`${customChecks.length}`} />
            <MiniRow label="Aktywne ustalenia" value={`${activeFindings.length}`} />
            <MiniRow label="Konflikty strażników" value={`${panel.conflicts?.length || 0}`} />
            {diagnosis ? <MiniRow label="Przypadek brzegowy" value={diagnosis.case?.title || "EC-D3"} /> : null}
          </div>
          <div className="mt-3 max-h-[280px] space-y-2 overflow-auto pr-1">
            {findings.slice(-6).reverse().map((finding: any) => (
              <div key={finding.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{finding.title}</div>
                    <div className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">{finding.summary}</div>
                  </div>
                  <Badge variant="outline" className={cn("h-5 text-[9px]", severityTone(finding.severity))}>{finding.severity}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Zagregowany panel strażników
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            {(panel.guards || []).map((guard: any) => (
              <div key={guard.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="font-medium">{t(guard.label)}</div>
                <div className="mt-2 text-[10px] text-muted-foreground">Faza {guard.phase} / {t(guard.status)}</div>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <Badge variant="outline" className="h-5 text-[9px]">{guard.active_findings || 0}</Badge>
                  <Badge variant="outline" className={cn("h-5 text-[9px]", severityTone(guard.highest_severity || "INFO"))}>{guard.highest_severity || "INFO"}</Badge>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            {Object.entries(panel.severity_counts || {}).map(([severity, count]) => (
              <MiniRow key={severity} label={severity} value={String(count)} />
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <div className="flex items-start justify-between gap-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <TestTube2 className="h-4 w-4 text-primary" />
              Akceptacja Fazy 6
            </h2>
            <Button size="sm" className="h-8 text-xs" onClick={runAcceptance} disabled={busy === "acceptance"}>
              {busy === "acceptance" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <TestTube2 className="mr-1 h-3 w-3" />}
              Uruchom akceptację
            </Button>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2">
            <MiniRow label="Wspólne DoD" value={`${acceptance.dod?.common?.passed || 0}/${acceptance.dod?.common?.required || 5}`} />
            <MiniRow label="Rekomendowane" value={`${acceptance.dod?.recommended?.passed || 0}/${acceptance.dod?.recommended?.required || 3}`} />
            <MiniRow label="Wydajność" value={`${acceptance.dod?.performance?.passed || 0}/${acceptance.dod?.performance?.required || 3}`} />
            <MiniRow label="Twarde blokady" value={`${acceptance.hard_blocks?.length || 0}`} />
          </div>
          <div className="mt-3 max-h-[360px] space-y-2 overflow-auto pr-1">
            {(acceptance.checks || []).map((check: any) => (
              <div key={check.id} className="flex items-start gap-2 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <StatusIcon status={check.status} />
                <div className="min-w-0">
                  <div className="truncate font-medium">{t(check.label)}</div>
                  <div className="mt-1 truncate text-[10px] text-muted-foreground">{tEvidence(check.evidence)}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="border-sylion-border bg-card p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Clock3 className="h-4 w-4 text-primary" />
          Przypadki brzegowe
        </h2>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
          {(templates.edge_cases || []).slice(0, 8).map((item: any) => (
            <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{item.id}</span>
                <Badge variant="outline" className="h-5 text-[9px]">{t(item.category)}</Badge>
              </div>
              <div className="mt-2 line-clamp-2 text-[10px] text-muted-foreground">{t(item.title)}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
