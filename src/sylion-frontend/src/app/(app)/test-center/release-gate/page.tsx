"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, RefreshCw, Shield, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HelpTip } from "@/components/common/HelpTip";
import { useHealth } from "@/lib/api/hooks";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface GateData {
  as_of: number;
  project_id: string;
  rc_checklist: string[];
  prod_checklist: string[];
  charter_summary?: {
    total: number;
    approved: number;
    proposed: number;
    latest_charter_id?: string | null;
    latest_status?: string | null;
  };
  production_summary?: {
    rc_id?: string | null;
    branch_id?: string | null;
    gate_status?: string | null;
    checks?: Record<string, boolean>;
  };
  no_mock_scan?: {
    status: "PASS" | "FAIL" | string;
    scanned_files: number;
    issue_count: number;
    blocking_count: number;
    details_url: string;
    blocking_issues?: Array<{
      rule_id: string;
      severity: string;
      path: string;
      line: number;
      snippet: string;
      description: string;
    }>;
  };
  report: {
    project_id?: string;
    status?: string;
    checklist_results?: Record<string, boolean>;
    blockers?: string[];
    [key: string]: unknown;
  };
}

const STATUS_COLOR: Record<string, string> = {
  NOT_TESTED: "bg-gray-500/15 text-gray-700",
  TESTING_IN_PROGRESS: "bg-blue-500/15 text-blue-700",
  BLOCKED_BY_FINDINGS: "bg-rose-500/15 text-rose-700",
  BLOCKED_BY_GOVERNANCE: "bg-rose-500/15 text-rose-700",
  READY_FOR_RELEASE_CANDIDATE: "bg-emerald-500/15 text-emerald-700",
  RELEASE_CANDIDATE: "bg-emerald-500/15 text-emerald-700",
  READY_FOR_PRODUCTION: "bg-emerald-500/15 text-emerald-700",
  PRODUCTION_RELEASED: "bg-emerald-500/15 text-emerald-700",
  ROLLBACK_REQUIRED: "bg-rose-500/15 text-rose-700",
  ARCHIVED: "bg-gray-500/15 text-gray-700",
  blocked: "bg-rose-500/15 text-rose-700",
  release_candidate: "bg-emerald-500/15 text-emerald-700",
  production_ready: "bg-emerald-500/15 text-emerald-700",
};

const STATUS_LABEL: Record<string, string> = {
  NOT_TESTED: "Nie testówano",
  TESTING_IN_PROGRESS: "Testy w toku",
  BLOCKED_BY_FINDINGS: "Zablokowane przez błędy",
  BLOCKED_BY_GOVERNANCE: "Zablokowane przez governance",
  READY_FOR_RELEASE_CANDIDATE: "Gotowe na Release Candidate",
  RELEASE_CANDIDATE: "Release Candidate",
  READY_FOR_PRODUCTION: "Gotowe na produkcję",
  PRODUCTION_RELEASED: "Wydane na produkcję",
  ROLLBACK_REQUIRED: "Wymagany rollback",
  ARCHIVED: "Zarchiwizowane",
  blocked: "Zablokowane",
  release_candidate: "Release Candidate",
  production_ready: "Gotowe na produkcję",
};

const CHECKLIST_LABEL: Record<string, string> = {
  sot_approved: "Księga / Source of Truth zatwierdzona",
  masterplan_approved: "Masterplan zatwierdzony",
  test_charter_approved: "Katalog testów zatwierdzony",
  all_mandatory_tests_passed: "Wszystkie testy obowiązkowe zaliczone",
  every_pass_has_evidence: "Każdy PASS ma dowód",
  no_p0_p1_findings: "Brak otwartych błędów P0/P1",
  d3_findings_decided: "Findingi D3+ mają decyzję",
  regression_passed: "Regresja zaliczona",
  human_like_passed: "Test człowieko-podobny zaliczony",
  audit_chain_intact: "Audit chain jest integralny",
  no_mock_as_live: "Brak syntetycznych danych/demo jako live",
  artifact_hashes_present: "Hash artefaktu zapisany",
  release_rehearsal_passed: "Próba release zaliczona",
  rollback_tested_within_7d: "Rollback testówany w ostatnich 7 dniach",
  final_approval_signed: "Finalny podpis zatwierdzający",
  council_completed_d4_d5: "Council D4/D5 zakończony",
  sentinels_pass: "Sentinele PASS",
  operator_signed_final_gate: "Operator podpisał finalną bramkę",
};

export default function ReleaseGatePage() {
  const healthStatus = (useHealth().data as { status?: string })?.status;
  const backendLive = healthStatus === "ok" || healthStatus === "unknown";
  const [data, setData] = useState<GateData | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string>("proj_test_center_manual");

  const refresh = async () => {
    if (!backendLive || !projectId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE}/api/v1/test-center/release-gate?project_id=${encodeURIComponent(projectId)}`,
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setData(await response.json());
    } catch (err: unknown) {
      setError(String((err as Error)?.message || err));
    } finally {
      setLoading(false);
    }
  };

  const refreshAfterWrite = async () => {
    await refresh();
    window.setTimeout(() => {
      void refresh();
    }, 900);
  };

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendLive, projectId]);

  const checklist = data?.report.checklist_results || {};
  const status = (data?.report.status as string) || "NOT_TESTED";
  const blockers = (data?.report.blockers as string[]) || [];
  const charterSummary = data?.charter_summary;
  const productionSummary = data?.production_summary;
  const productionChecks = productionSummary?.checks || {};
  const noMockScan = data?.no_mock_scan;

  const runCharterAction = async (action: "propose" | "approve") => {
    if (!backendLive || !projectId) return;
    setActionLoading(action);
    setError(null);
    setActionMessage(null);
    try {
      const response = await fetch(
        `${API_BASE}/api/v1/test-center/charters/project/${encodeURIComponent(projectId)}/${action}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            actor: "operator-dashboard",
            rationale:
              action === "propose"
                ? "Operator utworzył Katalog Testów z zamrożonej Księgi, Masterplanu i wyników walidacji."
                : "Operator zatwierdził Katalog Testów jako HumanGate D3 przed promocją Release Candidate.",
          }),
        },
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      const body = await response.json();
      const charterId = body?.charter?.charter_id || body?.summary?.latest_charter_id || "";
      setActionMessage(
        action === "propose"
          ? `Katalog Testów utworzony: ${charterId}`
          : `HumanGate D3 zatwierdził Katalog Testów: ${charterId}`,
      );
      await refreshAfterWrite();
    } catch (err: unknown) {
      setError(String((err as Error)?.message || err));
    } finally {
      setActionLoading(null);
    }
  };

  const runProductionAction = async (
    action: "rehearse" | "rollback-test" | "council-sentinels" | "final-sign",
  ) => {
    if (!backendLive || !projectId) return;
    setActionLoading(action);
    setError(null);
    setActionMessage(null);
    try {
      const response = await fetch(
        `${API_BASE}/api/v1/test-center/production-release/project/${encodeURIComponent(projectId)}/${action}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            actor: "operator-dashboard",
            rationale: `Operator wykonał akcję produkcyjnej bramki: ${action}.`,
          }),
        },
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      const body = await response.json();
      const nextSummary = body?.summary || {};
      setActionMessage(
        `Zapisano dowód produkcyjny: ${action}; RC: ${nextSummary.rc_id || "n/a"}`,
      );
      await refreshAfterWrite();
    } catch (err: unknown) {
      setError(String((err as Error)?.message || err));
    } finally {
      setActionLoading(null);
    }
  };

  const renderItem = (item: string) => {
    const result = checklist[item];
    const label = CHECKLIST_LABEL[item] ?? item;
    return (
      <div key={item} className="flex items-center gap-2 text-sm">
        {result ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        ) : (
          <XCircle className="h-4 w-4 text-amber-500" />
        )}
        <span>{label}</span>
        <span className="font-mono text-[10px] text-muted-foreground">({item})</span>
      </div>
    );
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/test-center" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Shield className="h-6 w-6" />
            Bramka wdrożenia
            <HelpTip text="Brama wdrożenia produkcyjnego: zbiór wymagań, które muszą być spełnione przed promocją do RC oraz dodatkowe 6 wymagań przed promocją do PROD. Brama działa w trybie strict i blokuje release, gdy wymagania nie są spełnione." />
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
            {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center text-xs text-muted-foreground" htmlFor="release-gate-project-id">
            project_id
            <HelpTip text="Identyfikator projektu do oceny przez Release Gate. Domyślnie: proj_test_center_manual. Zmień wartość i kliknij Oceń, aby pobrać aktualny stan checklisty." />
          </label>
          <input
            id="release-gate-project-id"
            placeholder="project_id"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            className="w-56 rounded border px-2 py-1 font-mono text-xs"
          />
          <Button onClick={refresh} disabled={loading} size="sm" variant="outline">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            <span className="ml-2">Oceń</span>
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
          Błąd: {error}
        </Card>
      )}

      {actionMessage && (
        <Card className="border-emerald-500/30 bg-emerald-500/5 p-3 text-sm text-emerald-700">
          {actionMessage}
        </Card>
      )}

      {noMockScan && (
        <Card className="border-sky-500/30 bg-sky-500/5 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold">
                Dowód `no_mock_as_live`
                <HelpTip text="Bezpośredni wynik skanera, którego używa Release Gate dla pozycji no_mock_as_live. Jeśli skaner wykryje blokujący syntetyczny fallback albo demo jako live, release zostanie zatrzymany." />
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                Pliki: {noMockScan.scanned_files} · problemy: {noMockScan.issue_count} · blokery:{" "}
                {noMockScan.blocking_count}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={
                  noMockScan.status === "PASS"
                    ? "bg-emerald-500/15 text-emerald-700"
                    : "bg-rose-500/15 text-rose-700"
                }
              >
                {noMockScan.status}
              </Badge>
              <Link
                href={noMockScan.details_url || "/test-center/no-mock-scan"}
                className="rounded border px-3 py-1 text-xs hover:bg-muted"
              >
                Otwórz szczegóły
              </Link>
            </div>
          </div>
          {(noMockScan.blocking_issues || []).length > 0 && (
            <div className="mt-3 space-y-1 text-xs text-rose-700">
              {(noMockScan.blocking_issues || []).map((issue) => (
                <div key={`${issue.path}:${issue.line}:${issue.rule_id}`} className="font-mono">
                  {issue.severity} {issue.rule_id} · {issue.path}:{issue.line}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <Card className="p-4">
        <div className="flex items-baseline justify-between">
          <div className="flex items-center font-semibold">
            Status wdrożenia
            <HelpTip text="Aktualny stan bramki dla wybranego projektu. Wartość techniczna pochodzi z backendu, a etykieta pokazuje jej polskie znaczenie." />
          </div>
          <Badge variant="outline" className={`text-xs ${STATUS_COLOR[status] || ""}`}>
            {STATUS_LABEL[status] ?? status} ({status})
          </Badge>
        </div>
        {blockers.length > 0 && (
          <div className="mt-3">
            <div className="mb-1 flex items-center text-xs text-muted-foreground">
              Blokery
              <HelpTip text="Konkretne wymagania, które nie zostały spełnione i blokują promocję. Każdy bloker musi być rozwiązany albo formalnie zaakceptowany jako znane ryzyko, zanim Release Gate przepuści projekt dalej." />
            </div>
            <div className="flex flex-wrap gap-1">
              {blockers.map((blocker) => (
                <Badge
                  key={blocker}
                  variant="outline"
                  className="bg-rose-500/15 text-[10px] text-rose-700"
                  title={blocker}
                >
                  {CHECKLIST_LABEL[blocker] ?? blocker}
                </Badge>
              ))}
            </div>
          </div>
        )}
        <div className="mt-4 rounded border bg-muted/20 p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">Katalog Testów / Test Charter</div>
              <div className="text-xs text-muted-foreground">
                Status: {charterSummary?.latest_status ?? "brak"} · zatwierdzone:{" "}
                {charterSummary?.approved ?? 0} · proponowane: {charterSummary?.proposed ?? 0}
              </div>
              {charterSummary?.latest_charter_id && (
                <div className="font-mono text-[10px] text-muted-foreground">
                  {charterSummary.latest_charter_id}
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => runCharterAction("propose")}
                disabled={actionLoading !== null || (charterSummary?.total ?? 0) > 0}
                size="sm"
                variant="outline"
              >
                Utwórz Katalog Testów
              </Button>
              <Button
                onClick={() => runCharterAction("approve")}
                disabled={actionLoading !== null || charterSummary?.latest_status !== "proposed"}
                size="sm"
              >
                Zatwierdź HG D3
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <Card className="p-4">
        <div className="mb-3 flex items-center font-semibold">
          Produkcyjna bramka HumanGate / Council / sentinele
          <HelpTip text="Cztery jawne kroki produkcyjne. Każdy zapisuje osobny dowód w W14 ontology: rehearsal jako T15, rollback drill jako T13, Council D4/D5 z podpisem krytyka i sentinelami oraz finalny ReleaseDecision z podpisami operatorów i DPO." />
        </div>
        <div className="mb-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
          <div>
            RC: <span className="font-mono">{productionSummary?.rc_id ?? "brak"}</span>
          </div>
          <div>
            Branch: <span className="font-mono">{productionSummary?.branch_id ?? "brak"}</span>
          </div>
          <div>Status RC: {productionSummary?.gate_status ?? "brak"}</div>
          <div>Tryb: strict, bez override i bez syntetycznych danych jako live</div>
        </div>
        <div className="grid gap-2 md:grid-cols-4">
          <Button
            onClick={() => runProductionAction("rehearse")}
            disabled={actionLoading !== null || !checklist.test_charter_approved || productionChecks.release_rehearsal_passed}
            size="sm"
            variant="outline"
          >
            Wykonaj próbę release
          </Button>
          <Button
            onClick={() => runProductionAction("rollback-test")}
            disabled={actionLoading !== null || !productionChecks.release_rehearsal_passed || productionChecks.rollback_tested_within_7d}
            size="sm"
            variant="outline"
          >
            Przetestuj rollback
          </Button>
          <Button
            onClick={() => runProductionAction("council-sentinels")}
            disabled={actionLoading !== null || !productionChecks.rollback_tested_within_7d || (productionChecks.council_completed_d4_d5 && productionChecks.sentinels_pass)}
            size="sm"
            variant="outline"
          >
            Council D4/D5 + sentinele
          </Button>
          <Button
            onClick={() => runProductionAction("final-sign")}
            disabled={
              actionLoading !== null
              || !productionChecks.council_completed_d4_d5
              || !productionChecks.sentinels_pass
              || productionChecks.operator_signed_final_gate
            }
            size="sm"
          >
            Podpisz finalny gate
          </Button>
        </div>
      </Card>

      <Card className="p-4">
        <div className="mb-3 flex items-center font-semibold">
          Lista RC ({data?.rc_checklist.length ?? 12} pozycji)
          <HelpTip text="12 wymagań, które muszą być spełnione przed promocją projektu do statusu Release Candidate. Obejmuje to zatwierdzenie SoT, Masterplanu i Test Charteru, brak P0/P1 findingów, zaliczoną regresję, integralny audit chain i brak syntetycznych danych jako live." />
        </div>
        <div className="space-y-1">
          {(data?.rc_checklist || []).map(renderItem)}
        </div>
      </Card>

      <Card className="p-4">
        <div className="mb-3 flex items-center font-semibold">
          Lista produkcyjna (dodatkowe {data?.prod_checklist.length ?? 6} pozycji)
          <HelpTip text="Dodatkowe 6 wymagań, które obowiązują podczas promocji RC do produkcji. Obejmują próbę release, rollback testówany w ostatnich 7 dniach, finalny podpis, Council D4/D5, sentinele i końcowy podpis operatora." />
        </div>
        <div className="space-y-1">
          {(data?.prod_checklist || []).map(renderItem)}
        </div>
      </Card>

      {data && (
        <div className="text-right text-xs text-muted-foreground">
          project_id: <span className="font-mono">{data.project_id}</span> · stan na{" "}
          {new Date(data.as_of * 1000).toLocaleTimeString("pl-PL")}
        </div>
      )}
    </div>
  );
}
