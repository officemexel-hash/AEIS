"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import { Network, ArrowLeft, RefreshCw } from "lucide-react";
import { HelpTip } from "@/components/common/HelpTip";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "";

interface TruthData {
  as_of: number;
  project_id?: string | null;
  layers: string[];
  summary: {
    total_features: number;
    aligned_count: number;
    drift_count: number;
    aligned_ratio: number;
  };
  drifts: { feature_id: string; drift: string[]; captured_at: number }[];
  aligned: string[];
}

export default function TruthAlignmentPage() {
  const backendLive =
    ((useHealth().data as { status?: string })?.status === "ok");
  const [data, setData] = useState<TruthData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string>("");

  const refresh = async () => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    try {
      const query = projectId.trim()
        ? `?project_id=${encodeURIComponent(projectId.trim())}`
        : "";
      const r = await fetch(`${API_BASE}/api/v1/test-center/truth-alignment${query}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
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

  const layers = data?.layers || [
    "sot", "masterplan", "runtime", "api", "ui", "test", "docs",
  ];
  const ratio = data?.summary.aligned_ratio ?? 0;

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
            <Network className="w-6 h-6" />
            Macierz wyrównania prawdy
            <HelpTip text="Macierz spójności 7 warstw prawdy: SoT, Masterplan, Runtime, API, UI, Testy, Docs. SprawdŹa, czy feature 'X' jest tak samo zdefiniowany we wszystkich warstwach. Drift = warstwy się rozjeżdżają, najczęściej docs/UI nie nadążają za API. Cel: aligned_ratio >= 0.95." />
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
            {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground flex items-center" htmlFor="truth-project-id">
            project_id
            <HelpTip text="Opcjonalny filtr projektu. Dla projektu AEIS macierz buduje snapshot z SoT, Masterplanu, runtime, API, UI, testów W14 i dokumentacji/artefaktu." />
          </label>
          <input
            id="truth-project-id"
            placeholder="project_id (opcjonalnie)"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-xs text-muted-foreground flex items-center">
            Funkcje łącznie
            <HelpTip text="Całkowita liczba funkcjonalności (features) śledzonych przez Truth Alignment. Suma aligned + drift. Default: lista pochodzi z Masterplanu i SoT." />
          </div>
          <div className="text-2xl font-bold font-mono">
            {data?.summary.total_features ?? "—"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground flex items-center">
            Wyrownane
            <HelpTip text="Funkcjonalności, które są spójne we wszystkich 7 warstwach prawdy - SoT, Masterplan, Runtime, API, UI, Testy, Docs. Im więcej tym lepiej. Cel: 100% przed promocją do PROD." />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-700">
            {data?.summary.aligned_count ?? "—"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground flex items-center">
            Drift
            <HelpTip text="Funkcjonalności, których warstwy się rozjeżdżają (np. API zwraca pole X, ale docs go nie wspomina). Każdy drift = bloker dla Release Gate. Kliknij poniższą tabelę, żeby zobaczyć, które warstwy zawiodły." />
          </div>
          <div className="text-2xl font-bold font-mono text-rose-700">
            {data?.summary.drift_count ?? "—"}
          </div>
        </Card>
      </div>

      <Card className="p-4">
        <div className="font-semibold mb-2 flex items-center">
          Wskaźnik wyrównania
          <HelpTip text="Procent feature'ów, które są spójne we wszystkich 7 warstwach. Cel: >= 95% przed RC, 100% przed PROD. Pasek pokazuje aktualny stan; cel poniżej to zalecany próg." />
        </div>
        <div className="h-3 rounded bg-muted overflow-hidden">
          <div
            className="h-full bg-emerald-500"
            style={{ width: `${(ratio * 100).toFixed(1)}%` }}
          />
        </div>
        <div className="text-xs text-muted-foreground mt-1">
          {(ratio * 100).toFixed(1)}% wyrównania na 7 warstwach prawdy
        </div>
      </Card>

      <Card className="p-4">
        <div className="font-semibold mb-3 flex items-center">
          7 warstw prawdy
          <HelpTip text="Kanoniczna lista warstw porównywanych przez Truth Alignment: sot (Source of Truth - decyzję), masterplan (specyfikacja), runtime (zachowanie procesu), api (kontrakty), ui (frontend), test (suite testówy), docs (dokumentacja). Wszystkie 7 musi być spójne." />
        </div>
        <div className="flex flex-wrap gap-2">
          {layers.map((l) => (
            <Badge key={l} variant="outline" className="text-xs">
              {l}
            </Badge>
          ))}
        </div>
      </Card>

      <Card className="p-4">
        <div className="font-semibold mb-3 flex items-center">
          Driftow ({data?.drifts.length ?? 0})
          <HelpTip text="Lista feature'ów, które zawiodły Truth Alignment - razem z konkretnymi warstwami, które się rozjechały. Czas captured pokazuje, kiedy drift został wykryty. Każdy drift wymaga reconciliation - albo zaktualizować docs/UI/testy, albo cofnąć zmianę API." />
        </div>
        {data && data.drifts.length === 0 ? (
          <div className="text-xs text-muted-foreground">
            Brak zarejestrowanych driftów - wszystkie funkcjonalności w tym snapshotcie są wyrównane.
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="border-b text-muted-foreground">
              <tr>
                <th className="text-left py-1.5 font-normal">Funkcja</th>
                <th className="text-left py-1.5 font-normal">Drift</th>
                <th className="text-right py-1.5 font-normal">Wykryto</th>
              </tr>
            </thead>
            <tbody>
              {(data?.drifts || []).map((d) => (
                <tr key={d.feature_id} className="border-b last:border-0">
                  <td className="py-1.5 font-mono">{d.feature_id}</td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {d.drift.map((x) => (
                        <Badge
                          key={x}
                          variant="outline"
                          className="text-[10px] bg-amber-500/15 text-amber-700"
                        >
                          {x}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="text-right text-muted-foreground">
                    {new Date(d.captured_at * 1000).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card className="p-4">
        <div className="font-semibold mb-3 flex items-center">
          Wyrównane funkcjonalności ({data?.aligned.length ?? 0})
          <HelpTip text="Lista feature'ów, które zaliczyły Truth Alignment - są spójne we wszystkich 7 warstwach. Te funkcjonalności są gotowe pod kątem governance dla release. Im dłuższa ta lista tym bliżej promocji RC/PROD." />
        </div>
        <div className="flex flex-wrap gap-1">
          {(data?.aligned || []).map((f) => (
            <Badge
              key={f}
              variant="outline"
              className="text-[10px] bg-emerald-500/15 text-emerald-700"
            >
              {f}
            </Badge>
          ))}
          {(data?.aligned || []).length === 0 && (
            <span className="text-xs text-muted-foreground">
              brak wyrównanych funkcjonalności
            </span>
          )}
        </div>
      </Card>

      {data && (
        <div className="text-xs text-muted-foreground text-right">
          {data.project_id ? `projekt=${data.project_id} · ` : ""}
          stan na {new Date(data.as_of * 1000).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
