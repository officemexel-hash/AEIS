"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, ArrowLeft, CheckCircle2, Loader2, RefreshCw, WifiOff } from "lucide-react";

import { HelpTip } from "@/components/common/HelpTip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useHealth } from "@/lib/api/hooks";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface DashboardData {
  as_of: number;
  project_id: string | null;
  charters: {
    total: number;
    approved: number;
    in_review: number;
  };
  findings: {
    total: number;
    by_severity: Record<string, number>;
    by_status: Record<string, number>;
    open_p0_p1: number;
  };
  recent_runs: Array<{
    run_id: string;
    status: string;
    started_at?: number;
    completed_at?: number;
    duration_ms?: number;
    cost_usd?: number;
  }>;
}

interface ReleaseGateData {
  as_of: number;
  project_id: string;
  report: {
    status: string;
    checklist_results: Record<string, boolean>;
    blockers: string[];
  };
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export default function TestCenterDashboardPage() {
  const { data: healthRaw, refresh: refreshHealth } = useHealth();
  const backendLive = (healthRaw as { status?: string })?.status === "ok";
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [gate, setGate] = useState<ReleaseGateData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState("");

  const refresh = useCallback(async () => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    try {
      const dashboardQuery = projectId.trim()
        ? `?project_id=${encodeURIComponent(projectId.trim())}`
        : "";
      const gateProjectId = projectId.trim() || "proj_test_center_manual";
      const [dashboardData, gateData] = await Promise.all([
        fetchJson<DashboardData>(`/api/v1/test-center/dashboard${dashboardQuery}`),
        fetchJson<ReleaseGateData>(
          `/api/v1/test-center/release-gate?project_id=${encodeURIComponent(gateProjectId)}`,
        ),
      ]);
      setDashboard(dashboardData);
      setGate(gateData);
    } catch (err) {
      setDashboard(null);
      setGate(null);
      setError(err instanceof Error ? err.message : "Nie udało się pobrać danych test-center.");
    } finally {
      setLoading(false);
    }
  }, [backendLive, projectId]);

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
  }, [refresh]);

  const criticalCount = dashboard?.findings.open_p0_p1 ?? 0;
  const gateStatus = gate?.report.status ?? "not_evaluated";
  const blockers = gate?.report.blockers ?? [];

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/test-center" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Activity className="w-6 h-6" />
            Pulpit testów projektu
            <HelpTip text="Centralny widok zdrowia testówego: liczba chartersow, krytyczne findingi P0/P1 oraz status Release Gate z backendu W14." />
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
            {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground flex items-center" htmlFor="test-dashboard-project-id">
            project_id
            <HelpTip text="Opcjonalny filtr projektu. Dashboard i Release Gate zostana policzone dla tego samego projektu, zamiast mieszac wyniki globalne z audit-project." />
          </label>
          <input
            id="test-dashboard-project-id"
            placeholder="project_id (opcjonalnie)"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            className="text-xs px-2 py-1 border rounded font-mono w-56"
          />
          <Button
            onClick={() => {
              refreshHealth();
              void refresh();
            }}
            disabled={loading}
            size="sm"
            variant="outline"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            <span className="ml-2">Odśwież</span>
          </Button>
        </div>
      </div>

      {!backendLive && (
        <Card className="border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-700 flex items-center gap-2">
          <WifiOff className="w-4 h-4" />
          Backend test-center jest niedostępny. Ekran nie podstawia danych przykladowych.
        </Card>
      )}

      {error && (
        <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
          Błąd: {error}
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground flex items-center">
            Chartery
            <HelpTip text="Liczba Test Charters odczytana z /api/v1/test-center/dashboard. Clean-state moze miec 0." />
          </div>
          <div className="text-2xl font-bold">{dashboard?.charters.total ?? 0}</div>
          <div className="text-[11px] text-muted-foreground">
            approved {dashboard?.charters.approved ?? 0} / in_review {dashboard?.charters.in_review ?? 0}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Krytyczne P0/P1
            <HelpTip text="Każdy otwarty P0/P1 blokuje Release Gate. Wartosc pochodzi z backendu, nie z lokalnej listy." />
          </div>
          <div className="text-2xl font-bold">{criticalCount}</div>
          <div className="text-[11px] text-muted-foreground">
            total findings {dashboard?.findings.total ?? 0}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase text-muted-foreground flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> Bramka wdrozenia
            <HelpTip text={`Release Gate dla ${projectId.trim() || "proj_test_center_manual"}. Backend zwraca checklisty RC/PROD i blokery.`} />
          </div>
          <div className="text-2xl font-bold capitalize">
            {gateStatus.replaceAll("_", " ")}
          </div>
          <div className="text-[11px] text-muted-foreground">
            blockers {blockers.length}
          </div>
        </Card>
      </div>

      <Card className="p-6">
        <div className="text-sm font-semibold mb-2 flex items-center">
          Ostatnie uruchomienia
          <HelpTip text="Ostatnie TestRun z backendowego agregatora. Brak pozycji w clean-state jest prawidlowym wynikiem." />
        </div>
        {dashboard?.recent_runs.length ? (
          <ul className="text-sm space-y-1">
            {dashboard.recent_runs.slice(0, 8).map((run) => (
              <li key={run.run_id} className="flex items-center gap-2">
                <Badge variant="outline">{run.status}</Badge>
                <span className="text-xs text-muted-foreground font-mono">{run.run_id}</span>
                <span className="text-xs text-muted-foreground">
                  {run.duration_ms ?? 0} ms / ${Number(run.cost_usd ?? 0).toFixed(4)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-sm text-muted-foreground">Brak uruchomien testów w aktualnym clean-state.</div>
        )}
      </Card>

      <Card className="p-6">
        <div className="text-sm font-semibold mb-2 flex items-center">
          Blokery bramki wdrozenia
          <HelpTip text="Lista niespelnionych warunkow z Release Gate. Dopoki nie jest pusta, release pozostaje blocked." />
        </div>
        {blockers.length === 0 ? (
          <div className="text-sm text-muted-foreground">Brak blokerow.</div>
        ) : (
          <ul className="text-sm list-disc pl-5">
            {blockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
