"use client";

import { useEffect, useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import {
  Globe, ArrowLeft, RefreshCw, Eye, MessageSquare, Mail,
  AlertCircle, CheckCircle2, WifiOff,
} from "lucide-react";
import Link from "next/link";

interface Project {
  project_id: string; slug: string; title: string;
  view_count: number; owner_id: string;
}

const API_BASE = "/api/v1/reference/portal";

export default function PortalReferencePage() {
  const { data: healthRaw } = useHealth();
  const backendLive = ((healthRaw as { status?: string })?.status === "ok");

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [referenceStatus, setReferenceStatus] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!backendLive) return;
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/projects`).then(r => r.json());
      setProjects(r.items || []);
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [backendLive]);

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
  }, [refresh]);

  const createReference = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const slug = `reference-${Math.floor(Math.random() * 100000)}`;
      const r = await fetch(`${API_BASE}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          owner_id: "reference_op_" + Math.floor(Math.random() * 1000),
          slug, title: "Reference Project " + slug,
          description: "Auto-created showcase project",
          visibility: "public",
        }),
      }).then(r => r.json());
      setReferenceStatus(`Created project ${r.project_id}`);
      await refresh();
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [refresh]);

  const triggerSpamLimit = useCallback(async () => {
    setLoading(true); setError(null);
    let blocked = false;
    try {
      for (let i = 0; i < 4; i++) {
        const r = await fetch(`${API_BASE}/contact`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: null,
            submitter_email: `spam${i}@x.com`,
            body: "spam test",
            submitter_ip: "9.9.9.9",
          }),
        });
        if (r.status === 429) { blocked = true; break; }
      }
      setReferenceStatus(blocked
        ? "Rate-limit uruchomiony (4. zgłoszenie zablokowane HTTP 429) - antyspam działa"
        : "All 4 submissions accepted (limit not reached?)");
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, []);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/test-center" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Globe className="w-6 h-6" />
            Publiczna prezentacja projektu - referencja D3
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
            {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
        </div>
        <Button onClick={refresh} disabled={loading || !backendLive} size="sm" variant="outline">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {!backendLive && (
        <Card className="border-amber-500/30 bg-amber-500/5 p-3">
          <div className="flex items-center gap-2 text-sm text-amber-700">
            <WifiOff className="w-4 h-4" />Backend offline. Destructive actions disabled.
          </div>
        </Card>
      )}
      {error && <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
        <AlertCircle className="w-4 h-4 inline mr-2" />{error}</Card>}
      {referenceStatus && <Card className="border-green-500/30 bg-green-500/5 p-3 text-sm text-green-700">
        <CheckCircle2 className="w-4 h-4 inline mr-2" />{referenceStatus}</Card>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="font-semibold mb-3">Reference actions</div>
          <div className="space-y-2">
            <Button onClick={createReference} disabled={loading || !backendLive} className="w-full" size="sm">
              <Globe className="w-4 h-4 mr-2" />Create reference project
            </Button>
            <Button onClick={triggerSpamLimit} disabled={loading || !backendLive} className="w-full" size="sm" variant="outline">
              <Mail className="w-4 h-4 mr-2" />Test rate-limit (4 contacts)
            </Button>
          </div>
          <div className="mt-4 text-xs text-muted-foreground space-y-1">
            <div className="font-semibold">W14 protections active:</div>
            <div>- RBAC: 4 viewer roles (public/auth/owner/admin)</div>
            <div>- IDOR guard on edit (owner check)</div>
            <div>- Rate-limit: 3 submissions/IP/min</div>
            <div>- Slug uniqueness</div>
          </div>
        </Card>

        <Card className="p-4 col-span-2">
          <div className="font-semibold mb-3 flex items-center justify-between">
            <span>Public projects ({projects.length})</span>
            <Badge variant="outline" className="text-xs">
              <Eye className="w-3 h-3 mr-1" />
              {projects.reduce((s, p) => s + p.view_count, 0)} total views
            </Badge>
          </div>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {projects.length === 0 && (
              <div className="text-sm text-muted-foreground text-center py-8">
                No projects yet. Click &quot;Create reference project&quot;.
              </div>
            )}
            {projects.map(p => (
              <div key={p.project_id} className="border rounded p-2 text-sm">
                <div className="flex items-center justify-between">
                  <div className="font-mono text-xs">{p.slug}</div>
                  <Badge variant="outline" className="text-xs">
                    <Eye className="w-3 h-3 mr-1" />{p.view_count}
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground mt-1">{p.title}</div>
                <div className="text-xs text-muted-foreground">owner: {p.owner_id}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

