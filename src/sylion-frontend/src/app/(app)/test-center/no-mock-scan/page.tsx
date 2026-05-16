"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Loader2,
  RefreshCw,
  ShieldAlert,
  WifiOff,
} from "lucide-react";

import { HelpTip } from "@/components/common/HelpTip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useHealth } from "@/lib/api/hooks";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface NoMockIssue {
  rule_id: string;
  severity: string;
  path: string;
  line: number;
  snippet: string;
  description: string;
  blocking: boolean;
}

interface NoMockScanResult {
  status: "PASS" | "FAIL";
  scanned_files: number;
  issue_count: number;
  blocking_count: number;
  issues: NoMockIssue[];
  rules: Array<{ rule_id: string; severity: string; description: string }>;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export default function NoMockScanPage() {
  const { data: healthRaw, refresh: refreshHealth } = useHealth();
  const backendLive = (healthRaw as { status?: string })?.status === "ok";
  const [scan, setScan] = useState<NoMockScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    try {
      setScan(await fetchJson<NoMockScanResult>("/api/v1/test-center/no-mock-scan"));
    } catch (err) {
      setScan(null);
      setError(err instanceof Error ? err.message : "Nie udało się uruchomi? skanera.");
    } finally {
      setLoading(false);
    }
  }, [backendLive]);

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
  }, [refresh]);

  const blockers = scan?.issues.filter((issue) => issue.blocking) ?? [];
  const allowed = scan?.issues.filter((issue) => !issue.blocking) ?? [];

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/test-center" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ShieldAlert className="w-6 h-6" />
            Skan uczciwości runtime
            <HelpTip text="Skanuje runtime UI/API i blokuje produkcyjne atrapy, banery testówe, panele bez backendu oraz puste odpowiedzi udające prawdziwy endpoint." />
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
            {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
          {scan && (
            <Badge variant={scan.status === "PASS" ? "default" : "destructive"}>
              {scan.status}
            </Badge>
          )}
        </div>
        <Button
          onClick={() => {
            refreshHealth();
            void refresh();
          }}
          disabled={loading}
          size="sm"
          variant="outline"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          <span className="ml-2">Uruchom skan</span>
        </Button>
      </div>

      {!backendLive && (
        <Card className="border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-700 flex items-center gap-2">
          <WifiOff className="w-4 h-4" />
          Backend offline. Skaner nie podstawia danych przykladowych.
        </Card>
      )}

      {error && (
        <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
          Błąd: {error}
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground">Status</div>
          <div className="text-2xl font-bold flex items-center gap-2">
            {scan?.status === "PASS" ? <CheckCircle2 className="w-5 h-5 text-emerald-500" /> : <AlertTriangle className="w-5 h-5 text-amber-500" />}
            {scan?.status ?? "not run"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground">Pliki</div>
          <div className="text-2xl font-bold">{scan?.scanned_files ?? 0}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground">Blokery</div>
          <div className="text-2xl font-bold">{scan?.blocking_count ?? 0}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground">Wszystkie trafienia</div>
          <div className="text-2xl font-bold">{scan?.issue_count ?? 0}</div>
        </Card>
      </div>

      <Card className="p-6">
        <div className="text-sm font-semibold mb-3">Blokujące trafienia</div>
        {blockers.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            Brak blokujących atrap i produkcyjnych podstawień w powierzchni runtime.
          </div>
        ) : (
          <div className="space-y-3">
            {blockers.map((issue) => (
              <div key={`${issue.path}:${issue.line}:${issue.rule_id}`} className="rounded-md border border-red-500/30 bg-red-500/5 p-3">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Badge variant="destructive">{issue.severity}</Badge>
                  {issue.rule_id}
                </div>
                <div className="mt-1 text-xs text-muted-foreground font-mono">
                  {issue.path}:{issue.line}
                </div>
                <div className="mt-2 text-sm">{issue.description}</div>
                <pre className="mt-2 overflow-auto rounded bg-background p-2 text-xs">{issue.snippet}</pre>
              </div>
            ))}
          </div>
        )}
      </Card>

      {allowed.length > 0 && (
        <Card className="p-6">
          <div className="text-sm font-semibold mb-3">Dozwolone wzmianki w laboratoriach demo / typach</div>
          <ul className="space-y-2 text-xs text-muted-foreground">
            {allowed.slice(0, 20).map((issue) => (
              <li key={`${issue.path}:${issue.line}:${issue.rule_id}`} className="font-mono">
                {issue.path}:{issue.line} - {issue.rule_id}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
