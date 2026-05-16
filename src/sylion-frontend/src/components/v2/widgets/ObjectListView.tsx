"use client";

/**
 * SYLION AEIS v2 — W16 G1 widget: ObjectListView.
 *
 * Renders a table of instances of a W15 ontology type. Phase 0 wire:
 * - Fetches the manifest (`GET /api/v1/ontology/types/{typeId}`).
 * - Renders columns derived from `spec.dedicated_columns` (subset configurable
 *   via `columns` prop).
 * - Body is intentionally a static placeholder until W15 G2 (OSDK + instance
 *   query API) lands. Operator briefs explicitly call this out.
 */

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, AlertTriangle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { HelpTip } from "@/components/common/HelpTip";
import { request } from "@/lib/api/client";

interface DedicatedColumn {
  name: string;
  type: string;
  nullable?: boolean;
  description?: string;
}

interface OntologyManifest {
  metadata: {
    id: string;
    name_pl: string;
    name_en?: string;
    description_pl?: string;
  };
  spec: {
    dedicated_columns: DedicatedColumn[];
  };
}

export interface ObjectListViewProps {
  typeId: string;
  columns?: string[];
  pageSize?: number;
  onRowClick?: (instance: Record<string, unknown>) => void;
  filters?: Record<string, string | number | boolean>;
  emptyMessage?: string;
}

export function ObjectListView({
  typeId,
  columns,
  pageSize = 25,
  onRowClick,
  filters,
  emptyMessage,
}: ObjectListViewProps) {
  const [manifest, setManifest] = useState<OntologyManifest | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    request<OntologyManifest>(`/api/v1/ontology/types/${encodeURIComponent(typeId)}`)
      .then((m) => {
        if (active) setManifest(m);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [typeId]);

  const allColumns = manifest?.spec.dedicated_columns ?? [];
  const visibleColumns: DedicatedColumn[] = columns
    ? allColumns.filter((c) => columns.includes(c.name))
    : allColumns;

  const title = manifest?.metadata.name_pl ?? typeId;
  const phase0EmptyMsg =
    emptyMessage ??
    "Tabela (Phase 0): brak danych — instances będą dostępne po W15 G2 OSDK.";
  const filterCount = filters ? Object.keys(filters).length : 0;

  // Phase 0: void unused props to satisfy noUnusedParameters once strict lint
  // is on. They are part of the public API for forward compatibility.
  void onRowClick;
  void pageSize;

  return (
    <Card className="overflow-hidden">
      <header className="flex items-center justify-between border-b border-foreground/10 px-4 py-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">
            {title}
            <HelpTip
              text={
                manifest?.metadata.description_pl ||
                `Lista obiektów typu ${typeId}. Kolumny pochodzą z manifestu W15.`
              }
            />
          </h3>
          {filterCount > 0 && (
            <Badge variant="outline" className="text-[10px]">
              {filterCount} filtr{filterCount === 1 ? "" : "y"}
            </Badge>
          )}
        </div>
        <Badge variant="secondary" className="text-[10px]">
          0 / 0
        </Badge>
      </header>

      {loading && (
        <div className="flex items-center justify-center gap-2 px-4 py-6 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Wczytywanie manifestu…
        </div>
      )}

      {error && !loading && (
        <div className="flex items-center gap-2 px-4 py-3 text-xs text-destructive">
          <AlertTriangle className="h-3.5 w-3.5" />
          Błąd manifestu: {error}
        </div>
      )}

      {!loading && !error && manifest && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                {visibleColumns.map((col) => (
                  <TableHead key={col.name} className="text-[11px] uppercase">
                    {col.name}
                    {col.description && (
                      <HelpTip text={col.description} />
                    )}
                  </TableHead>
                ))}
                {visibleColumns.length === 0 && (
                  <TableHead className="text-[11px] uppercase">brak kolumn</TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell
                  colSpan={Math.max(1, visibleColumns.length)}
                  className="py-6 text-center text-xs text-muted-foreground"
                >
                  {phase0EmptyMsg}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>

          <footer className="flex items-center justify-between border-t border-foreground/10 px-4 py-2 text-[11px] text-muted-foreground">
            <span>strona 1 z 1</span>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon-xs" disabled aria-label="poprzednia strona">
                <ChevronLeft />
              </Button>
              <Button variant="ghost" size="icon-xs" disabled aria-label="następna strona">
                <ChevronRight />
              </Button>
            </div>
          </footer>
        </>
      )}
    </Card>
  );
}
