"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import { FileCheck, ArrowLeft, RefreshCw } from "lucide-react";
import { HelpTip } from "@/components/common/HelpTip";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "";

interface CatalogRow {
  code: string;
  name: string;
  description: string;
  runs_total: number;
  passed: number;
  failed: number;
}

interface CatalogData {
  as_of: number;
  project_id: string | null;
  classes: CatalogRow[];
}

export default function TestCatalogPage() {
  const backendLive =
    ((useHealth().data as { status?: string })?.status === "ok");
  const [data, setData] = useState<CatalogData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string>("");
  const [runStatus, setRunStatus] = useState<string>("");

  const refresh = async () => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    try {
      const url = `${API_BASE}/api/v1/test-center/catalog${
        projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""
      }`;
      const r = await fetch(url);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e: unknown) {
      setError(String((e as Error)?.message || e));
    } finally {
      setLoading(false);
    }
  };

  const runCatalogClass = async (testClass: string, status: "passed" | "failed") => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    setRunStatus("");
    try {
      const effectiveProjectId = projectId.trim() || "proj_test_center_manual";
      const url = `${API_BASE}/api/v1/test-center/catalog/run?test_class=${encodeURIComponent(testClass)}&project_id=${encodeURIComponent(effectiveProjectId)}&status=${encodeURIComponent(status)}`;
      const r = await fetch(url, { method: "POST" });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      const payload = await r.json();
      setRunStatus(
        `${testClass} ${status.toUpperCase()} zapisany jako ${payload.run?.run_id ?? "run"}`,
      );
      await refresh();
    } catch (e: unknown) {
      setError(String((e as Error)?.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendLive, projectId]);

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
            <FileCheck className="w-6 h-6" />
            Katalog testów (T0-T19)
            <HelpTip text="Pełny katalog 20 klas testów (T0-T19) z procentem zaliczenia, liczba uruchomien i historia. Każda klasa to inny rodzaj weryfikacji (unit, integration, contract, soak, chaos). Użyj filtra project_id żeby zobaczyć dane konkretnego projektu." />
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
            {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground flex items-center" htmlFor="catalog-project-id">
            project_id
            <HelpTip text="Opcjonalny filtr - wpisz identyfikator projektu żeby zawezic statystyki katalogu do testów tego projektu. Pusta wartość = agregat globalny po wszystkich projektach." />
          </label>
          <input
            id="catalog-project-id"
            placeholder="project_id (opcjonalnie)"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="text-xs px-2 py-1 border rounded font-mono w-56"
          />
          <Button onClick={refresh} disabled={loading} size="sm" variant="outline">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            <span className="ml-2">Odśwież</span>
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
          Błąd: {error}
        </Card>
      )}

      <Card className="p-4">
        <table className="w-full text-xs">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="text-left py-1.5 font-normal w-12">Kod</th>
              <th className="text-left py-1.5 font-normal">Nazwa</th>
              <th className="text-left py-1.5 font-normal">Opis</th>
              <th className="text-right py-1.5 font-normal">Uruchomienia</th>
              <th className="text-right py-1.5 font-normal">Zaliczone</th>
              <th className="text-right py-1.5 font-normal">Niezaliczone</th>
              <th className="text-right py-1.5 font-normal w-32">% zaliczen</th>
              <th className="text-right py-1.5 font-normal w-36">Akcja</th>
            </tr>
          </thead>
          <tbody>
            {(data?.classes || []).map((c) => {
              const rate = c.runs_total
                ? c.passed / c.runs_total
                : 0;
              return (
                <tr key={c.code} className="border-b last:border-0">
                  <td className="py-1.5">
                    <Badge
                      variant="outline"
                      className="text-[10px] font-mono w-12 justify-center"
                    >
                      {c.code}
                    </Badge>
                  </td>
                  <td className="py-1.5 font-semibold">{c.name}</td>
                  <td className="py-1.5 text-muted-foreground">
                    {c.description}
                  </td>
                  <td className="text-right py-1.5 font-mono">
                    {c.runs_total}
                  </td>
                  <td className="text-right py-1.5 font-mono text-emerald-700">
                    {c.passed}
                  </td>
                  <td className="text-right py-1.5 font-mono text-rose-700">
                    {c.failed}
                  </td>
                  <td className="text-right py-1.5">
                    {c.runs_total > 0 ? (
                      <div className="flex items-center justify-end gap-2">
                        <div className="h-1.5 w-16 rounded bg-muted overflow-hidden">
                          <div
                            className="h-full bg-emerald-500"
                            style={{ width: `${(rate * 100).toFixed(0)}%` }}
                          />
                        </div>
                        <span className="font-mono text-[10px] w-10 text-right">
                          {(rate * 100).toFixed(0)}%
                        </span>
                      </div>
                    ) : (
                      <span className="text-[10px] text-muted-foreground">
                        brak uruchomien
                      </span>
                    )}
                  </td>
                  <td className="text-right py-1.5">
                    <div className="flex justify-end gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={loading}
                        onClick={() => runCatalogClass(c.code, "passed")}
                        className="h-7 px-2 text-[10px]"
                      >
                        PASS
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={loading}
                        onClick={() => runCatalogClass(c.code, "failed")}
                        className="h-7 px-2 text-[10px] border-rose-300 text-rose-700"
                      >
                        FAIL
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {(data?.classes || []).length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  className="py-4 text-center text-muted-foreground"
                >
                  ladowanie klas testów…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      {runStatus && (
        <Card className="border-emerald-500/30 bg-emerald-500/5 p-3 text-sm text-emerald-700">
          {runStatus}
        </Card>
      )}

      {data && (
        <div className="text-xs text-muted-foreground text-right">
          {data.classes.length} klas testów ·
          {data.project_id ? ` projekt=${data.project_id} ·` : ""} stan na{" "}
          {new Date(data.as_of * 1000).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
