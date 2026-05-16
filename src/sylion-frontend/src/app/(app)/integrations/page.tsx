"use client";

import { useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth, useApi } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import {
  Plug,
  RefreshCw,
  WifiOff,
  CheckCircle2,
  XCircle,
  Clock,
  Activity,
  Link2,
  Plus,
  AlertTriangle,
  Loader2,
  PlayCircle,
  Trash2,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Integration {
  integration_id?: string;
  id?: string;
  name: string;
  provider?: string;
  type?: string;
  scope?: string;
  status?: "healthy" | "unhealthy" | "unknown";
  last_test_at?: number;
  last_test_status?: string;
  registered_at?: number;
  description?: string;
}

interface IntegrationList {
  integrations: Integration[];
}

/* ============================================================
   FE-9.4 SaaS provider list
   ============================================================ */

const SAAS_PROVIDERS: { id: string; label: string }[] = [
  { id: "deepl", label: "DeepL Translation" },
  { id: "stripe", label: "Stripe Payments" },
  { id: "openai_api", label: "OpenAI API" },
  { id: "anthropic_api", label: "Anthropic API" },
  { id: "perplexity_api", label: "Perplexity API" },
  { id: "sendgrid", label: "SendGrid Email" },
  { id: "twilio", label: "Twilio SMS" },
  { id: "slack", label: "Slack Webhooks" },
  { id: "github", label: "GitHub" },
];

/* ============================================================
   Helpers
   ============================================================ */

function fmtDate(ts?: number): string {
  if (!ts) return "--";
  const d = new Date(ts);
  const now = Date.now();
  const diff = now - d.getTime();
  if (diff < 60_000) return "przed chwila";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m temu`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h temu`;
  return d.toLocaleDateString();
}

function healthBadge(status?: string): string {
  if (status === "healthy" || status === "ok") return "border-sylion-green/30 text-sylion-green bg-sylion-green/5";
  if (status === "unhealthy" || status === "failed") return "border-sylion-red/30 text-sylion-red bg-sylion-red/5";
  return "border-border/50 text-muted-foreground";
}

function healthDot(status?: string): string {
  if (status === "healthy" || status === "ok") return "bg-sylion-green";
  if (status === "unhealthy" || status === "failed") return "bg-sylion-red";
  return "bg-muted-foreground";
}

/* ============================================================
   Page Component
   ============================================================ */

export default function IntegrationsPage() {
  const { data: healthRaw, loading: healthLoading, refresh: refreshHealth } = useHealth();
  const backendLive = (healthRaw as any).status === "ok";

  const { data: integrationsRaw, loading: intLoading, refresh: refreshIntegrations } = useApi<IntegrationList>(
    () => api.listIntegrations(),
    { integrations: [] },
    15000
  );

  const loading = healthLoading || intLoading;
  const integrations: Integration[] = (integrationsRaw as IntegrationList).integrations || [];

  /* ---------- form state ---------- */
  const [form, setForm] = useState({
    provider: "deepl",
    name: "",
    scope: "global",
    credentials: '{\n  "api_key": "..."\n}',
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);
  const [credsError, setCredsError] = useState<string | null>(null);

  const handleRegister = useCallback(async () => {
    if (!form.name.trim()) return;
    setCredsError(null);
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(form.credentials);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        throw new Error("Wartosc musi byc obiektem JSON");
      }
    } catch (e) {
      setCredsError(`Niepoprawny JSON: ${e instanceof Error ? e.message : String(e)}`);
      return;
    }
    setBusy("register");
    setSubmitError(null);
    setSubmitSuccess(null);
    try {
      // FE-9.4: integracje SaaS używaj? tego samego endpointu /api/v1/connectors (BE-8)
      await api.registerConnector({
        provider: form.provider,
        name: form.name.trim(),
        scope: form.scope,
        credentials: parsed,
      });
      setSubmitSuccess(`Integracja "${form.name.trim()}" (${form.provider}) zostala zarejestrowana.`);
      setForm((f) => ({ ...f, name: "" }));
      refreshIntegrations();
      window.setTimeout(() => setSubmitSuccess(null), 4000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Nieznany błąd rejestracji";
      if (msg.includes("404")) {
        setSubmitError("Backend endpoint w przygotowaniu (BE-8). Sprobuj ponownie po wdrozeniu.");
      } else {
        setSubmitError(msg);
      }
    } finally {
      setBusy(null);
    }
  }, [form, refreshIntegrations]);

  const handleTest = useCallback(async (id: string) => {
    setBusy(`test-${id}`);
    setSubmitError(null);
    try {
      await api.testConnector(id);
      refreshIntegrations();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Test failed";
      setSubmitError(msg.includes("404") ? "Endpoint testu w przygotowaniu (BE-8)." : msg);
    } finally {
      setBusy(null);
    }
  }, [refreshIntegrations]);

  const handleDelete = useCallback(async (id: string) => {
    if (!confirm("Usunac te integracje?")) return;
    setBusy(`del-${id}`);
    setSubmitError(null);
    try {
      await api.deleteConnector(id);
      refreshIntegrations();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Delete failed";
      setSubmitError(msg.includes("404") ? "Endpoint usuwania w przygotowaniu (BE-8)." : msg);
    } finally {
      setBusy(null);
    }
  }, [refreshIntegrations]);

  /* ---------- Derived ---------- */
  const healthyCount = useMemo(
    () => integrations.filter((i) => i.status === "healthy" || i.last_test_status === "ok").length,
    [integrations]
  );
  const unhealthyCount = useMemo(
    () => integrations.filter((i) => i.status === "unhealthy" || i.last_test_status === "failed").length,
    [integrations]
  );

  /* ---------- Loading skeleton ---------- */
  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
          <div>
            <div className="h-6 w-36 bg-muted animate-pulse rounded" />
            <div className="h-4 w-52 bg-muted animate-pulse rounded mt-1" />
          </div>
        </div>
        <div className="h-64 bg-muted animate-pulse rounded-lg" />
      </div>
    );
  }

  /* ---------- Backend unreachable ---------- */
  if (!backendLive) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-red/10 border border-sylion-red/20 flex items-center justify-center">
            <Plug className="w-4 h-4 text-sylion-red" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Integracje
              <HelpTip text="Integracje z zewn?trznymi SaaS API (DeepL, Stripe, OpenAI itd.). Dla cloud providers (AWS/Hetzner) uzyj zak?adki Connectory." />
            </h1>
            <p className="text-sm text-muted-foreground">Polaczenia do zewnętrznych SaaS API</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Status integracji wymaga dzialajacego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => { refreshHealth(); refreshIntegrations(); }}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  /* ---------- Stats ---------- */
  const stats = [
    { label: "??cznie", value: integrations.length, icon: Link2, color: "text-sylion-blue", bgColor: "bg-sylion-blue/10" },
    { label: "Sprawne", value: healthyCount, icon: CheckCircle2, color: "text-sylion-green", bgColor: "bg-sylion-green/10" },
    {
      label: "Z bledami",
      value: unhealthyCount,
      icon: XCircle,
      color: unhealthyCount > 0 ? "text-sylion-red" : "text-muted-foreground",
      bgColor: unhealthyCount > 0 ? "bg-sylion-red/10" : "bg-muted/20",
    },
  ];

  return (
    <div className="space-y-5">
      {/* ====== HEADER ====== */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Plug className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Integracje
              <HelpTip text="Integracje z zewn?trznymi SaaS API (DeepL, Stripe, OpenAI itd.). Dla cloud providers (AWS/Hetzner) uzyj zak?adki Connectory. Backend wsp?lny: /api/v1/connectors." />
            </h1>
            <p className="text-sm text-muted-foreground">Polaczenia do zewnętrznych SaaS API</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => { refreshIntegrations(); refreshHealth(); }} data-testid="integrations-refresh">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Odśwież
        </Button>
      </div>

      {/* ====== FE-9.4 ADD INTEGRATION FORM ====== */}
      <Card className="p-4 bg-[#0f1629] border-sylion-border" data-testid="integrations-add-card">
        <div className="flex items-center gap-2 mb-3">
          <Plus className="w-3.5 h-3.5 text-sylion-blue" />
          <h3 className="text-xs font-medium uppercase tracking-wider">
            Dodaj now? integracj?
            <HelpTip text="Rejestruje now? integracj? SaaS. Credentials są zapisywane w vault sekret?w. Po rejestracji uzyj 'Test' aby zweryfikowac dostep." />
          </h3>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] text-muted-foreground mb-1 block">
              Provider
              <HelpTip text="Dostawca SaaS API. Wyb?r wp?ywa na schemat credentials (każdy provider ma sw?j zestaw kluczy)." />
            </label>
            <select
              data-testid="integrations-form-provider"
              value={form.provider}
              onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              disabled={busy === "register"}
            >
              {SAAS_PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground mb-1 block">
              Nazwa
              <HelpTip text="Czytelna nazwa integracji (np. deepl-prod, openai-shared). U?ywana w widokach operatora i logach." />
            </label>
            <input
              data-testid="integrations-form-name"
              placeholder="np. deepl-prod"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              disabled={busy === "register"}
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground mb-1 block">
              Zakres
              <HelpTip text="Zakres dostepnosci integracji: global (wszedzie), workspace (caly workspace), pipeline (jeden pipeline)." />
            </label>
            <select
              data-testid="integrations-form-scope"
              value={form.scope}
              onChange={(e) => setForm((f) => ({ ...f, scope: e.target.value }))}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              disabled={busy === "register"}
            >
              <option value="global">global</option>
              <option value="workspace">workspace</option>
              <option value="pipeline">pipeline</option>
            </select>
          </div>
        </div>
        <div className="mt-3">
          <label className="text-[10px] text-muted-foreground mb-1 block">
            Credentials (JSON)
            <HelpTip text="Klucze API i konfiguracja w formacie JSON. Caly obiekt zostanie zaszyfrowany. Typowo: api_key, secret, webhook_url." />
          </label>
          <textarea
            data-testid="integrations-form-credentials"
            value={form.credentials}
            onChange={(e) => { setForm((f) => ({ ...f, credentials: e.target.value })); setCredsError(null); }}
            rows={5}
            className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-xs shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 font-mono"
            disabled={busy === "register"}
            spellCheck={false}
          />
          {credsError && (
            <p className="mt-1 text-[10px] text-sylion-red flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> {credsError}
            </p>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 mt-3">
          <Button
            data-testid="integrations-form-submit"
            size="sm"
            onClick={handleRegister}
            disabled={busy === "register" || !form.name.trim()}
          >
            {busy === "register" ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
            Zarejestruj integracje
          </Button>
        </div>
        <AnimatePresence>
          {submitError && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-3 flex items-start gap-2 rounded-md border border-sylion-red/20 bg-sylion-red/5 p-2 text-xs text-sylion-red"
              data-testid="integrations-form-error"
            >
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5" />
              <span>{submitError}</span>
            </motion.div>
          )}
          {submitSuccess && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-3 flex items-start gap-2 rounded-md border border-sylion-green/20 bg-sylion-green/5 p-2 text-xs text-sylion-green"
              data-testid="integrations-form-success"
            >
              <CheckCircle2 className="w-3.5 h-3.5 mt-0.5" />
              <span>{submitSuccess}</span>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>

      {/* ====== STATS ROW ====== */}
      <div className="grid grid-cols-3 gap-3">
        {stats.map((stat) => {
          const SIcon = stat.icon;
          return (
            <motion.div key={stat.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
              <Card className="p-4 bg-[#0f1629] border-sylion-border card-hover">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{stat.label}</p>
                    <p className={cn("text-xl font-semibold mt-1 font-mono", stat.color)}>{stat.value}</p>
                  </div>
                  <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", stat.bgColor)}>
                    <SIcon className={cn("w-4 h-4", stat.color)} />
                  </div>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* ====== INTEGRATIONS TABLE ====== */}
      <Card className="bg-[#0f1629] border-sylion-border" data-testid="integrations-list">
        <div className="p-3 border-b border-border/30 flex items-center justify-between">
          <h3 className="text-xs font-medium text-muted-foreground">
            Zarejestrowane integracje
            <HelpTip text="Lista zarejestrowanych integracji SaaS. 'Test' weryfikuje dostep do API providera." />
          </h3>
          <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
            {integrations.length} ??cznie
          </span>
        </div>
        {integrations.length === 0 ? (
          <div className="p-8 text-center">
            <Plug className="w-6 h-6 text-muted-foreground mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">Brak zarejestrowanych integracji</p>
            <p className="text-[10px] text-muted-foreground/70 mt-1">Użyj formularza powyzej, aby doda? pierwsz? integracj?.</p>
          </div>
        ) : (
          <div className="divide-y divide-border/20">
            {integrations.map((intg, idx) => {
              const id = intg.integration_id || intg.id || String(idx);
              const status = intg.last_test_status || intg.status || "unknown";
              return (
                <div
                  key={id}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors"
                  data-testid={`integrations-row-${id}`}
                >
                  <span className={cn("w-2 h-2 rounded-full shrink-0", healthDot(status))} />
                  <span className="text-xs font-medium flex-1 min-w-0 truncate">{intg.name}</span>
                  {intg.provider && (
                    <Badge variant="outline" className="text-[9px] shrink-0 border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5">
                      {intg.provider}
                    </Badge>
                  )}
                  {intg.type && !intg.provider && (
                    <Badge variant="outline" className="text-[9px] shrink-0 border-border/50 text-muted-foreground">
                      {intg.type}
                    </Badge>
                  )}
                  {intg.scope && (
                    <Badge variant="outline" className="text-[9px] shrink-0 border-border/50 text-muted-foreground">
                      {intg.scope}
                    </Badge>
                  )}
                  <Badge variant="outline" className={cn("text-[9px] shrink-0", healthBadge(status))}>
                    {String(status).toUpperCase()}
                  </Badge>
                  <span className="text-[10px] text-muted-foreground flex items-center gap-1 shrink-0 w-24 text-right">
                    <Clock className="w-2.5 h-2.5" />
                    {fmtDate(intg.last_test_at || intg.registered_at)}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-[10px]"
                    onClick={() => handleTest(id)}
                    disabled={busy === `test-${id}`}
                    data-testid={`integrations-test-${id}`}
                  >
                    {busy === `test-${id}` ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <PlayCircle className="w-3 h-3 mr-1" />}
                    Test
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-[10px] hover:border-sylion-red/40 hover:text-sylion-red"
                    onClick={() => handleDelete(id)}
                    disabled={busy === `del-${id}`}
                    data-testid={`integrations-delete-${id}`}
                  >
                    {busy === `del-${id}` ? <Loader2 className="w-3 h-3" /> : <Trash2 className="w-3 h-3" />}
                    <span className="ml-1">Usun</span>
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Empty-state hint reflects honest data flow even when list non-empty */}
      {integrations.length === 0 && (
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <Activity className="w-3 h-3" />
          Po dodaniu integracji status sie pojawi tutaj automatycznie (refresh co 15s).
        </div>
      )}
    </div>
  );
}
