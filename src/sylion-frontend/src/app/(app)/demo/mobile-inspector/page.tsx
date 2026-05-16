"use client";

import { useEffect, useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import {
  Smartphone, ArrowLeft, RefreshCw, MapPin, Camera, FileSignature,
  CheckCircle2, AlertCircle, WifiOff, Cloud, AlertTriangle,
} from "lucide-react";
import Link from "next/link";

interface Inspection {
  inspection_id: string;
  inspector_id: string;
  project_id: string;
  location_label: string;
  status: string;
  revision: number;
  created_at: number;
  synced_at: number | null;
  has_gps: boolean;
}

interface QueueEntry {
  queue_id: string;
  inspection_id: string;
  queued_at: number;
  attempt_count: number;
  last_error: string | null;
}

const STATUS_COLOR: Record<string, string> = {
  draft: "bg-gray-500/15 text-gray-700",
  ready_to_sync: "bg-blue-500/15 text-blue-700",
  syncing: "bg-amber-500/15 text-amber-700",
  synced: "bg-green-500/15 text-green-700",
  failed: "bg-red-500/15 text-red-700",
  rejected: "bg-red-500/15 text-red-700",
};

const API_BASE = "/api/v1/reference/mobile-inspector";

export default function MobileInspectorReferencePage() {
  const { data: healthRaw } = useHealth();
  const backendLive = ((healthRaw as { status?: string })?.status === "ok");

  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [referenceStatus, setReferenceStatus] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    try {
      const [insp, q] = await Promise.all([
        fetch(`${API_BASE}/inspections`).then(r => r.json()),
        fetch(`${API_BASE}/queue`).then(r => r.json()),
      ]);
      setInspections(insp.items || []);
      setQueue(q.items || []);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [backendLive]);

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
  }, [refresh]);

  const createReferenceInspection = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Create inspection
      const create = await fetch(`${API_BASE}/inspections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          inspector_id: "reference_op_" + Math.floor(Math.random() * 1000),
          project_id: "proj_reference",
          location_label: "Reference Site",
          notes: "Auto-created by UI reference",
          gps: { lat: 52.23, lon: 21.01, accuracy_m: 10.0 },
        }),
      }).then(r => r.json());
      const iid = create.inspection_id;

      // 2. Attach photo
      await fetch(`${API_BASE}/inspections/${iid}/photo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sha256: "a".repeat(64),
          size_bytes: 524288,
          mime_type: "image/jpeg",
        }),
      });

      // 3. Attach signature
      await fetch(`${API_BASE}/inspections/${iid}/signature`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          signer_id: create.inspector_id || "reference_op",
          signature_data_b64: "x".repeat(120),
        }),
      });

      // 4. Queue for sync (uses revision 1 - gps update bumped revision once)
      await fetch(
        `${API_BASE}/inspections/${iid}/queue?expected_revision=0`,
        { method: "POST" },
      );

      setReferenceStatus(`Created ${iid} + photo + signature + queued`);
      await refresh();
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [refresh]);

  const syncAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/queue/sync`, { method: "POST" })
        .then(r => r.json());
      setReferenceStatus(`Sync: ${r.success}/${r.total} success`);
      await refresh();
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }, [refresh]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/test-center" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Smartphone className="w-6 h-6" />
            Mobilny inspektor terenowy - referencja E11
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
            {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
        </div>
        <div className="flex gap-2">
          <Button onClick={refresh} disabled={loading || !backendLive} size="sm" variant="outline">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            <span className="ml-2">Refresh</span>
          </Button>
        </div>
      </div>

      {!backendLive && (
        <Card className="border-amber-500/30 bg-amber-500/5 p-3">
          <div className="flex items-center gap-2 text-sm text-amber-700">
            <WifiOff className="w-4 h-4" />
            Backend offline. Destructive actions disabled (offline-action guard).
          </div>
        </Card>
      )}

      {error && (
        <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
          <AlertCircle className="w-4 h-4 inline mr-2" />
          {error}
        </Card>
      )}

      {referenceStatus && (
        <Card className="border-green-500/30 bg-green-500/5 p-3 text-sm text-green-700">
          <CheckCircle2 className="w-4 h-4 inline mr-2" />
          {referenceStatus}
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 col-span-1">
          <div className="font-semibold mb-3">Reference actions</div>
          <div className="space-y-2">
            <Button onClick={createReferenceInspection} disabled={loading || !backendLive}
                    className="w-full" size="sm">
              <MapPin className="w-4 h-4 mr-2" />
              Create reference inspection
            </Button>
            <Button onClick={syncAll} disabled={loading || !backendLive || queue.length === 0}
                    className="w-full" size="sm" variant="outline">
              <Cloud className="w-4 h-4 mr-2" />
              Sync all ({queue.length})
            </Button>
          </div>
          <div className="mt-4 text-xs text-muted-foreground space-y-1">
            <div className="font-semibold">W14 protections active:</div>
            <div>- GPS range + drift &lt; 5km</div>
            <div>- Photo SHA256 + size 1KB-25MB</div>
            <div>- Signature required for sync</div>
            <div>- Konflikt rewizji (wiele kart) -&gt; 409</div>
          </div>
        </Card>

        <Card className="p-4 col-span-2">
          <div className="font-semibold mb-3 flex items-center justify-between">
            <span>Inspections ({inspections.length})</span>
            <Badge variant="outline" className="text-xs">
              {inspections.filter(i => i.status === "synced").length} synced
            </Badge>
          </div>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {inspections.length === 0 && (
              <div className="text-sm text-muted-foreground text-center py-8">
                No inspections yet. Click &quot;Create reference inspection&quot; to start.
              </div>
            )}
            {inspections.map(i => (
              <div key={i.inspection_id} className="border rounded p-2 text-sm">
                <div className="flex items-center justify-between">
                  <div className="font-mono text-xs">{i.inspection_id}</div>
                  <Badge variant="outline" className={`text-xs ${STATUS_COLOR[i.status] || ""}`}>
                    {i.status}
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {i.inspector_id} - rewizja {i.revision}
                  {i.has_gps && <span className="ml-2"><MapPin className="w-3 h-3 inline" /></span>}
                  {i.synced_at && (
                    <span className="ml-2 text-green-600">
                      <CheckCircle2 className="w-3 h-3 inline" /> synced
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {queue.length > 0 && (
        <Card className="p-4">
          <div className="font-semibold mb-3 flex items-center gap-2">
            <Cloud className="w-4 h-4" />
            Offline Sync Queue ({queue.length})
          </div>
          <div className="space-y-2">
            {queue.map(q => (
              <div key={q.queue_id} className="text-sm flex items-center justify-between border rounded p-2">
                <div className="font-mono text-xs">{q.inspection_id}</div>
                <div className="flex items-center gap-2 text-xs">
                  {q.attempt_count > 0 && (
                    <Badge variant="outline" className="text-xs text-amber-700">
                      <AlertTriangle className="w-3 h-3 mr-1" />
                      attempt {q.attempt_count}
                    </Badge>
                  )}
                  {q.last_error && (
                    <span className="text-red-600 truncate max-w-xs" title={q.last_error}>
                      {q.last_error.slice(0, 60)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="text-xs text-muted-foreground text-center">
        Referencja E11 - pełna implementacja per projekt. Backend: 11 endpointów REST,
        38 tests pass. UI: minimal MVP showcasing W14 guards.
      </div>
    </div>
  );
}

