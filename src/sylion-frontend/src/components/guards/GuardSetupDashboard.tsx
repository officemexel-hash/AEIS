"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileSearch,
  Gauge,
  Layers3,
  Loader2,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  TestTube2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

type GuardId = "cost" | "security" | "quality" | "provenance";

const goalOptions = [
  { id: "apps_internal", label: "Aplikacje wewnętrzne" },
  { id: "public_products", label: "Produkty publiczne" },
  { id: "cybersecurity", label: "Cyberbezpieczeństwo" },
  { id: "research", label: "Badania" },
];

const guardTitleMap: Record<GuardId, string> = {
  cost: "Strażnik kosztów",
  security: "Strażnik bezpieczeństwa",
  quality: "Strażnik jakości",
  provenance: "Strażnik pochodzenia",
};

const severityLabels: Record<string, string> = {
  CRITICAL: "KRYTYCZNE",
  BLOCKER: "BLOKER",
  ERROR: "BŁĄD",
  WARNING: "OSTRZEŻENIE",
  INFO: "INFO",
};

function guardText(value: unknown): string {
  let text = String(value ?? "");
  const exact: Record<string, string> = {
    enabled: "włączony",
    disabled: "wyłączony",
    initialized: "zainicjowany",
    cold: "zimny start",
    reviewed: "sprawdźone",
    pending: "oczekuje",
    ready: "gotowe",
    none: "brak",
    unknown: "nieznane",
    standard: "standard",
    balanced: "zrównoważony",
  };
  if (exact[text]) return exact[text];
  const replacements: Array<[RegExp, string]> = [
    [/\bQuality Guard\b/g, "Strażnik jakości"],
    [/\bQuality\b/g, "Jakość"],
    [/\bCost Guard\b/g, "Strażnik kosztów"],
    [/\bSecurity Guard\b/g, "Strażnik bezpieczeństwa"],
    [/\bProvenance Guard\b/g, "Strażnik pochodzenia"],
    [/\bGuard\b/g, "Strażnik"],
    [/\bPhase\b/g, "Faza"],
    [/\bphase\b/g, "faza"],
    [/\bL1-L5 gates\b/g, "bramki L1-L5"],
    [/\bgates\b/g, "bramki"],
    [/\bchecks\b/g, "kontrole"],
    [/\bChecks\b/g, "Kontrole"],
    [/\bscope\b/g, "zakres"],
    [/\bScope\b/g, "Zakres"],
    [/\bfindings\b/g, "znaleziska"],
    [/\bFindings\b/g, "Znaleziska"],
    [/\bEdge cases\b/g, "Przypadki brzegowe"],
    [/\bedge cases\b/g, "przypadki brzegowe"],
    [/\bHard blocks\b/g, "Twarde blokady"],
    [/\bhard blocks\b/g, "twarde blokady"],
    [/\bWorker\b/g, "Worker"],
    [/\bCache\b/g, "Pamięć podręczna"],
    [/\bAutonomy\b/g, "Autonomia"],
    [/\bLatest run\b/g, "Ostatnie uruchomienie"],
    [/\bactive\b/g, "aktywne"],
    [/\bActive\b/g, "Aktywne"],
    [/\bTotal active guards\b/g, "Wszystkie aktywne strażniki"],
    [/\bEdge diagnosis\b/g, "Diagnoza przypadku brzegowego"],
    [/\bBaseline\b/g, "Bazowe"],
    [/\bbaseline\b/g, "bazowe"],
    [/\bauto-fix\b/g, "autonaprawa"],
    [/\bAuto-fix\b/g, "Autonaprawa"],
    [/\bperformance\b/g, "wydajność"],
    [/\btest execution\b/g, "wykonywanie testów"],
    [/\biterations\b/g, "iteracje"],
    [/\bbaselines\b/g, "linie bazowe"],
    [/\breports\b/g, "raporty"],
    [/\band\b/g, "i"],
    [/\bquality reporting\b/g, "raportowanie jakości"],
    [/\baccepted\b/g, "zaakceptowano"],
    [/\baccepted\b/g, "zaakceptowano"],
    [/\bPASS\b/g, "PRZECHODZI"],
    [/\bpass\b/g, "przechodzi"],
    [/\bWARNING\b/g, "OSTRZEŻENIE"],
    [/\bERROR\b/g, "BŁĄD"],
    [/\bINFO\b/g, "INFO"],
    [/\bON\b/g, "WŁ."],
    [/\bOFF\b/g, "WYŁ."],
    [/\bInternal apps\b/g, "aplikacje wewnętrzne"],
    [/\bPublic products\b/g, "produkty publiczne"],
    [/\bCybersecurity\b/g, "cyberbezpieczeństwo"],
    [/\bResearch\b/g, "badania"],
    [/\bError rate\b/g, "Wskaźnik błędów"],
    [/\bLinter errors\b/g, "Błędy lintera"],
    [/\bcoverage\b/g, "pokrycie"],
    [/\bCoverage\b/g, "Pokrycie"],
    [/\bDuplicate code\b/g, "Duplikacja kodu"],
    [/\bCyclomatic complexity\b/g, "Złożoność cyklomatyczna"],
    [/\bCritical paths\b/g, "Ścieżki krytyczne"],
    [/\bunit tests\b/g, "testy jednostkowe"],
    [/\bUnit\b/g, "jednostkowe"],
    [/\bIntegration\b/g, "integracyjne"],
    [/\bintegration tests\b/g, "testy integracyjne"],
    [/\bE2E tests\b/g, "testy E2E"],
    [/\bhuman-like UI scenarios\b/g, "scenariusze UI jak człowiek"],
    [/\bfinding\b/g, "znalezisko"],
    [/\bfindings\b/g, "znaleziska"],
  ];
  for (const [pattern, replacement] of replacements) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

function statusLabel(value: string): string {
  return severityLabels[value] ?? guardText(value);
}

function StatusIcon({ status }: { status?: string }) {
  if (status === "pass") return <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-sylion-green" />;
  if (status === "warn" || status === "progress") return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-amber" />;
  return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-red" />;
}

function Metric({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "green" | "amber" | "red";
}) {
  return (
    <Card
      className={cn(
        "border-sylion-border bg-card p-4",
        tone === "green" && "border-sylion-green/30",
        tone === "amber" && "border-sylion-amber/30",
        tone === "red" && "border-sylion-red/30",
      )}
    >
      <div className="text-[11px] uppercase text-muted-foreground">{guardText(label)}</div>
      <div className="mt-2 text-2xl font-semibold tracking-tight">{value}</div>
    </Card>
  );
}

function MiniRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-sylion-border bg-secondary/10 px-3 py-2 text-xs">
      <span className="truncate font-medium">{guardText(label)}</span>
      <span className="truncate text-muted-foreground">{guardText(value)}</span>
    </div>
  );
}

function severityTone(severity: string) {
  if (severity === "CRITICAL" || severity === "BLOCKER") return "border-sylion-red/30 text-sylion-red";
  if (severity === "ERROR") return "border-sylion-amber/40 text-sylion-amber";
  if (severity === "WARNING") return "border-primary/30 text-primary";
  return "border-sylion-border text-muted-foreground";
}

function guardIntro(guardId: GuardId) {
  if (guardId === "cost") {
    return "Monitoring kosztów w czasie rzeczywistym, cztery poziomy anomalii, predykcje, przełączanie modeli, ograniczanie tempa, pauzy, twarde stopery i raporty zamknięcia.";
  }
  if (guardId === "security") {
    return "Siedem warstw bezpieczeństwa, bazowe 25 kontroli, zgodność GDPR/KSeF, analiza zagrożeń i procedury incydentowe.";
  }
  if (guardId === "quality") {
    return "Bramki L1-L5, progi DIM-7, budżety iteracji autonaprawy, linia bazowa wydajności i raportowanie jakości.";
  }
  return "Łańcuch hashy, podpis Ed25519, pochodzenie artefaktów, szablony dowodów zgodności i rekonstrukcja śledcza.";
}

export function GuardSetupDashboard({ guardId }: { guardId: GuardId }) {
  const { data: health, loading: healthLoading } = useHealth();
  const backendLive = health.status === "ok";
  const backendPending = healthLoading || health.status === "unknown";
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
      setStatus(backendPending ? "Łączenie z backendem..." : "Backend niedostępny.");
      return;
    }
    setLoading(true);
    try {
      const data = await api.getGuardSetup(guardId, goal);
      setSnapshot(data);
      setStatus("");
    } catch (err: any) {
      setStatus(`${guardTitleMap[guardId]}: ${err.message || String(err)}`);
    } finally {
      setLoading(false);
    }
  }, [backendLive, backendPending, goal, guardId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const settings = snapshot?.settings || {};
  const templates = snapshot?.templates || {};
  const catalog = templates.catalog || {};
  const acceptance = snapshot?.acceptance || {};
  const panel = snapshot?.aggregated_panel || {};
  const phase = catalog.phase || snapshot?.phase || "?";
  const phaseReady = Boolean(acceptance.accepted && acceptance.audit_chain?.[`phase_${phase}_complete`]);
  const checks = useMemo(() => Object.values(settings.checks || {}) as any[], [settings.checks]);
  const enabledChecks = checks.filter((check: any) => check.enabled);
  const findings = settings.findings || [];
  const activeFindings = findings.filter((finding: any) => finding.status === "active");
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
  const edgeCount = (templates.edge_cases || []).length;
  const checkTotal = checks.length || (templates.checks || []).length;

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
      const data = await api.applyGuardDefaults(guardId, { goal, autonomy_preset: "balanced" });
      setSnapshot(data);
      setStatus(`Zastosowano domyślne ustawieńia fazy ${phase}.`);
    });

  const saveConfig = () =>
    withBusy("config", async () => {
      const data = await api.saveGuardConfig(guardId, {
        scope: Object.fromEntries(scopeRows.map((item: any) => [item.id, true])),
        flags: { scope_configured: true },
        feature_overrides: {},
      });
      setSnapshot(data.snapshot);
      setStatus("Zapisano konfigurację zakresu i funkcji.");
    });

  const reviewChecks = () =>
    withBusy("checks", async () => {
      const data = await api.reviewGuardChecks(guardId, {
        reviewed_check_ids: checks.map((check: any) => check.id),
        disabled_check_ids: [],
        accepted_baseline: true,
      });
      setSnapshot(data.snapshot);
      setStatus(`Kontrole strażnika dla fazy ${phase} zostały sprawdźone.`);
    });

  const runCheck = () =>
    withBusy("run", async () => {
      const data = await api.runGuardCheck(guardId, { depth: "standard", project_id: "dashboard_current" });
      setSnapshot(data.snapshot);
      setStatus(`Kontrola ${guardText(catalog.title || guardTitleMap[guardId])} utworzyła ${data.findings?.length || 0} znalezisk.`);
    });

  const saveOverride = () =>
    withBusy("override", async () => {
      const data = await api.saveGuardAutonomyOverride(guardId, {
        inherits_phase5: true,
        preset: "balanced",
        auto_actions: { notify: "auto", suppress: "operator", hard_stop: "operator" },
        operator_note: `Phase ${phase} keeps Phase 5 policy with per-Guard operator override.`,
      });
      setSnapshot(data.snapshot);
      setStatus("Zapisano nadpisanie autonomii dla tego strażnika.");
    });

  const diagnoseEdge = () =>
    withBusy("edge", async () => {
      const caseId = (templates.edge_cases || [])[0]?.id || "EC-A1";
      const data = await api.diagnoseGuardEdgeCase(guardId, {
        case_id: caseId,
        context: { goal, active_findings: activeFindings.length, source: "operator_dashboard" },
      });
      setDiagnosis(data);
      setStatus(`Diagnoza ${caseId} gotowa.`);
    });

  const applyQualityFix = () =>
    withBusy("fix", async () => {
      const fixable = findings.find((finding: any) => finding.can_auto_fix && finding.status === "active");
      if (!fixable) {
        setStatus("Brak aktywnego znaleziska możliwego do autonaprawy.");
        return;
      }
      const data = await api.actOnGuardFinding(guardId, fixable.id, { action: "apply_fix", note: "balanced preset auto-fix iteration" });
      setSnapshot(data.snapshot);
      setStatus("Autonaprawa zastosowana do znaleziska jakości.");
    });

  const runAcceptance = () =>
    withBusy("acceptance", async () => {
      const data = await api.runGuardAcceptanceTest(guardId, goal);
      const fresh = await api.getGuardSetup(guardId, goal);
      setSnapshot(fresh);
      setStatus(data.accepted ? `Faza ${phase} zaakceptowana.` : `Faza ${phase}, twarde blokady: ${data.hard_blocks?.length || 0}.`);
    });

  return (
    <div className="space-y-4 p-4 md:p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">{guardText(catalog.route_title || `${guardTitleMap[guardId]} - konfiguracja`)}</h1>
            <Badge variant="outline" className={cn("text-[10px]", phaseReady ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
              {phaseReady ? `FAZA ${phase} GOTOWA` : `FAZA ${phase} AKTYWNA`}
            </Badge>
            <Badge variant="outline" className={cn("text-[10px]", backendLive ? "border-sylion-green/30 text-sylion-green" : backendPending ? "border-sylion-amber/30 text-sylion-amber" : "border-sylion-red/30 text-sylion-red")}>
              {backendLive ? "BACKEND DZIAŁA" : backendPending ? "ŁĄCZENIE Z BACKENDEM" : "BACKEND NIEDOSTĘPNY"}
            </Badge>
          </div>
          <div className="mt-1 max-w-4xl text-xs text-muted-foreground">{guardIntro(guardId)}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            className="h-9 rounded-md border border-sylion-border bg-background px-3 text-xs outline-none focus:border-primary"
          >
            {goalOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" className="h-9 text-xs" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={cn("mr-1 h-3 w-3", loading && "animate-spin")} />
            Odśwież
          </Button>
          <Button size="sm" className="h-9 text-xs" onClick={applyDefaults} disabled={!backendLive || busy === "defaults"}>
            {busy === "defaults" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <ShieldCheck className="mr-1 h-3 w-3" />}
            Zastosuj domyślne ustawieńia fazy {phase}
          </Button>
        </div>
      </div>

      {status ? <div className="rounded-md border border-sylion-border bg-secondary/10 px-3 py-2 text-xs text-muted-foreground">{status}</div> : null}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        <Metric label="Aktywny zakres" value={`${enabledScope.length}/${scopeRows.length || 0}`} tone={enabledScope.length === scopeRows.length ? "green" : "amber"} />
        <Metric label="Włączone kontrole" value={`${enabledChecks.length}/${checkTotal}`} tone={enabledChecks.length === checkTotal ? "green" : "amber"} />
        <Metric label="Aktywne znaleziska" value={activeFindings.length} tone={activeFindings.length ? "amber" : "green"} />
        <Metric label="Przypadki brzegowe" value={edgeCount} tone={edgeCount >= 22 ? "green" : "amber"} />
        <Metric label="Twarde blokady" value={acceptance.hard_blocks?.length || 0} tone={acceptance.hard_blocks?.length ? "red" : "green"} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <Layers3 className="h-4 w-4 text-primary" />
                Zakres i możliwości
              </h2>
              <div className="mt-1 text-[11px] text-muted-foreground">{guardText(catalog.summary || "Zakres strażnika i grupy możliwości.")}</div>
            </div>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={saveConfig} disabled={busy === "config"}>
              <SlidersHorizontal className="mr-1 h-3 w-3" />
              Zapisz konfigurację zakresu
            </Button>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {scopeRows.map((item: any) => (
              <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">{guardText(item.label)}</div>
                  <Badge variant="outline" className={cn("h-5 text-[9px]", item.config?.enabled ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
                    {item.config?.enabled ? "WŁ." : "WYŁ."}
                  </Badge>
                </div>
                <div className="mt-2 line-clamp-2 text-[10px] text-muted-foreground">{guardText((item.config?.items || item.items || []).join(", "))}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Gauge className="h-4 w-4 text-primary" />
            Worker i autonomia
          </h2>
          <div className="mt-3 space-y-2">
            <MiniRow label="Worker" value={`${settings.worker?.enabled ? "włączony" : "wyłączony"} / ${settings.worker?.status || "nieznane"}`} />
            <MiniRow label="Pamięć podręczna" value={`${settings.worker?.cache_initialized ? "zainicjowana" : "zimny start"} / ${settings.worker?.cache_hit_rate_pct || 0}%`} />
            <MiniRow label="Autonomia" value={`${settings.autonomy_override?.preset || settings.autonomy_preset || "zrównoważony"} / ${settings.autonomy_override?.considered ? "sprawdźona" : "oczekuje"}`} />
            <MiniRow label="Ostatnie uruchomienie" value={latestRun ? `${latestRun.depth} / ${latestRun.findings_created} znalezisk` : "brak"} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2">
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={saveOverride} disabled={busy === "override"}>
              <ShieldAlert className="mr-1 h-3 w-3" />
              Zapisz nadpisanie autonomii
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={diagnoseEdge} disabled={busy === "edge"}>
              <AlertTriangle className="mr-1 h-3 w-3" />
              Diagnozuj przypadek brzegowy
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
                Kontrole strażnika
              </h2>
              <div className="mt-1 text-[11px] text-muted-foreground">Kontrole bazowe są sprawdźane i egzekwowane przez backendowy endpoint akceptacji.</div>
            </div>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={reviewChecks} disabled={busy === "checks"}>
              Sprawdź kontrole strażnika
            </Button>
          </div>
          <div className="mt-3 grid max-h-[520px] grid-cols-1 gap-2 overflow-auto pr-1 lg:grid-cols-2">
            {checks.map((check: any) => (
              <div key={check.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{guardText(check.label)}</div>
                    <div className="mt-1 truncate text-[10px] text-muted-foreground">{guardText(check.tier)} / {guardText(check.category)} / {check.reviewed ? "sprawdźone" : "oczekuje"}</div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Badge variant="outline" className={cn("h-5 text-[9px]", severityTone(check.severity))}>{statusLabel(check.severity)}</Badge>
                    <Badge variant="outline" className={cn("h-5 text-[9px]", check.enabled ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
                      {check.enabled ? "WŁ." : "WYŁ."}
                    </Badge>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Play className="h-4 w-4 text-primary" />
            Znaleziska
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2">
            <Button size="sm" className="h-8 text-xs" onClick={runCheck} disabled={busy === "run"}>
              {busy === "run" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Play className="mr-1 h-3 w-3" />}
              Uruchom kontrolę strażnika
            </Button>
            {guardId === "quality" ? (
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={applyQualityFix} disabled={busy === "fix"}>
                <ShieldCheck className="mr-1 h-3 w-3" />
                Zastosuj autonaprawę jakości
              </Button>
            ) : null}
          </div>
          <div className="mt-3 space-y-2">
            <MiniRow label="Aktywne znaleziska" value={`${activeFindings.length}`} />
            <MiniRow label="Wszystkie aktywne strażniki" value={`${panel.total_active_findings || 0}`} />
            {diagnosis ? <MiniRow label="Diagnoza przypadku brzegowego" value={diagnosis.case?.id || "gotowe"} /> : null}
          </div>
          <div className="mt-3 max-h-[280px] space-y-2 overflow-auto pr-1">
            {findings.slice(-6).reverse().map((finding: any) => (
              <div key={finding.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{guardText(finding.title)}</div>
                    <div className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">{guardText(finding.summary)}</div>
                  </div>
                  <Badge variant="outline" className={cn("h-5 text-[9px]", severityTone(finding.severity))}>{statusLabel(finding.severity)}</Badge>
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
            Zbiorczy panel strażników
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            {(panel.guards || []).map((guard: any) => (
              <div key={guard.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="font-medium">{guardText(guard.label)}</div>
                <div className="mt-2 text-[10px] text-muted-foreground">Faza {guard.phase} / {guardText(guard.status)}</div>
                <div className="mt-2 flex items-center justify-between gap-2">
                  <Badge variant="outline" className="h-5 text-[9px]">{guard.active_findings || 0}</Badge>
                  <Badge variant="outline" className={cn("h-5 text-[9px]", severityTone(guard.highest_severity || "INFO"))}>{statusLabel(guard.highest_severity || "INFO")}</Badge>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
            {Object.entries(panel.severity_counts || {}).map(([severity, count]) => (
              <MiniRow key={severity} label={statusLabel(severity)} value={String(count)} />
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <div className="flex items-start justify-between gap-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <TestTube2 className="h-4 w-4 text-primary" />
              Akceptacja fazy {phase}
            </h2>
            <Button size="sm" className="h-8 text-xs" onClick={runAcceptance} disabled={busy === "acceptance"}>
              {busy === "acceptance" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <TestTube2 className="mr-1 h-3 w-3" />}
              Uruchom akceptację
            </Button>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2">
            <MiniRow label="Wspólne DoD" value={`${acceptance.dod?.common?.passed || 0}/${acceptance.dod?.common?.required || 0}`} />
            <MiniRow label="Wszystkie kontrole" value={`${acceptance.dod?.counts?.checks_passed || 0}/${acceptance.dod?.counts?.checks_total || 0}`} />
            <MiniRow label="Miękkie ostrzeżenia" value={`${acceptance.soft_warnings?.length || 0}`} />
            <MiniRow label="Postęp" value={`${acceptance.dod?.counts?.progress || 0}`} />
          </div>
          <div className="mt-3 max-h-[360px] space-y-2 overflow-auto pr-1">
            {(acceptance.checks || []).map((check: any) => (
              <div key={check.id} className="flex items-start gap-2 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <StatusIcon status={check.status} />
                <div className="min-w-0">
                  <div className="truncate font-medium">{guardText(check.label)}</div>
                  <div className="mt-1 truncate text-[10px] text-muted-foreground">{guardText(check.evidence)}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            Grupy możliwości
          </h2>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {(templates.capability_groups || []).map((group: any) => (
              <div key={group.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="font-medium">{guardText(group.label)}</div>
                <div className="mt-2 line-clamp-3 text-[10px] text-muted-foreground">{guardText((group.items || []).join(", "))}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Clock3 className="h-4 w-4 text-primary" />
            Przypadki brzegowe
          </h2>
          <div className="mt-3 max-h-[300px] space-y-2 overflow-auto pr-1">
            {(templates.edge_cases || []).slice(0, 10).map((item: any) => (
              <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{item.id}</span>
                  <Badge variant="outline" className="h-5 text-[9px]">{guardText(item.category)}</Badge>
                </div>
                <div className="mt-2 line-clamp-2 text-[10px] text-muted-foreground">{guardText(item.title)}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
