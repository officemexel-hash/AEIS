"use client";

import { useMemo, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import { useApi } from "@/lib/api/hooks";
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
  Server,
  Cable,
  Activity,
  Plus,
  AlertTriangle,
  Loader2,
  PlayCircle,
  Trash2,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface Connector {
  id: string;
  connector_id?: string;
  name: string;
  provider?: string;
  type?: string;
  scope?: string;
  status?: "healthy" | "unhealthy" | "degraded" | "unknown";
  last_test_at?: number;
  last_test_status?: string;
  last_health_check?: number;
}

interface ConnectorList {
  connectors: Connector[];
}

/* ============================================================
   Provider list (FE-9.2 cloud / infra connectors)
   ============================================================ */

const PROVIDERS: { id: string; label: string }[] = [
  { id: "hetzner", label: "Hetzner Cloud" },
  { id: "aws", label: "AWS" },
  { id: "gcp", label: "Google Cloud" },
  { id: "azure", label: "Azure" },
  { id: "digitalocean", label: "DigitalOcean" },
  { id: "vultr", label: "Vultr" },
  { id: "ovh", label: "OVHcloud" },
  { id: "linode", label: "Linode" },
];

const HETZNER_TEMPLATE = JSON.stringify(
  {
    api_token: "...",
    default_region: "nbg1",
    default_image: "ubuntu-22.04",
    default_server_type: "cx21",
  },
  null,
  2
);

/* ============================================================
   Helpers
   ============================================================ */

function formatTimestamp(ts?: number): string {
  if (!ts) return "--";
  const diff = Date.now() - ts;
  if (diff < 5000) return "przed chwila";
  if (diff < 60000) return `${Math.floor(diff / 1000)}s temu`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m temu`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h temu`;
  return new Date(ts).toLocaleDateString();
}

const statusStyles: Record<string, { dot: string; badge: string }> = {
  healthy: { dot: "bg-sylion-green", badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5" },
  ok: { dot: "bg-sylion-green", badge: "border-sylion-green/30 text-sylion-green bg-sylion-green/5" },
  degraded: { dot: "bg-sylion-amber", badge: "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5" },
  unhealthy: { dot: "bg-sylion-red", badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5" },
  failed: { dot: "bg-sylion-red", badge: "border-sylion-red/30 text-sylion-red bg-sylion-red/5" },
  unknown: { dot: "bg-muted-foreground", badge: "border-border/50 text-muted-foreground bg-muted/20" },
};

/* ============================================================
   Page Component
   ============================================================ */

export default function ConnectorsPage() {
  const { data: healthRaw, loading, refresh: fetchHealth } = useHealth();
  const backendLive = (healthRaw as any).status === "ok";

  const { data: connectorsData, refresh: refreshConnectors } = useApi<ConnectorList>(
    // Use cloud-connectors (BE-8) endpoint, not legacy /connectors/list
    () => api.listCloudConnectors().then((d: any) => ({ connectors: Array.isArray(d) ? d : (d.connectors ?? []) })) as Promise<ConnectorList>,
    { connectors: [] },
    15000
  );

  const connectors = connectorsData.connectors || [];

  /* ---------- form state ---------- */
  const [form, setForm] = useState({ provider: "hetzner", name: "", scope: "global", credentials: HETZNER_TEMPLATE });
  const [busy, setBusy] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);
  const [credsError, setCredsError] = useState<string | null>(null);

  const handleProviderChange = useCallback((provider: string) => {
    setForm((f) => ({
      ...f,
      provider,
      credentials: provider === "hetzner" ? HETZNER_TEMPLATE : "{\n  \n}",
    }));
  }, []);

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
      await api.registerConnector({
        provider: form.provider,
        name: form.name.trim(),
        scope: form.scope,
        credentials: parsed,
      });
      setSubmitSuccess(`Connector "${form.name.trim()}" (${form.provider}) zostal zarejestrowany.`);
      setForm((f) => ({ ...f, name: "", credentials: f.provider === "hetzner" ? HETZNER_TEMPLATE : "{\n  \n}" }));
      refreshConnectors();
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
  }, [form, refreshConnectors]);

  const handleTest = useCallback(async (id: string) => {
    setBusy(`test-${id}`);
    setSubmitError(null);
    try {
      await api.testConnector(id);
      refreshConnectors();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Test failed";
      setSubmitError(msg.includes("404") ? "Endpoint testu w przygotowaniu (BE-8)." : msg);
    } finally {
      setBusy(null);
    }
  }, [refreshConnectors]);

  const handleDelete = useCallback(async (id: string) => {
    if (!confirm("Usunac tego connectora?")) return;
    setBusy(`del-${id}`);
    setSubmitError(null);
    try {
      await api.deleteConnector(id);
      refreshConnectors();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Delete failed";
      setSubmitError(msg.includes("404") ? "Endpoint usuwania w przygotowaniu (BE-8)." : msg);
    } finally {
      setBusy(null);
    }
  }, [refreshConnectors]);

  /* ---------- Derived stats ---------- */
  const healthyCount = useMemo(
    () => connectors.filter((c) => (c.last_test_status === "ok" || c.status === "healthy")).length,
    [connectors]
  );
  const unhealthyCount = useMemo(
    () => connectors.filter((c) => c.status === "unhealthy" || c.status === "degraded" || c.last_test_status === "failed").length,
    [connectors]
  );

  /* ---------- Loading skeleton ---------- */
  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-muted animate-pulse rounded-lg" />
          <div>
            <div className="h-6 w-40 bg-muted animate-pulse rounded" />
            <div className="h-4 w-56 bg-muted animate-pulse rounded mt-1" />
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
              Connectory
              <HelpTip text="Connectory chmurowe (Hetzner, AWS, GCP itd.). Dostarczaja credentials i konfiguracje regionu/typu maszyny dla deployment?w." />
            </h1>
            <p className="text-sm text-muted-foreground">Polaczenia do dostawcow chmury</p>
          </div>
        </div>
        <Card className="p-8 bg-[#0f1629] border-sylion-red/20 flex flex-col items-center justify-center text-center">
          <div className="w-14 h-14 rounded-full bg-sylion-red/10 flex items-center justify-center mb-4">
            <WifiOff className="w-7 h-7 text-sylion-red" />
          </div>
          <h2 className="text-lg font-semibold text-sylion-red mb-1">Backend niedostępny</h2>
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            Backend SYLION nie odpowiada. Status connector?w wymaga dzialajacego backendu.
          </p>
          <Button variant="outline" size="sm" onClick={() => { fetchHealth(); refreshConnectors(); }}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Ponów połączenie
          </Button>
        </Card>
      </div>
    );
  }

  const summaryCards = [
    { label: "??cznie", value: connectors.length, icon: Cable, color: "text-sylion-blue", bgColor: "bg-sylion-blue/10" },
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
              Connectory
              <HelpTip text="Connectory chmurowe (Hetzner, AWS, GCP itd.). Dostarczaja credentials i konfiguracje regionu/typu maszyny dla deployment?w. Dla SaaS APIs uzyj zak?adki Integracje." />
            </h1>
            <p className="text-sm text-muted-foreground">Polaczenia do dostawcow chmury</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => refreshConnectors()} data-testid="connectors-refresh">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Odśwież
        </Button>
      </div>

      {/* ====== FE-9.2 ADD CONNECTOR FORM ====== */}
      <Card className="p-4 bg-[#0f1629] border-sylion-border" data-testid="connectors-add-card">
        <div className="flex items-center gap-2 mb-3">
          <Plus className="w-3.5 h-3.5 text-sylion-blue" />
          <h3 className="text-xs font-medium uppercase tracking-wider">
            Dodaj nowego connectora
            <HelpTip text="Rejestruje nowego connectora chmurowego. Credentials są zapisywane w vault sekret?w (zaszyfrowane at-rest). Po rejestracji uzyj 'Test connection' aby zweryfikowac dostep." />
          </h3>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] text-muted-foreground mb-1 block">
              Provider
              <HelpTip text="Dostawca chmury. Hetzner ma najlepszy stosunek ceny/wydajnosci dla regionu EU." />
            </label>
            <select
              data-testid="connectors-form-provider"
              value={form.provider}
              onChange={(e) => handleProviderChange(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              disabled={busy === "register"}
            >
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground mb-1 block">
              Nazwa
              <HelpTip text="Czytelna nazwa connectora (np. hetzner-prod-eu). U?ywana w widokach operatora i logach." />
            </label>
            <input
              data-testid="connectors-form-name"
              placeholder="np. hetzner-prod-eu"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              disabled={busy === "register"}
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground mb-1 block">
              Zakres
              <HelpTip text="Zakres dostepnosci connectora: global (wszedzie), workspace (caly workspace), pipeline (jeden pipeline)." />
            </label>
            <select
              data-testid="connectors-form-scope"
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
            <HelpTip text="Klucze API i konfiguracja w formacie JSON. Caly obiekt zostanie zaszyfrowany. Hetzner: api_token + default_region/image/server_type." />
          </label>
          <textarea
            data-testid="connectors-form-credentials"
            value={form.credentials}
            onChange={(e) => { setForm((f) => ({ ...f, credentials: e.target.value })); setCredsError(null); }}
            rows={form.provider === "hetzner" ? 7 : 5}
            className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-xs shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 font-mono"
            disabled={busy === "register"}
            spellCheck={false}
          />
          {credsError && (
            <p className="mt-1 text-[10px] text-sylion-red flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> {credsError}
            </p>
          )}
          {form.provider === "hetzner" && !credsError && (
            <p className="mt-1 text-[10px] text-muted-foreground">
              Hetzner template: api_token, default_region (np. nbg1), default_image (ubuntu-22.04), default_server_type (cx21).
            </p>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 mt-3">
          <Button
            data-testid="connectors-form-submit"
            size="sm"
            onClick={handleRegister}
            disabled={busy === "register" || !form.name.trim()}
          >
            {busy === "register" ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
            Zarejestruj connector
          </Button>
        </div>
        <AnimatePresence>
          {submitError && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-3 flex items-start gap-2 rounded-md border border-sylion-red/20 bg-sylion-red/5 p-2 text-xs text-sylion-red"
              data-testid="connectors-form-error"
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
              data-testid="connectors-form-success"
            >
              <CheckCircle2 className="w-3.5 h-3.5 mt-0.5" />
              <span>{submitSuccess}</span>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>

      {/* ====== SUMMARY CARDS ====== */}
      <div className="grid grid-cols-3 gap-3">
        {summaryCards.map((stat) => {
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

      {/* ====== CONNECTORS LIST ====== */}
      <Card className="bg-[#0f1629] border-sylion-border" data-testid="connectors-list">
        <div className="p-3 border-b border-border/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="w-3.5 h-3.5 text-muted-foreground" />
            <h3 className="text-xs font-medium text-muted-foreground">
              Zarejestrowane connectory
              <HelpTip text="Lista zarejestrowanych connector?w. 'Test connection' weryfikuje dostep do API providera. last_test_status = ok/failed/unknown." />
            </h3>
          </div>
          <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
            {connectors.length} ??cznie
          </span>
        </div>
        <div className="divide-y divide-border/20">
          {connectors.map((connector, idx) => {
            const id = connector.id || connector.connector_id || String(idx);
            const lastStatus = connector.last_test_status || connector.status || "unknown";
            const styles = statusStyles[lastStatus] || statusStyles.unknown;
            return (
              <motion.div
                key={id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: idx * 0.03, duration: 0.2 }}
                className="flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors"
                data-testid={`connectors-row-${id}`}
              >
                <span className={cn("w-2 h-2 rounded-full shrink-0", styles.dot)} />
                <span className="text-xs font-medium flex-1 min-w-0 truncate">{connector.name}</span>
                {connector.provider && (
                  <Badge variant="outline" className="text-[9px] shrink-0 border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5">
                    {connector.provider}
                  </Badge>
                )}
                {connector.scope && (
                  <Badge variant="outline" className="text-[9px] shrink-0 border-border/50 text-muted-foreground">
                    {connector.scope}
                  </Badge>
                )}
                <Badge variant="outline" className={cn("text-[9px] shrink-0", styles.badge)}>
                  {String(lastStatus).toUpperCase()}
                </Badge>
                <span className="text-[10px] text-muted-foreground flex items-center gap-1 shrink-0 w-28 justify-end">
                  <Clock className="w-2.5 h-2.5" />
                  {formatTimestamp(connector.last_test_at || connector.last_health_check)}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-[10px]"
                  onClick={() => handleTest(id)}
                  disabled={busy === `test-${id}`}
                  data-testid={`connectors-test-${id}`}
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
                  data-testid={`connectors-delete-${id}`}
                >
                  {busy === `del-${id}` ? <Loader2 className="w-3 h-3" /> : <Trash2 className="w-3 h-3" />}
                  <span className="ml-1">Usun</span>
                </Button>
              </motion.div>
            );
          })}

          {connectors.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Activity className="w-6 h-6 text-muted-foreground mb-2" />
              <p className="text-xs text-muted-foreground">Brak zarejestrowanych connector?w</p>
              <p className="text-[10px] text-muted-foreground/70 mt-1">Użyj formularza powyzej, aby doda? pierwszego connectora.</p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
