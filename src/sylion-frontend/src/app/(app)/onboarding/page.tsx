"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  HardDrive,
  KeyRound,
  Languages,
  Lock,
  PlayCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UserCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { WizardShell, type WizardStepDef } from "@/components/wizard";
import { advisorApi, type Phase1AcceptanceReport, type Phase1ModelGate, type Phase1StorageValidation, type Phase1SystemCheck } from "@/lib/api/advisor";
import { useOnboarding } from "@/lib/hooks/advisor";
import { cn } from "@/lib/utils";

const PHASE1_STEPS: WizardStepDef[] = [
  { id: 1, title: "Start", description: "System check, język i szybkie rozpoznanie lokalnej maszyny." },
  { id: 2, title: "Tożsamość", description: "Display name, system name, email, rola i strefa czasu." },
  { id: 3, title: "Storage", description: "Workspace, backup i walidacja ścieżki roboczej." },
  { id: 4, title: "Security", description: "Master password albo świadomie wybrany low-security mode." },
  { id: 5, title: "Profil", description: "Cele pracy i startowy preset autonomii." },
  { id: 6, title: "Tutorial", description: "Głębokość tutorialu i projekt szkoleniowy." },
  { id: 7, title: "Model gate", description: "Hard gate: minimum jeden model, API shortcut albo demo mode." },
  { id: 8, title: "Gotowe", description: "Acceptance test Fazy 1 i przejście do kolejnego kroku." },
];

const ROLES = [
  { id: "solo", label: "Solo", hint: "Sam pracuję i sam zatwierdzam decyzję." },
  { id: "team_lead", label: "Team Lead", hint: "Prowadzę mały zespół i potrzebuję czytelnego governance." },
  { id: "client", label: "Klient", hint: "Testuję możliwości platformy i chcę prostszy interfejs." },
];

const GOALS = [
  { id: "internal_apps", label: "Apps internal", hint: "CRM, dashboardy, panele zarządzania." },
  { id: "public_products", label: "Public products", hint: "SaaS, e-commerce, real users." },
  { id: "research", label: "Research", hint: "Eksperymenty AI, prototypy, R&D." },
  { id: "cybersecurity", label: "Cybersecurity tooling", hint: "Hard policy enforcement, air-gap, sovereign infra." },
  { id: "mixed", label: "Mixed / explore", hint: "Jeszcze wybieram kierunek." },
];

const AUTONOMY_PRESETS = [
  { id: "conservative", label: "Conservative", hint: "Najwięcej Human Gate i najniższe ryzyko." },
  { id: "balanced", label: "Balanced", hint: "Domyślny balans kontroli, szybkości i kosztu." },
  { id: "aggressive", label: "Aggressive", hint: "Szybsze iteracje dla sandboxów i R&D." },
];

const TUTORIAL_PROJECTS = [
  { id: "personal_knowledge_base", label: "Personal Knowledge Base", hint: "Notatki, tagi, search, lokalnie." },
  { id: "local_crm", label: "Lokalny CRM dla freelancera", hint: "Klienci, projekty, faktury, SQLite." },
  { id: "tailor_lite", label: "Sylion Tailor Lite", hint: "Web shop, mobile, lokalny deploy." },
  { id: "custom", label: "Custom", hint: "Operator opisuje własny pomysł." },
];

const API_SHORTCUT_PROVIDERS = [
  { id: "openai", label: "OpenAI" },
  { id: "anthropic", label: "Anthropic" },
  { id: "perplexity", label: "Perplexity" },
  { id: "google", label: "Google" },
  { id: "zai", label: "Z.ai" },
  { id: "openrouter", label: "OpenRouter" },
  { id: "moonshot", label: "Kimi / Moonshot" },
  { id: "deepseek", label: "DeepSeek" },
  { id: "xai", label: "xAI" },
  { id: "mistral", label: "Mistral" },
  { id: "groq", label: "Groq" },
  { id: "cohere", label: "Cohere" },
  { id: "fireworks", label: "Fireworks" },
  { id: "together", label: "Together" },
];

type Phase1Values = Record<string, unknown> & {
  language?: "pl" | "en";
  operator_name?: string;
  display_name?: string;
  system_name?: string;
  operator_email?: string;
  email_skipped?: boolean;
  operator_role?: string;
  timezone?: string;
  timezone_confirmed?: boolean;
  workspace_path?: string;
  backup_frequency?: "daily" | "weekly" | "manual";
  backup_retention_days?: number | "forever";
  storage_validation?: Phase1StorageValidation;
  security_mode?: "password" | "low_security";
  master_password_configured?: boolean;
  low_security_confirm?: string;
  goals?: string[];
  goals_decide_later?: boolean;
  initial_autonomy_preset?: string;
  notification_channel?: "in_app";
  telemetry_consent?: boolean;
  tutorial_mode?: "quick" | "standard" | "full" | "skip";
  tutorial_project?: string;
  api_keys?: Array<Record<string, unknown>>;
  phase1_api_provider?: string;
  demo_mode_accepted?: boolean;
  phase1_model_gate?: Phase1ModelGate;
};

function asValues(values: Record<string, unknown>): Phase1Values {
  return values as Phase1Values;
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function systemNameFromDisplay(value: string): string {
  const cleaned = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9.]+/g, ".")
    .replace(/\.+/g, ".")
    .replace(/^\.+|\.+$/g, "")
    .slice(0, 32);
  return cleaned || "operator";
}

function isEmailValid(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function isMaskedSecret(value: unknown): boolean {
  if (typeof value !== "string") return false;
  const textValue = value.trim();
  return !textValue || textValue === "***" || textValue.includes("...");
}

function hasPhase1ApiShortcut(values: Phase1Values): boolean {
  const rows = Array.isArray(values.api_keys) ? values.api_keys : [];
  return rows.some((row) => typeof row?.provider === "string" && !isMaskedSecret(row.key));
}

function warningLabel(code: string): string {
  const map: Record<string, string> = {
    cloud_synced_path: "Ścieżka wygląda na synchronizowaną z chmurą.",
    disk_space_below_5gb: "Mniej niż 5 GB wolnego miejsca.",
    write_speed_below_10mbps: "Zapis jest wolniejszy niż rekomendowane 10 MB/s.",
    workspace_parent_will_be_created: "Brakujące foldery workspace zostaną utworzone przy finalizacji.",
  };
  return map[code] ?? code;
}

function errorLabel(code: string): string {
  const map: Record<string, string> = {
    blocked_system_path: "Ścieżka systemowa jest zablokowana.",
    parent_missing: "Katalog nadrzędny nie istnieje.",
    parent_not_directory: "Katalog nadrzędny nie jest folderem.",
    disk_space_below_2gb: "Mniej niż 2 GB wolnego miejsca.",
    permission_denied: "Brak uprawnień zapisu.",
    sqlite_readback_failed: "Test SQLite nie przeszedł.",
    workspace_path_is_file: "Podana ścieżka jest plikiem, nie folderem.",
  };
  return map[code] ?? code;
}

function Panel({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "ok" | "warn" | "danger" }) {
  return (
    <div
      className={cn(
        "rounded-md border px-4 py-3",
        tone === "default" && "border-border bg-muted/10",
        tone === "ok" && "border-sylion-green/35 bg-sylion-green/5",
        tone === "warn" && "border-sylion-amber/35 bg-sylion-amber/5",
        tone === "danger" && "border-destructive/40 bg-destructive/10",
      )}
    >
      {children}
    </div>
  );
}

function OptionButton({
  active,
  title,
  hint,
  onClick,
  testId,
}: {
  active: boolean;
  title: string;
  hint?: string;
  onClick: () => void;
  testId?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      data-active={active || undefined}
      className={cn(
        "w-full rounded-md border px-3 py-2 text-left transition",
        active ? "border-sylion-blue/60 bg-sylion-blue/10 text-sylion-blue" : "border-border hover:bg-muted/30",
      )}
    >
      <span className="block text-sm font-semibold">{title}</span>
      {hint ? <span className="mt-0.5 block text-xs text-muted-foreground">{hint}</span> : null}
    </button>
  );
}

function StepStart({
  values,
  systemCheck,
  loading,
  checkedAt,
  error,
  onRefresh,
  onChange,
}: {
  values: Phase1Values;
  systemCheck: Phase1SystemCheck | null;
  loading: boolean;
  checkedAt: number | null;
  error: string | null;
  onRefresh: () => void;
  onChange: (patch: Partial<Phase1Values>) => void;
}) {
  return (
    <div className="space-y-4">
      <Panel>
        <div className="flex items-start gap-3">
          <Sparkles className="mt-0.5 h-5 w-5 text-sylion-blue" />
          <div>
            <p className="text-sm font-semibold">Faza 1 przygotowuje operatora i maszynę.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Ten flow nie dodaje pełnego katalogu providerów, nie ustawia budżetów projektu i nie tworzy pierwszego projektu.
              Te kroki są dostępne po zakończeniu Fazy 1.
            </p>
          </div>
        </div>
      </Panel>

      <div className="grid gap-3 md:grid-cols-2">
        <Panel tone={systemCheck?.status === "ok" ? "ok" : "warn"}>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <HardDrive className="h-4 w-4" />
              System check
            </div>
            <Button type="button" variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
              <RefreshCw className={cn("mr-1 h-3.5 w-3.5", loading && "animate-spin")} />
              {checkedAt ? "Sprawdź ponownie" : "Sprawdź"}
            </Button>
          </div>
          <div className="mt-3 space-y-1 text-xs text-muted-foreground">
            <p>Backend: {systemCheck?.backend.health ?? "sprawdźam"}</p>
            <p>Dysk: {systemCheck?.disk.free_gb ?? "?"} GB wolne</p>
            <p>Modele lokalne: {systemCheck?.local_models.count ?? 0}</p>
            <p>Workspace default: <code>{systemCheck?.workspace_default ?? "..."}</code></p>
            {checkedAt ? <p>Ostatni check: {new Date(checkedAt).toLocaleTimeString()}</p> : null}
            {error ? <p className="text-destructive">Błąd: {error}</p> : null}
            <p>RAM/GPU: wykrywanie pełne w Tauri, web dev pokazuje stan techniczny.</p>
          </div>
        </Panel>

        <Panel>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Languages className="h-4 w-4" />
            Język UI
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <OptionButton
              active={(values.language ?? "pl") === "pl"}
              title="Polski"
              onClick={() => onChange({ language: "pl" })}
              testId="phase1-language-pl"
            />
            <OptionButton
              active={values.language === "en"}
              title="English"
              onClick={() => onChange({ language: "en" })}
              testId="phase1-language-en"
            />
          </div>
        </Panel>
      </div>
    </div>
  );
}

function StepIdentity({ values, onChange }: { values: Phase1Values; onChange: (patch: Partial<Phase1Values>) => void }) {
  const display = text(values.operator_name);
  const systemName = text(values.system_name);
  return (
    <div className="space-y-4">
      <Panel>
        <div className="flex items-start gap-3">
          <UserCircle className="mt-0.5 h-5 w-5 text-sylion-blue" />
          <div>
            <p className="text-sm font-semibold">Tożsamość trafia do UI, raportów i audit chain.</p>
            <p className="mt-1 text-xs text-muted-foreground">System name jest technicznym identyfikatorem workspace i powinien być stabilny.</p>
          </div>
        </div>
      </Panel>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
          Display name
          <input
            value={display}
            onChange={(e) => {
              const next = e.target.value;
              onChange({
                operator_name: next,
                display_name: next,
                system_name: values.system_name ? values.system_name : systemNameFromDisplay(next),
              });
            }}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
            data-testid="phase1-display-name"
          />
        </label>
        <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
          System name
          <input
            value={systemName}
            onChange={(e) => onChange({ system_name: e.target.value.toLowerCase() })}
            placeholder="operator"
            className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
            data-testid="phase1-system-name"
          />
          <span className="block text-[11px] normal-case text-muted-foreground">Regex: ^[a-z0-9.]+$, 1-32 znaki.</span>
        </label>
      </div>

      <div className="grid gap-3 md:grid-cols-[1fr_auto]">
        <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
          Email
          <input
            value={text(values.operator_email)}
            disabled={Boolean(values.email_skipped)}
            onChange={(e) => onChange({ operator_email: e.target.value, email_skipped: false })}
            placeholder="operator@example.com"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60 disabled:opacity-50"
            data-testid="phase1-email"
          />
        </label>
        <label className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={Boolean(values.email_skipped)}
            onChange={(e) => onChange({ email_skipped: e.target.checked, operator_email: e.target.checked ? "" : values.operator_email })}
            data-testid="phase1-email-skip"
          />
          Pomiń email
        </label>
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        {ROLES.map((role) => (
          <OptionButton
            key={role.id}
            active={values.operator_role === role.id}
            title={role.label}
            hint={role.hint}
            onClick={() => onChange({ operator_role: role.id })}
            testId={`phase1-role-${role.id}`}
          />
        ))}
      </div>

      <Panel>
        <div className="grid gap-3 md:grid-cols-[1fr_auto]">
          <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
            Time zone
            <input
              value={text(values.timezone) || "Europe/Warsaw"}
              onChange={(e) => onChange({ timezone: e.target.value, timezone_confirmed: false })}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
              data-testid="phase1-timezone"
            />
          </label>
          <label className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={Boolean(values.timezone_confirmed)}
              onChange={(e) => onChange({ timezone_confirmed: e.target.checked, timezone: values.timezone || "Europe/Warsaw" })}
              data-testid="phase1-timezone-confirm"
            />
            Potwierdzam
          </label>
        </div>
      </Panel>
    </div>
  );
}

function StepStorage({
  values,
  validating,
  onValidate,
  onChange,
}: {
  values: Phase1Values;
  validating: boolean;
  onValidate: () => void;
  onChange: (patch: Partial<Phase1Values>) => void;
}) {
  const validation = values.storage_validation;
  return (
    <div className="space-y-4">
      <Panel>
        <div className="flex items-start gap-3">
          <Database className="mt-0.5 h-5 w-5 text-sylion-blue" />
          <div>
            <p className="text-sm font-semibold">Workspace zawiera projekty, audit chain, artefakty, logi i backupy.</p>
            <p className="mt-1 text-xs text-muted-foreground">Domyślnie: ~/.sylion/&lt;system-name&gt;/. Unikaj OneDrive/Dropbox i dysków sieciowych.</p>
          </div>
        </div>
      </Panel>

      <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
        Ścieżka workspace
        <div className="flex gap-2">
          <input
            value={text(values.workspace_path)}
            onChange={(e) => onChange({ workspace_path: e.target.value, storage_validation: undefined })}
            placeholder={`~/.sylion/${text(values.system_name) || "operator"}`}
            className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
            data-testid="phase1-workspace-path"
          />
          <Button type="button" variant="outline" onClick={onValidate} disabled={validating} data-testid="phase1-validate-storage">
            <RefreshCw className={cn("mr-1 h-3.5 w-3.5", validating && "animate-spin")} />
            Waliduj
          </Button>
        </div>
      </label>

      {validation ? (
        <Panel tone={validation.ok ? "ok" : "danger"}>
          <div className="flex items-center gap-2 text-sm font-semibold">
            {validation.ok ? <CheckCircle2 className="h-4 w-4 text-sylion-green" /> : <AlertTriangle className="h-4 w-4 text-destructive" />}
            {validation.ok ? "Storage gotowy" : "Storage wymaga poprawy"}
          </div>
          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
            <p>Path: <code>{validation.path}</code></p>
            <p>Free: {validation.free_gb ?? "?"} GB, write: {validation.write_mbps ?? "?"} MB/s, SQLite: {validation.sqlite_ok ? "OK" : "NIE"}</p>
            {validation.warnings.map((item) => <p key={item}>Ostrzeżenie: {warningLabel(item)}</p>)}
            {validation.errors.map((item) => <p key={item} className="text-destructive">Błąd: {errorLabel(item)}</p>)}
            {validation.probe_path && validation.probe_path !== validation.path ? <p>Probe: <code>{validation.probe_path}</code></p> : null}
          </div>
        </Panel>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
          Backup frequency
          <select
            value={text(values.backup_frequency) || "daily"}
            onChange={(e) => onChange({ backup_frequency: e.target.value as Phase1Values["backup_frequency"] })}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
            data-testid="phase1-backup-frequency"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="manual">Manual only</option>
          </select>
        </label>
        <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
          Retention
          <select
            value={String(values.backup_retention_days ?? 30)}
            onChange={(e) => onChange({ backup_retention_days: e.target.value === "forever" ? "forever" : Number(e.target.value) })}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
            data-testid="phase1-backup-retention"
          >
            <option value="7">7 dni</option>
            <option value="30">30 dni</option>
            <option value="90">90 dni</option>
            <option value="365">365 dni</option>
            <option value="forever">forever</option>
          </select>
        </label>
      </div>
    </div>
  );
}

function StepSecurity({ values, onChange }: { values: Phase1Values; onChange: (patch: Partial<Phase1Values>) => void }) {
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [showSeed, setShowSeed] = useState(false);
  const strongEnough = password.length >= 12 && /[A-Z]/.test(password) && /\d/.test(password);
  const passwordOk = strongEnough && password === repeat;
  return (
    <div className="space-y-4">
      <Panel>
        <div className="flex items-start gap-3">
          <KeyRound className="mt-0.5 h-5 w-5 text-sylion-blue" />
          <div>
            <p className="text-sm font-semibold">Faza 1 nie zapisuje raw password w localStorage ani preferences.</p>
            <p className="mt-1 text-xs text-muted-foreground">Po walidacji zapisujemy tylko fakt konfiguracji. Low-security mode wymaga jawnego potwierdzenia.</p>
          </div>
        </div>
      </Panel>

      <div className="grid gap-2 md:grid-cols-2">
        <OptionButton
          active={values.security_mode === "password"}
          title="Ustaw master password"
          hint="Rekomendowane. Wymaga hasła min. 12 znaków i potwierdzenia recovery seed."
          onClick={() => onChange({ security_mode: "password", low_security_confirm: "" })}
          testId="phase1-security-password"
        />
        <OptionButton
          active={values.security_mode === "low_security"}
          title="Pomiń świadomie"
          hint="Low-security mode. Sekrety wymagają późniejszego ustawieńia ochrony."
          onClick={() => onChange({ security_mode: "low_security", master_password_configured: false })}
          testId="phase1-security-low"
        />
      </div>

      {values.security_mode === "password" ? (
        <Panel tone={values.master_password_configured ? "ok" : "default"}>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  onChange({ master_password_configured: false });
                }}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
                data-testid="phase1-master-password"
              />
            </label>
            <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
              Powtórz
              <input
                type="password"
                value={repeat}
                onChange={(e) => {
                  setRepeat(e.target.value);
                  onChange({ master_password_configured: false });
                }}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
                data-testid="phase1-master-password-repeat"
              />
            </label>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>Min 12 znaków: {password.length >= 12 ? "OK" : "NIE"}</span>
            <span>Wielka litera: {/[A-Z]/.test(password) ? "OK" : "NIE"}</span>
            <span>Cyfra: {/\d/.test(password) ? "OK" : "NIE"}</span>
            <span>Zgodność: {password && password === repeat ? "OK" : "NIE"}</span>
          </div>
          <div className="mt-3 flex gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={!passwordOk}
              onClick={() => setShowSeed(true)}
              data-testid="phase1-generate-seed"
            >
              Pokaż recovery verification
            </Button>
            <Button
              type="button"
              disabled={!passwordOk || !showSeed}
              onClick={() => onChange({ master_password_configured: true })}
              data-testid="phase1-confirm-password"
            >
              Potwierdzam zapis seed
            </Button>
          </div>
          {showSeed ? (
            <div className="mt-3 rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
              Recovery seed w produkcyjnym Tauri powinien być generowany natywnie i zapisywany tylko przez operatora.
              W tym web flow potwierdzasz, że zapis recovery został wykonany poza localStorage.
            </div>
          ) : null}
        </Panel>
      ) : null}

      {values.security_mode === "low_security" ? (
        <Panel tone="warn">
          <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
            Wpisz ROZUMIEM
            <input
              value={text(values.low_security_confirm)}
              onChange={(e) => onChange({ low_security_confirm: e.target.value })}
              className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
              data-testid="phase1-low-security-confirm"
            />
          </label>
        </Panel>
      ) : null}
    </div>
  );
}

function StepProfile({ values, onChange }: { values: Phase1Values; onChange: (patch: Partial<Phase1Values>) => void }) {
  const goals = values.goals ?? [];
  const toggleGoal = (id: string) => {
    const next = goals.includes(id) ? goals.filter((goal) => goal !== id) : [...goals, id].slice(0, 3);
    onChange({ goals: next, goals_decide_later: false });
  };
  return (
    <div className="space-y-4">
      <Panel>
        <p className="text-sm font-semibold">Wybierz 1-3 typy projektów lub odłóż decyzję.</p>
        <p className="mt-1 text-xs text-muted-foreground">Te wybory tworzą draft defaults dla późniejszych faz, ale nie konfigurują jeszcze council, budżetów ani providerów.</p>
      </Panel>
      <div className="grid gap-2 md:grid-cols-2">
        {GOALS.map((goal) => (
          <OptionButton
            key={goal.id}
            active={goals.includes(goal.id)}
            title={goal.label}
            hint={goal.hint}
            onClick={() => toggleGoal(goal.id)}
            testId={`phase1-goal-${goal.id}`}
          />
        ))}
        <OptionButton
          active={Boolean(values.goals_decide_later)}
          title="Decide later"
          hint="Przejdź dalej bez wyboru kategorii projektów."
          onClick={() => onChange({ goals: [], goals_decide_later: true })}
          testId="phase1-goals-later"
        />
      </div>
      <div className="grid gap-2 md:grid-cols-3">
        {AUTONOMY_PRESETS.map((preset) => (
          <OptionButton
            key={preset.id}
            active={values.initial_autonomy_preset === preset.id}
            title={preset.label}
            hint={preset.hint}
            onClick={() => onChange({ initial_autonomy_preset: preset.id })}
            testId={`phase1-autonomy-${preset.id}`}
          />
        ))}
      </div>
      <Panel>
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={values.telemetry_consent === true}
            onChange={(e) => onChange({ telemetry_consent: e.target.checked, notification_channel: "in_app" })}
            data-testid="phase1-telemetry"
          />
          Włącz anonimową telemetrię. Domyślnie OFF.
        </label>
      </Panel>
    </div>
  );
}

function StepTutorial({ values, onChange }: { values: Phase1Values; onChange: (patch: Partial<Phase1Values>) => void }) {
  const mode = values.tutorial_mode;
  return (
    <div className="space-y-4">
      <div className="grid gap-2 md:grid-cols-4">
        <OptionButton active={mode === "quick"} title="Quick" hint="15-20 min, lokalny sandbox." onClick={() => onChange({ tutorial_mode: "quick", tutorial_project: values.tutorial_project === "tailor_lite" || values.tutorial_project === "custom" ? "personal_knowledge_base" : values.tutorial_project })} testId="phase1-tutorial-quick" />
        <OptionButton active={mode === "standard"} title="Standard" hint="45-60 min, pełniejszy workflow." onClick={() => onChange({ tutorial_mode: "standard" })} testId="phase1-tutorial-standard" />
        <OptionButton active={mode === "full"} title="Full" hint="2-4h, real build bez deploy bez Human Gate." onClick={() => onChange({ tutorial_mode: "full" })} testId="phase1-tutorial-full" />
        <OptionButton active={mode === "skip"} title="Skip" hint="Pomiń tutorial, wrócisz później." onClick={() => onChange({ tutorial_mode: "skip", tutorial_project: "" })} testId="phase1-tutorial-skip" />
      </div>

      {mode && mode !== "skip" ? (
        <div className="grid gap-2 md:grid-cols-2">
          {TUTORIAL_PROJECTS.map((project) => {
            const disabled = mode === "quick" && (project.id === "tailor_lite" || project.id === "custom");
            return (
              <button
                key={project.id}
                type="button"
                disabled={disabled}
                onClick={() => onChange({ tutorial_project: project.id })}
                data-testid={`phase1-tutorial-project-${project.id}`}
                className={cn(
                  "rounded-md border px-3 py-2 text-left transition",
                  values.tutorial_project === project.id ? "border-sylion-blue/60 bg-sylion-blue/10 text-sylion-blue" : "border-border hover:bg-muted/30",
                  disabled && "cursor-not-allowed opacity-45",
                )}
              >
                <span className="block text-sm font-semibold">{project.label}</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">{disabled ? "Niedostępne dla Quick." : project.hint}</span>
              </button>
            );
          })}
        </div>
      ) : (
        <Panel tone="warn">
          <p className="text-sm font-semibold">Tutorial pominięty.</p>
          <p className="mt-1 text-xs text-muted-foreground">System zapisze możliwość powrotu przez Help / Settings.</p>
        </Panel>
      )}
    </div>
  );
}

function StepModelGate({
  values,
  gate,
  loading,
  onRefresh,
  onTest,
  onChange,
}: {
  values: Phase1Values;
  gate: Phase1ModelGate | null;
  loading: boolean;
  onRefresh: () => void;
  onTest: () => void;
  onChange: (patch: Partial<Phase1Values>) => void;
}) {
  const effective = gate ?? values.phase1_model_gate;
  const models = effective?.local_probe?.models ?? [];
  const [shortcutProvider, setShortcutProvider] = useState(text(values.phase1_api_provider) || "openai");
  const [shortcutKey, setShortcutKey] = useState("");
  const apiRows = Array.isArray(values.api_keys) ? values.api_keys : [];
  const hasShortcut = Boolean(effective?.has_api_key || hasPhase1ApiShortcut(values));
  const gatePassed = Boolean(effective?.passed || hasShortcut || values.demo_mode_accepted);
  const applyApiShortcut = () => {
    const key = shortcutKey.trim();
    if (!key) return;
    const nextRows = apiRows.filter((row) => row?.id !== "phase1-shortcut");
    onChange({
      phase1_api_provider: shortcutProvider,
      api_keys: [
        ...nextRows,
        {
          id: "phase1-shortcut",
          provider: shortcutProvider,
          key,
          validation_status: "phase1_shortcut",
        },
      ],
    });
    setShortcutKey("");
  };
  return (
    <div className="space-y-4">
      <Panel tone={gatePassed ? "ok" : "warn"}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 h-5 w-5 text-sylion-green" />
            <div>
              <p className="text-sm font-semibold">Hard gate P1.20: minimum 1 model lokalny, API shortcut albo demo mode.</p>
              <p className="mt-1 text-xs text-muted-foreground">Pełne API keys są w Fazie 2. Faza 1 używa tylko detekcji lokalnej lub jawnego demo mode.</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
              <RefreshCw className={cn("mr-1 h-3.5 w-3.5", loading && "animate-spin")} />
              Re-scan
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={onTest} disabled={loading || models.length === 0}>
              <PlayCircle className="mr-1 h-3.5 w-3.5" />
              Test
            </Button>
          </div>
        </div>
      </Panel>

      <div className="grid gap-3 md:grid-cols-3">
        <Panel tone={effective?.local_model_count ? "ok" : "default"}>
          <p className="text-xs uppercase text-muted-foreground">Modele lokalne</p>
          <p className="mt-1 text-2xl font-semibold">{effective?.local_model_count ?? 0}</p>
        </Panel>
        <Panel tone={hasShortcut ? "ok" : "default"}>
          <p className="text-xs uppercase text-muted-foreground">API shortcut</p>
          <p className="mt-1 text-2xl font-semibold">{hasShortcut ? "OK" : "0"}</p>
        </Panel>
        <Panel tone={values.demo_mode_accepted ? "warn" : "default"}>
          <p className="text-xs uppercase text-muted-foreground">Demo mode</p>
          <p className="mt-1 text-2xl font-semibold">{values.demo_mode_accepted ? "ON" : "OFF"}</p>
        </Panel>
      </div>

      <Panel tone={hasShortcut ? "ok" : "default"}>
        <div className="grid gap-3 md:grid-cols-[160px_1fr_auto]">
          <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
            Provider
            <select
              value={shortcutProvider}
              onChange={(event) => {
                setShortcutProvider(event.target.value);
                onChange({ phase1_api_provider: event.target.value });
              }}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
              data-testid="phase1-api-provider"
            >
              {API_SHORTCUT_PROVIDERS.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1.5 text-xs font-semibold uppercase text-muted-foreground">
            API shortcut key
            <input
              type="password"
              value={shortcutKey}
              onChange={(event) => setShortcutKey(event.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm normal-case text-foreground outline-none focus:border-sylion-blue/60"
              data-testid="phase1-api-key"
            />
          </label>
          <Button
            type="button"
            variant="outline"
            className="self-end"
            disabled={!shortcutKey.trim()}
            onClick={applyApiShortcut}
            data-testid="phase1-api-shortcut-save"
          >
            Użyj
          </Button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Ten skrót służy wyłącznie do przejścia hard gate w Fazie 1. Pełna konfiguracja providerów jest w Fazie 2.
        </p>
      </Panel>

      {models.length > 0 ? (
        <div className="max-h-44 overflow-auto rounded-md border border-border">
          {models.slice(0, 12).map((model, index) => (
            <div key={`${String(model.name)}-${index}`} className="flex items-center justify-between border-b border-border/60 px-3 py-2 text-xs last:border-b-0">
              <span className="font-mono">{String(model.name ?? "(bez nazwy)")}</span>
              <span className="text-muted-foreground">{String(model.size_gb ?? "?")} GB</span>
            </div>
          ))}
        </div>
      ) : (
        <Panel tone="warn">
          <p className="text-sm font-semibold">Nie wykryto modelu lokalnego.</p>
          <p className="mt-1 text-xs text-muted-foreground">Zainstaluj Ollama/LM Studio i uruchom re-scan albo kontynuuj w demo mode tylko do nauki.</p>
          <label className="mt-3 flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={Boolean(values.demo_mode_accepted)}
              onChange={(e) => onChange({ demo_mode_accepted: e.target.checked })}
              data-testid="phase1-demo-mode"
            />
            Rozumiem, że demo mode jest tylko do nauki, bez prawdziwych artefaktów.
          </label>
        </Panel>
      )}

      {effective?.local_probe?.functional_check ? (
        <Panel>
          <p className="text-xs uppercase text-muted-foreground">Functional check</p>
          <pre className="mt-2 overflow-auto text-[11px] text-muted-foreground">{JSON.stringify(effective.local_probe.functional_check, null, 2)}</pre>
        </Panel>
      ) : null}
    </div>
  );
}

function StepReady({ values, acceptance }: { values: Phase1Values; acceptance: Phase1AcceptanceReport | null }) {
  return (
    <div className="space-y-4">
      <Panel>
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-5 w-5 text-sylion-green" />
          <div>
            <p className="text-sm font-semibold">Faza 1 zapisze operator-level setup i zainicjuje workspace.</p>
            <p className="mt-1 text-xs text-muted-foreground">Po kliknięciu końca backend uruchomi acceptance checks, utworzy 15 folderów workspace i zapisze audit chain.</p>
          </div>
        </div>
      </Panel>
      <div className="grid gap-2 text-xs md:grid-cols-2">
        <Panel><b>Operator:</b> {text(values.operator_name)}</Panel>
        <Panel><b>System:</b> <code>{text(values.system_name)}</code></Panel>
        <Panel><b>Workspace:</b> <code>{text(values.workspace_path) || "(default)"}</code></Panel>
        <Panel><b>Tutorial:</b> {text(values.tutorial_mode) || "(brak)"}</Panel>
      </div>
      {acceptance ? (
        <Panel tone={acceptance.accepted ? "ok" : "warn"}>
          <p className="text-sm font-semibold">Acceptance: {acceptance.passed}/{acceptance.total}</p>
          <div className="mt-2 grid gap-1 text-xs">
            {acceptance.checks.map((check) => (
              <div key={check.key} className="flex items-center gap-2">
                {check.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-sylion-green" /> : <AlertTriangle className="h-3.5 w-3.5 text-sylion-amber" />}
                <span>{check.label}</span>
              </div>
            ))}
          </div>
        </Panel>
      ) : null}
    </div>
  );
}

function Phase1CompleteScreen({ state }: { state: ReturnType<typeof useOnboarding>["state"] }) {
  const values = asValues(state.values);
  const report = state.phase1_acceptance;
  return (
    <div className="mx-auto flex min-h-[80vh] w-full max-w-5xl flex-col gap-6 px-6 py-10">
      <Panel tone="ok">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-1 h-6 w-6 text-sylion-green" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Faza 1 zakończona</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Workspace operatora jest gotowy. Następny zalecany krok to Faza 2, a power user może od razu przejść do pierwszego projektu.
            </p>
          </div>
        </div>
      </Panel>
      <div className="grid gap-3 md:grid-cols-3">
        <Panel><p className="text-xs uppercase text-muted-foreground">Operator</p><p className="mt-1 font-semibold">{text(values.operator_name)}</p></Panel>
        <Panel><p className="text-xs uppercase text-muted-foreground">Workspace</p><p className="mt-1 break-all font-mono text-xs">{text(values.workspace_path)}</p></Panel>
        <Panel><p className="text-xs uppercase text-muted-foreground">Acceptance</p><p className="mt-1 font-semibold">{report ? `${report.passed}/${report.total}` : "zapisane"}</p></Panel>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Link href="/ai-models" className="rounded-md border border-sylion-blue/40 bg-sylion-blue/10 px-4 py-4 text-sm transition hover:bg-sylion-blue/15">
          <span className="block font-semibold">Faza 2: Provider Catalog Configuration</span>
          <span className="mt-1 block text-xs text-muted-foreground">Dodaj API keys, katalog modeli, routing i providerów.</span>
        </Link>
        <Link href="/projects" className="rounded-md border border-border bg-muted/10 px-4 py-4 text-sm transition hover:bg-muted/20">
          <span className="block font-semibold">Rozpocznij pierwszy projekt</span>
          <span className="mt-1 block text-xs text-muted-foreground">Przejdź do Fazy 16 używając minimalnego setupu i lokalnych modeli.</span>
        </Link>
      </div>
      <div className="flex gap-2">
        <Link href="/settings/profile" className="rounded-md border border-border px-3 py-2 text-xs hover:bg-muted/20">Settings</Link>
        <Link href="/advisor/cockpit" className="rounded-md border border-border px-3 py-2 text-xs hover:bg-muted/20">Advisor cockpit</Link>
      </div>
    </div>
  );
}

export function canAdvanceReason(step: number, values: Phase1Values, gate?: Phase1ModelGate | null): string | null {
  switch (step) {
    case 1:
      return values.language ? null : "Wybierz język UI.";
    case 2: {
      const display = text(values.operator_name).trim();
      const systemName = text(values.system_name).trim();
      if (!display || display.length > 64) return "Podaj display name 1-64 znaków.";
      if (!/^[a-z0-9.]{1,32}$/.test(systemName)) return "System name musi pasować do ^[a-z0-9.]+$ i mieć 1-32 znaki.";
      if (["admin", "root", "system", "aeis"].includes(systemName)) return "System name jest zarezerwowany.";
      if (!values.email_skipped && !isEmailValid(text(values.operator_email))) return "Podaj poprawny email albo zaznacz pominięcie email.";
      if (!values.operator_role) return "Wybierz rolę operatora.";
      if (!values.timezone_confirmed) return "Potwierdź strefę czasu.";
      return null;
    }
    case 3:
      if (!values.storage_validation?.ok) return "Zweryfikuj storage i popraw błędy ścieżki.";
      if (!values.backup_frequency) return "Wybierz częstotliwość backupu.";
      if (!values.backup_retention_days) return "Wybierz retention backupu.";
      return null;
    case 4:
      if (values.security_mode === "password" && values.master_password_configured) return null;
      if (values.security_mode === "low_security" && text(values.low_security_confirm).trim().toUpperCase() === "ROZUMIEM") return null;
      return "Ustaw master password albo świadomie potwierdź low-security mode.";
    case 5:
      if (!values.goals_decide_later && ((values.goals ?? []).length < 1 || (values.goals ?? []).length > 3)) return "Wybierz 1-3 cele albo Decide later.";
      if (!values.initial_autonomy_preset) return "Wybierz startowy autonomy preset.";
      return null;
    case 6:
      if (!values.tutorial_mode) return "Wybierz tryb tutorialu.";
      if (values.tutorial_mode !== "skip" && !values.tutorial_project) return "Wybierz projekt tutorialu.";
      if (values.tutorial_mode === "quick" && ["tailor_lite", "custom"].includes(text(values.tutorial_project))) return "Ta kombinacja tutorialu jest zablokowana.";
      return null;
    case 7: {
      const effective = gate ?? values.phase1_model_gate;
      return effective?.passed || hasPhase1ApiShortcut(values) || values.demo_mode_accepted
        ? null
        : "Hard gate wymaga lokalnego modelu, API shortcut albo jawnego demo mode.";
    }
    case 8:
      return null;
    default:
      return null;
  }
}

export default function OnboardingPage() {
  const { state, saveStep, completePhase1, reset } = useOnboarding();
  const [current, setCurrent] = useState<number>(() => state.step || 1);
  const [mounted, setMounted] = useState(false);
  const initialStepSynced = useRef(false);
  const values = asValues(state.values);
  const [systemCheck, setSystemCheck] = useState<Phase1SystemCheck | null>(null);
  const [systemLoading, setSystemLoading] = useState(false);
  const [systemCheckedAt, setSystemCheckedAt] = useState<number | null>(null);
  const [systemError, setSystemError] = useState<string | null>(null);
  const [storageValidating, setStorageValidating] = useState(false);
  const [modelGate, setModelGate] = useState<Phase1ModelGate | null>(null);
  const [modelLoading, setModelLoading] = useState(false);
  const [acceptance, setAcceptance] = useState<Phase1AcceptanceReport | null>(state.phase1_acceptance ?? null);
  const [completeError, setCompleteError] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);

  useEffect(() => {
    queueMicrotask(() => setMounted(true));
  }, []);

  useEffect(() => {
    if (initialStepSynced.current) return;
    if (!state.step || state.step <= 1) return;
    initialStepSynced.current = true;
    queueMicrotask(() => setCurrent(Math.min(Math.max(state.step, 1), PHASE1_STEPS.length)));
  }, [state.step]);

  const onChange = useCallback(
    (patch: Partial<Phase1Values>) => {
      void saveStep(current, patch as Record<string, unknown>);
    },
    [current, saveStep],
  );

  const loadSystemCheck = useCallback(async () => {
    setSystemLoading(true);
    setSystemError(null);
    try {
      const next = await advisorApi.phase1SystemCheck();
      setSystemCheck(next);
      setSystemCheckedAt(Date.now());
      if (!values.workspace_path && next.workspace_default) {
        onChange({ workspace_path: next.workspace_default, language: values.language ?? "pl", timezone: values.timezone ?? "Europe/Warsaw" });
      }
    } catch (error) {
      setSystemCheck(null);
      setSystemError(error instanceof Error ? error.message : String(error));
      setSystemCheckedAt(Date.now());
    } finally {
      setSystemLoading(false);
    }
  }, [onChange, values.language, values.timezone, values.workspace_path]);

  const loadModelGate = useCallback(async (runTest = false) => {
    setModelLoading(true);
    try {
      const next = await advisorApi.phase1ModelGate(runTest);
      setModelGate(next);
      onChange({ phase1_model_gate: next });
    } catch {
      setModelGate(null);
    } finally {
      setModelLoading(false);
    }
  }, [onChange]);

  useEffect(() => {
    if (!mounted) return;
    queueMicrotask(() => {
      void loadSystemCheck();
      void loadModelGate(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("reset") !== "1") return;
    queueMicrotask(() => {
      reset();
      setCurrent(1);
      setAcceptance(null);
      setModelGate(null);
      window.history.replaceState(null, "", "/onboarding");
    });
  }, [reset]);

  const validateStorage = useCallback(async () => {
    setStorageValidating(true);
    try {
      const path = text(values.workspace_path) || systemCheck?.workspace_default || "";
      const validation = await advisorApi.validatePhase1Storage(path);
      onChange({
        workspace_path: validation.path,
        storage_validation: validation,
        backup_frequency: values.backup_frequency ?? "daily",
        backup_retention_days: values.backup_retention_days ?? 30,
      });
    } finally {
      setStorageValidating(false);
    }
  }, [onChange, systemCheck?.workspace_default, values.backup_frequency, values.backup_retention_days, values.workspace_path]);

  const blockingReason = canAdvanceReason(current, values, modelGate);
  const canAdvance = !blockingReason && !completing;

  const goNext = useCallback(() => {
    setCurrent((step) => {
      const next = Math.min(step + 1, PHASE1_STEPS.length);
      window.setTimeout(() => void saveStep(next, {}), 0);
      return next;
    });
  }, [saveStep]);

  const goPrev = useCallback(() => setCurrent((step) => Math.max(step - 1, 1)), []);
  const onStepChange = useCallback((step: number) => {
    setCurrent(step);
    void saveStep(step, {});
  }, [saveStep]);

  const onComplete = useCallback(async () => {
    if (completing) return;
    setCompleting(true);
    setCompleteError(null);
    try {
      const completed = await completePhase1({
        ...values,
        language: values.language ?? "pl",
        timezone: values.timezone ?? "Europe/Warsaw",
        notification_channel: "in_app",
        telemetry_consent: Boolean(values.telemetry_consent),
      });
      setAcceptance(completed.phase1_acceptance ?? null);
      setCurrent(PHASE1_STEPS.length);
    } catch (error) {
      setCompleteError(error instanceof Error ? error.message : String(error));
    } finally {
      setCompleting(false);
    }
  }, [completePhase1, completing, values]);

  const stepContent = useMemo(() => {
    switch (current) {
      case 1:
        return <StepStart values={values} systemCheck={systemCheck} loading={systemLoading} checkedAt={systemCheckedAt} error={systemError} onRefresh={loadSystemCheck} onChange={onChange} />;
      case 2:
        return <StepIdentity values={values} onChange={onChange} />;
      case 3:
        return <StepStorage values={values} validating={storageValidating} onValidate={validateStorage} onChange={onChange} />;
      case 4:
        return <StepSecurity values={values} onChange={onChange} />;
      case 5:
        return <StepProfile values={values} onChange={onChange} />;
      case 6:
        return <StepTutorial values={values} onChange={onChange} />;
      case 7:
        return <StepModelGate values={values} gate={modelGate} loading={modelLoading} onRefresh={() => void loadModelGate(false)} onTest={() => void loadModelGate(true)} onChange={onChange} />;
      case 8:
        return <StepReady values={values} acceptance={acceptance ?? state.phase1_acceptance ?? null} />;
      default:
        return null;
    }
  }, [acceptance, current, loadModelGate, loadSystemCheck, modelGate, modelLoading, onChange, state.phase1_acceptance, storageValidating, systemCheck, systemCheckedAt, systemError, systemLoading, validateStorage, values]);

  if (!mounted) {
    return (
      <div data-testid="onboarding-wizard" data-step={current} className="px-6 py-10 text-sm text-muted-foreground">
        Ładowanie Fazy 1…
      </div>
    );
  }

  if (state.phase1_completed_at || state.completed_at) {
    return <Phase1CompleteScreen state={state} />;
  }

  return (
    <div data-testid="onboarding-wizard" data-step={current}>
      {completeError ? (
        <div
          data-testid="onboarding-complete-error"
          className="mx-auto mt-4 w-full max-w-4xl rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <Lock className="mr-1 inline h-4 w-4" />
          {completeError}
        </div>
      ) : null}
      <WizardShell
        steps={PHASE1_STEPS}
        current={current}
        maxReachable={Math.max(current, state.step || 1)}
        canAdvance={Boolean(canAdvance)}
        blockingReason={completing ? "Trwa finalizacja Fazy 1…" : blockingReason ?? undefined}
        onStepChange={onStepChange}
        onNext={goNext}
        onPrev={goPrev}
        onComplete={onComplete}
      >
        {stepContent}
      </WizardShell>
    </div>
  );
}
