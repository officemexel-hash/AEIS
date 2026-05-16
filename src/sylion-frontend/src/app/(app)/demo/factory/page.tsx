"use client";

import { useEffect, useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import {
  Factory, ArrowLeft, RefreshCw, Shield, AlertTriangle,
  AlertCircle, CheckCircle2, WifiOff, ShieldAlert,
} from "lucide-react";
import Link from "next/link";

const API_BASE = "/api/v1/reference/factory";

export default function FactoryReferencePage() {
  const { data: healthRaw } = useHealth();
  const backendLive = ((healthRaw as { status?: string })?.status === "ok");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<string[]>([]);

  const log = useCallback((msg: string) => {
    setResults(r => [`${new Date().toLocaleTimeString()} ${msg}`, ...r].slice(0, 20));
  }, []);

  const runSafetyChainReference = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      // 1. Register cabinet
      const cab = await fetch(`${API_BASE}/cabinets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plant_id: "plant_reference", name: "Line A",
      plc_serial: "PLC-REF-" + Math.floor(Math.random() * 9999),
        }),
      }).then(r => r.json());
      log(`Cabinet registered: ${cab.cabinet_id}`);

      // 2. Take backup
      await fetch(`${API_BASE}/cabinets/${cab.cabinet_id}/backup`, { method: "POST" });
      log("Backup taken");

      // 3. E-stop test
      await fetch(`${API_BASE}/cabinets/${cab.cabinet_id}/estop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operator_id: "op_1", response_time_ms: 120, passed: true }),
      });
      log("E-stop tested (response 120ms < 500ms limit)");

      // 4. IO map
      const map = await fetch(`${API_BASE}/cabinets/${cab.cabinet_id}/iomap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          program_id: "prog_reference",
          expected_plc_serial: cab.plc_serial,
          io_signature: "b".repeat(64),
        }),
      }).then(r => r.json());
      log(`IO map created: ${map.mapping_id}`);

      // 5. Attempt upload (happy path with dryrun)
      const up = await fetch(`${API_BASE}/cabinets/${cab.cabinet_id}/upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mapping_id: map.mapping_id,
          program_sha256: "a".repeat(64),
          operator_id: "op_1", dryrun_passed: true,
        }),
      }).then(r => r.json());
      log(`Upload ready: ${up.upload_id} (passed all 5 D5 safety checks)`);
    } catch (e: any) {
      log(`ERROR: ${e?.message || e}`);
      setError(String(e?.message || e));
    } finally { setLoading(false); }
  }, [log]);

  const triggerNoBackupViolation = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const cab = await fetch(`${API_BASE}/cabinets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plant_id: "plant_x", name: "BadLine",
          plc_serial: "PLC-NOBACK-" + Math.floor(Math.random() * 9999),
        }),
      }).then(r => r.json());
      // Skip backup AND e-stop intentionally
      const map = await fetch(`${API_BASE}/cabinets/${cab.cabinet_id}/iomap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          program_id: "p", expected_plc_serial: cab.plc_serial,
          io_signature: "b".repeat(64),
        }),
      }).then(r => r.json());
      const r = await fetch(`${API_BASE}/cabinets/${cab.cabinet_id}/upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mapping_id: map.mapping_id,
          program_sha256: "a".repeat(64),
          operator_id: "op_x", dryrun_passed: true,
        }),
      });
      const result = await r.json();
      if (r.status === 422) {
        log(`BLOCKED 422 (correct): ${result.detail}`);
      } else {
        log(`UNEXPECTED: HTTP ${r.status}`);
      }
    } catch (e: any) { log(`ERROR: ${e?.message || e}`); }
    finally { setLoading(false); }
  }, [log]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Link href="/test-center" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Factory className="w-6 h-6" />
          Panel automatyzacji fabryki - referencja D5
        </h1>
        <Badge variant={backendLive ? "default" : "outline"}>
          {backendLive ? "LIVE" : "OFFLINE"}
        </Badge>
        <Badge variant="outline" className="bg-red-500/10 text-red-700">D5 SAFETY</Badge>
      </div>

      {!backendLive && (
        <Card className="border-amber-500/30 bg-amber-500/5 p-3">
          <div className="flex items-center gap-2 text-sm text-amber-700">
            <WifiOff className="w-4 h-4" />Backend offline. D5 safety actions disabled.
          </div>
        </Card>
      )}
      {error && <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
        <AlertCircle className="w-4 h-4 inline mr-2" />{error}</Card>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4">
          <div className="font-semibold mb-3 flex items-center gap-2">
            <Shield className="w-4 h-4 text-green-600" />
            Happy path: full safety chain
          </div>
          <Button onClick={runSafetyChainReference} disabled={loading || !backendLive} className="w-full" size="sm">
            Run 5-step safety chain reference
          </Button>
          <div className="text-xs text-muted-foreground mt-3 space-y-1">
            <div>1. Register cabinet (PLC serial)</div>
            <div>2. Take backup</div>
            <div>3. Test e-stop (&lt;500ms response)</div>
            <div>4. Define IO map (expected PLC serial)</div>
            <div>5. Upload (with dry-run pass)</div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="font-semibold mb-3 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-red-600" />
            Adversarial: skip backup
          </div>
          <Button onClick={triggerNoBackupViolation} disabled={loading || !backendLive} className="w-full" size="sm" variant="outline">
            Try upload without backup (should 422)
          </Button>
          <div className="text-xs text-muted-foreground mt-3 space-y-1">
            <div>D5 safety chain rejects:</div>
            <div>- Wrong cabinet (PLC mismatch)</div>
            <div>- Missing backup (24h freshness)</div>
            <div>- Missing e-stop test (7 day freshness)</div>
            <div>- Failed dry-run</div>
            <div>- Interlock override w/o Council</div>
          </div>
        </Card>
      </div>

      <Card className="p-4">
        <div className="font-semibold mb-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          Activity log
        </div>
        <div className="space-y-1 max-h-64 overflow-y-auto text-xs font-mono">
          {results.length === 0 && (
            <div className="text-muted-foreground text-center py-4">
              No activity yet. Click a reference button.
            </div>
          )}
          {results.map((r, i) => (
            <div key={i} className={r.includes("ERROR") || r.includes("BLOCKED") ? "text-red-600" : "text-green-600"}>
              {r}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

