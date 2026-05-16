"use client";

import { useObservabilitySnapshot, useLogs, useMetrics, useTraces } from "@/lib/api/hooks";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Activity, FileText, BarChart3, GitBranch } from "lucide-react";
import { HelpTip } from "@/components/common/HelpTip";

export default function ObservabilityPage() {
  const { data: snap, loading: snapLoading } = useObservabilitySnapshot();
  const { data: logs, loading: logsLoading } = useLogs(undefined, undefined, 10);
  const { data: metrics, loading: metricsLoading } = useMetrics();
  const { data: traces, loading: tracesLoading } = useTraces(undefined, 10);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">
          Obserwowalność
          <HelpTip text="Centralny dashboard logów, metryk i traceów. Każde wywołanie LLM jest tu rejestrowane: prompt + response + tokeny + koszt. Filtrowanie po module/operatorze/projekcie." />
        </h1>
        <Badge variant="outline">{snap?.backend || "Lokalny"}</Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
              Metryki
              <HelpTip text="Łączna liczba zarejestrowanych metryk numerycznych (counters, gauges, histograms). Punkt startowy do alertów." />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{snap?.metrics_count ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <GitBranch className="h-4 w-4 text-muted-foreground" />
              Trace'y
              <HelpTip text="Liczba aktywnych traceów (multi-span). Trace = pełna ścieżka requestu przez moduły. Pomocne do debugowania latencji." />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{snap?.traces_count ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <FileText className="h-4 w-4 text-muted-foreground" />
              Ostatnie logi
              <HelpTip text="Ostatnie wpisy ze wszystkich modułów. Domyślnie ostatnie 10 — pełny dziennik dostępny w API /logs." />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{snap?.recent_logs?.length ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Activity className="h-4 w-4 text-muted-foreground" />
              Ostatnie logi
              <HelpTip text="Strumień zdarzeń logowych z poziomami (info/warn/error). Czerwone badge = błąd; kliknij wpis, aby zobaczyć szczegóły w API." />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {logsLoading && <Loader2 className="h-4 w-4 animate-spin" />}
            {logs?.logs?.length === 0 && <div className="text-sm text-muted-foreground">Brak logów</div>}
            {logs?.logs?.map((log: any, i: number) => (
              <div key={i} className="text-sm border-b last:border-0 pb-2 last:pb-0">
                <div className="flex items-center gap-2">
                  <Badge variant={log.level === "error" ? "destructive" : "outline"} className="text-xs">{log.level}</Badge>
                  <span className="text-muted-foreground text-xs">{log.service}</span>
                </div>
                <div>{log.message}</div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <GitBranch className="h-4 w-4 text-muted-foreground" />
              Ostatnie trace'y
              <HelpTip text="Każdy trace = przepływ requestu przez moduły z czasem trwania. Status ok/error + duration_ms ułatwiają lokalizację wąskich gardeł." />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {tracesLoading && <Loader2 className="h-4 w-4 animate-spin" />}
            {traces?.traces?.length === 0 && <div className="text-sm text-muted-foreground">Brak traceów</div>}
            {traces?.traces?.map((t: any, i: number) => (
              <div key={i} className="text-sm border-b last:border-0 pb-2 last:pb-0">
                <div className="flex items-center gap-2">
                  <Badge variant={t.status === "ok" ? "outline" : "destructive"} className="text-xs">{t.status}</Badge>
                  <span className="font-mono text-xs">{t.trace_id}</span>
                </div>
                <div className="text-muted-foreground">{t.operation} · {t.service} · {t.duration_ms}ms</div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">
            Nazwy metryk
            <HelpTip text="Wszystkie zarejestrowane nazwy metryk dostępne do query/alertów. Konwencja nazw: domena.metryka.akcja (np. council.vote.duration)." />
          </CardTitle>
        </CardHeader>
        <CardContent>
          {metricsLoading && <Loader2 className="h-4 w-4 animate-spin" />}
          <div className="flex flex-wrap gap-2">
            {metrics?.metrics?.map((m: string) => (
              <Badge key={m} variant="secondary" className="text-xs">{m}</Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
