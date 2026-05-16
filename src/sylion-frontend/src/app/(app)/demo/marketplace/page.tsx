"use client";

import { useEffect, useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import {
  Package, ArrowLeft, RefreshCw, Shield, Bug,
  AlertCircle, CheckCircle2, WifiOff, ShieldAlert,
} from "lucide-react";
import Link from "next/link";

interface Skill {
  skill_id: string; name: string; version: string;
  status: string; cost_budget_usd: number;
}

const API_BASE = "/api/v1/reference/marketplace";

const STATUS_COLOR: Record<string, string> = {
  uploaded: "bg-gray-500/15 text-gray-700",
  scanning: "bg-amber-500/15 text-amber-700",
  scan_failed: "bg-red-500/15 text-red-700",
  ready_for_review: "bg-blue-500/15 text-blue-700",
  approved: "bg-green-500/15 text-green-700",
  rejected: "bg-red-500/15 text-red-700",
  deprecated: "bg-gray-500/15 text-gray-700",
};

export default function MarketplaceReferencePage() {
  const { data: healthRaw } = useHealth();
  const backendLive = ((healthRaw as { status?: string })?.status === "ok");
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [referenceStatus, setReferenceStatus] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!backendLive) return;
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/skills`).then(r => r.json());
      setSkills(r.items || []);
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [backendLive]);

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
  }, [refresh]);

  const uploadCleanSkill = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const i = Math.floor(Math.random() * 100000);
      const s = await fetch(`${API_BASE}/skills`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `clean-skill-${i}`, version: "1.0.0",
          author_id: "reference_author",
          sha256: "a".repeat(64),
          signature_pubkey: "x".repeat(64),
          description: "Reference clean skill",
          cost_budget_usd: 5.0,
        }),
      }).then(r => r.json());

      // Run clean scan
      const scan = await fetch(`${API_BASE}/skills/${s.skill_id}/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ findings: [] }),
      }).then(r => r.json());

      // Approve with Council
      const ap = await fetch(`${API_BASE}/skills/${s.skill_id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ council_session_id: "cs_d5_marketplace_001" }),
      }).then(r => r.json());

      setReferenceStatus(`Clean skill ${s.name}: scan ${scan.severity_max} -> ${ap.status}`);
      await refresh();
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [refresh]);

  const uploadMaliciousSkill = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const i = Math.floor(Math.random() * 100000);
      const s = await fetch(`${API_BASE}/skills`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `malicious-${i}`, version: "1.0.0",
          author_id: "attacker_reference",
          sha256: "b".repeat(64),
          signature_pubkey: "y".repeat(64),
          description: "Reference malicious skill",
          cost_budget_usd: 5.0,
        }),
      }).then(r => r.json());

      // Run scan with critical finding
      const scan = await fetch(`${API_BASE}/skills/${s.skill_id}/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          findings: [
            { severity: "critical", rule: "shell_injection",
              file: "exec.py", line: 42 },
          ],
        }),
      }).then(r => r.json());

      // Try approve (should fail)
      const apResp = await fetch(`${API_BASE}/skills/${s.skill_id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ council_session_id: "cs_d5_001" }),
      });
      if (apResp.status === 422) {
        setReferenceStatus(`Scan severity_max=${scan.severity_max}, status=${scan.skill_status}; approval BLOCKED 422 (correct)`);
      } else {
        setReferenceStatus(`Unexpected approve HTTP ${apResp.status}`);
      }
      await refresh();
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [refresh]);

  const tryApproveWithoutCouncil = useCallback(async () => {
    const ready = skills.find(s => s.status === "ready_for_review");
    if (!ready) {
      setReferenceStatus("No skill in ready_for_review status to test");
      return;
    }
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/skills/${ready.skill_id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ council_session_id: "" }),
      });
      if (r.status === 403) {
        setReferenceStatus("BLOCKED 403 (correct): D5 approval requires council_session_id");
      } else {
        setReferenceStatus(`Unexpected HTTP ${r.status}`);
      }
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [skills]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/test-center" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Package className="w-6 h-6" />Rynek umiejętności - łańcuch dostaw D5
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>{backendLive ? "LIVE" : "OFFLINE"}</Badge>
          <Badge variant="outline" className="bg-red-500/10 text-red-700">D5</Badge>
        </div>
        <Button onClick={refresh} disabled={loading || !backendLive} size="sm" variant="outline">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {!backendLive && <Card className="border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-700">
        <WifiOff className="w-4 h-4 inline mr-2" />Backend offline.</Card>}
      {error && <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
        <AlertCircle className="w-4 h-4 inline mr-2" />{error}</Card>}
      {referenceStatus && <Card className="border-green-500/30 bg-green-500/5 p-3 text-sm text-green-700">
        <CheckCircle2 className="w-4 h-4 inline mr-2" />{referenceStatus}</Card>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="font-semibold mb-3">Reference actions</div>
          <div className="space-y-2">
            <Button onClick={uploadCleanSkill} disabled={loading || !backendLive} className="w-full" size="sm">
              <Shield className="w-4 h-4 mr-2" />Upload clean skill (full flow)
            </Button>
            <Button onClick={uploadMaliciousSkill} disabled={loading || !backendLive} className="w-full" size="sm" variant="outline">
              <Bug className="w-4 h-4 mr-2" />Upload malicious (should block)
            </Button>
            <Button onClick={tryApproveWithoutCouncil} disabled={loading || !backendLive} className="w-full" size="sm" variant="outline">
              <ShieldAlert className="w-4 h-4 mr-2" />Try approve w/o Council
            </Button>
          </div>
          <div className="mt-4 text-xs text-muted-foreground space-y-1">
            <div className="font-semibold">W14 D5 protections:</div>
            <div>- Anti-typosquat: name+version unique</div>
            <div>- Mandatory static scan</div>
            <div>- High/critical findings -&gt; auto fail</div>
            <div>- Council session required (D5)</div>
            <div>- Per-skill cost budget guard</div>
          </div>
        </Card>

        <Card className="p-4 col-span-2">
          <div className="font-semibold mb-3">Skills ({skills.length})</div>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {skills.length === 0 && (
              <div className="text-sm text-muted-foreground text-center py-8">No skills. Try uploading.</div>
            )}
            {skills.map(s => (
              <div key={s.skill_id} className="border rounded p-2 text-sm">
                <div className="flex items-center justify-between">
                  <div className="font-mono text-xs">{s.name}@{s.version}</div>
                  <Badge variant="outline" className={`text-xs ${STATUS_COLOR[s.status]}`}>{s.status}</Badge>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  budget: ${s.cost_budget_usd.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

