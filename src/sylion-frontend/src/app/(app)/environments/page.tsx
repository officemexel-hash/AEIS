"use client";

import { useCallback, useEffect, useMemo, useState, type ElementType } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, Cloud, Cpu, Database, Globe2, HardDrive, Loader2, LockKeyhole, Network, Plus, RefreshCw, Router, Server, ShieldCheck, SlidersHorizontal, XCircle, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useHealth } from "@/lib/api/hooks";
import { api } from "@/lib/api/client";
import { cn, fmtDateTime } from "@/lib/utils";
import { Phase3FullPanels } from "./_components/Phase3FullPanels";
import { HelpTip } from "@/components/common/HelpTip";

type EnvView = "type" | "purpose" | "flat";

const inputClass =
  "h-9 w-full rounded-md border border-sylion-border bg-background px-3 text-xs outline-none focus:border-primary";
const selectClass =
  "h-9 w-full rounded-md border border-sylion-border bg-background px-3 text-xs outline-none focus:border-primary";

const viewOptions: Array<{ id: EnvView; label: string }> = [
  { id: "type", label: "Według typu" },
  { id: "purpose", label: "Według celu" },
  { id: "flat", label: "Lista" },
];

const purposeOptions = [
  "development",
  "testing",
  "staging",
  "production",
  "edge",
  "demo_sandbox",
  "sovereign",
  "air_gapped",
];

function fmtTs(value?: number | string | null) {
  if (!value) return "--";
  const n = Number(value);
  return fmtDateTime(Number.isFinite(n) && n < 10_000_000_000 ? n * 1000 : value);
}

function fmtMoney(value?: number, currency = "USD") {
  const n = Number(value || 0);
  if (n === 0) return currency === "EUR" ? "€0" : "$0";
  return currency === "EUR" ? `€${n.toFixed(2)}` : `$${n.toFixed(2)}`;
}

function fmtGb(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? `${n.toFixed(n >= 10 ? 0 : 1)} GB` : "--";
}

function envText(value: unknown): string {
  const raw = String(value ?? "").trim();
  const labels: Record<string, string> = {
    unknown: "nieznane",
    healthy: "zdrowe",
    running: "działa",
    degraded: "zdegradowane",
    configured: "skonfigurowane",
    installed: "zainstalowane",
    missing: "brak",
    config: "konfiguracja",
    development: "rozwój",
    testing: "testy",
    staging: "staging",
    production: "produkcja",
    edge: "edge",
    demo_sandbox: "sandbox demo",
    sovereign: "suwerenne",
    air_gapped: "odizolowane",
    local: "lokalne",
    hetzner: "Hetzner",
    on_prem: "on-prem",
    type: "według typu",
    purpose: "według celu",
    flat: "lista",
  };
  return labels[raw] ?? raw.replace(/_/g, " ");
}

function boundedCount(value: string | number, fallback = 1, min = 1, max = 20): number {
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

function healthClass(health?: string) {
  if (health === "healthy" || health === "running") return "border-sylion-green/30 text-sylion-green";
  if (health === "degraded" || health === "unknown" || health === "configured") return "border-sylion-amber/30 text-sylion-amber";
  return "border-sylion-red/30 text-sylion-red";
}

function MetricCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: ElementType }) {
  return (
    <Card className="p-4 border-sylion-border bg-card">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="h-4 w-4 text-primary" />
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight">{value}</div>
    </Card>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-sylion-border px-3 py-5 text-center text-xs text-muted-foreground">{text}</div>;
}

function EnvironmentRow({ env }: { env: any }) {
  return (
    <div className="grid grid-cols-[minmax(160px,1.4fr)_110px_100px_120px_90px_90px] items-center gap-3 border-b border-sylion-border/50 py-2 text-xs last:border-b-0">
      <div className="min-w-0">
        <div className="truncate font-medium">{env.display_name || env.name}</div>
        <div className="truncate font-mono text-[10px] text-muted-foreground">{env.environment_id}</div>
      </div>
      <Badge variant="outline" className="w-fit text-[10px]">{envText(env.type)}</Badge>
      <span className="text-muted-foreground">{envText(env.purpose)}</span>
      <span className="truncate text-muted-foreground">{env.region || "lokalne"}</span>
      <span className="text-muted-foreground">{fmtMoney(env.monthly_estimate_usd, "USD")}</span>
      <Badge variant="outline" className={cn("w-fit text-[10px]", healthClass(env.health || env.status?.health))}>
        {envText(env.health || env.status?.health || "unknown")}
      </Badge>
    </div>
  );
}

function LocalScanPanel({ catalog, onScan, onAccept, busy }: { catalog: any; onScan: () => void; onAccept: () => void; busy: string }) {
  const scan = catalog?.local_scan || {};
  const os = scan.os || {};
  const hardware = scan.hardware || {};
  const software = scan.software || {};
  const network = hardware.network || {};
  const ports = Array.isArray(scan.ports) ? scan.ports : [];
  const cliTools = Array.isArray(scan.cloud_cli_tools) ? scan.cloud_cli_tools : [];
  const localDev = (catalog?.environments || []).find((env: any) => env.environment_id === "env_local_dev");

  return (
    <Card className="p-4 border-sylion-border bg-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <HardDrive className="h-4 w-4 text-primary" />
            Skan maszyny lokalnej
          </h2>
          <div className="mt-1 text-[11px] text-muted-foreground">{scan.scanned_at ? fmtTs(scan.scanned_at) : "nie skanowano"}</div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="h-8 text-[10px]" onClick={onScan} disabled={busy === "scan"}>
            {busy === "scan" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
            Skanuj ponownie
          </Button>
          <Button size="sm" className="h-8 text-[10px]" onClick={onAccept} disabled={busy === "accept" || Boolean(localDev?.accepted_at)}>
            {busy === "accept" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <CheckCircle2 className="mr-1 h-3 w-3" />}
            {localDev?.accepted_at ? "Zaakceptowano" : "Akceptuj domyślne"}
          </Button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-md border border-sylion-border bg-secondary/10 p-3">
          <div className="text-[10px] uppercase text-muted-foreground">OS</div>
          <div className="mt-1 font-medium">{os.platform || "--"} {os.platform_release || ""}</div>
          <div className="font-mono text-[10px] text-muted-foreground">{os.architecture || "--"}</div>
        </div>
        <div className="rounded-md border border-sylion-border bg-secondary/10 p-3">
          <div className="text-[10px] uppercase text-muted-foreground">CPU / RAM</div>
          <div className="mt-1 font-medium">{hardware.cpu_cores || 0} rdzeni</div>
          <div className="text-[10px] text-muted-foreground">{fmtGb(hardware.memory?.available_gb)} wolne / {fmtGb(hardware.memory?.total_gb)}</div>
        </div>
        <div className="rounded-md border border-sylion-border bg-secondary/10 p-3">
          <div className="text-[10px] uppercase text-muted-foreground">Docker</div>
          <div className="mt-1 font-medium">{software.docker_daemon?.running ? "działa" : software.docker?.installed ? "zainstalowany" : "brak"}</div>
          <div className="text-[10px] text-muted-foreground">{software.docker_daemon?.version || software.docker?.version || "--"}</div>
        </div>
        <div className="rounded-md border border-sylion-border bg-secondary/10 p-3">
          <div className="text-[10px] uppercase text-muted-foreground">Sieć</div>
          <div className="mt-1 font-medium">{network.local_ips?.[0] || "localhost"}</div>
          <div className="text-[10px] text-muted-foreground">Hosty SSH: {network.ssh_host_entries_count || 0}</div>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium">
          <Router className="h-3.5 w-3.5 text-primary" />
          Zajęte porty lokalne
        </div>
        <div className="flex flex-wrap gap-1.5">
          {ports.filter((port: any) => port.busy).length === 0 ? (
            <Badge variant="outline" className="text-[10px] text-muted-foreground">nie wykryto</Badge>
          ) : (
            ports.filter((port: any) => port.busy).map((port: any) => (
              <Badge key={port.port} variant="outline" className="border-sylion-amber/30 text-[10px] text-sylion-amber">
                {port.port} {port.label}
              </Badge>
            ))
          )}
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-medium">
          <Cloud className="h-3.5 w-3.5 text-primary" />
          Wykryte narzędzia CLI
        </div>
        <div className="space-y-1">
          {cliTools.map((tool: any) => (
            <div key={tool.provider} className="flex items-center justify-between rounded-md border border-sylion-border bg-secondary/10 px-2 py-1.5 text-xs">
              <span>{tool.label}</span>
              <Badge variant="outline" className={cn("text-[9px]", tool.installed ? "border-sylion-green/30 text-sylion-green" : "text-muted-foreground")}>
                {tool.installed ? (tool.config_present ? "konfiguracja" : "zainstalowane") : "brak"}
              </Badge>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function TypeView({ data }: { data: any }) {
  const groups = data?.groups || [];
  return (
    <div className="space-y-3">
      {groups.filter((group: any) => !group.empty || ["local", "edge", "on_prem", "air_gapped", "aws", "hetzner", "scaleway", "ionos"].includes(group.id)).map((group: any) => (
        <div key={group.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">{group.display_name}</span>
              <Badge variant="outline" className="text-[9px]">{group.category}</Badge>
            </div>
            <span className="text-[11px] text-muted-foreground">{group.environment_count} środ. / {group.account_count} kont</span>
          </div>
          {group.accounts?.length ? (
            <div className="mt-3 space-y-2">
              {group.accounts.map((account: any) => (
                <div key={`${group.id}-${account.account}`} className="rounded-md border border-sylion-border bg-background/40 p-2">
                  <div className="text-xs font-medium">{account.account}</div>
                  <div className="mt-2 space-y-2">
                    {account.regions?.map((region: any) => (
                      <div key={`${group.id}-${account.account}-${region.region}`}>
                        <div className="mb-1 text-[10px] uppercase text-muted-foreground">{region.region}</div>
                        {region.environments?.length ? region.environments.map((env: any) => <EnvironmentRow key={env.environment_id} env={env} />) : <EmptyState text="Brak środowisk w tym regionie" />}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3 text-xs text-muted-foreground">Puste miejsce</div>
          )}
        </div>
      ))}
    </div>
  );
}

function PurposeView({ data }: { data: any }) {
  return (
    <div className="space-y-3">
      {(data?.groups || []).map((group: any) => (
        <div key={group.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">{group.label}</div>
              <div className="text-[10px] text-muted-foreground">{group.description}</div>
            </div>
            <Badge variant="outline" className="text-[10px]">{group.environment_count}</Badge>
          </div>
          <div className="mt-3">
            {group.environments?.length ? group.environments.map((env: any) => <EnvironmentRow key={env.environment_id} env={env} />) : <EmptyState text="Brak środowisk dla tego celu" />}
          </div>
        </div>
      ))}
    </div>
  );
}

function FlatView({ data }: { data: any }) {
  const rows = data?.rows || [];
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[760px]">
        <div className="grid grid-cols-[minmax(160px,1.4fr)_110px_100px_120px_90px_90px] gap-3 border-b border-sylion-border pb-2 text-[10px] uppercase text-muted-foreground">
          <span>Name</span>
          <span>Typ</span>
          <span>Cel</span>
          <span>Region</span>
          <span>Cost</span>
          <span>Status</span>
        </div>
        {rows.length ? rows.map((env: any) => <EnvironmentRow key={env.environment_id} env={env} />) : <EmptyState text="Brak skonfigurowanych środowisk" />}
      </div>
    </div>
  );
}

function CloudProvidersPanel({ catalog, onAddDetected, busy }: { catalog: any; onAddDetected: () => void; busy: string }) {
  const templates = catalog?.cloud_provider_templates || [];
  const detected = (catalog?.local_scan?.cloud_cli_tools || []).filter((tool: any) => tool.installed && !["terraform", "pulumi"].includes(tool.provider));
  const [selected, setSelected] = useState("hetzner");
  const active = templates.find((item: any) => item.provider === selected) || templates[0];

  return (
    <Card className="p-4 border-sylion-border bg-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Globe2 className="h-4 w-4 text-primary" />
            Cloud providers
          </h2>
          <div className="mt-1 text-[11px] text-muted-foreground">Tier 1 + Tier 2 + EU sovereign, custom adapter included</div>
        </div>
        <Button variant="outline" size="sm" className="h-8 text-[10px]" onClick={onAddDetected} disabled={busy === "providers" || detected.length === 0}>
          {busy === "providers" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Plus className="mr-1 h-3 w-3" />}
          Add detected CLI
        </Button>
      </div>

      <div className="mt-4 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-4">
        <div className="space-y-1">
          {templates.map((provider: any) => (
            <button
              key={provider.provider}
              type="button"
              onClick={() => setSelected(provider.provider)}
              className={cn(
                "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-xs",
                active?.provider === provider.provider ? "border-primary bg-primary/10" : "border-sylion-border bg-secondary/10 hover:border-primary/50",
              )}
            >
              <span>{provider.display_name}</span>
              <span className="text-[10px] text-muted-foreground">{fmtMoney(provider.min_monthly_cost, provider.currency)}</span>
            </button>
          ))}
        </div>

        {active ? (
          <div className="rounded-md border border-sylion-border bg-secondary/10 p-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <div className="text-sm font-medium">{active.display_name}</div>
                <div className="text-[10px] text-muted-foreground">{active.sovereignty} / setup {active.setup_minutes} min / SLA {active.sla}</div>
              </div>
              <Badge variant="outline" className="text-[10px]">{active.tier}</Badge>
            </div>
            <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
              <div>
                <div className="mb-1 text-[10px] uppercase text-muted-foreground">Auth</div>
                <div className="space-y-1">{active.auth_methods?.map((m: string) => <Badge key={m} variant="outline" className="mr-1 text-[9px]">{m}</Badge>)}</div>
              </div>
              <div>
                <div className="mb-1 text-[10px] uppercase text-muted-foreground">Regions</div>
                <div className="space-y-1">{active.regions?.slice(0, 4).map((r: any) => <div key={r.id}>{r.id} <span className="text-muted-foreground">{r.sovereignty}</span></div>)}</div>
              </div>
              <div>
                <div className="mb-1 text-[10px] uppercase text-muted-foreground">Quirks</div>
                <div className="space-y-1 text-muted-foreground">{active.quirks?.slice(0, 3).map((q: string) => <div key={q}>{q}</div>)}</div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function AddEnvironmentPanel({ catalog, onSaved, setStatus }: { catalog: any; onSaved: () => void; setStatus: (status: string) => void }) {
  const providers = catalog?.cloud_provider_templates || [];
  const [form, setForm] = useState({
    name: "staging-cloud",
    environment_type: "hetzner",
    provider: "hetzner",
    purpose: "staging",
    region: "warsaw-1",
    monthly_estimate_usd: "0",
    environment_count: "1",
    sovereign: true,
    air_gapped: false,
  });
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const count = boundedCount(form.environment_count, 1, 1, 20);
      const baseName = form.name.trim();
      for (let index = 1; index <= count; index += 1) {
        const indexedName = count === 1 ? baseName : `${baseName}-${String(index).padStart(2, "0")}`;
        await api.createEnvironmentCatalogEntry({
          name: indexedName,
          display_name: indexedName,
          environment_type: form.environment_type,
          provider: form.provider,
          purpose: form.purpose,
          tier: form.purpose === "production" ? "prod" : form.purpose,
          region: form.region,
          cost: { monthly_estimate_usd: Number(form.monthly_estimate_usd || 0) },
          status: { state: "configured", health: "unknown" },
          policies: {
            auto_cleanup: form.purpose !== "production",
            cleanup_after_days: form.purpose === "production" ? null : 14,
            backup_strategy: form.purpose === "production" ? "daily" : "manual",
            snapshot_retention: form.purpose === "production" ? 30 : 3,
          },
          metadata: {
            created_by_phase: 3,
            sovereign: form.sovereign,
            air_gapped: form.air_gapped,
            batch_size: count,
            batch_index: index,
            tags: [form.environment_type, form.purpose],
          },
        });
      }
      setStatus(count === 1 ? `Środowisko ${baseName} zapisane.` : `Zapisano ${count} środowisk z prefiksem ${baseName}.`);
      onSaved();
    } catch (err: any) {
      setStatus(`Nie udało się zapisać środowiska: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="p-4 border-sylion-border bg-card">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <Plus className="h-4 w-4 text-primary" />
        Dodaj środowisko
      </h2>
      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <label className="text-xs">
          <span className="mb-1 block text-muted-foreground">Name</span>
          <input className={inputClass} value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
        </label>
        <label className="text-xs">
          <span className="mb-1 block text-muted-foreground">Typ</span>
          <select
            className={selectClass}
            value={form.environment_type}
            onChange={(e) => setForm((p) => ({ ...p, environment_type: e.target.value, provider: e.target.value }))}
          >
            <option value="local">local</option>
            <option value="on_prem">on_prem</option>
            <option value="air_gapped">air_gapped</option>
            <option value="edge">edge</option>
            {providers.map((provider: any) => <option key={provider.provider} value={provider.provider}>{provider.provider}</option>)}
          </select>
        </label>
        <label className="text-xs">
          <span className="mb-1 block text-muted-foreground">Cel</span>
          <select className={selectClass} value={form.purpose} onChange={(e) => setForm((p) => ({ ...p, purpose: e.target.value }))}>
            {purposeOptions.map((purpose) => <option key={purpose} value={purpose}>{purpose}</option>)}
          </select>
        </label>
        <label className="text-xs">
          <span className="mb-1 block text-muted-foreground">Region</span>
          <input className={inputClass} value={form.region} onChange={(e) => setForm((p) => ({ ...p, region: e.target.value }))} />
        </label>
        <label className="text-xs">
          <span className="mb-1 block text-muted-foreground">Monthly USD</span>
          <input className={inputClass} type="number" min="0" value={form.monthly_estimate_usd} onChange={(e) => setForm((p) => ({ ...p, monthly_estimate_usd: e.target.value }))} />
        </label>
        <label className="text-xs">
          <span className="mb-1 block text-muted-foreground">Liczba środowisk</span>
          <input className={inputClass} type="number" min="1" max="20" value={form.environment_count} onChange={(e) => setForm((p) => ({ ...p, environment_count: e.target.value }))} />
        </label>
        <div className="flex items-end gap-4 text-xs">
          <label className="flex h-9 items-center gap-2">
            <input type="checkbox" checked={form.sovereign} onChange={(e) => setForm((p) => ({ ...p, sovereign: e.target.checked }))} />
            Sovereign
          </label>
          <label className="flex h-9 items-center gap-2">
            <input type="checkbox" checked={form.air_gapped} onChange={(e) => setForm((p) => ({ ...p, air_gapped: e.target.checked, environment_type: e.target.checked ? "air_gapped" : p.environment_type }))} />
            Air-gap
          </label>
        </div>
      </div>
      <Button className="mt-4 h-8 text-xs" size="sm" onClick={save} disabled={saving || !form.name.trim()}>
        {saving ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <CheckCircle2 className="mr-1 h-3 w-3" />}
        Zapisz środowisko
      </Button>
    </Card>
  );
}

function SovereignEdgePanel({ catalog, onSaved, setStatus }: { catalog: any; onSaved: () => void; setStatus: (status: string) => void }) {
  const [edgeForm, setEdgeForm] = useState({
    display_name: "rpi-fabryka-1",
    pairing_method: "ssh",
    hostname: "",
    ssh_username: "pi",
    device_type: "raspberry_pi_4",
    location: "Warsaw",
    owner: "operator",
  });
  const [saving, setSaving] = useState(false);

  const saveEdge = async () => {
    if (!edgeForm.display_name.trim()) return;
    setSaving(true);
    try {
      await api.createEdgeEnvironmentDevice({
        ...edgeForm,
        ssh_port: 22,
        capabilities: ["linux", "ssh", "docker"],
        ram_gb: 4,
        storage_gb: 32,
      });
      setStatus(`Urządzenie edge ${edgeForm.display_name} zapisane.`);
      onSaved();
    } catch (err: any) {
      setStatus(`Nie udało się zapisać edge: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <Card className="p-4 border-sylion-border bg-card">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <LockKeyhole className="h-4 w-4 text-primary" />
          Sovereign profiles
        </h2>
        <div className="mt-4 space-y-2">
          {(catalog?.sovereign_profiles || []).map((profile: any) => (
            <div key={profile.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{profile.label}</span>
                <Badge variant="outline" className="text-[10px]">{profile.type}</Badge>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {profile.enforced_restrictions?.slice(0, 4).map((item: string) => (
                  <Badge key={item} variant="outline" className="text-[9px] text-muted-foreground">{item}</Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-4 border-sylion-border bg-card">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Zap className="h-4 w-4 text-primary" />
          Urządzenie edge
        </h2>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="text-xs">
            <span className="mb-1 block text-muted-foreground">Display name</span>
            <input className={inputClass} value={edgeForm.display_name} onChange={(e) => setEdgeForm((p) => ({ ...p, display_name: e.target.value }))} />
          </label>
          <label className="text-xs">
            <span className="mb-1 block text-muted-foreground">Pairing</span>
            <select className={selectClass} value={edgeForm.pairing_method} onChange={(e) => setEdgeForm((p) => ({ ...p, pairing_method: e.target.value }))}>
              {(catalog?.edge?.pairing_methods || []).map((method: any) => <option key={method.id} value={method.id}>{method.label}</option>)}
            </select>
          </label>
          <label className="text-xs">
            <span className="mb-1 block text-muted-foreground">Hostname/IP</span>
            <input className={inputClass} value={edgeForm.hostname} onChange={(e) => setEdgeForm((p) => ({ ...p, hostname: e.target.value }))} />
          </label>
          <label className="text-xs">
            <span className="mb-1 block text-muted-foreground">SSH user</span>
            <input className={inputClass} value={edgeForm.ssh_username} onChange={(e) => setEdgeForm((p) => ({ ...p, ssh_username: e.target.value }))} />
          </label>
          <label className="text-xs">
            <span className="mb-1 block text-muted-foreground">Typ urządzenia</span>
            <select className={selectClass} value={edgeForm.device_type} onChange={(e) => setEdgeForm((p) => ({ ...p, device_type: e.target.value }))}>
              <option value="raspberry_pi_4">Raspberry Pi 4</option>
              <option value="raspberry_pi_5">Raspberry Pi 5</option>
              <option value="jetson_orin">NVIDIA Jetson Orin</option>
              <option value="intel_nuc">Intel NUC</option>
              <option value="industrial_pc">Industrial PC</option>
            </select>
          </label>
          <label className="text-xs">
            <span className="mb-1 block text-muted-foreground">Location</span>
            <input className={inputClass} value={edgeForm.location} onChange={(e) => setEdgeForm((p) => ({ ...p, location: e.target.value }))} />
          </label>
        </div>
        <Button className="mt-4 h-8 text-xs" size="sm" onClick={saveEdge} disabled={saving || !edgeForm.display_name.trim()}>
          {saving ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Plus className="mr-1 h-3 w-3" />}
          Zapisz urządzenie edge
        </Button>
      </Card>
    </div>
  );
}

export default function EnvironmentsPage() {
  const { data: health, loading: healthLoading } = useHealth();
  const backendLive = health.status === "ok";
  const backendPending = healthLoading || health.status === "unknown";
  const [view, setView] = useState<EnvView>("type");
  const [catalog, setCatalog] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  const loadCatalog = useCallback(async () => {
    if (!backendLive) {
      setCatalog(null);
      setLoading(false);
      setStatus(backendPending ? "Łączenie z backendem..." : "Backend niedostępny.");
      return;
    }
    setLoading(true);
    try {
      const data = await api.getEnvironmentCatalog(view, true);
      setCatalog(data);
      setStatus("");
    } catch (err: any) {
      setStatus(`Błąd katalogu środowisk: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [backendLive, backendPending, view]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadCatalog();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadCatalog]);

  const runScan = async () => {
    setBusy("scan");
    try {
      const data = await api.scanLocalEnvironment({ auto_create_local_dev: true, deep_scan: false });
      setCatalog(data.catalog);
      setStatus("Skan maszyny lokalnej odświeżony.");
    } catch (err: any) {
      setStatus(`Skan nie powiódł się: ${err.message}`);
    } finally {
      setBusy("");
    }
  };

  const acceptLocal = async () => {
    setBusy("accept");
    try {
      const data = await api.acceptLocalDevEnvironment({ notes: "Phase 3 defaults accepted in Environment Catalog." });
      setStatus(`local-dev: ${envText(data.status)}.`);
      await loadCatalog();
    } catch (err: any) {
      setStatus(`Akceptacja nie powiodła się: ${err.message}`);
    } finally {
      setBusy("");
    }
  };

  const addDetectedProviders = async () => {
    setBusy("providers");
    try {
      const data = await api.addDetectedEnvironmentProviders();
      setCatalog(data.catalog);
      setStatus(`Dodano wykrytych providerów: ${data.added?.length || 0}.`);
    } catch (err: any) {
      setStatus(`Dodanie providerów nie powiodło się: ${err.message}`);
    } finally {
      setBusy("");
    }
  };

  const summary = catalog?.summary || {};
  const acceptance = catalog?.acceptance;
  const selectedViewData = catalog?.views?.[view] || catalog?.selected_view_data;
  const localDev = useMemo(() => (catalog?.environments || []).find((env: any) => env.environment_id === "env_local_dev"), [catalog]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Globe2 className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
              Konfiguracja środowisk - Faza 3
              <HelpTip text="Warstwa W5/W6: tutaj operator ustala, gdzie działa kod, jakie są limity kosztów, regiony, izolacja danych, lokalne skany oraz środowiska edge. Domyślnie AEIS działa local-first." />
            </h1>
            <p className="text-sm text-muted-foreground">Cele obliczeniowe, polityka sieci, rezydencja danych, koszt, cleanup i operacje edge.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/environments/theater"
            className="inline-flex h-8 items-center gap-1 rounded-md border border-sylion-border bg-background px-3 text-[10px] font-medium hover:border-primary/50 hover:text-primary"
          >
            <Network className="h-3 w-3" />
            Teatr środowisk
          </Link>
          <Button variant="outline" size="sm" className="h-8 text-[10px]" onClick={() => void loadCatalog()} disabled={loading}>
            {loading ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
            Odśwież
          </Button>
          <Badge variant="outline" className={cn("text-[10px]", backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
            {backendLive ? "BACKEND DZIAŁA" : backendPending ? "ŁĄCZENIE Z BACKENDEM" : "BACKEND NIEDOSTĘPNY"}
          </Badge>
          <Badge variant="outline" className={cn("text-[10px]", acceptance?.accepted ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>
            {acceptance?.accepted ? "AKCEPTACJA PRZESZŁA" : "AKCEPTACJA OCZEKUJE"}
          </Badge>
        </div>
      </div>

      {status ? (
        <Card className="border-sylion-amber/30 bg-sylion-amber/10 p-3 text-xs text-sylion-amber">
          {status}
        </Card>
      ) : null}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-6">
        <MetricCard label="Środowiska" value={summary.active_environments ?? 0} icon={Server} />
        <MetricCard label="Konta providerów" value={summary.active_provider_accounts ?? 0} icon={Cloud} />
        <MetricCard label="Urządzenia edge" value={summary.edge_devices ?? 0} icon={Zap} />
        <MetricCard label="Suwerenne" value={summary.sovereign_environments ?? 0} icon={ShieldCheck} />
        <MetricCard label="Miesięcznie USD" value={fmtMoney(summary.monthly_cost_usd, "USD")} icon={Database} />
        <MetricCard label="Wykryte CLI" value={summary.cloud_cli_detected ?? 0} icon={Cpu} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_390px] gap-4">
        <Card className="p-4 border-sylion-border bg-card">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <Network className="h-4 w-4 text-primary" />
                Katalog środowisk
              </h2>
              <div className="mt-1 text-[11px] text-muted-foreground">
                Widok domyślny: {envText(catalog?.default_view || "type")} / local-dev: {localDev ? "skonfigurowane" : "brak"}
              </div>
            </div>
            <div className="flex rounded-md border border-sylion-border bg-secondary/10 p-1">
              {viewOptions.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setView(option.id)}
                  className={cn(
                    "h-7 rounded px-3 text-[10px]",
                    view === option.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4">
            {loading ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Ładowanie katalogu środowisk...
              </div>
            ) : !catalog ? (
              <EmptyState text="Katalog środowisk niedostępny" />
            ) : view === "type" ? (
              <TypeView data={selectedViewData} />
            ) : view === "purpose" ? (
              <PurposeView data={selectedViewData} />
            ) : (
              <FlatView data={selectedViewData} />
            )}
          </div>
        </Card>

        <LocalScanPanel catalog={catalog} onScan={runScan} onAccept={acceptLocal} busy={busy} />
      </div>

      <CloudProvidersPanel catalog={catalog} onAddDetected={addDetectedProviders} busy={busy} />

      <AddEnvironmentPanel catalog={catalog} onSaved={loadCatalog} setStatus={setStatus} />

      <SovereignEdgePanel catalog={catalog} onSaved={loadCatalog} setStatus={setStatus} />

      <Phase3FullPanels catalog={catalog} onSaved={loadCatalog} setStatus={setStatus} />

      <Card className="p-4 border-sylion-border bg-card">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <SlidersHorizontal className="h-4 w-4 text-primary" />
          Kontrole akceptacyjne
        </h2>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">
          {(acceptance?.checks || []).map((check: any) => (
            <div key={check.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3">
              <div className="flex items-start gap-2">
                {check.status === "pass" ? (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-sylion-green" />
                ) : check.status === "warn" ? (
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-sylion-amber" />
                ) : (
                  <XCircle className="mt-0.5 h-3.5 w-3.5 text-sylion-red" />
                )}
                <div>
                  <div className="text-xs font-medium">{check.label}</div>
                  <div className="mt-1 text-[10px] text-muted-foreground">{check.evidence}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
