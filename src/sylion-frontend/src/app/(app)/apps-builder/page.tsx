"use client";

/**
 * SYLION AEIS v2 - W16 Apps Builder Plane.
 *
 * Read-only preview of the apps that the future W16 manifest compiler
 * will assemble out of W15 ontology types + the curated v2 widget
 * catalogue. The page lists canonical templates and operator-created
 * draft manifests persisted by the backend.
 *
 * Source: GET /api/v1/apps  (sylion.api.apps_routes).
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/common/HelpTip";
import { request } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  AppWindow,
  AlertTriangle,
  Boxes,
  Database,
  ExternalLink,
  Info,
  Layers,
  Loader2,
  RefreshCw,
  Wand2,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

interface AppEntry {
  id: string;
  name: string;
  description: string;
  object_types: string[];
  widgets: string[];
  version: string;
}

interface AppsListResponse {
  count: number;
  apps: AppEntry[];
}

/* ============================================================
   Page
   ============================================================ */

export default function AppsBuilderPage() {
  const [apps, setApps] = useState<AppEntry[]>([]);
  const [count, setCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await request<AppsListResponse>("/api/v1/apps");
      setApps(Array.isArray(data?.apps) ? data.apps : []);
      setCount(typeof data?.count === "number" ? data.count : 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się pobrać apek.");
      setApps([]);
      setCount(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
  }, [refresh]);

  /* ============================================================
     Render
     ============================================================ */
  return (
    <div className="space-y-5 p-6">
      {/* ===== Header ===== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-start justify-between gap-3"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <AppWindow className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight flex items-center">
              Apps Builder (W16)
              <HelpTip
                text={
                  "W16 to manifest-driven builder aplikacji operacyjnych — odpowiednik Palantir Workshop. " +
                  "Aplikacje sklejane z W15 obiektow + widget catalogue (G1+G2). Faza 0: tylko podglad " +
                  "które aplikacje *mog?* zostać zbudowane — bez kompilatora i bez idea->app studio."
                }
                side="bottom"
              />
            </h1>
            <p className="text-sm text-muted-foreground">
              Live catalog of canonical templates and generated draft manifests.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-[11px]">
            {count} apek
          </Badge>
          <Link href="/apps-builder/wizard">
            <Button
              variant="default"
              size="sm"
              title="W16 G2 wizard: opisz pomysl po polsku, dostan dopasowane szablony"
            >
              <Wand2 className="w-3.5 h-3.5 mr-1.5" />
              Studio Idei (W16 G2)
            </Button>
          </Link>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refresh()}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            )}
            Odśwież
          </Button>
        </div>
      </motion.div>

      {/* ===== Live registry banner ===== */}
      <Card className="border-sylion-blue/30 bg-sylion-blue/5">
        <div className="p-3 flex items-start gap-2 text-xs">
          <Info className="w-4 h-4 text-sylion-blue mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold text-sylion-blue">Live registry:</span>{" "}
            canonical templates plus operator-created draft manifests from{" "}
            <span className="font-mono">POST /api/v1/apps/from-template</span>.
            Each card opens the backend manifest returned by{" "}
            <span className="font-mono">GET /api/v1/apps/&#123;id&#125;</span>.
          </div>
        </div>
      </Card>

      {/* ===== Error ===== */}
      {error && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <div className="p-3 flex items-center gap-2 text-amber-600">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs">{error}</span>
          </div>
        </Card>
      )}

      {/* ===== App grid ===== */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-44 bg-muted/30 animate-pulse rounded-md border border-border/30"
            />
          ))}
        </div>
      ) : apps.length === 0 ? (
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-8 flex flex-col items-center justify-center text-muted-foreground">
            <Boxes className="w-7 h-7 mb-2 opacity-40" />
            <p className="text-xs">Brak aplikacji do wyswietlenia.</p>
            <p className="text-[10px] mt-1 opacity-60">
              Backend zwróci? pusta liste — sprawdź <span className="font-mono">/api/v1/apps</span>.
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {apps.map((app) => (
            <AppCard key={app.id} app={app} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ============================================================
   AppCard
   ============================================================ */

function AppCard({ app }: { app: AppEntry }) {
  return (
    <Card className="bg-[#0f1629] border-sylion-border flex flex-col">
      <div className="p-4 space-y-3 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <AppWindow className="w-4 h-4 text-sylion-blue shrink-0" />
            <h3 className="text-sm font-semibold">{app.name}</h3>
          </div>
          <Badge variant="outline" className="font-mono text-[10px] shrink-0">
            v{app.version}
          </Badge>
        </div>

        <p className="text-xs text-muted-foreground leading-relaxed">
          {app.description}
        </p>

        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-[10px] uppercase text-muted-foreground tracking-wider">
            <Database className="w-3 h-3" />
            <span>Typy obiektow (W15)</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {app.object_types.length === 0 ? (
              <span className="text-[10px] text-muted-foreground">brak</span>
            ) : (
              app.object_types.map((t) => (
                <Badge
                  key={t}
                  variant="outline"
                  className={cn(
                    "font-mono text-[10px]",
                    "border-sylion-blue/40 bg-sylion-blue/5 text-sylion-blue",
                  )}
                >
                  {t}
                </Badge>
              ))
            )}
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-[10px] uppercase text-muted-foreground tracking-wider">
            <Layers className="w-3 h-3" />
            <span>Widgety</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {app.widgets.length === 0 ? (
              <span className="text-[10px] text-muted-foreground">brak</span>
            ) : (
              app.widgets.map((w) => (
                <Badge
                  key={w}
                  variant="outline"
                  className="font-mono text-[10px]"
                >
                  {w}
                </Badge>
              ))
            )}
          </div>
        </div>

        <div className="text-[10px] font-mono text-muted-foreground pt-1 border-t border-border/20">
          id: {app.id}
        </div>
      </div>

      <div className="p-3 border-t border-border/30 flex items-center justify-between gap-2">
        <span className="text-[10px] text-muted-foreground">
          Otworz manifest
        </span>
        <Link href={`/apps-builder/${encodeURIComponent(app.id)}`}>
          <Button variant="outline" size="sm">
            <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
            Otworz
          </Button>
        </Link>
      </div>
    </Card>
  );
}
