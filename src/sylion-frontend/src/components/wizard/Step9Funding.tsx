"use client";

import { Globe, MapPin } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { SmartDefault } from "./SmartDefault";
import type { ApiKeyEntry, LocalModelEntry } from "./Step2Providers";
import { cn } from "@/lib/utils";

export const FUNDING_COUNTRIES: Array<{ id: string; label: string; eu?: boolean }> = [
  { id: "PL", label: "Polska", eu: true },
  { id: "DE", label: "Niemcy", eu: true },
  { id: "FR", label: "Francja", eu: true },
  { id: "ES", label: "Hiszpania", eu: true },
  { id: "IT", label: "Włochy", eu: true },
  { id: "NL", label: "Holandia", eu: true },
  { id: "EU", label: "EU (Horizon, EIC)" },
  { id: "UK", label: "Wielka Brytania" },
  { id: "US", label: "Stany Zjednoczone" },
];

export const PL_VOIVODESHIPS: string[] = [
  "mazowieckie",
  "dolnoslaskie",
  "wielkopolskie",
  "malopolskie",
  "slaskie",
  "lubelskie",
  "lodzkie",
  "podkarpackie",
  "pomorskie",
  "swietokrzyskie",
  "warminsko-mazurskie",
  "zachodniopomorskie",
  "kujawsko-pomorskie",
  "lubuskie",
  "opolskie",
  "podlaskie",
];

export interface Step9Values {
  funding_advisor_enabled?: boolean;
  funding_countries?: string[];
  funding_pl_regions?: string[];
  funding_model_profile?: {
    research_provider: "perplexity" | "manual";
    polish_specialists: string[];
    require_polish_specialist: boolean;
    missing_polish_models: string[];
  };
}

interface Step9Context {
  apiKeys?: ApiKeyEntry[];
  localModels?: LocalModelEntry[];
}

interface Props {
  values: Step9Values;
  context?: Step9Context;
  onChange: (patch: Step9Values) => void;
}

export function Step9Funding({ values, context, onChange }: Props) {
  const enabled = values.funding_advisor_enabled === true;
  const countries = values.funding_countries ?? [];
  const plRegions = values.funding_pl_regions ?? [];
  const plSelected = countries.includes("PL");
  const apiKeys = context?.apiKeys ?? [];
  const localModels = context?.localModels ?? [];
  const hasUsablePerplexity = apiKeys.some(
    (k) =>
      k.provider === "perplexity" &&
      k.key?.trim().length >= 10 &&
      k.validation_status !== "error" &&
      k.validation_status !== "testing",
  );
  const installedLocalNames = localModels.filter((m) => m.status === "installed").map((m) => m.name);
  const bielikModel = installedLocalNames.find((name) => name.toLowerCase().includes("bielik"));
  const pllumModel = installedLocalNames.find((name) => name.toLowerCase().includes("pllum"));
  const missingPolishModels = [
    bielikModel ? "" : "Bielik",
    pllumModel ? "" : "PLLuM",
  ].filter(Boolean);
  const modelProfile = values.funding_model_profile;

  const toggleCountry = (id: string) => {
    const next = countries.includes(id) ? countries.filter((c) => c !== id) : [...countries, id];
    onChange({ funding_countries: next });
  };

  const toggleRegion = (r: string) => {
    const next = plRegions.includes(r) ? plRegions.filter((x) => x !== r) : [...plRegions, r];
    onChange({ funding_pl_regions: next });
  };

  const applyPolishFundingProfile = () => {
    onChange({
      funding_model_profile: {
        research_provider: hasUsablePerplexity ? "perplexity" : "manual",
        polish_specialists: [
          bielikModel ?? "Bielik (wymagany model lokalny)",
          pllumModel ?? "PLLuM (wymagany model lokalny)",
        ],
        require_polish_specialist: true,
        missing_polish_models: missingPolishModels,
      },
    });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4 rounded-md border border-border bg-muted/10 p-3">
        <div>
          <p className="text-sm font-semibold">Włącz Doradcę Finansowania</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Wyszukuje granty, ocenia kwalifikowalność i pokazuje terminy. Domyślnie wyłączony —
            działa tylko po świadomym włączeniu przez operatora.
          </p>
        </div>
        <Switch
          checked={enabled}
          onCheckedChange={(v) => onChange({ funding_advisor_enabled: Boolean(v) })}
          data-testid="step9-toggle"
        />
      </div>

      {enabled ? (
        <>
          <div className="space-y-2">
            <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <Globe className="h-3.5 w-3.5" /> Kraje / regiony
            </label>
            <div className="grid grid-cols-3 gap-2" data-testid="step9-countries">
              {FUNDING_COUNTRIES.map((c) => {
                const active = countries.includes(c.id);
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => toggleCountry(c.id)}
                    className={cn(
                      "rounded-md border px-3 py-2 text-left text-sm transition",
                      active
                        ? "border-sylion-blue/60 bg-sylion-blue/10 text-sylion-blue"
                        : "border-border hover:bg-muted/30",
                    )}
                    data-testid={`step9-country-${c.id}`}
                    data-active={active}
                  >
                    <span className="font-medium">{c.id}</span>
                    <span className="ml-1 text-[11px] text-muted-foreground">{c.label}</span>
                    {c.eu ? (
                      <span className="ml-1 rounded bg-sylion-blue/15 px-1 text-[9px] uppercase text-sylion-blue">
                        EU
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
            {countries.length === 0 ? (
              <SmartDefault
                label="Zacznij od PL + EU"
                rationale="Obejmuje FENG i Horizon — dwa programy o największym wolumenie w ustawieńiach domyślnych."
                onApply={() => onChange({ funding_countries: ["PL", "EU"] })}
              />
            ) : null}
          </div>

          {plSelected ? (
            <div className="space-y-2 border-t border-border pt-4" data-testid="step9-pl-regions">
              <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <MapPin className="h-3.5 w-3.5" /> Województwa (Polska)
              </label>
              <div className="grid grid-cols-3 gap-1.5">
                {PL_VOIVODESHIPS.map((r) => {
                  const active = plRegions.includes(r);
                  return (
                    <button
                      key={r}
                      type="button"
                      onClick={() => toggleRegion(r)}
                      className={cn(
                        "rounded-md border px-2 py-1 text-left text-[11px] transition",
                        active
                          ? "border-sylion-blue/60 bg-sylion-blue/10 text-sylion-blue"
                          : "border-border hover:bg-muted/30",
                      )}
                      data-testid={`step9-region-${r}`}
                    >
                      {r}
                    </button>
                  );
                })}
              </div>
              <p className="text-[11px] text-muted-foreground">
                Opcjonalne — zostaw puste, aby otrzymywać wszystkie polskie programy krajowe.
              </p>
            </div>
          ) : null}

          <div
            className="space-y-3 rounded-md border border-sylion-blue/30 bg-sylion-blue/5 p-3"
            data-testid="step9-polish-funding-model-profile"
          >
            <div>
              <p className="text-sm font-semibold text-sylion-blue">
                Profil modeli dla polskich grantów
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Dla FENG, PARP, NCBR, Horizon i konkursów regionalnych AEIS powinien łączyć
                aktualne źródła z modelem dobrze rozumiejącym polski język urzędowy.
              </p>
            </div>
            <div className="grid gap-2 md:grid-cols-3">
              <div className="rounded-md border border-border bg-background/40 p-2 text-xs">
                <p className="font-semibold">Perplexity</p>
                <p className="mt-0.5 text-muted-foreground">Wyszukiwanie aktualnych naborów i cytowania.</p>
                <p className={cn("mt-1 font-mono text-[11px]", hasUsablePerplexity ? "text-sylion-green" : "text-sylion-amber")}>
                  {hasUsablePerplexity ? "dostępny" : "brak działającego klucza"}
                </p>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-2 text-xs">
                <p className="font-semibold">Bielik.ai</p>
                <p className="mt-0.5 text-muted-foreground">Polski język, streszczenia regulaminów, pytania do operatora.</p>
                <p className={cn("mt-1 font-mono text-[11px]", bielikModel ? "text-sylion-green" : "text-sylion-amber")}>
                  {bielikModel ?? "nie wykryto w Ollama"}
                </p>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-2 text-xs">
                <p className="font-semibold">PLLuM</p>
                <p className="mt-0.5 text-muted-foreground">Polskie teksty publiczne, kryteria formalne, administracja.</p>
                <p className={cn("mt-1 font-mono text-[11px]", pllumModel ? "text-sylion-green" : "text-sylion-amber")}>
                  {pllumModel ?? "nie wykryto w Ollama"}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={applyPolishFundingProfile}
              className="rounded-md border border-sylion-blue/40 px-3 py-2 text-xs font-semibold text-sylion-blue transition hover:bg-sylion-blue/10"
              data-testid="step9-apply-polish-funding-profile"
            >
              Użyj profilu: Perplexity + Bielik + PLLuM
            </button>
            {modelProfile ? (
              <div className="rounded-md border border-sylion-green/30 bg-sylion-green/5 p-2 text-[11px]" data-testid="step9-model-profile-summary">
                <p className="font-semibold text-sylion-green">Profil aktywny</p>
                <p className="mt-0.5 text-muted-foreground">
                  Badanie źródeł: {modelProfile.research_provider}; specjaliści PL:{" "}
                  {modelProfile.polish_specialists.join(", ")}
                </p>
              </div>
            ) : null}
            {modelProfile?.require_polish_specialist && modelProfile.missing_polish_models.length > 0 ? (
              <div
                className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-[11px] text-amber-200"
                data-testid="step9-polish-model-hg-warning"
              >
                Brakuje modeli: {modelProfile.missing_polish_models.join(", ")}. AEIS ma wymagać
                HumanGate przed scoringiem polskich grantów albo instalacji modelu lokalnego w kroku 2.
              </div>
            ) : null}
          </div>
        </>
      ) : (
        <p className="text-xs text-muted-foreground">
          Doradca Finansowania jest wyłączony. Możesz włączyć go później w Ustawienia → Doradca.
        </p>
      )}
    </div>
  );
}
