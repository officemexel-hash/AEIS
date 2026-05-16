"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Clock,
  Database,
  ExternalLink,
  History,
  Languages,
  RefreshCw,
  Save,
  ShieldCheck,
  UserCircle,
} from "lucide-react";

import { BackendErrorBanner } from "@/components/advisor/BackendErrorBanner";
import { HelpTip } from "@/components/common/HelpTip";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { advisorApi, AdvisorConfigurationCounts, DEFAULT_OPERATOR_ID } from "@/lib/api/advisor";
import { useOnboarding, usePreferences } from "@/lib/hooks/advisor";
import { cn, fmtDateTime } from "@/lib/utils";

const PROFILE_GOALS = [
  { id: "build_apps", label: "Budowa aplikacji przez AEIS" },
  { id: "audit_runtime", label: "Audyt runtime i decyzji" },
  { id: "funding", label: "Funding i dotacje" },
  { id: "deploy", label: "Deploy na infrastrukturę" },
  { id: "skills", label: "Rozwój warstwy skills" },
];

const USAGE_OPTIONS = [
  { value: "daily", label: "Codziennie" },
  { value: "weekly", label: "Kilka razy w tygodniu" },
  { value: "project_based", label: "Projektowo" },
  { value: "audit_only", label: "Tylko audyty" },
];

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function normalizeGoals(value: unknown): string[] {
  const allowed = new Set(PROFILE_GOALS.map((goal) => goal.id));
  const legacyMap: Record<string, string> = {
    ship_software: "build_apps",
    audit_governance: "audit_runtime",
    win_grants: "funding",
    ops: "deploy",
    research: "skills",
  };
  const normalized = asStringArray(value)
    .map((goal) => legacyMap[goal] ?? goal)
    .filter((goal) => allowed.has(goal));
  return Array.from(new Set(normalized));
}

function parseTimestamp(value: unknown): string | null {
  if (typeof value === "number") return new Date(value * 1000).toISOString();
  if (typeof value === "string" && value.trim()) return value;
  return null;
}

export default function OperatorProfilePage() {
  const { state, saveStep } = useOnboarding();
  const { preferences, source, refresh } = usePreferences(DEFAULT_OPERATOR_ID);
  const [counts, setCounts] = useState<AdvisorConfigurationCounts | null>(null);
  const [countsError, setCountsError] = useState<string | null>(null);
  const [auditEntries, setAuditEntries] = useState<Array<Record<string, unknown>>>([]);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const initial = state.values;
  const [operatorName, setOperatorName] = useState(asString(initial.operator_name, "Operator AEIS"));
  const [operatorRole, setOperatorRole] = useState(asString(initial.operator_role, "Operator / audytor"));
  const [operatorEmail, setOperatorEmail] = useState(asString(initial.operator_email));
  const [usageCadence, setUsageCadence] = useState(asString(initial.usage_cadence, "project_based"));
  const [goals, setGoals] = useState<string[]>(() => normalizeGoals(initial.goals));
  const [notes, setNotes] = useState(asString(initial.profile_notes));

  useEffect(() => {
    queueMicrotask(() => {
      const values = state.values;
      setOperatorName(asString(values.operator_name, "Operator AEIS"));
      setOperatorRole(asString(values.operator_role, "Operator / audytor"));
      setOperatorEmail(asString(values.operator_email));
      setUsageCadence(asString(values.usage_cadence, "project_based"));
      setGoals(normalizeGoals(values.goals));
      setNotes(asString(values.profile_notes));
    });
  }, [state.values]);

  const indexedPreferences = useMemo(() => {
    const map = new Map<string, (typeof preferences)[number]>();
    for (const preference of preferences) map.set(preference.preference_key, preference);
    return map;
  }, [preferences]);

  const profilePreference = indexedPreferences.get("operator_profile");
  const lastProfileUpdate = parseTimestamp(profilePreference?.updated_at);

  async function loadRuntimeStatus() {
    setCountsError(null);
    try {
      const [nextCounts, audit] = await Promise.all([
        advisorApi.getConfigurationCounts(),
        advisorApi.preferenceAudit(DEFAULT_OPERATOR_ID, "operator_profile"),
      ]);
      setCounts(nextCounts);
      setAuditEntries(audit.entries);
    } catch (error) {
      setCountsError(error instanceof Error ? error.message : String(error));
      setCounts(null);
      setAuditEntries([]);
    }
  }

  useEffect(() => {
    queueMicrotask(() => {
      void loadRuntimeStatus();
    });
  }, []);

  function toggleGoal(goalId: string) {
    setGoals((current) =>
      current.includes(goalId) ? current.filter((goal) => goal !== goalId) : [...current, goalId],
    );
  }

  function validateProfile(): string | null {
    if (!operatorName.trim()) return "Imię operatora jest wymagane.";
    if (operatorEmail.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(operatorEmail.trim())) {
      return "E-mail operatora ma niepoprawny format.";
    }
    if (goals.length === 0) return "Wybierz przynajmniej jeden cel pracy z AEIS.";
    return null;
  }

  async function handleSave() {
    setSaveMessage(null);
    const validation = validateProfile();
    setFormError(validation);
    if (validation) return;

    const payload = {
      operator_name: operatorName.trim(),
      operator_role: operatorRole.trim(),
      operator_email: operatorEmail.trim(),
      locale: "pl-PL",
      timezone: "Europe/Warsaw",
      usage_cadence: usageCadence,
      goals,
      profile_notes: notes.trim(),
    };

    setSaving(true);
    try {
      await saveStep(1, payload);
      await Promise.all([
        advisorApi.setPreference(DEFAULT_OPERATOR_ID, "operator_profile", payload),
        advisorApi.setPreference(DEFAULT_OPERATOR_ID, "operator_name", payload.operator_name),
        advisorApi.setPreference(DEFAULT_OPERATOR_ID, "operator_role", payload.operator_role),
        advisorApi.setPreference(DEFAULT_OPERATOR_ID, "operator_email", payload.operator_email),
        advisorApi.setPreference(DEFAULT_OPERATOR_ID, "operator_language", "pl-PL"),
        advisorApi.setPreference(DEFAULT_OPERATOR_ID, "operator_timezone", "Europe/Warsaw"),
        advisorApi.setPreference(DEFAULT_OPERATOR_ID, "usage_cadence", payload.usage_cadence),
        advisorApi.setPreference(DEFAULT_OPERATOR_ID, "goals", payload.goals),
        advisorApi.setPreference(DEFAULT_OPERATOR_ID, "profile_notes", payload.profile_notes),
      ]);
      await refresh();
      await loadRuntimeStatus();
      setSaveMessage("Profil operatora zapisany i odnotowany w audycie preferencji.");
    } catch (error) {
      setSaveMessage(`Zapis profilu nie powiódł się: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
            <UserCircle className="h-3.5 w-3.5" /> Ustawienia profilu
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">
            Profil operatora AEIS
            <HelpTip text="Profil operatora zasila onboarding, preferencje Doradcy i decyzję meta-orkiestracji. Zmiany są zapisywane w backendzie i widoczne w audycie preferencji." />
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Ten ekran nie jest statycznym formularzem. Zapisuje tożsamość, język, cele i rytm pracy operatora do
            live backendu, aby późniejsze HumanGate, Rada i rekomendacje fundingowe mogły używać tych ustawień.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/settings/advisor" className={buttonVariants({ variant: "outline", size: "sm" })}>
            Konfigurator Doradcy <ExternalLink className="ml-1 h-3.5 w-3.5" />
          </Link>
          <Button variant="outline" size="sm" onClick={() => void loadRuntimeStatus()}>
            <RefreshCw className="mr-1 h-3.5 w-3.5" /> Odśwież status
          </Button>
        </div>
      </header>

      <BackendErrorBanner source={source} />

      <div className="grid gap-4 lg:grid-cols-[1.35fr_0.9fr]">
        <Card className="p-5">
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">
                Dane operatora
                <HelpTip text="Dane z tego formularza są zapisywane jako onboarding step 1 oraz preference operator_profile. Walidacja wykrywa typowe błędy ludzkie: puste imie, zły e-mail, brak celów." />
              </h2>
              <p className="text-xs text-muted-foreground">Wypełnij jak człowiek przed pierwszą pracą z systemem.</p>
            </div>
            <Badge variant="outline" className="border-sylion-green/30 text-sylion-green">
              Język: polski
            </Badge>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-xs">
              <span className="text-muted-foreground">Imię / nazwa operatora</span>
              <input
                value={operatorName}
                onChange={(event) => setOperatorName(event.target.value)}
                className="w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-secondary/30 px-3 py-2 text-sm outline-none focus:border-primary/40"
                placeholder="np. Robert"
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-muted-foreground">Rola w audycie</span>
              <input
                value={operatorRole}
                onChange={(event) => setOperatorRole(event.target.value)}
                className="w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-secondary/30 px-3 py-2 text-sm outline-none focus:border-primary/40"
                placeholder="np. Operator / DPO / architekt"
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-muted-foreground">E-mail operatora</span>
              <input
                value={operatorEmail}
                onChange={(event) => setOperatorEmail(event.target.value)}
                className="w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-secondary/30 px-3 py-2 text-sm outline-none focus:border-primary/40"
                placeholder="operator@example.com"
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-muted-foreground">Rytm pracy</span>
              <select
                value={usageCadence}
                onChange={(event) => setUsageCadence(event.target.value)}
                className="w-full rounded-lg border border-[rgba(148,163,184,0.14)] bg-secondary/30 px-3 py-2 text-sm outline-none focus:border-primary/40"
              >
                {USAGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-4 space-y-2">
            <p className="text-xs text-muted-foreground">Cele pracy z AEIS</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {PROFILE_GOALS.map((goal) => {
                const selected = goals.includes(goal.id);
                return (
                  <button
                    key={goal.id}
                    type="button"
                    onClick={() => toggleGoal(goal.id)}
                    className={cn(
                      "rounded-lg border px-3 py-2 text-left text-xs transition",
                      selected
                        ? "border-primary/40 bg-primary/10 text-foreground"
                        : "border-[rgba(148,163,184,0.14)] bg-secondary/20 text-muted-foreground hover:border-primary/20",
                    )}
                  >
                    {goal.label}
                  </button>
                );
              })}
            </div>
          </div>

          <label className="mt-4 block space-y-1 text-xs">
            <span className="text-muted-foreground">Notatka operatora dla Rady i HumanGate</span>
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={4}
              className="w-full resize-none rounded-lg border border-[rgba(148,163,184,0.14)] bg-secondary/30 px-3 py-2 text-sm outline-none focus:border-primary/40"
              placeholder="Np. podczas audytu testuj błędy ludzkie, nie omijaj HumanGate, preferuj język polski i realne endpointy."
            />
          </label>

          {formError ? (
            <p className="mt-3 rounded-md border border-sylion-red/30 bg-sylion-red/5 px-3 py-2 text-xs text-sylion-red">
              {formError}
            </p>
          ) : null}
          {saveMessage ? (
            <p
              className={cn(
                "mt-3 rounded-md border px-3 py-2 text-xs",
                saveMessage.includes("nie powiódł")
                  ? "border-sylion-red/30 bg-sylion-red/5 text-sylion-red"
                  : "border-sylion-green/30 bg-sylion-green/5 text-sylion-green",
              )}
            >
              {saveMessage}
            </p>
          ) : null}

          <Separator className="my-4" />

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Languages className="h-3.5 w-3.5" /> locale: pl-PL
              </span>
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" /> timezone: Europe/Warsaw
              </span>
            </div>
            <Button onClick={handleSave} disabled={saving}>
              <Save className="mr-1 h-3.5 w-3.5" />
              {saving ? "Zapisywanie..." : "Zapisz profil"}
            </Button>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Activity className="h-4 w-4 text-sylion-blue" /> Status konfiguracji runtime
            </h2>
            {countsError ? (
              <p className="rounded-md border border-sylion-red/30 bg-sylion-red/5 px-3 py-2 text-xs text-sylion-red">
                Nie udało się pobrać statusu konfiguracji: {countsError}
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                <RuntimeMetric label="Klucze API" value={counts?.api_keys} />
                <RuntimeMetric label="Modele lokalne" value={counts?.local_models} />
                <RuntimeMetric label="Reguły routingu" value={counts?.routing_rules} />
                <RuntimeMetric label="Skills" value={counts?.skills} />
              </div>
            )}
          </Card>

          <Card className="p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <ShieldCheck className="h-4 w-4 text-sylion-green" /> Źródło danych
            </h2>
            <div className="space-y-2 text-xs text-muted-foreground">
              <p>
                Operator ID:{" "}
                <code className="rounded bg-muted/40 px-1 py-0.5 font-mono text-[11px]">{DEFAULT_OPERATOR_ID}</code>
              </p>
              <p>
                Ostatnia zmiana profilu:{" "}
                <span className="text-foreground">
                  {lastProfileUpdate ? fmtDateTime(lastProfileUpdate) : "brak zapisu operator_profile"}
                </span>
              </p>
              <p>
                Źródło preferencji:{" "}
                <Badge variant="outline" className={cn(source === "live" ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
                  {source === "live" ? "backend live" : source}
                </Badge>
              </p>
            </div>
          </Card>
        </div>
      </div>

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <History className="h-4 w-4 text-sylion-amber" /> Audyt zmian profilu
            </h2>
            <p className="text-xs text-muted-foreground">
              Wpisy z append-only historii preferencji dla klucza <code className="font-mono">operator_profile</code>.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void loadRuntimeStatus()}>
            Odśwież audyt
          </Button>
        </div>
        {auditEntries.length === 0 ? (
          <p className="rounded-md border border-border/50 bg-muted/10 px-3 py-4 text-center text-xs text-muted-foreground">
            Brak wpisów audytowych dla profilu. Zapisz formularz, aby utworzyć pierwszy wpis.
          </p>
        ) : (
          <div className="space-y-2">
            {auditEntries.slice(0, 8).map((entry, index) => (
              <div key={index} className="rounded-md border border-border/50 bg-muted/10 px-3 py-2 font-mono text-[11px]">
                <div className="flex flex-wrap justify-between gap-2 text-muted-foreground">
                  <span>{String(entry.changed_at ?? "czas nieznany")}</span>
                  <span>{String(entry.changed_by ?? "operator")}</span>
                </div>
                <p className="mt-1 text-foreground">
                  <span className="text-sylion-blue">{String(entry.preference_key ?? "operator_profile")}</span>{" "}
                  <span className="text-muted-foreground">{String(entry.change_type ?? "UPDATE")}</span>
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function RuntimeMetric({ label, value }: { label: string; value?: number }) {
  return (
    <div className="rounded-lg border border-[rgba(148,163,184,0.14)] bg-secondary/20 p-3">
      <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        <Database className="h-3 w-3" /> {label}
      </div>
      <p className="text-xl font-semibold">{typeof value === "number" ? value : "..."}</p>
    </div>
  );
}
