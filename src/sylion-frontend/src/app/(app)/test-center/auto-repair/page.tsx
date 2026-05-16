"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import { GitBranch, ArrowLeft, RefreshCw } from "lucide-react";
import { HelpTip } from "@/components/common/HelpTip";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "";

interface RepairSession {
  finding_id: string;
  title: string;
  severity: string;
  d_level: string;
  r_status: string;
  attempts_used: number;
  attempts_max: number;
  files_touched_total: number;
  diff_lines_total: number;
  started_at: number;
}

interface LoopReport {
  report_id: string;
  loop_type: string;
  finding_id: string;
  created_at: number;
}

interface RepairData {
  as_of: number;
  project_id?: string;
  project_scope: string;
  limits: Record<string, number>;
  open_count: number;
  global_hidden_count: number;
  archived_global_count: number;
  active_sessions: RepairSession[];
  loop_reports_total: number;
  loop_reports_recent: LoopReport[];
}

interface LoopGuardSimulationResult {
  project_id: string;
  reason: string;
  loop_report?: {
    report_id: string;
    loop_type: string;
    attempts_n: number;
  };
  human_gate?: {
    request_id: string;
    status: string;
  };
  blocked_actions?: string[];
}

const SEVERITY_COLOR: Record<string, string> = {
  P0: "bg-rose-500/15 text-rose-700",
  P1: "bg-rose-500/15 text-rose-700",
  P2: "bg-amber-500/15 text-amber-700",
  P3: "bg-blue-500/15 text-blue-700",
  P4: "bg-gray-500/15 text-gray-700",
};

const PHASES = [
  "OPEN", "TRIAGED", "REPRODUCED", "CLASSIFIED", "REPAIR_PROPOSED",
  "WAITING_FOR_HUMAN_GATE", "REPAIRING", "READY_FOR_RETEST",
  "REGRESSION_FAILED", "VERIFIED", "ESCALATED", "WAIVED_BY_HUMAN", "CLOSED",
];

export default function AutoRepairLedgerPage() {
  const backendLive =
    ((useHealth().data as { status?: string })?.status === "ok");
  const [data, setData] = useState<RepairData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loopProjectId, setLoopProjectId] = useState("project_c22029a3af06");
  const [simulatingLoop, setSimulatingLoop] = useState(false);
  const [simulation, setSimulation] = useState<LoopGuardSimulationResult | null>(null);
  const [archivingGlobal, setArchivingGlobal] = useState(false);

  const refresh = async () => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (loopProjectId.trim()) params.set("project_id", loopProjectId.trim());
      const r = await fetch(`${API_BASE}/api/v1/test-center/auto-repair?${params.toString()}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e: unknown) {
      setError(String((e as Error)?.message || e));
    } finally {
      setLoading(false);
    }
  };

  const archiveGlobalFindings = async () => {
    if (!backendLive || !loopProjectId.trim()) return;
    setArchivingGlobal(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        project_id: loopProjectId.trim(),
        actor: "operator-dashboard",
      });
      const r = await fetch(`${API_BASE}/api/v1/test-center/auto-repair/archive-global?${params.toString()}`, {
        method: "POST",
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await refresh();
    } catch (e: unknown) {
      setError(String((e as Error)?.message || e));
    } finally {
      setArchivingGlobal(false);
    }
  };

  const triggerLoopGuard = async () => {
    if (!backendLive || !loopProjectId.trim()) return;
    setSimulatingLoop(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/v1/test-center/auto-repair/loop-guard/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: loopProjectId.trim(),
          actor: "operator-dashboard",
          rationale: "Kontrolowany test audytowy LoopGuard przez dashboard.",
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSimulation(await r.json());
      await refresh();
    } catch (e: unknown) {
      setError(String((e as Error)?.message || e));
    } finally {
      setSimulatingLoop(false);
    }
  };

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendLive]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/test-center"
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <GitBranch className="w-6 h-6" />
            Rejestr auto-naprawy
            <HelpTip text="Automatyczna naprawa testów, które padły z powodu znanych transient errors (timeout, rate limit, flaky deps). Re-runs do 3x z exponential backoff. Pokazuje aktywne sesje w cyklu R0-R9 i raporty Loop Governor (eskalacje, limity prób)." />
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
            {backendLive ? "NA ZYWO" : "NIEDOSTEPNY"}
          </Badge>
        </div>
        <Button onClick={refresh} disabled={loading} size="sm" variant="outline">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          <span className="ml-2">Odśwież</span>
        </Button>
      </div>

      {error && (
        <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
          Błąd: {error}
        </Card>
      )}

      <Card className="p-4">
        <div className="text-sm font-semibold mb-2 flex items-center">
          Cykl życia R0-R9 (13 statusów)
          <HelpTip text="Pełny cykl statusów findingu - od OPEN przez TRIAGED, REPRODUCED, REPAIRING aż do VERIFIED lub WAIVED_BY_HUMAN. Śledzi całość historii naprawy. Default: nowe findingi startują w OPEN." />
        </div>
        <div className="flex flex-wrap gap-1">
          {PHASES.map((p, i) => (
            <Badge key={p} variant="outline" className="text-xs">
              {i}. {p}
            </Badge>
          ))}
        </div>
      </Card>

      <Card className="p-4">
        <div className="text-sm font-semibold mb-2 flex items-center">
          Limity Loop Governor
          <HelpTip text="Twarde progi liczby prób, czasu naprawy i kosztów LLM. Po przekroczeniu finding eskaluje do operatora (ESCALATED). Default: max_attempts=3, max_loop_minutes=30, max_cost_usd=2.0." />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
          {Object.entries(data?.limits || {}).map(([k, v]) => (
            <div
              key={k}
              className="flex items-center justify-between border rounded px-2 py-1"
            >
              <span className="font-mono text-muted-foreground">{k}</span>
              <span className="font-mono font-semibold">{v}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-4 space-y-3">
        <div className="text-sm font-semibold flex items-center">
          Kontrolowany test LoopGuard
          <HelpTip text="Tworzy realny finding, realne próby RepairAttempt, wywołuje LoopGovernor.check(), zapisuje LoopReport i tworzy HumanGate. Używane do audytu: system ma zatrzymać pętlę, nie tylko pokazać uzbrojony guard." />
        </div>
        <div className="grid gap-3 md:grid-cols-[1fr_auto]">
          <label className="text-xs">
            <span className="mb-1 block text-muted-foreground">
              project_id do testu
            </span>
            <input
              aria-label="Projekt LoopGuard"
              value={loopProjectId}
              onChange={(e) => setLoopProjectId(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2 font-mono text-xs"
            />
          </label>
          <Button
            onClick={triggerLoopGuard}
            disabled={!backendLive || simulatingLoop || !loopProjectId.trim()}
            variant="destructive"
            className="self-end"
          >
            {simulatingLoop ? "Uruchamiam..." : "Wywołaj blokadę pętli"}
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/20 p-3 text-xs">
          <span className="text-muted-foreground">
            zakres: <span className="font-mono">{data?.project_id || loopProjectId || "-"}</span>
          </span>
          <span className="text-muted-foreground">
            ukryte globalne: <span className="font-mono">{data?.global_hidden_count ?? 0}</span>
          </span>
          <span className="text-muted-foreground">
            zarchiwizowane: <span className="font-mono">{data?.archived_global_count ?? 0}</span>
          </span>
          <Button
            onClick={archiveGlobalFindings}
            disabled={!backendLive || archivingGlobal || !loopProjectId.trim() || (data?.global_hidden_count ?? 0) === 0}
            size="sm"
            variant="outline"
            className="ml-auto"
          >
            {archivingGlobal ? "Archiwizuje..." : "Archiwizuj obce findingi"}
          </Button>
        </div>
        {simulation && (
          <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs">
            <div className="font-semibold text-amber-800">
              LoopGuard zatrzymał flow: {simulation.reason}
            </div>
            <div className="mt-1 font-mono">
              report={simulation.loop_report?.report_id || "-"} · hg=
              {simulation.human_gate?.request_id || "-"} · status=
              {simulation.human_gate?.status || "-"}
            </div>
            <div className="mt-1 text-muted-foreground">
              zablokowane akcje: {(simulation.blocked_actions || []).join(", ") || "-"}
            </div>
          </div>
        )}
      </Card>

      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="font-semibold flex items-center">
            Aktywne sesje ({data?.active_sessions.length ?? 0})
            <HelpTip text="Findingi obecnie w naprawie (status != OPEN, != CLOSED). Pokazuje wykorzystanie prob, liczb? dotknietych plikow i LOC zmiany. Czerwony licznik prob = bliski limitu, zaraz eskalacja." />
          </div>
          <div className="text-xs text-muted-foreground">
            otwarte findingi: {data?.open_count ?? 0} · raporty loop łącznie:{" "}
            {data?.loop_reports_total ?? 0}
          </div>
        </div>
        <table className="w-full text-xs">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="text-left py-1.5 font-normal">ID znaleziska</th>
              <th className="text-left py-1.5 font-normal">tytul</th>
              <th className="text-left py-1.5 font-normal">priorytet</th>
              <th className="text-left py-1.5 font-normal">D</th>
              <th className="text-left py-1.5 font-normal">status R</th>
              <th className="text-right py-1.5 font-normal">próby</th>
              <th className="text-right py-1.5 font-normal">pliki</th>
              <th className="text-right py-1.5 font-normal">linie</th>
            </tr>
          </thead>
          <tbody>
            {(data?.active_sessions || []).map((s) => {
              const ratio = s.attempts_max
                ? s.attempts_used / s.attempts_max
                : 0;
              return (
                <tr key={s.finding_id} className="border-b last:border-0">
                  <td className="py-1.5 font-mono">
                    {s.finding_id.slice(0, 16)}
                  </td>
                  <td className="py-1.5">{s.title.slice(0, 40)}</td>
                  <td>
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${
                        SEVERITY_COLOR[s.severity] || ""
                      }`}
                    >
                      {s.severity}
                    </Badge>
                  </td>
                  <td className="font-mono text-[10px]">{s.d_level}</td>
                  <td className="font-mono text-[10px]">{s.r_status}</td>
                  <td className="text-right">
                    <span
                      className={`font-mono ${
                        ratio >= 1
                          ? "text-rose-700"
                          : ratio >= 0.5
                          ? "text-amber-700"
                          : "text-emerald-700"
                      }`}
                    >
                      {s.attempts_used}/{s.attempts_max}
                    </span>
                  </td>
                  <td className="text-right font-mono">
                    {s.files_touched_total}
                  </td>
                  <td className="text-right font-mono">
                    {s.diff_lines_total}
                  </td>
                </tr>
              );
            })}
            {(data?.active_sessions || []).length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  className="py-4 text-center text-muted-foreground"
                >
                  brak otwartych sesji naprawy
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      <Card className="p-4">
        <div className="font-semibold mb-3 flex items-center">
          Ostatnie raporty Loop Governor ({data?.loop_reports_recent.length ?? 0})
          <HelpTip text="Lista eskalacji - sytuacji gdy Loop Governor zatrzymał automatyczną pętlę naprawy (przekroczono limit prób/czasu/kosztu). Każda eskalacja wymaga decyzji operatora: kontynuować, waiver lub close manualnie." />
        </div>
        {data && data.loop_reports_recent.length === 0 ? (
          <div className="text-xs text-muted-foreground">
            Brak eskalacji Loop Governor.
          </div>
        ) : (
          <ul className="text-xs space-y-1">
            {(data?.loop_reports_recent || []).map((l) => (
              <li
                key={l.report_id}
                className="flex items-center justify-between border-b last:border-0 py-1"
              >
                <span className="font-mono">{l.report_id}</span>
                <Badge variant="outline" className="text-[10px]">
                  {l.loop_type}
                </Badge>
                <span className="font-mono">{l.finding_id.slice(0, 16)}</span>
                <span className="text-muted-foreground">
                  {new Date((l.created_at || 0) * 1000).toLocaleTimeString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {data && (
        <div className="text-xs text-muted-foreground text-right">
          stan na {new Date(data.as_of * 1000).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
