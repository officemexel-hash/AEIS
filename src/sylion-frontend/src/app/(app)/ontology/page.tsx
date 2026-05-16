"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { HelpTip } from "@/components/common/HelpTip";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  Boxes,
  Database,
  FileCode2,
  Layers,
  RefreshCw,
  ScrollText,
  Loader2,
  AlertTriangle,
  Wrench,
} from "lucide-react";

/* ============================================================
   Typy odpowiedzi z backendu (W15)
   ============================================================ */

interface OntologyColumn {
  name: string;
  type: string;
  nullable?: boolean;
  indexed?: boolean;
  searchable?: boolean;
  enum?: string[] | null;
  default?: unknown;
}

interface OntologyTypeSummary {
  id: string;
  name?: string;
  domain?: string;
  version?: string;
  description?: string;
  columns_count?: number;
  actions_count?: number;
}

interface OntologyTypesResponse {
  count: number;
  types: OntologyTypeSummary[];
}

interface OntologyManifest {
  id: string;
  name?: string;
  domain?: string;
  version?: string;
  description?: string;
  table?: string;
  columns?: OntologyColumn[];
  [key: string]: unknown;
}

interface OntologyDdlResponse {
  id: string;
  ddl: string;
  dialect?: string;
}

interface OntologyAction {
  action_id: string;
  d_level?: string;
  hg_required?: boolean;
  endpoint?: string;
  description?: string;
}

interface OntologyActionsResponse {
  id: string;
  actions: OntologyAction[];
}

/* ============================================================
   Pomocnicze
   ============================================================ */

function jsonPretty(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/* ============================================================
   Strona
   ============================================================ */

export default function OntologyPage() {
  const [types, setTypes] = useState<OntologyTypeSummary[]>([]);
  const [count, setCount] = useState<number>(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [manifest, setManifest] = useState<OntologyManifest | null>(null);
  const [ddl, setDdl] = useState<OntologyDdlResponse | null>(null);
  const [actions, setActions] = useState<OntologyActionsResponse | null>(null);
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reloading, setReloading] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<string>("manifest");

  /* ---------- Pobranie listy typów ---------- */
  const fetchTypes = useCallback(async () => {
    setLoadingList(true);
    setError(null);
    try {
      const data = (await api.listOntologyTypes()) as OntologyTypesResponse;
      const list = Array.isArray(data?.types) ? data.types : [];
      setTypes(list);
      setCount(typeof data?.count === "number" ? data.count : list.length);
      if (!selectedId && list.length > 0) {
        setSelectedId(list[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się pobrać typów.");
      setTypes([]);
      setCount(0);
    } finally {
      setLoadingList(false);
    }
  }, [selectedId]);

  useEffect(() => {
    void fetchTypes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---------- Pobranie szczegółów wybranego typu ---------- */
  useEffect(() => {
    if (!selectedId) {
      setManifest(null);
      setDdl(null);
      setActions(null);
      return;
    }
    let cancelled = false;
    setLoadingDetails(true);
    setError(null);

    Promise.allSettled([
      api.getOntologyType(selectedId),
      api.getOntologyDdl(selectedId),
      api.getOntologyActions(selectedId),
    ]).then((results) => {
      if (cancelled) return;
      const [m, d, a] = results;
      setManifest(m.status === "fulfilled" ? (m.value as OntologyManifest) : null);
      setDdl(d.status === "fulfilled" ? (d.value as OntologyDdlResponse) : null);
      setActions(a.status === "fulfilled" ? (a.value as OntologyActionsResponse) : null);
      setLoadingDetails(false);
    });

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  /* ---------- Reload manifestów (POST) ---------- */
  const handleReload = useCallback(async () => {
    setReloading(true);
    try {
      await api.reloadOntology();
      await fetchTypes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reload nie powiódł się.");
    } finally {
      setReloading(false);
    }
  }, [fetchTypes]);

  const columns: OntologyColumn[] = useMemo(() => {
    if (!manifest) return [];
    const arr = (manifest.columns ?? []) as OntologyColumn[];
    return Array.isArray(arr) ? arr : [];
  }, [manifest]);

  /* ============================================================
     Render
     ============================================================ */
  return (
    <div className="space-y-5 p-6">
      {/* ===== Nagłówek ===== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-start justify-between gap-3"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Boxes className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight flex items-center">
              Ontologia (W15)
              <HelpTip
                text={
                  "Ogólny model danych definiowany manifestami YAML. Każdy typ ma auto-generowane DDL, REST oraz SDK. " +
                  "Faza 0: tylko podgląd — bez edycji ani publikacji nowych typów."
                }
                side="bottom"
              />
            </h1>
            <p className="text-sm text-muted-foreground">
              Przeglądarka typów obiektów, DDL oraz dostępnych akcji.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-[11px]">
            {count} typów
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={handleReload}
            disabled={reloading || loadingList}
          >
            {reloading ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            )}
            Odśwież manifesty
          </Button>
          <HelpTip
            text={
              "Wymusza ponowne odczytanie manifestów YAML z dysku. Użyj po edycji plików w docs/ontology. " +
              "Domyślnie są wczytywane raz przy starcie backendu."
            }
            side="bottom"
          />
        </div>
      </motion.div>

      {/* ===== Komunikat błędu ===== */}
      {error && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <div className="p-3 flex items-center gap-2 text-amber-600">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs">{error}</span>
          </div>
        </Card>
      )}

      {/* ===== Layout 1/3 + 2/3 ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* --- Lewa kolumna: lista typów --- */}
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-xs font-semibold">Typy obiektów</h3>
              <HelpTip
                text={
                  "Lista wszystkich załadowanych typów ontologii. Klik wybiera typ — szczegóły pojawią się po prawej. " +
                  "Faza 0: lista jest tylko-do-odczytu."
                }
              />
            </div>
            <Badge variant="outline" className="font-mono text-[10px]">
              {types.length}
            </Badge>
          </div>

          <div className="p-2 space-y-1 max-h-[70vh] overflow-y-auto">
            {loadingList && (
              <div className="flex items-center justify-center py-12 text-muted-foreground text-xs">
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Ładowanie typów...
              </div>
            )}

            {!loadingList && types.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Database className="w-7 h-7 mb-2 opacity-40" />
                <p className="text-xs">Brak typów ontologii.</p>
                <p className="text-[10px] mt-1 opacity-60">
                  Dodaj manifest YAML i kliknij &quot;Odśwież manifesty&quot;.
                </p>
              </div>
            )}

            {!loadingList &&
              types.map((t) => {
                const active = t.id === selectedId;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setSelectedId(t.id)}
                    className={cn(
                      "w-full text-left rounded-lg px-3 py-2 transition-colors border",
                      active
                        ? "border-sylion-blue/40 bg-sylion-blue/10"
                        : "border-transparent hover:bg-muted/30",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium truncate">
                        {t.name || t.id}
                      </span>
                      {t.version && (
                        <Badge variant="outline" className="text-[9px] font-mono">
                          v{t.version}
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center justify-between mt-1 text-[10px] text-muted-foreground">
                      <span className="font-mono truncate">{t.id}</span>
                      {t.domain && <span className="opacity-70">{t.domain}</span>}
                    </div>
                    {(t.columns_count !== undefined ||
                      t.actions_count !== undefined) && (
                      <div className="flex gap-3 mt-1 text-[10px] text-muted-foreground">
                        {t.columns_count !== undefined && (
                          <span>{t.columns_count} kolumn</span>
                        )}
                        {t.actions_count !== undefined && (
                          <span>{t.actions_count} akcji</span>
                        )}
                      </div>
                    )}
                  </button>
                );
              })}
          </div>
        </Card>

        {/* --- Prawa kolumna: szczegóły --- */}
        <Card className="bg-[#0f1629] border-sylion-border lg:col-span-2">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-xs font-semibold">
                Szczegóły typu
                {manifest?.name ? (
                  <span className="ml-2 font-mono text-muted-foreground">
                    {manifest.name}
                  </span>
                ) : null}
              </h3>
              <HelpTip
                text={
                  "Pełny manifest YAML, wygenerowane DDL oraz lista akcji dostępnych dla tego typu. " +
                  "Wybierz zakładkę aby zobaczyć interesujący Cię widok."
                }
              />
            </div>
            {loadingDetails && (
              <div className="text-[11px] text-muted-foreground inline-flex items-center">
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                Pobieranie...
              </div>
            )}
          </div>

          <div className="p-3">
            {!selectedId ? (
              <div className="text-xs text-muted-foreground py-12 text-center">
                Wybierz typ z listy po lewej, aby zobaczyć szczegóły.
              </div>
            ) : (
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList>
                  <TabsTrigger value="manifest">
                    <ScrollText className="w-3.5 h-3.5 mr-1.5" />
                    Manifest
                  </TabsTrigger>
                  <TabsTrigger value="ddl">
                    <Database className="w-3.5 h-3.5 mr-1.5" />
                    DDL
                  </TabsTrigger>
                  <TabsTrigger value="actions">
                    <Wrench className="w-3.5 h-3.5 mr-1.5" />
                    Akcje
                  </TabsTrigger>
                </TabsList>

                {/* ====== Manifest ====== */}
                <TabsContent value="manifest" className="mt-3 space-y-4">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-semibold">Podgląd JSON</h4>
                    <HelpTip
                      text={
                        "Surowy manifest typu w formacie JSON (wygenerowany z YAML). " +
                        "Pokazuje wszystkie metadane: domain, version, kolumny, indeksy."
                      }
                    />
                  </div>
                  <pre className="text-[11px] leading-relaxed font-mono bg-black/40 rounded-md p-3 overflow-auto max-h-[40vh] border border-border/30">
                    {manifest ? jsonPretty(manifest) : "—"}
                  </pre>

                  {columns.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-semibold">Kolumny</h4>
                        <HelpTip
                          text={
                            "Lista kolumn typu z atrybutami: typ danych, dopuszcza puste wartości, indeksowane, " +
                            "wyszukiwalne (FTS), enum oraz wartość domyślna."
                          }
                        />
                      </div>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="text-[10px] uppercase">
                              Nazwa
                            </TableHead>
                            <TableHead className="text-[10px] uppercase">
                              Typ
                            </TableHead>
                            <TableHead className="text-[10px] uppercase">
                              Puste
                            </TableHead>
                            <TableHead className="text-[10px] uppercase">
                              Indeks
                            </TableHead>
                            <TableHead className="text-[10px] uppercase">
                              Wyszukiwanie
                            </TableHead>
                            <TableHead className="text-[10px] uppercase">
                              Enum
                            </TableHead>
                            <TableHead className="text-[10px] uppercase">
                              Domyślna
                            </TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {columns.map((col) => (
                            <TableRow key={col.name}>
                              <TableCell className="text-xs font-mono">
                                {col.name}
                              </TableCell>
                              <TableCell className="text-xs">{col.type}</TableCell>
                              <TableCell className="text-xs">
                                {col.nullable ? "tak" : "nie"}
                              </TableCell>
                              <TableCell className="text-xs">
                                {col.indexed ? "tak" : "—"}
                              </TableCell>
                              <TableCell className="text-xs">
                                {col.searchable ? "tak" : "—"}
                              </TableCell>
                              <TableCell className="text-[11px] font-mono text-muted-foreground">
                                {Array.isArray(col.enum) && col.enum.length > 0
                                  ? col.enum.join(", ")
                                  : "—"}
                              </TableCell>
                              <TableCell className="text-[11px] font-mono text-muted-foreground">
                                {col.default !== undefined && col.default !== null
                                  ? String(col.default)
                                  : "—"}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </TabsContent>

                {/* ====== DDL ====== */}
                <TabsContent value="ddl" className="mt-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-semibold">
                      Wygenerowany DDL
                      {ddl?.dialect ? (
                        <Badge
                          variant="outline"
                          className="ml-2 font-mono text-[9px]"
                        >
                          {ddl.dialect}
                        </Badge>
                      ) : null}
                    </h4>
                    <HelpTip
                      text={
                        "Auto-wygenerowany skrypt DDL na podstawie manifestu YAML. " +
                        "Dialekt: SQLite (Faza 0). Plain text — brak runtime'owej kolorystyki."
                      }
                    />
                  </div>
                  <pre className="text-[11px] leading-relaxed font-mono bg-black/40 rounded-md p-3 overflow-auto max-h-[60vh] border border-border/30 whitespace-pre-wrap">
                    {ddl?.ddl ? ddl.ddl : "— brak DDL —"}
                  </pre>
                </TabsContent>

                {/* ====== Akcje ====== */}
                <TabsContent value="actions" className="mt-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-semibold">Dostępne akcje</h4>
                    <HelpTip
                      text={
                        "Lista akcji REST/SDK przypisanych do tego typu. " +
                        "Kolumny: action_id, klasa decyzji (D-level), wymagane Human Gate, endpoint."
                      }
                    />
                  </div>
                  {actions && actions.actions && actions.actions.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-[10px] uppercase">
                            Action ID
                          </TableHead>
                          <TableHead className="text-[10px] uppercase">
                            D-level
                          </TableHead>
                          <TableHead className="text-[10px] uppercase">
                            Human Gate
                          </TableHead>
                          <TableHead className="text-[10px] uppercase">
                            Endpoint
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {actions.actions.map((act) => (
                          <TableRow key={act.action_id}>
                            <TableCell className="text-xs font-mono">
                              {act.action_id}
                            </TableCell>
                            <TableCell className="text-xs">
                              {act.d_level ? (
                                <Badge
                                  variant="outline"
                                  className="font-mono text-[9px]"
                                >
                                  {act.d_level}
                                </Badge>
                              ) : (
                                "—"
                              )}
                            </TableCell>
                            <TableCell className="text-xs">
                              {act.hg_required ? "tak" : "nie"}
                            </TableCell>
                            <TableCell className="text-[11px] font-mono text-muted-foreground">
                              {act.endpoint || "—"}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-xs text-muted-foreground py-6 text-center">
                      Brak akcji dla tego typu.
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
