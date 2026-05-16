"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ChevronRight,
  GitBranch,
  Keyboard,
  Loader2,
  Palette,
  ReceiptText,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  TestTube,
  Trash2,
  Users,
  Workflow,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";

const selectClass =
  "h-9 w-full rounded-md border border-sylion-border bg-background px-3 text-xs outline-none focus:border-primary";

function money(value: unknown) {
  return `$${Number(value || 0).toFixed(2)}`;
}

function wsText(value: unknown): string {
  const raw = String(value ?? "").trim();
  const labels: Record<string, string> = {
    apps_internal: "aplikacje wewnętrzne",
    public_products: "produkty publiczne",
    customer_facing_saas: "SaaS dla klientów",
    internal_app: "aplikacja wewnętrzna",
    balanced_human_like: "zbalansowane testy jak człowiek",
    balanced: "zbalansowany",
    power_user: "operator zaawansowany",
    compact: "kompaktowy",
    required: "wymagane",
    reduced: "ograniczone",
    yes: "tak",
    no: "nie",
  };
  return labels[raw] ?? raw.replace(/_/g, " ");
}

function StatusIcon({ status }: { status?: string }) {
  if (status === "pass") return <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-sylion-green" />;
  if (status === "warn") return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-amber" />;
  return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-red" />;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="border-sylion-border bg-card p-4">
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

export default function WorkspaceDefaultsPage() {
  const { data: health, loading: healthLoading } = useHealth();
  const [goal, setGoal] = useState("apps_internal");
  const [snapshot, setSnapshot] = useState<any | null>(null);
  const [snapshotReachable, setSnapshotReachable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [activeStep, setActiveStep] = useState(1);
  const [estimate, setEstimate] = useState<any | null>(null);
  const [edgeDiagnosis, setEdgeDiagnosis] = useState<any | null>(null);
  const [inheritance, setInheritance] = useState<any | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getWorkspaceDefaults(goal);
      setSnapshot(data);
      setSnapshotReachable(true);
      setActiveStep(Number(data.wizard?.current_step || 1));
      setStatus("");
    } catch (err: any) {
      setSnapshot(null);
      setSnapshotReachable(false);
      setStatus(`Błąd domyślnych ustawień obszaru pracy: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [goal]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const settings = snapshot?.settings || {};
  const templates = snapshot?.templates || {};
  const acceptance = snapshot?.acceptance || {};
  const wizard = snapshot?.wizard || {};
  const backendPending = healthLoading || health.status === "unknown";
  const backendLive = health.status === "ok" || snapshotReachable;
  const budgetTemplates = settings.budget_templates || [];
  const notificationMatrix = settings.notifications?.matrix || {};
  const cleanupDefaults = settings.cleanup_defaults || [];
  const edgeCases = templates.edge_cases || [];
  const activeChannels = useMemo(() => {
    const channels = new Set<string>();
    Object.values(notificationMatrix).forEach((value: any) => {
      if (Array.isArray(value)) value.forEach((channel) => channels.add(String(channel)));
    });
    return Array.from(channels).sort();
  }, [notificationMatrix]);

  const withBusy = async (key: string, action: () => Promise<void>) => {
    setBusy(key);
    try {
      await action();
    } catch (err: any) {
      setStatus(err.message || String(err));
    } finally {
      setBusy("");
    }
  };

  const applySmartDefaults = () =>
    withBusy("smart", async () => {
      const data = await api.applyWorkspaceSmartDefaults();
      setSnapshot(data);
      setStatus("Zastosowano inteligentne ustawieńia domyślne.");
    });

  const saveCurrentStep = (skipped = false) =>
    withBusy("step", async () => {
      const data = await api.saveWorkspaceDefaultWizardStep({
        step: activeStep,
        skipped,
        values: { goal, saved_from_ui: true },
      });
      setSnapshot(data.snapshot);
      setActiveStep(Number(data.wizard?.current_step || activeStep));
      setStatus(skipped ? "Krok pominięty z ustawieńiami systemowymi." : "Krok zapisany.");
    });

  const runAcceptance = () =>
    withBusy("acceptance", async () => {
      const data = await api.runWorkspaceDefaultsAcceptanceTest(goal);
      setSnapshot(await api.getWorkspaceDefaults(goal));
      setStatus(data.accepted ? "Akceptacja fazy 4 przeszła." : `Faza 4, twarde blokady: ${data.hard_blocks?.length || 0}.`);
    });

  const estimateSample = () =>
    withBusy("estimate", async () => {
      const data = await api.estimateWorkspaceProjectBudget({
        project_type: goal === "public_products" ? "customer_facing_saas" : "internal_app",
        d_level: goal === "public_products" ? 4 : 3,
        goal,
        build_phases: goal === "public_products" ? 18 : 12,
        council_rounds: 3,
        human_like_scenarios: 8,
      });
      setEstimate(data);
      setStatus(`Estymacja gotowa: ${money(data.recommended_budget_usd)}.`);
    });

  const saveAutonomy = (preset: string) =>
    withBusy("autonomy", async () => {
      await api.saveWorkspaceAutonomyMapping({ goal, preset });
      await load();
      setStatus(`Mapowanie autonomii zapisane: ${wsText(goal)} -> ${wsText(preset)}.`);
    });

  const saveNotifications = () =>
    withBusy("notifications", async () => {
      await api.saveWorkspaceNotificationMatrix({
        matrix: notificationMatrix,
        quiet_hours: settings.notifications?.quiet_hours || { enabled: true, start: "22:00", end: "07:00", critical_override: true },
      });
      await load();
      setStatus("Macierz powiadomień zapisana.");
    });

  const pairMobile = () =>
    withBusy("mobile", async () => {
      await api.pairWorkspaceMobile({
        pairing_code: "123456",
        auth_method: "pin",
        permissions: ["receive_notifications", "view_project_status", "approve_hard_gates", "approve_cost_overruns", "view_audit_chain"],
      });
      await load();
      setStatus("Demo parowania mobile zweryfikowane.");
    });

  const saveUi = () =>
    withBusy("ui", async () => {
      await api.saveWorkspaceUiSettings({ preset: "power_user", settings: { density: "compact", show_cost_overlay: true, safe_mode: true } });
      await load();
      setStatus("Domyślne ustawieńia UI zapisane.");
    });

  const saveShortcut = () =>
    withBusy("shortcut", async () => {
      await api.saveWorkspaceShortcut({ id: "open_today_project", combo: "Cmd+Shift+Y", action: "open_today_project", category: "custom" });
      await load();
      setStatus("Skrót własny zapisany.");
    });

  const saveTesting = () =>
    withBusy("testing", async () => {
      await api.saveWorkspaceTestStrategy({
        strategy_id: "balanced_human_like",
        human_like_required: true,
        scenarios: ["first_run", "create_project", "budget_warning", "human_gate", "mobile_approval", "cleanup_override"],
      });
      await load();
      setStatus("Strategia testów jak człowiek zapisana.");
    });

  const diagnoseEdge = () =>
    withBusy("edge", async () => {
      const data = await api.diagnoseWorkspaceDefaultEdgeCase({ case_id: "EC-A2", context: { source: "workspace_defaults_ui" } });
      setEdgeDiagnosis(data);
      setStatus("Runbook przypadku brzegowego wygenerowany.");
    });

  const previewInheritance = () =>
    withBusy("inheritance", async () => {
      const data = await api.previewWorkspaceInheritance({
        goal,
        d_level: goal === "public_products" ? 4 : 3,
        project_type: goal === "public_products" ? "customer_facing_saas" : "internal_app",
      });
      setInheritance(data);
      setStatus("Podgląd dziedziczenia gotowy.");
    });

  const renderStep = () => {
    if (!snapshot) return null;
    if (activeStep === 1) {
      return (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          {snapshot.smart_recommendations?.map((item: any) => (
            <div key={item.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
              <div className="font-medium">{item.suggestion}</div>
              <div className="mt-2 text-[11px] text-muted-foreground">{item.why?.join(" / ")}</div>
            </div>
          ))}
        </div>
      );
    }
    if (activeStep === 2) {
      return (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
            {budgetTemplates.map((item: any) => (
              <button key={item.id} type="button" className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-left text-xs">
                <div className="font-medium">{item.name}</div>
                <div className="mt-1 text-lg font-semibold">{money(item.cap_usd)}</div>
                <div className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">{item.description}</div>
              </button>
            ))}
          </div>
          <Button size="sm" className="h-8 text-xs" onClick={estimateSample} disabled={busy === "estimate"}>
            {busy === "estimate" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <ReceiptText className="mr-1 h-3 w-3" />}
            Oszacuj przykład
          </Button>
          {estimate ? <MiniRow label="Rekomendowany budżet" value={`${money(estimate.recommended_budget_usd)} / ${wsText(estimate.recommendation)}`} /> : null}
        </div>
      );
    }
    if (activeStep === 3) {
      const mapping = settings.autonomy?.goal_mapping || {};
      return (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          {Object.entries(settings.autonomy?.presets || {}).map(([id, preset]: any) => (
            <button key={id} type="button" onClick={() => saveAutonomy(id)} className={cn("rounded-md border p-3 text-left text-xs", mapping[goal] === id ? "border-primary bg-primary/10" : "border-sylion-border bg-secondary/10")}>
              <div className="font-medium">{preset.name}</div>
              <div className="mt-1 line-clamp-3 text-[10px] text-muted-foreground">{preset.description}</div>
            </button>
          ))}
        </div>
      );
    }
    if (activeStep === 4) {
      return (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {Object.entries(notificationMatrix).slice(0, 10).map(([event, channels]: any) => (
              <MiniRow key={event} label={event} value={channels.join(", ")} />
            ))}
          </div>
          <div className="space-y-2">
            <MiniRow label="Mobile sparowane" value={settings.mobile?.paired ? "tak" : "nie"} />
            <MiniRow label="Aktywne kanały" value={activeChannels.join(", ")} />
            <Button size="sm" className="h-8 w-full text-xs" onClick={pairMobile} disabled={busy === "mobile"}>
              {busy === "mobile" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Smartphone className="mr-1 h-3 w-3" />}
              Sparuj demo mobile
            </Button>
            <Button variant="outline" size="sm" className="h-8 w-full text-xs" onClick={saveNotifications} disabled={busy === "notifications"}>
              Zapisz macierz
            </Button>
          </div>
        </div>
      );
    }
    if (activeStep === 5) {
      return (
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-5">
          {cleanupDefaults.map((item: any) => (
            <MiniRow key={item.environment_type} label={item.environment_type} value={item.policy} />
          ))}
        </div>
      );
    }
    if (activeStep === 6) {
      return (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {(templates.ui_presets || []).map((item: any) => (
            <button key={item.id} type="button" onClick={saveUi} className={cn("rounded-md border p-3 text-left text-xs", settings.ui?.preset === item.id ? "border-primary bg-primary/10" : "border-sylion-border bg-secondary/10")}>
              <div className="font-medium">{item.label}</div>
              <div className="mt-1 text-[10px] text-muted-foreground">{item.density} / {item.theme} / {item.accent}</div>
            </button>
          ))}
        </div>
      );
    }
    if (activeStep === 7) {
      return (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div className="space-y-2">
            {(settings.shortcuts?.predefined || []).slice(0, 7).map((item: any) => (
              <MiniRow key={item.id} label={item.combo} value={item.action} />
            ))}
          </div>
          <div className="space-y-2">
            <MiniRow label="Grupowanie nawigacji" value={wsText(settings.navigation?.grouping || "status")} />
            <MiniRow label="Szybkie wyszukiwanie" value={settings.navigation?.quick_search?.shortcut || "Cmd+K"} />
            <Button size="sm" className="h-8 text-xs" onClick={saveShortcut} disabled={busy === "shortcut"}>
              <Keyboard className="mr-1 h-3 w-3" />
              Dodaj sugerowany skrót
            </Button>
          </div>
        </div>
      );
    }
    if (activeStep === 8) {
      return (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {Object.entries(settings.approvals?.workflows || {}).map(([event, config]: any) => (
            <MiniRow key={event} label={event} value={`${config.primary?.join("+")} -> ${config.fallback?.channel || "none"}`} />
          ))}
        </div>
      );
    }
    return (
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="space-y-2">
          <MiniRow label="Strategia testów" value={wsText(settings.test_strategy?.default || "balanced_human_like")} />
          <MiniRow label="Test jak człowiek" value={settings.test_strategy?.human_like_required ? "wymagany" : "ograniczony"} />
          <MiniRow label="Szablony Rady" value={String(Object.keys(settings.council_templates || {}).length)} />
          <Button size="sm" className="h-8 text-xs" onClick={saveTesting} disabled={busy === "testing"}>
            <TestTube className="mr-1 h-3 w-3" />
            Zapisz domyślne testy
          </Button>
        </div>
        <div className="space-y-2">
          <MiniRow label="Przypadki brzegowe" value={String(edgeCases.length)} />
          <MiniRow label="Biblioteka ról" value={String((templates.role_library || []).length)} />
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={diagnoseEdge} disabled={busy === "edge"}>
              <Zap className="mr-1 h-3 w-3" />
              Diagnozuj przypadek brzegowy
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={previewInheritance} disabled={busy === "inheritance"}>
              <GitBranch className="mr-1 h-3 w-3" />
              Podgląd dziedziczenia
            </Button>
          </div>
          {edgeDiagnosis ? <MiniRow label="Runbook" value={edgeDiagnosis.case?.action || ""} /> : null}
          {inheritance ? <MiniRow label="Rozwiązane" value={`${wsText(inheritance.resolved?.budget_template)} / ${wsText(inheritance.resolved?.autonomy_preset)}`} /> : null}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Workflow className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
              Domyślne ustawieńia obszaru pracy - Faza 4
              <HelpTip text="Warstwa W8: domyślne budżety, autonomia, powiadomienia, cleanup, UI, zgody, testy i szablony Rady. Operator ustawia tu bezpieczny punkt startowy dla nowych projektów." />
            </h1>
            <p className="text-sm text-muted-foreground">Inteligentne ustawieńia domyślne budżetów, autonomii, powiadomień, cleanupu, UI, zgód, testów i Rady.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select className={cn(selectClass, "w-[180px]")} value={goal} onChange={(e) => setGoal(e.target.value)}>
            {["apps_internal", "public_products", "cybersecurity", "research"].map((item) => <option key={item} value={item}>{wsText(item)}</option>)}
          </select>
          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => void load()} disabled={loading}>
            {loading ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
            Odśwież
          </Button>
          <Button size="sm" className="h-8 text-xs" onClick={applySmartDefaults} disabled={busy === "smart"}>
            <Zap className="mr-1 h-3 w-3" />
            Zastosuj inteligentne domyślne
          </Button>
          <Badge variant="outline" className={cn("text-[10px]", backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
            {backendLive ? "BACKEND DZIAŁA" : backendPending ? "ŁĄCZENIE Z BACKENDEM" : "BACKEND NIEDOSTĘPNY"}
          </Badge>
          <Badge variant="outline" className={cn("text-[10px]", acceptance.accepted ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
            {acceptance.accepted ? "FAZA 4 GOTOWA" : "FAZA 4 OCZEKUJE"}
          </Badge>
        </div>
      </div>

      {status ? <Card className="border-sylion-amber/30 bg-sylion-amber/10 p-3 text-xs text-sylion-amber">{status}</Card> : null}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-6">
        <Metric label="Szablony budżetu" value={budgetTemplates.length || 0} />
        <Metric label="Presety autonomii" value={Object.keys(settings.autonomy?.presets || {}).length || 0} />
        <Metric label="Kanały powiadomień" value={activeChannels.length || 0} />
        <Metric label="Typy cleanupu" value={cleanupDefaults.length || 0} />
        <Metric label="Zestawy Rady" value={Object.keys(settings.council_templates || {}).length || 0} />
        <Metric label="Przypadki brzegowe" value={edgeCases.length || 0} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="border-sylion-border bg-card p-3">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Workflow className="h-4 w-4 text-primary" />
            Kreator 1-9
          </div>
          <div className="space-y-1">
            {(wizard.steps || []).map((step: any) => (
              <button
                key={step.step}
                type="button"
                onClick={() => setActiveStep(step.step)}
                className={cn("flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-xs", activeStep === step.step ? "bg-primary text-primary-foreground" : "bg-secondary/10 text-muted-foreground hover:text-foreground")}
              >
                <span>{step.step}. {step.label}</span>
                <ChevronRight className="h-3 w-3" />
              </button>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-[10px] text-muted-foreground">
            <div>Gotowe: {(wizard.completed_steps || []).length}</div>
            <div>Pominięte: {(wizard.skipped_steps || []).length}</div>
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <ShieldCheck className="h-4 w-4 text-primary" />
                Krok {activeStep}/9 - {(wizard.steps || []).find((step: any) => step.step === activeStep)?.label || "Domyślne ustawieńia"}
              </h2>
              <div className="mt-1 text-[11px] text-muted-foreground">{(wizard.steps || []).find((step: any) => step.step === activeStep)?.advisor}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => saveCurrentStep(true)} disabled={busy === "step"}>Pomiń krok</Button>
              <Button size="sm" className="h-8 text-xs" onClick={() => saveCurrentStep(false)} disabled={busy === "step"}>
                {busy === "step" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <CheckCircle2 className="mr-1 h-3 w-3" />}
                Zapisz krok
              </Button>
            </div>
          </div>
          <div className="mt-4 min-h-[260px]">{loading ? <div className="text-xs text-muted-foreground">Ładowanie domyślnych ustawień...</div> : renderStep()}</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Bell className="h-4 w-4 text-primary" />
            Powiadomienia i zgody
          </h2>
          <div className="mt-3 space-y-2">
            <MiniRow label="Kanały" value={activeChannels.join(", ")} />
            <MiniRow label="Mobile" value={settings.mobile?.paired ? "sparowane + push zweryfikowany" : "fallback tylko desktop"} />
            <MiniRow label="Twarda bramka" value={(settings.approvals?.workflows?.hard_gate?.primary || []).join("+")} />
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Palette className="h-4 w-4 text-primary" />
            UI, skróty i nawigacja
          </h2>
          <div className="mt-3 space-y-2">
            <MiniRow label="Preset UI" value={wsText(settings.ui?.preset || "power_user")} />
            <MiniRow label="Skróty własne" value={String((settings.shortcuts?.custom || []).length)} />
            <MiniRow label="Grupowanie projektów" value={wsText(settings.navigation?.grouping || "status")} />
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Trash2 className="h-4 w-4 text-primary" />
            Cleanup i testy
          </h2>
          <div className="mt-3 space-y-2">
            <MiniRow label="Domyślne cleanupy" value={`${cleanupDefaults.length || 0} typów`} />
            <MiniRow label="Strategia testów" value={wsText(settings.test_strategy?.default || "balanced_human_like")} />
            <MiniRow label="Jak człowiek" value={settings.test_strategy?.human_like_required ? "wymagane" : "ograniczone"} />
          </div>
        </Card>
      </div>

      <Card className="border-sylion-border bg-card p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Users className="h-4 w-4 text-primary" />
              Akceptacja fazy 4
            </h2>
            <div className="mt-1 text-[11px] text-muted-foreground">Wspólne DoD oraz kontrole specyficzne dla celu: {wsText(goal)}.</div>
          </div>
          <Button size="sm" className="h-8 text-xs" onClick={runAcceptance} disabled={busy === "acceptance"}>
            {busy === "acceptance" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
            Uruchom akceptację
          </Button>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
          {(acceptance.checks || []).map((check: any) => (
            <div key={check.id} className="flex items-start gap-2 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
              <StatusIcon status={check.status} />
              <div className="min-w-0">
                <div className="truncate font-medium">{check.label}</div>
                <div className="mt-1 truncate text-[10px] text-muted-foreground">{check.evidence}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
