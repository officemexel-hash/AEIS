"use client";

import { useEffect, useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import {
  DollarSign, ArrowLeft, RefreshCw, FileText, Send,
  AlertCircle, CheckCircle2, WifiOff, Clock, AlertTriangle,
} from "lucide-react";
import Link from "next/link";

const API_BASE = "/api/v1/reference/funding";

const STATUS_COLOR: Record<string, string> = {
  draft: "bg-gray-500/15 text-gray-700",
  pending_signature: "bg-amber-500/15 text-amber-700",
  ready_to_submit: "bg-blue-500/15 text-blue-700",
  submitted: "bg-green-500/15 text-green-700",
  accepted: "bg-green-500/15 text-green-700",
  rejected: "bg-red-500/15 text-red-700",
  withdrawn: "bg-gray-500/15 text-gray-700",
};

export default function FundingReferencePage() {
  const { data: healthRaw } = useHealth();
  const backendLive = ((healthRaw as { status?: string })?.status === "ok");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<string[]>([]);
  const [appId, setAppId] = useState<string | null>(null);

  const log = useCallback((msg: string) => {
    setResults(r => [`${new Date().toLocaleTimeString()} ${msg}`, ...r].slice(0, 20));
  }, []);

  const happyPath = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const app = await fetch(`${API_BASE}/applications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          submitter_id: "op_reference",
          grant_program: "HORIZON-EU-CLUSTER-4",
          title: "AI for Healthcare",
          deadline_ts: Date.now() / 1000 + 30 * 86400,
          requested_amount_eur: 500_000,
        }),
      }).then(r => r.json());
      setAppId(app.application_id);
      log(`Application: ${app.application_id} (deadline +30d)`);

      await fetch(`${API_BASE}/applications/${app.application_id}/attachments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: "proposal.pdf", sha256: "a".repeat(64),
          size_bytes: 1024 * 1024, mime_type: "application/pdf",
        }),
      });
      log("Attachment 1MB attached (within 20MB cap)");

      await fetch(`${API_BASE}/applications/${app.application_id}/signatures`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          signer_id: "ceo_1", signer_role: "CEO",
          cert_serial: "C001",
          expires_at: Date.now() / 1000 + 365 * 86400,
        }),
      });
      log("CEO signature added (cert valid 1 year)");

      const sub = await fetch(`${API_BASE}/applications/${app.application_id}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hg_ticket_id: "hg_d4_external_001" }),
      }).then(r => r.json());
      log(`SUBMITTED: ${sub.status} (D4 external_action gate passed)`);
    } catch (e: any) { log(`ERROR: ${e?.message || e}`); }
    finally { setLoading(false); }
  }, [log]);

  const tryWithoutHg = useCallback(async () => {
    if (!appId) return;
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/applications/${appId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hg_ticket_id: "" }),
      });
      if (r.status === 403) {
        log(`BLOCKED 403 (correct): submit requires hg_ticket_id (D4)`);
      } else { log(`Unexpected HTTP ${r.status}`); }
    } catch (e: any) { log(`ERROR: ${e?.message || e}`); }
    finally { setLoading(false); }
  }, [appId, log]);

  const tryOversizedAttachment = useCallback(async () => {
    if (!appId) return;
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/applications/${appId}/attachments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: "huge.pdf", sha256: "b".repeat(64),
          size_bytes: 25 * 1024 * 1024,  // 25MB > 20MB cap
        }),
      });
      if (r.status === 413) {
        log(`BLOCKED 413 (correct): attachment >20MB hard cap`);
      } else { log(`Unexpected HTTP ${r.status}`); }
    } catch (e: any) { log(`ERROR: ${e?.message || e}`); }
    finally { setLoading(false); }
  }, [appId, log]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Link href="/test-center" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <DollarSign className="w-6 h-6" />Pipeline finansowania - akcja zewnętrzna D4
        </h1>
        <Badge variant={backendLive ? "default" : "outline"}>{backendLive ? "LIVE" : "OFFLINE"}</Badge>
      </div>

      {!backendLive && <Card className="border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-700">
        <WifiOff className="w-4 h-4 inline mr-2" />Backend offline.</Card>}
      {error && <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
        <AlertCircle className="w-4 h-4 inline mr-2" />{error}</Card>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4">
          <div className="font-semibold mb-3">Happy path</div>
          <Button onClick={happyPath} disabled={loading || !backendLive} className="w-full" size="sm">
            <Send className="w-4 h-4 mr-2" />Run full submission flow
          </Button>
          <div className="text-xs text-muted-foreground mt-3 space-y-1">
            <div>1. Create application (deadline +30d)</div>
            <div>2. Attach proposal.pdf (1MB)</div>
            <div>3. Add CEO signature (cert valid)</div>
            <div>4. Submit to external portal (with HG)</div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-600" />Adversarial
          </div>
          <div className="space-y-2">
            <Button onClick={tryWithoutHg} disabled={loading || !backendLive || !appId} className="w-full" size="sm" variant="outline">
              Submit w/o HG (should 403)
            </Button>
            <Button onClick={tryOversizedAttachment} disabled={loading || !backendLive || !appId} className="w-full" size="sm" variant="outline">
              Attach 25MB file (should 413)
            </Button>
          </div>
          <div className="text-xs text-muted-foreground mt-3 space-y-1">
            <div className="font-semibold">W14 D4 protections:</div>
            <div>- Per-file 20MB / total 100MB cap</div>
            <div>- Deadline enforced (no clock drift)</div>
            <div>- Signature freshness {"<"}30 days</div>
            <div>- Cert validity check</div>
            <div>- External submit requires HG</div>
          </div>
        </Card>
      </div>

      <Card className="p-4">
        <div className="font-semibold mb-3 flex items-center gap-2">
          <FileText className="w-4 h-4" />Activity log
        </div>
        <div className="space-y-1 max-h-64 overflow-y-auto text-xs font-mono">
          {results.length === 0 && <div className="text-muted-foreground text-center py-4">No activity yet.</div>}
          {results.map((r, i) => (
            <div key={i} className={r.includes("ERROR") || r.includes("BLOCKED") ? "text-red-600" : "text-green-600"}>{r}</div>
          ))}
        </div>
      </Card>
    </div>
  );
}

