"use client";

import { useEffect, useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import {
  Users, ArrowLeft, RefreshCw, Trash2, Crown,
  AlertCircle, CheckCircle2, WifiOff, ShieldAlert,
} from "lucide-react";
import Link from "next/link";

interface Contact {
  contact_id: string; full_name: string; email: string;
  role: string; status: string;
}

const API_BASE = "/api/v1/reference/crm";

const ROLE_COLOR: Record<string, string> = {
  lead: "bg-gray-500/15 text-gray-700",
  customer: "bg-blue-500/15 text-blue-700",
  partner: "bg-purple-500/15 text-purple-700",
  vip: "bg-amber-500/15 text-amber-700",
};

const STATUS_COLOR: Record<string, string> = {
  active: "bg-green-500/15 text-green-700",
  deleted_gdpr: "bg-red-500/15 text-red-700",
  merged: "bg-gray-500/15 text-gray-700",
  archived: "bg-gray-500/15 text-gray-700",
};

export default function CrmReferencePage() {
  const { data: healthRaw } = useHealth();
  const backendLive = ((healthRaw as { status?: string })?.status === "ok");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [referenceStatus, setReferenceStatus] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!backendLive) return;
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/contacts`).then(r => r.json());
      setContacts(r.items || []);
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [backendLive]);

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
  }, [refresh]);

  const createContact = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const i = Math.floor(Math.random() * 100000);
      const r = await fetch(`${API_BASE}/contacts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actor_id: "op_reference", full_name: `User ${i}`,
          email: `user${i}@reference.com`, phone: `+48 ${i}`,
          role: "customer",
        }),
      }).then(r => r.json());
      setReferenceStatus(`Utworzono ${r.contact_id} - PII ukryte w audycie`);
      await refresh();
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [refresh]);

  const gdprDelete = useCallback(async (id: string) => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/contacts/${id}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor_id: "op_admin", hg_ticket_id: "hg_reference_001" }),
      });
      if (r.status === 200) {
        setReferenceStatus(`RODO usunęło ${id} - PII ukryte, audyt zachowany`);
        await refresh();
      } else {
        setError(`HTTP ${r.status}: ${(await r.json()).detail}`);
      }
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [refresh]);

  const tryGdprWithoutHg = useCallback(async () => {
    if (contacts.length === 0) return;
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/contacts/${contacts[0].contact_id}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor_id: "op_reference", hg_ticket_id: "" }),
      });
      if (r.status === 403) {
        setReferenceStatus("BLOCKED 403 (correct): GDPR delete requires hg_ticket_id (D4)");
      } else {
        setError(`Unexpected HTTP ${r.status}`);
      }
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [contacts]);

  const tryPromoteWithoutAdmin = useCallback(async () => {
    if (contacts.length === 0) return;
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/contacts/${contacts[0].contact_id}/role`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actor_id: "op_regular", new_role: "vip",
          actor_role: "operator", hg_ticket_id: "hg_x",
        }),
      });
      if (r.status === 403) {
        setReferenceStatus("BLOCKED 403 (correct): VIP promotion requires admin actor (D4)");
      } else {
        setError(`Unexpected HTTP ${r.status}`);
      }
    } catch (e: any) { setError(String(e?.message || e)); }
    finally { setLoading(false); }
  }, [contacts]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/test-center" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users className="w-6 h-6" />Operator CRM - D4 PII
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>{backendLive ? "LIVE" : "OFFLINE"}</Badge>
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
            <Button onClick={createContact} disabled={loading || !backendLive} className="w-full" size="sm">
              <Users className="w-4 h-4 mr-2" />Create contact
            </Button>
            <Button onClick={tryGdprWithoutHg} disabled={loading || !backendLive || contacts.length === 0} className="w-full" size="sm" variant="outline">
              <ShieldAlert className="w-4 h-4 mr-2" />Try GDPR delete w/o HG (should 403)
            </Button>
            <Button onClick={tryPromoteWithoutAdmin} disabled={loading || !backendLive || contacts.length === 0} className="w-full" size="sm" variant="outline">
              <Crown className="w-4 h-4 mr-2" />Try VIP w/o admin (should 403)
            </Button>
          </div>
          <div className="mt-4 text-xs text-muted-foreground space-y-1">
            <div className="font-semibold">W14 protections:</div>
            <div>- GDPR delete: PII redacted, audit kept</div>
            <div>- D4 governance gate: hg_ticket_id required</div>
            <div>- Audit log: PII auto-redacted</div>
            <div>- Role escalation: admin + HG for VIP</div>
            <div>- Merge conflict detection</div>
          </div>
        </Card>

        <Card className="p-4 col-span-2">
          <div className="font-semibold mb-3">Contacts ({contacts.length})</div>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {contacts.length === 0 && (
              <div className="text-sm text-muted-foreground text-center py-8">
                No contacts. Click &quot;Create contact&quot;.
              </div>
            )}
            {contacts.map(c => (
              <div key={c.contact_id} className="border rounded p-2 text-sm flex items-center justify-between">
                <div>
                  <div className="font-mono text-xs">{c.full_name}</div>
                  <div className="text-xs text-muted-foreground">{c.email}</div>
                </div>
                <div className="flex items-center gap-1">
                  <Badge variant="outline" className={`text-xs ${ROLE_COLOR[c.role]}`}>{c.role}</Badge>
                  <Badge variant="outline" className={`text-xs ${STATUS_COLOR[c.status]}`}>{c.status}</Badge>
                  {c.status === "active" && (
                    <Button onClick={() => gdprDelete(c.contact_id)}
                            disabled={loading || !backendLive}
                            size="sm" variant="ghost" className="h-6 w-6 p-0">
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

