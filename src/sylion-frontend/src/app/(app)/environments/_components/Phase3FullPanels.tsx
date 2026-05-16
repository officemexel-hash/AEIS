"use client";

import { useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, GitBranch, Loader2, Network, Radar, ReceiptText, RefreshCw, ShieldCheck, Trash2, Workflow, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const inputClass =
  "h-9 w-full rounded-md border border-sylion-border bg-background px-3 text-xs outline-none focus:border-primary";
const selectClass =
  "h-9 w-full rounded-md border border-sylion-border bg-background px-3 text-xs outline-none focus:border-primary";

function money(value: unknown) {
  const n = Number(value || 0);
  return `$${n.toFixed(2)}`;
}

function firstId(items: any[], key = "id") {
  return String(items?.[0]?.[key] || "");
}

function CheckIcon({ status }: { status?: string }) {
  if (status === "pass") return <CheckCircle2 className="h-3.5 w-3.5 text-sylion-green" />;
  if (status === "warn") return <AlertTriangle className="h-3.5 w-3.5 text-sylion-amber" />;
  return <AlertTriangle className="h-3.5 w-3.5 text-sylion-red" />;
}

function SectionTitle({ icon: Icon, title, right }: { icon: any; title: string; right?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <h2 className="flex items-center gap-2 text-sm font-semibold">
        <Icon className="h-4 w-4 text-primary" />
        {title}
      </h2>
      {right}
    </div>
  );
}

export function Phase3FullPanels({ catalog, onSaved, setStatus }: { catalog: any; onSaved: () => Promise<void> | void; setStatus: (value: string) => void }) {
  const environments = useMemo(() => (Array.isArray(catalog?.environments) ? catalog.environments : []), [catalog]);
  const network = catalog?.network || {};
  const residency = catalog?.residency || {};
  const costs = catalog?.costs || {};
  const cleanup = catalog?.cleanup || {};
  const edgeCases = catalog?.edge_cases || {};
  const phase3Acceptance = catalog?.phase3_acceptance || {};

  const [networkEnvId, setNetworkEnvId] = useState("");
  const [networkMode, setNetworkMode] = useState("");
  const [vpnMode, setVpnMode] = useState("");
  const [meshProvider, setMeshProvider] = useState("");
  const [firewallTemplate, setFirewallTemplate] = useState("");
  const [networkDiagnostic, setNetworkDiagnostic] = useState<any | null>(null);

  const [residencyEnvId, setResidencyEnvId] = useState("");
  const [residencyProfile, setResidencyProfile] = useState("gdpr_eu");
  const [residencyResult, setResidencyResult] = useState<any | null>(null);

  const [costEnvId, setCostEnvId] = useState("");
  const [budgetCap, setBudgetCap] = useState("80");
  const [cleanupStrategy, setCleanupStrategy] = useState("manual");
  const [cleanupPlan, setCleanupPlan] = useState<any | null>(null);

  const [edgeCaseId, setEdgeCaseId] = useState("");
  const [edgeDiagnosis, setEdgeDiagnosis] = useState<any | null>(null);
  const [inheritanceGoal, setInheritanceGoal] = useState("apps_internal");
  const [inheritanceResult, setInheritanceResult] = useState<any | null>(null);
  const [acceptanceGoal, setAcceptanceGoal] = useState("apps_internal");
  const [acceptanceResult, setAcceptanceResult] = useState<any | null>(null);
  const [busy, setBusy] = useState("");

  const selectedNetworkEnv = environments.find((env: any) => env.environment_id === networkEnvId) || environments[0];
  const selectedNetworkPolicy =
    (network.policies || []).find((item: any) => item.environment_id === selectedNetworkEnv?.environment_id) || {};
  const selectedNetworkEnvId = selectedNetworkEnv?.environment_id || "";
  const selectedResidencyEnvId = residencyEnvId || selectedNetworkEnvId;
  const selectedCostEnvId = costEnvId || selectedNetworkEnvId;
  const selectedCaseId = edgeCaseId || firstId(edgeCases.cases || []);
  const currentAcceptance = acceptanceResult || phase3Acceptance;

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

  const saveNetworkPolicy = () =>
    withBusy("network", async () => {
      const data = await api.updateEnvironmentNetworkPolicy({
        environment_id: selectedNetworkEnvId,
        network_mode: networkMode || selectedNetworkPolicy.network_mode || "isolated",
        vpn_mode: vpnMode || selectedNetworkPolicy.vpn_mode || "disabled",
        mesh_provider: meshProvider || selectedNetworkPolicy.mesh_provider || "",
        firewall_template: firewallTemplate || selectedNetworkPolicy.firewall_template || "basic_web",
        sensitive: selectedNetworkEnv?.purpose === "production" || selectedNetworkPolicy.sensitive || false,
      });
      setNetworkDiagnostic(null);
      setStatus(`Network policy saved: ${data.policy?.environment_id || selectedNetworkEnvId}.`);
      await onSaved();
    });

  const runNetworkDiagnostic = () =>
    withBusy("network-diagnostic", async () => {
      const data = await api.runEnvironmentNetworkDiagnostic({ environment_id: selectedNetworkEnvId });
      setNetworkDiagnostic(data);
      setStatus(`Network diagnostic checked ${data.diagnostics?.length || 0} environment(s).`);
    });

  const saveResidencyRule = () =>
    withBusy("residency-rule", async () => {
      await api.saveEnvironmentResidencyRule({
        project_id: "workspace-default",
        compliance_profile: residencyProfile,
        allowed_regions: residencyProfile === "poland_only" ? ["PL"] : ["EU"],
        data_classes: ["PII", "customer_data"],
        hard_requirements: residencyProfile === "poland_only" ? ["polish_datacenter_or_on_prem"] : ["no_us_processing"],
        subprocessor_disclosure: true,
      });
      setStatus(`Residency rule saved: ${residencyProfile}.`);
      await onSaved();
    });

  const checkResidency = () =>
    withBusy("residency-check", async () => {
      const data = await api.checkEnvironmentResidency({
        project_id: "workspace-default",
        environment_id: selectedResidencyEnvId,
        data_classes: ["PII"],
        allowed_regions: residencyProfile === "poland_only" ? ["PL"] : ["EU"],
        requires_poland: residencyProfile === "poland_only",
      });
      setResidencyResult(data);
      setStatus(`Residency decision: ${data.decision}.`);
    });

  const saveCostAlert = () =>
    withBusy("cost-alert", async () => {
      await api.saveEnvironmentCostAlert({
        environment_id: selectedCostEnvId,
        monthly_budget_cap: Number(budgetCap || 0),
        thresholds: [50, 80, 95, 100],
        channels: ["in_app"],
        auto_actions: { above_100: "human_gate" },
      });
      setStatus("Cost alert saved.");
      await onSaved();
    });

  const saveCleanupPolicy = () =>
    withBusy("cleanup-policy", async () => {
      await api.saveEnvironmentCleanupPolicy({
        environment_id: selectedCostEnvId,
        strategy: cleanupStrategy,
        cleanup_after_hours: cleanupStrategy === "auto_after_hours" ? 72 : null,
        inactive_days: cleanupStrategy === "conditional" ? 14 : null,
        schedule: cleanupStrategy === "schedule" ? "Sun 02:00" : "",
        action: cleanupStrategy === "manual" ? "notify_only" : "snapshot_then_stop",
      });
      setStatus("Cleanup policy saved.");
      await onSaved();
    });

  const createCleanupPlan = () =>
    withBusy("cleanup-plan", async () => {
      const data = await api.createEnvironmentBulkCleanupPlan({
        purposes: ["testing", "demo_sandbox"],
        inactive_days: 14,
        include_tags: [],
        exclude_tags: ["keep-permanent", "customer-prod"],
      });
      setCleanupPlan(data.plan);
      setStatus(`Cleanup plan candidates: ${data.plan?.candidates?.length || 0}.`);
    });

  const diagnoseEdgeCase = () =>
    withBusy("edge-case", async () => {
      const data = await api.diagnoseEnvironmentEdgeCase({
        case_id: selectedCaseId,
        environment_id: selectedNetworkEnvId,
        context: { source: "operator_console" },
      });
      setEdgeDiagnosis(data);
      setStatus(`Runbook ready: ${selectedCaseId}.`);
    });

  const resolveInheritance = () =>
    withBusy("inheritance", async () => {
      const data = await api.resolveEnvironmentInheritance({
        project_id: "workspace-default",
        purpose: selectedNetworkEnv?.purpose || "production",
        goal: inheritanceGoal,
        overrides: {},
      });
      setInheritanceResult(data);
      setStatus(`Inheritance resolved for ${inheritanceGoal}.`);
    });

  const runAcceptance = () =>
    withBusy("acceptance", async () => {
      const data = await api.runEnvironmentAcceptanceTest(acceptanceGoal);
      setAcceptanceResult(data);
      setStatus(data.accepted ? "Phase 3 acceptance passed." : `Phase 3 hard blocks: ${data.hard_blocks?.length || 0}.`);
      await onSaved();
    });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card className="border-sylion-border bg-card p-4">
          <SectionTitle icon={Network} title="Network topology and federation" right={<Badge variant="outline" className="text-[10px]">{network.policies?.length || 0} policies</Badge>} />
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
            {(network.topologięs || []).map((item: any) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setNetworkMode(item.id)}
                className={cn(
                  "rounded-md border p-3 text-left text-xs",
                  (networkMode || selectedNetworkPolicy.network_mode || "isolated") === item.id ? "border-primary bg-primary/10" : "border-sylion-border bg-secondary/10",
                )}
              >
                <div className="font-medium">{item.label}</div>
                <div className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">{item.description}</div>
              </button>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-5">
            <label className="text-xs md:col-span-2">
              <span className="mb-1 block text-muted-foreground">Environment</span>
              <select className={selectClass} value={selectedNetworkEnvId} onChange={(e) => setNetworkEnvId(e.target.value)}>
                {environments.map((env: any) => (
                  <option key={env.environment_id} value={env.environment_id}>{env.display_name || env.name}</option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">VPN</span>
              <select className={selectClass} value={vpnMode || selectedNetworkPolicy.vpn_mode || "disabled"} onChange={(e) => setVpnMode(e.target.value)}>
                {(network.vpn_modes || []).map((item: any) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">Mesh</span>
              <select className={selectClass} value={meshProvider || selectedNetworkPolicy.mesh_provider || ""} onChange={(e) => setMeshProvider(e.target.value)}>
                <option value="">none</option>
                {(network.mesh_providers || []).map((item: any) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">Firewall</span>
              <select className={selectClass} value={firewallTemplate || selectedNetworkPolicy.firewall_template || "basic_web"} onChange={(e) => setFirewallTemplate(e.target.value)}>
                {(network.firewall_templates || []).map((item: any) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" className="h-8 text-xs" onClick={saveNetworkPolicy} disabled={!selectedNetworkEnvId || busy === "network"}>
              {busy === "network" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <ShieldCheck className="mr-1 h-3 w-3" />}
              Save policy
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={runNetworkDiagnostic} disabled={!selectedNetworkEnvId || busy === "network-diagnostic"}>
              {busy === "network-diagnostic" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Radar className="mr-1 h-3 w-3" />}
              Diagnostic
            </Button>
          </div>
          {networkDiagnostic ? (
            <div className="mt-3 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
              {(networkDiagnostic.diagnostics?.[0]?.checks || []).map((check: any) => (
                <div key={check.id} className="flex items-center gap-2 py-1">
                  <CheckIcon status={check.status} />
                  <span>{check.id}</span>
                  <span className="text-muted-foreground">{String(check.evidence)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <SectionTitle icon={ShieldCheck} title="Data residency" right={<Badge variant="outline" className="text-[10px]">{residency.rules?.length || 0} rules</Badge>} />
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">Profile</span>
              <select className={selectClass} value={residencyProfile} onChange={(e) => setResidencyProfile(e.target.value)}>
                {(residency.templates || []).map((item: any) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label className="text-xs md:col-span-2">
              <span className="mb-1 block text-muted-foreground">Environment</span>
              <select className={selectClass} value={selectedResidencyEnvId} onChange={(e) => setResidencyEnvId(e.target.value)}>
                {environments.map((env: any) => (
                  <option key={env.environment_id} value={env.environment_id}>{env.display_name || env.name}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={saveResidencyRule} disabled={busy === "residency-rule"}>
              {busy === "residency-rule" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <ShieldCheck className="mr-1 h-3 w-3" />}
              Save rule
            </Button>
            <Button size="sm" className="h-8 text-xs" onClick={checkResidency} disabled={!selectedResidencyEnvId || busy === "residency-check"}>
              {busy === "residency-check" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <CheckCircle2 className="mr-1 h-3 w-3" />}
              Check
            </Button>
          </div>
          <div className="mt-3 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
            {residencyResult ? (
              <div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className={cn("text-[10px]", residencyResult.allowed ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red")}>
                    {residencyResult.decision}
                  </Badge>
                  <span className="text-muted-foreground">{residencyResult.region_bucket}</span>
                </div>
                <div className="mt-2 text-[11px] text-muted-foreground">{(residencyResult.reasons || []).join(", ")}</div>
              </div>
            ) : (
              <div className="text-muted-foreground">Audit entries: {residency.audit?.length || 0}</div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card className="border-sylion-border bg-card p-4">
          <SectionTitle icon={ReceiptText} title="Cost tracking and alerts" right={<Badge variant="outline" className="text-[10px]">{money(costs.summary?.monthly_estimate_usd)} / month</Badge>} />
          <div className="mt-3 grid grid-cols-3 gap-2">
            {(costs.levels || []).map((level: any) => (
              <div key={level.id} className="rounded-md border border-sylion-border bg-secondary/10 p-3">
                <div className="text-xs font-medium capitalize">{level.id}</div>
                <div className="mt-1 text-[11px] text-muted-foreground">{level.rows?.length || 0} rows</div>
              </div>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
            <label className="text-xs md:col-span-2">
              <span className="mb-1 block text-muted-foreground">Environment</span>
              <select className={selectClass} value={selectedCostEnvId} onChange={(e) => setCostEnvId(e.target.value)}>
                {environments.map((env: any) => (
                  <option key={env.environment_id} value={env.environment_id}>{env.display_name || env.name}</option>
                ))}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">Budget cap</span>
              <input className={inputClass} value={budgetCap} onChange={(e) => setBudgetCap(e.target.value)} inputMode="decimal" />
            </label>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" className="h-8 text-xs" onClick={saveCostAlert} disabled={!selectedCostEnvId || busy === "cost-alert"}>
              {busy === "cost-alert" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <ReceiptText className="mr-1 h-3 w-3" />}
              Save alert
            </Button>
            <Badge variant="outline" className="h-8 px-2 py-2 text-[10px]">90d {money(costs.forecast?.next_90_days_usd)}</Badge>
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <SectionTitle icon={Trash2} title="Cleanup policy" right={<Badge variant="outline" className="text-[10px]">{cleanup.default_candidates?.length || 0} candidates</Badge>} />
          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
            {(cleanup.strategies || []).map((item: any) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setCleanupStrategy(item.id)}
                className={cn("rounded-md border p-3 text-left text-xs", cleanupStrategy === item.id ? "border-primary bg-primary/10" : "border-sylion-border bg-secondary/10")}
              >
                <div className="font-medium">{item.label}</div>
                <div className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">{item.description}</div>
              </button>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" className="h-8 text-xs" onClick={saveCleanupPolicy} disabled={!selectedCostEnvId || busy === "cleanup-policy"}>
              {busy === "cleanup-policy" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Trash2 className="mr-1 h-3 w-3" />}
              Save policy
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={createCleanupPlan} disabled={busy === "cleanup-plan"}>
              {busy === "cleanup-plan" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Workflow className="mr-1 h-3 w-3" />}
              Bulk plan
            </Button>
          </div>
          {cleanupPlan ? (
            <div className="mt-3 rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs text-muted-foreground">
              {cleanupPlan.candidates?.length || 0} candidates / savings {money(cleanupPlan.estimated_monthly_savings_usd)}
            </div>
          ) : null}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Card className="border-sylion-border bg-card p-4">
          <SectionTitle icon={Zap} title="Edge cases and inheritance" right={<Badge variant="outline" className="text-[10px]">{edgeCases.count || 0} runbooks</Badge>} />
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">Case</span>
              <select className={selectClass} value={selectedCaseId} onChange={(e) => setEdgeCaseId(e.target.value)}>
                {(edgeCases.cases || []).map((item: any) => <option key={item.id} value={item.id}>{item.id} - {item.title}</option>)}
              </select>
            </label>
            <label className="text-xs">
              <span className="mb-1 block text-muted-foreground">Goal</span>
              <select className={selectClass} value={inheritanceGoal} onChange={(e) => setInheritanceGoal(e.target.value)}>
                {["apps_internal", "public_products", "cybersecurity", "research"].map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <div className="flex items-end gap-2">
              <Button size="sm" className="h-8 text-xs" onClick={diagnoseEdgeCase} disabled={!selectedCaseId || busy === "edge-case"}>
                {busy === "edge-case" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Zap className="mr-1 h-3 w-3" />}
                Diagnose
              </Button>
              <Button variant="outline" size="sm" className="h-8 text-xs" onClick={resolveInheritance} disabled={busy === "inheritance"}>
                {busy === "inheritance" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <GitBranch className="mr-1 h-3 w-3" />}
                Resolve
              </Button>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
              <div className="font-medium">Runbook</div>
              <div className="mt-2 text-[11px] text-muted-foreground">{edgeDiagnosis?.case?.recommended_action || "No diagnosis yet"}</div>
            </div>
            <div className="rounded-md border border-sylion-border bg-secondary/10 p-3 text-xs">
              <div className="font-medium">Resolved policy</div>
              <div className="mt-2 grid grid-cols-2 gap-1 text-[11px] text-muted-foreground">
                {Object.entries(inheritanceResult?.resolved || {}).slice(0, 6).map(([key, value]) => (
                  <div key={key} className="truncate">{key}: {String(value)}</div>
                ))}
              </div>
            </div>
          </div>
        </Card>

        <Card className="border-sylion-border bg-card p-4">
          <SectionTitle icon={CheckCircle2} title="Phase 3 acceptance test" right={<Badge variant="outline" className={cn("text-[10px]", currentAcceptance.accepted ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber")}>{currentAcceptance.accepted ? "PASS" : "PENDING"}</Badge>} />
          <div className="mt-3 flex gap-2">
            <select className={selectClass} value={acceptanceGoal} onChange={(e) => setAcceptanceGoal(e.target.value)}>
              {["apps_internal", "public_products", "cybersecurity", "research"].map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <Button size="sm" className="h-9 text-xs" onClick={runAcceptance} disabled={busy === "acceptance"}>
              {busy === "acceptance" ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
              Run
            </Button>
          </div>
          <div className="mt-3 space-y-2">
            {(currentAcceptance.checks || []).slice(0, 6).map((check: any) => (
              <div key={check.id} className="flex items-start gap-2 rounded-md border border-sylion-border bg-secondary/10 p-2 text-xs">
                <CheckIcon status={check.status} />
                <div className="min-w-0">
                  <div className="truncate font-medium">{check.label}</div>
                  <div className="truncate text-[10px] text-muted-foreground">{check.evidence}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
