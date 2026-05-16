"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  ChevronDown,
  ChevronRight,
  Settings as SettingsIcon,
  RotateCcw,
  Power,
  History as HistoryIcon,
  ExternalLink,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn, fmtDateTime } from "@/lib/utils";
import { BackendErrorBanner } from "@/components/advisor/BackendErrorBanner";
import { useOnboarding, usePreferences } from "@/lib/hooks/advisor";
import { advisorApi, DEFAULT_OPERATOR_ID } from "@/lib/api/advisor";
import { Step1Welcome } from "@/components/wizard/Step1Welcome";
import { Step2Providers } from "@/components/wizard/Step2Providers";
import { Step3Budget } from "@/components/wizard/Step3Budget";
import { Step4Domain } from "@/components/wizard/Step4Domain";
import { Step5Autonomy } from "@/components/wizard/Step5Autonomy";
import { Step6Council } from "@/components/wizard/Step6Council";
import { Step7QualitySpeedCost } from "@/components/wizard/Step7QualitySpeedCost";
import { Step8TrustedBlocked } from "@/components/wizard/Step8TrustedBlocked";
import { Step9Funding } from "@/components/wizard/Step9Funding";
import { HelpTip } from "@/components/common/HelpTip";

type AnyStepProps = { values: Record<string, unknown>; onChange: (patch: Record<string, unknown>) => void };

interface SectionDef {
  id: string;
  title: string;
  description: string;
  preferenceKeys: string[];
  Step: React.ComponentType<AnyStepProps>;
}

const asStep = (Component: unknown) => Component as React.ComponentType<AnyStepProps>;

const SECTIONS: SectionDef[] = [
  { id: "welcome", title: "1. Powitanie i cele", description: "Tożsamość operatora, cele i częstotliwość u?ycia używane do ważenia rekomendacji opartych na historii.", preferenceKeys: ["operator_name", "goals", "usage_cadence"], Step: asStep(Step1Welcome) },
  { id: "providers", title: "2. Klucze API providerów", description: "Klucze zewnętrznych LLM + lokalny URL bazowy Ollama.", preferenceKeys: ["anthropic_api_key", "openai_api_key", "google_api_key", "ollama_base_url"], Step: asStep(Step2Providers) },
  { id: "budget", title: "3. Domyslne bud?ety", description: "Limity kosztu per poziom ryzyka wymuszane przed wywolaniem LLM judge.", preferenceKeys: ["cost_ceilings", "budget_thresholds"], Step: asStep(Step3Budget) },
  { id: "domain", title: "4. Domyślna domena projektu", description: "G??wna domena projektu — rozszerza 14 bazowych lub używa prefiksu `custom:*`.", preferenceKeys: ["default_project_domain"], Step: asStep(Step4Domain) },
  { id: "autonomy", title: "5. Domyślna autonomia", description: "Manualna / sugeruj / auto. Twarda preferencja (D3+ przy zmianie).", preferenceKeys: ["autonomy_level"], Step: asStep(Step5Autonomy) },
  { id: "council", title: "6. Rozmiar rady + routing LLM judge", description: "Rozmiar rady (1–11) i routing modeli per poziom ryzyka.", preferenceKeys: ["council_size", "llm_judge_routing_override"], Step: asStep(Step6Council) },
  { id: "qsc", title: "7. Jakosc / Szybkosc / Koszt", description: "3-osiowy slider sumujacy sie do 1.0; wp?ywa na ensemble + strategie cache.", preferenceKeys: ["quality_speed_cost"], Step: asStep(Step7QualitySpeedCost) },
  { id: "providers_pref", title: "8. Zaufani / zablokowani dostawcy", description: "Twarde preferencje — D3+ przy zmianie.", preferenceKeys: ["trusted_providers", "blocked_providers"], Step: asStep(Step8TrustedBlocked) },
  { id: "funding", title: "9. Funding Advisor", description: "Modul opt-in. Twarda preferencja: wlaczenie/wylaczenie wymaga potwierdzenia D3+.", preferenceKeys: ["funding_advisor_enabled", "funding_countries", "funding_token_budget_monthly"], Step: asStep(Step9Funding) },
];

export default function AdvisorSettingsPage() {
  const { state, saveStep } = useOnboarding();
  const { preferences, source, refresh } = usePreferences(DEFAULT_OPERATOR_ID);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [auditOpen, setAuditOpen] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  const indexed = useMemo(() => {
    const map = new Map<string, (typeof preferences)[number]>();
    for (const p of preferences) map.set(p.preference_key, p);
    return map;
  }, [preferences]);

  const values: Record<string, unknown> = state.values;

  function toggle(id: string) {
    setOpen((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  async function handleSectionSave(section: SectionDef) {
    setSavingId(section.id);
    setResetMessage(null);
    try {
      await saveStep(state.step, values);
      refresh();
    } finally {
      setSavingId(null);
    }
  }

  async function handleResetKey(key: string) {
    setResetMessage(null);
    try {
      await advisorApi.resetPreference(DEFAULT_OPERATOR_ID, key);
      setResetMessage(`reset:${key}`);
      refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "nieznany błąd";
      setResetMessage(`error:${key}:${message}`);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
            <SettingsIcon className="h-3.5 w-3.5" /> Ustawienia Doradcy
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">
            Konfigurator setupu
            <HelpTip text="Edytuj każdą decyzję z wizarda onboardingowego. Każda sekcja mapuje na jeden lub więcej kluczy w advisor_preferences.preferences. Twarde preferencje (autonomia, providers trust) wymagaj? potwierdzenia D3+." />
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Edytuj dowolna decyzję z onboardingu w późniejszym czasie. Każda sekcja mapuje na jeden lub więcej wpis?w w
            <code className="mx-1 rounded bg-muted/40 px-1 py-0.5 font-mono text-[11px]">advisor_preferences.preferences</code>.
            <Link href="/onboarding" className="ml-2 inline-flex items-center gap-0.5 text-sylion-blue hover:underline">
              uruchom wizard ponownie <ExternalLink className="h-3 w-3" />
            </Link>
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setAuditOpen((v) => !v)}>
          <HistoryIcon className="mr-1 h-3.5 w-3.5" />
          Historia audytu
        </Button>
      </header>

      <BackendErrorBanner source={source} />

      {auditOpen ? <AuditHistoryPanel /> : null}

      {resetMessage ? (
        <div className="rounded-md border border-sylion-amber/30 bg-sylion-amber/5 px-3 py-2 text-xs text-sylion-amber">
          {resetMessage.startsWith("error:")
            ? `Reset preferencji ${resetMessage.split(":")[1]} nie powiodl sie: ${resetMessage.split(":").slice(2).join(":")}.`
            : `Preferencja ${resetMessage.split(":")[1]} przywrocona do wartośći systemowej.`}
        </div>
      ) : null}

      <div className="space-y-3">
        {SECTIONS.map((section) => {
          const isOpen = !!open[section.id];
          const Step = section.Step;
          const setBy = section.preferenceKeys
            .map((k) => indexed.get(k)?.set_by)
            .filter(Boolean)
            .join(" · ");
          const updatedAt = section.preferenceKeys
            .map((k) => indexed.get(k)?.updated_at)
            .filter((v): v is number => typeof v === "number")
            .sort((a, b) => b - a)[0];
          return (
            <motion.div key={section.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
              <Card className="overflow-hidden">
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => toggle(section.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      toggle(section.id);
                    }
                  }}
                  className={cn(
                    "flex w-full cursor-pointer items-center justify-between gap-3 px-4 py-3 text-left transition",
                    isOpen ? "bg-muted/20" : "hover:bg-muted/10",
                  )}
                >
                  <div className="flex items-start gap-3">
                    {isOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                    <div>
                      <h2 className="text-sm font-semibold">
                        {section.title}
                        <HelpTip text={`Sekcja konfiguracji Doradcy (${section.preferenceKeys.join(", ")}). ${section.description}`} />
                      </h2>
                      <p className="text-xs text-muted-foreground">{section.description}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-1 text-[10px] uppercase tracking-wide text-muted-foreground/80">
                        {section.preferenceKeys.map((k) => (
                          <Badge key={k} variant="outline" className="border-border/50 font-mono text-[10px]">
                            {k}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end text-[10px] uppercase tracking-wide text-muted-foreground">
                    {setBy ? <span>ustawione przez {setBy}</span> : <span>nieustawione</span>}
                    {updatedAt ? <span>{fmtDateTime(new Date(updatedAt * 1000).toISOString())}</span> : null}
                  </div>
                </div>

                {isOpen ? (
                  <div className="border-t border-border/50 bg-background p-4">
                    <Step values={values} onChange={(patch) => saveStep(state.step, patch)} />
                    <Separator className="my-4" />
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        {section.preferenceKeys.map((k) => (
                          <Button
                            key={k}
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => handleResetKey(k)}
                            className="text-xs"
                          >
                            <RotateCcw className="mr-1 h-3.5 w-3.5" />
                            Resetuj {k}
                          </Button>
                        ))}
                        {section.preferenceKeys.includes("funding_advisor_enabled") ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => saveStep(state.step, { funding_advisor_enabled: false })}
                            className="text-xs text-orange-400"
                          >
                            <Power className="mr-1 h-3.5 w-3.5" />
                            Wylacz modul Funding
                          </Button>
                        ) : null}
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => handleSectionSave(section)}
                        disabled={savingId === section.id}
                      >
                        {savingId === section.id ? "Zapisywanie…" : "Zapisz sekcje"}
                      </Button>
                    </div>
                  </div>
                ) : null}
              </Card>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

function AuditHistoryPanel() {
  const [entries, setEntries] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await advisorApi.preferenceAudit(DEFAULT_OPERATOR_ID);
      setEntries(res.entries);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    queueMicrotask(() => {
      void load();
    });
  }, []);

  return (
    <Card className="p-4">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">
            Log audytowy preferencji
            <HelpTip text="Append-only zapis kazdej zmiany preferencji Doradcy: kto, kiedy, z czego na co. Sluzy do compliance i debugowania niespodziewanych zachowan systemu." />
          </h3>
          <p className="text-xs text-muted-foreground">
            Historia append-only z <code className="font-mono">advisor_preferences.preferences_audit</code>.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          {loading ? "Ładowanie…" : "Odśwież"}
        </Button>
      </header>
      {error ? (
        <p className="mb-2 rounded-md border border-orange-400/30 bg-orange-400/5 px-2 py-1 text-[11px] text-orange-400">
          Błąd: {error}
        </p>
      ) : null}
      {loading ? (
        <p className="py-4 text-center text-xs text-muted-foreground">Ładowanie…</p>
      ) : entries.length === 0 ? (
        <p className="py-4 text-center text-xs text-muted-foreground">Brak wpisów w historii.</p>
      ) : (
        <ul className="space-y-1.5">
          {entries.map((e, i) => (
            <li
              key={i}
              className="rounded border border-border/50 bg-muted/10 px-3 py-2 font-mono text-[11px] leading-tight"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 text-muted-foreground">
                <span>{String(e.changed_at ?? "")}</span>
                <span>{String(e.changed_by ?? "operator")}</span>
              </div>
              <p className="mt-1 text-foreground">
                <span className="text-sylion-blue">{String(e.preference_key ?? "?")}</span>{" "}
                <span className="text-muted-foreground">{String(e.change_type ?? "UPDATE")}</span>{" "}
                <span>{JSON.stringify(e.old_value ?? null)}</span>{" "}
                <span className="text-muted-foreground">→</span>{" "}
                <span>{JSON.stringify(e.new_value ?? null)}</span>
              </p>
              {e.reason ? <p className="text-muted-foreground/80">{String(e.reason)}</p> : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
