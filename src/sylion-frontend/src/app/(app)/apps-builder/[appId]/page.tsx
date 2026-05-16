"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, AppWindow, Database, Layers, Loader2, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { request } from "@/lib/api/client";

interface AppEntry {
  id: string;
  name: string;
  description: string;
  object_types: string[];
  widgets: string[];
  version: string;
  source: string;
  status: string;
  template_id: string;
  created_at?: number;
  updated_at?: number;
}

interface AppDetailResponse {
  app: AppEntry;
  manifest: Record<string, unknown>;
}

export default function AppsBuilderDetailPage() {
  const params = useParams<{ appId: string }>();
  const appId = useMemo(() => decodeURIComponent(String(params?.appId || "")), [params?.appId]);
  const [detail, setDetail] = useState<AppDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!appId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await request<AppDetailResponse>(`/api/v1/apps/${encodeURIComponent(appId)}`);
      setDetail(data);
    } catch (err) {
      setDetail(null);
      setError(err instanceof Error ? err.message : "Nie udało się pobrać manifestu aplikacji.");
    } finally {
      setLoading(false);
    }
  }, [appId]);

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
  }, [refresh]);

  return (
    <div className="space-y-5 p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <AppWindow className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Apps Builder Manifest</h1>
            <p className="text-sm text-muted-foreground font-mono">{appId}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/apps-builder">
            <Button variant="outline" size="sm">
              <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
              Katalog
            </Button>
          </Link>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}>
            {loading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
            Odśwież
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <div className="p-3 flex items-center gap-2 text-amber-600">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs">{error}</span>
          </div>
        </Card>
      )}

      {loading ? (
        <Card className="p-6 bg-[#0f1629] border-sylion-border">
          <div className="flex items-center text-xs text-muted-foreground">
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Ładowanie manifestu...
          </div>
        </Card>
      ) : detail ? (
        <div className="grid grid-cols-1 xl:grid-cols-[420px_1fr] gap-4">
          <Card className="bg-[#0f1629] border-sylion-border">
            <div className="p-4 space-y-4">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-lg font-semibold">{detail.app.name}</h2>
                  <Badge variant="outline" className="font-mono text-[10px]">{detail.app.status}</Badge>
                  <Badge variant="outline" className="font-mono text-[10px]">{detail.app.source}</Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-2 leading-relaxed">{detail.app.description}</p>
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5 text-[10px] uppercase text-muted-foreground tracking-wider">
                  <Database className="w-3 h-3" />
                  <span>Object types</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {detail.app.object_types.map((item) => (
                    <Badge key={item} variant="outline" className="font-mono text-[10px]">{item}</Badge>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5 text-[10px] uppercase text-muted-foreground tracking-wider">
                  <Layers className="w-3 h-3" />
                  <span>Widgets</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {detail.app.widgets.map((item) => (
                    <Badge key={item} variant="outline" className="font-mono text-[10px]">{item}</Badge>
                  ))}
                </div>
              </div>

              <div className="text-[10px] text-muted-foreground font-mono border-t border-border/30 pt-3 space-y-1">
                <div>template_id: {detail.app.template_id}</div>
                <div>version: {detail.app.version}</div>
              </div>
            </div>
          </Card>

          <Card className="bg-[#0f1629] border-sylion-border">
            <div className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">Backend manifest JSON</h2>
                <Badge variant="outline" className="font-mono text-[10px]">GET /api/v1/apps/{`{id}`}</Badge>
              </div>
              <pre className="max-h-[70vh] overflow-auto rounded-md bg-black/40 border border-border/40 p-3 text-[11px] leading-relaxed">
                {JSON.stringify(detail.manifest, null, 2)}
              </pre>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
