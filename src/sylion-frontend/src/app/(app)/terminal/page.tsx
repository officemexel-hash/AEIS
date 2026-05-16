"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/common/HelpTip";
import { api, request, API_BASE_URL } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  Terminal as TerminalIcon,
  Plus,
  Trash2,
  Send,
  Filter,
  WifiOff,
  Wifi,
  Loader2,
  Layers,
  ServerCog,
  AlertTriangle,
  Activity,
  ArrowRightCircle,
  Lightbulb,
  Film,
} from "lucide-react";

/* ============================================================
   Typy
   ============================================================ */

type Severity = "info" | "warn" | "error" | "debug";

type ResultKind = "text" | "table" | "error" | "redirect" | "not_implemented";

interface TerminalEvent {
  ts: number; // unix epoch (ms or s)
  layer?: string; // np. W14
  module?: string; // np. SimulationOrchestrator
  model?: string; // np. claude-opus-4
  host?: string; // np. local
  message: string;
  severity?: Severity;
  source?: "stream" | "exec" | "system";
  session_id?: string;
  extra?: Record<string, string | number | boolean | null | undefined>;
}

interface TerminalSession {
  session_id: string;
  title?: string;
  created_at?: number;
}

interface TerminalSessionsResponse {
  sessions: TerminalSession[];
}

interface CommandSpec {
  name: string;
  args: string;
  summary_pl: string;
  summary_en: string;
  aliases: string;
  implemented: string; // "yes" | "no"
}

interface CommandsResponse {
  count: number;
  implemented: number;
  commands: CommandSpec[];
}

interface CommandResult {
  kind: ResultKind;
  text?: string;
  rows?: Array<Record<string, unknown>> | null;
  headers?: string[] | null;
  target?: string | null;
  meta?: Record<string, unknown> | null;
}

/** Wpis w lokalnym buforze historii (echo, wynik, banner). */
interface HistoryEntry {
  id: string;
  ts: number;
  variant: "command" | "text" | "table" | "error" | "redirect" | "not_implemented" | "system";
  text?: string;
  rows?: Array<Record<string, unknown>>;
  headers?: string[];
  target?: string | null;
  session_id?: string;
}

interface PersistedFilters {
  layers: string[];
  hosts: string[];
  severities: Severity[];
}

/* ============================================================
   Pomocnicze
   ============================================================ */

const LAYERS = [
  "W1",
  "W2",
  "W3",
  "W4",
  "W5",
  "W6",
  "W7",
  "W8",
  "W9",
  "W10",
  "W11",
  "W12",
  "W13",
  "W14",
  "W15",
  "W16",
  "W17",
  "W18",
  "W19",
];
const SEVERITIES: Severity[] = ["info", "warn", "error", "debug"];
const HOSTS = ["local", "docker", "worktree", "vps", "cloud", "browser", "mobile"];

const HISTORY_LIMIT = 50;

const STORAGE_SESSIONS = "sylion-v2-terminal-sessions";
const STORAGE_FILTERS = "sylion-v2-terminal-filters";
const STORAGE_HISTORY = "sylion-v2-terminal-history";

function safeRandomId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function readJSON<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function writeJSON<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // quota / privacy mode — silently ignore.
  }
}

function formatTs(ts: number | undefined): string {
  if (!ts) {
    const now = new Date();
    return now.toLocaleTimeString("pl-PL", { hour12: false });
  }
  // Allow seconds (10-digit) or ms.
  const epochMs = ts > 1e12 ? ts : ts * 1000;
  const d = new Date(epochMs);
  return d.toLocaleTimeString("pl-PL", { hour12: false });
}

function severityColor(sev?: Severity): string {
  switch (sev) {
    case "warn":
      return "text-amber-400";
    case "error":
      return "text-red-400";
    case "debug":
      return "text-muted-foreground";
    case "info":
    default:
      return "text-foreground/85";
  }
}

function pad(value: string, length: number): string {
  if (value.length >= length) return value.slice(0, length);
  return value + " ".repeat(length - value.length);
}

/** Heurystyka sprawdźająca czy `target` to URL (zewnętrzny lub wewnętrzny). */
function isRouteTarget(target: string | null | undefined): boolean {
  if (!target) return false;
  return target.startsWith("/") || target.startsWith("http://") || target.startsWith("https://");
}

/* ============================================================
   Strona
   ============================================================ */

export default function TerminalPage() {
  const router = useRouter();

  /* ---------- Stan ---------- */
  const [events, setEvents] = useState<TerminalEvent[]>([]);
  const [sessions, setSessions] = useState<TerminalSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [streamConnected, setStreamConnected] = useState<boolean>(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [input, setInput] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [creatingSession, setCreatingSession] = useState<boolean>(false);

  // Filtry
  const [filterLayers, setFilterLayers] = useState<string[]>([]);
  const [filterHosts, setFilterHosts] = useState<string[]>([]);
  const [filterSeverities, setFilterSeverities] = useState<Severity[]>([]);

  // Historia (echo + wyniki) — bufor lokalny ostatnich N
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  // Command palette
  const [commandsCatalog, setCommandsCatalog] = useState<CommandSpec[]>([]);
  const [paletteOpen, setPaletteOpen] = useState<boolean>(false);
  const [paletteIndex, setPaletteIndex] = useState<number>(0);

  // Hydracja flagi — żeby nie nadpisywać localStorage zerami przed rehydratem
  const [hydrated, setHydrated] = useState<boolean>(false);

  /* ---------- Refy ---------- */
  const consoleRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const activeSessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  /* ---------- Hydracja localStorage ---------- */
  useEffect(() => {
    queueMicrotask(() => {
    // Filtry
    const persistedFilters = readJSON<PersistedFilters>(STORAGE_FILTERS);
    if (persistedFilters) {
      if (Array.isArray(persistedFilters.layers)) setFilterLayers(persistedFilters.layers);
      if (Array.isArray(persistedFilters.hosts)) setFilterHosts(persistedFilters.hosts);
      if (Array.isArray(persistedFilters.severities)) setFilterSeverities(persistedFilters.severities);
    }
    // Historia
    const persistedHistory = readJSON<HistoryEntry[]>(STORAGE_HISTORY);
    if (Array.isArray(persistedHistory) && persistedHistory.length > 0) {
      setHistory(persistedHistory.slice(-HISTORY_LIMIT));
    }
    // Sesje (cache lokalny — backend i tak będzie autorytatywny po refreshSessions)
    const persistedSessions = readJSON<TerminalSession[]>(STORAGE_SESSIONS);
    if (Array.isArray(persistedSessions) && persistedSessions.length > 0) {
      setSessions(persistedSessions);
      const firstId = persistedSessions[0]?.session_id ?? null;
      if (firstId) setActiveSessionId(firstId);
    }
    setHydrated(true);
    });
  }, []);

  /* ---------- Persist filters ---------- */
  useEffect(() => {
    if (!hydrated) return;
    writeJSON<PersistedFilters>(STORAGE_FILTERS, {
      layers: filterLayers,
      hosts: filterHosts,
      severities: filterSeverities,
    });
  }, [hydrated, filterLayers, filterHosts, filterSeverities]);

  /* ---------- Persist history ---------- */
  useEffect(() => {
    if (!hydrated) return;
    writeJSON<HistoryEntry[]>(STORAGE_HISTORY, history.slice(-HISTORY_LIMIT));
  }, [hydrated, history]);

  /* ---------- Persist sessions ---------- */
  useEffect(() => {
    if (!hydrated) return;
    writeJSON<TerminalSession[]>(STORAGE_SESSIONS, sessions);
  }, [hydrated, sessions]);

  /* ---------- Auto-scroll ---------- */
  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [events, history]);

  /* ---------- Pobranie sesji ---------- */
  const refreshSessions = useCallback(async () => {
    try {
      const data = (await api.listTerminalSessions()) as TerminalSessionsResponse;
      const list = Array.isArray(data?.sessions) ? data.sessions : [];
      setSessions(list);
      setActiveSessionId((current) => {
        if (current && list.some((s) => s.session_id === current)) return current;
        return list.length > 0 ? list[0].session_id : current;
      });
    } catch {
      // Nie czyścimy lokalnego cache — backend mógł chwilowo paść.
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void refreshSessions();
    });
  }, [refreshSessions]);

  /* ---------- Pobranie katalogu komend ---------- */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await request<CommandsResponse>("/api/v1/terminal/commands");
        if (cancelled) return;
        const list = Array.isArray(data?.commands) ? data.commands : [];
        setCommandsCatalog(list);
      } catch {
        // brak katalogu = palette po prostu nie sugeruje
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /* ---------- Subskrypcja stream'u (EventSource) ---------- */
  useEffect(() => {
    const params = new URLSearchParams();
    if (filterLayers.length > 0) params.set("layers", filterLayers.join(","));
    if (filterHosts.length > 0) params.set("hosts", filterHosts.join(","));
    if (filterSeverities.length > 0)
      params.set("severities", filterSeverities.join(","));

    const url = `${API_BASE_URL}/api/v1/terminal/stream${
      params.toString() ? `?${params.toString()}` : ""
    }`;

    let es: EventSource | null = null;
    try {
      es = new EventSource(url);
    } catch (err) {
      queueMicrotask(() => {
        setStreamConnected(false);
        setStreamError(err instanceof Error ? err.message : "EventSource init failed");
      });
      return;
    }

    queueMicrotask(() => {
      setStreamError(null);
    });

    es.onopen = () => {
      setStreamConnected(true);
      setStreamError(null);
    };

    es.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data) as Partial<TerminalEvent>;
        const next: TerminalEvent = {
          ts: typeof parsed.ts === "number" ? parsed.ts : Date.now(),
          layer: parsed.layer,
          module: parsed.module,
          model: parsed.model,
          host: parsed.host || "local",
          message: parsed.message ?? String(ev.data),
          severity: parsed.severity ?? "info",
          source: "stream",
          session_id: parsed.session_id ?? activeSessionIdRef.current ?? undefined,
          extra: parsed.extra,
        };
        setEvents((prev) => {
          const merged = [...prev, next];
          // Limit ring buffer to 500 entries — przewija się szybko.
          return merged.length > 500 ? merged.slice(merged.length - 500) : merged;
        });
      } catch {
        // Linia nie-JSON — i tak ją zaloguj.
        setEvents((prev) => [
          ...prev,
          {
            ts: Date.now(),
            host: "local",
            message: String(ev.data),
            severity: "info",
            source: "stream",
            session_id: activeSessionIdRef.current ?? undefined,
          },
        ]);
      }
    };

    es.onerror = () => {
      setStreamConnected(false);
      setStreamError("Stream rozłączony — backend nie wysyła zdarzeń lub jest offline.");
    };

    return () => {
      es?.close();
      setStreamConnected(false);
    };
  }, [filterLayers, filterHosts, filterSeverities]);

  /* ---------- Helper: wpis do bufora historii ---------- */
  const pushHistory = useCallback((entry: Omit<HistoryEntry, "id" | "ts"> & Partial<Pick<HistoryEntry, "ts">>) => {
    setHistory((prev) => {
      const next: HistoryEntry = {
        id: safeRandomId(),
        ts: entry.ts ?? Date.now(),
        variant: entry.variant,
        text: entry.text,
        rows: entry.rows,
        headers: entry.headers,
        target: entry.target ?? null,
        session_id: entry.session_id ?? activeSessionIdRef.current ?? undefined,
      };
      const merged = [...prev, next];
      return merged.length > HISTORY_LIMIT ? merged.slice(merged.length - HISTORY_LIMIT) : merged;
    });
  }, []);

  /* ---------- Wykonanie polecenia ---------- */
  const submitCommand = useCallback(
    async (rawLine: string) => {
      const trimmed = rawLine.trim();
      if (!trimmed || submitting) return;
      // Backend wymaga prefiksu "/" — UI go domyślnie dokleja, gdy operator
      // wpisze samą nazwę.
      const line = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;

      setSubmitting(true);
      setPaletteOpen(false);

      // Historia zostaje lokalna dla natychmiastowego feedbacku, a stream/replay
      // emituje backend przez /terminal/exec, żeby nagrania W18 były kompletne.
      pushHistory({ variant: "command", text: line });

      try {
        const result = (await api.execTerminalCommand(line, {
          session_id: activeSessionIdRef.current,
        })) as CommandResult;
        const kind: ResultKind = (result.kind as ResultKind) ?? "text";

        if (kind === "table") {
          pushHistory({
            variant: "table",
            text: result.text ?? "",
            rows: Array.isArray(result.rows) ? (result.rows as Array<Record<string, unknown>>) : [],
            headers: Array.isArray(result.headers) ? result.headers : undefined,
          });
        } else if (kind === "error") {
          pushHistory({ variant: "error", text: result.text ?? "(błąd bez treści)" });
        } else if (kind === "redirect") {
          pushHistory({
            variant: "redirect",
            text: result.text ?? "",
            target: result.target ?? null,
          });
          if (isRouteTarget(result.target)) {
            // Mała pauza wizualna — operator widzi "redirected to X"
            // przed nawigacją.
            const target = result.target as string;
            setTimeout(() => {
              router.push(target);
            }, 300);
          }
        } else if (kind === "not_implemented") {
          pushHistory({
            variant: "not_implemented",
            text:
              result.text ??
              "Funkcja w fazie G2/G3 — szczegóły w opisie.",
          });
        } else {
          pushHistory({ variant: "text", text: result.text ?? "" });
        }

        // Zachowujemy też echo w activity stream (dla operatorów, którzy patrzą tam)
      } catch (err) {
        const msg = err instanceof Error ? err.message : "exec failed";
        pushHistory({ variant: "error", text: msg });
        setEvents((prev) => [
          ...prev,
          {
            ts: Date.now(),
            host: "local",
            layer: "W18",
            module: "exec",
            message: msg,
            severity: "error",
            source: "exec",
            session_id: activeSessionIdRef.current ?? undefined,
          },
        ]);
      } finally {
        setSubmitting(false);
        setInput("");
      }
    },
    [submitting, router, pushHistory],
  );

  /* ---------- Submit z formularza ---------- */
  const onFormSubmit = useCallback(
    (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      void submitCommand(input);
    },
    [input, submitCommand],
  );

  /* ---------- Nowa sesja ---------- */
  const createSession = useCallback(async () => {
    setCreatingSession(true);
    try {
      const title = `Sesja ${new Date().toLocaleTimeString("pl-PL", { hour12: false })}`;
      const resp = (await api.createTerminalSession(title)) as TerminalSession;
      if (resp?.session_id) {
        setActiveSessionId(resp.session_id);
        // Optymistycznie dopisujemy do lokalnej listy — refresh poniżej skonsoliduje.
        setSessions((prev) => {
          if (prev.some((s) => s.session_id === resp.session_id)) return prev;
          return [resp, ...prev];
        });
      }
      await refreshSessions();
    } catch {
      // ignore — backend niedostępny, lokalny cache pozostaje.
    } finally {
      setCreatingSession(false);
    }
  }, [refreshSessions]);

  /* ---------- Toggle filter helpers ---------- */
  function toggleInArray<T>(arr: T[], value: T): T[] {
    return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
  }

  /* ---------- Czyszczenie ---------- */
  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  /* ---------- Command palette: filtrowanie sugestii ---------- */
  const paletteSuggestions = useMemo<CommandSpec[]>(() => {
    if (!input.startsWith("/")) return [];
    const stripped = input.slice(1).toLowerCase();
    const filtered = commandsCatalog.filter((c) => {
      if (!stripped) return true;
      if (c.name.toLowerCase().includes(stripped)) return true;
      if (c.aliases.toLowerCase().includes(stripped)) return true;
      if (c.summary_pl.toLowerCase().includes(stripped)) return true;
      return false;
    });
    return filtered.slice(0, 10);
  }, [input, commandsCatalog]);

  // Otwieramy paletę gdy wpisany jest "/", zamykamy gdy operator wyczyści lub wyśle.
  useEffect(() => {
    queueMicrotask(() => {
      if (input.startsWith("/") && paletteSuggestions.length > 0) {
        setPaletteOpen(true);
        setPaletteIndex((idx) => Math.min(idx, paletteSuggestions.length - 1));
      } else {
        setPaletteOpen(false);
        setPaletteIndex(0);
      }
    });
  }, [input, paletteSuggestions.length]);

  /* ---------- Klawiatura w palette ---------- */
  const onInputKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        void submitCommand(input);
        return;
      }
      if (!paletteOpen || paletteSuggestions.length === 0) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setPaletteIndex((idx) => (idx + 1) % paletteSuggestions.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setPaletteIndex((idx) =>
          idx <= 0 ? paletteSuggestions.length - 1 : idx - 1,
        );
      } else if (e.key === "Tab") {
        e.preventDefault();
        const target = paletteSuggestions[paletteIndex];
        if (target) {
          setInput(`/${target.name}${target.args ? " " : ""}`);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        setPaletteOpen(false);
      }
    },
    [input, paletteOpen, paletteSuggestions, paletteIndex, submitCommand],
  );

  /* ---------- Render historii — kind switch ---------- */
  const renderHistoryEntry = useCallback((entry: HistoryEntry) => {
    const ts = formatTs(entry.ts);
    const tsBadge = (
      <span className="text-[10px] font-mono text-muted-foreground shrink-0">{ts}</span>
    );

    if (entry.variant === "command") {
      return (
        <div
          key={entry.id}
          className="flex items-start gap-2 px-3 py-1 border-b border-border/10"
        >
          {tsBadge}
          <span className="font-mono text-[11px] text-sylion-blue">
            {entry.text}
          </span>
        </div>
      );
    }

    if (entry.variant === "text") {
      return (
        <div
          key={entry.id}
          className="flex items-start gap-2 px-3 py-1.5 border-b border-border/10"
        >
          {tsBadge}
          <pre className="font-mono text-[11px] text-foreground/85 whitespace-pre-wrap break-words flex-1">
            {entry.text}
          </pre>
        </div>
      );
    }

    if (entry.variant === "table") {
      const rows = entry.rows ?? [];
      const headers =
        entry.headers && entry.headers.length > 0
          ? entry.headers
          : rows.length > 0
          ? Object.keys(rows[0])
          : [];
      return (
        <div
          key={entry.id}
          className="px-3 py-2 border-b border-border/10 space-y-2"
        >
          <div className="flex items-center gap-2">
            {tsBadge}
            {entry.text && (
              <span className="text-[10px] text-muted-foreground">
                {entry.text}
              </span>
            )}
          </div>
          {rows.length === 0 ? (
            <div className="text-[11px] text-muted-foreground italic">
              (pusta tabela)
            </div>
          ) : (
            <div className="overflow-x-auto rounded-md border border-border/30">
              <table className="table-auto w-full text-[11px] font-mono">
                <thead className="bg-muted/30">
                  <tr>
                    {headers.map((h) => (
                      <th
                        key={h}
                        className="text-left px-2 py-1 border-b border-border/40 text-sylion-blue/80 uppercase tracking-wide"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, ri) => (
                    <tr
                      key={ri}
                      className="border-b border-border/20 hover:bg-muted/20"
                    >
                      {headers.map((h) => {
                        const v = row[h];
                        const text =
                          v === null || v === undefined
                            ? ""
                            : typeof v === "string"
                            ? v
                            : JSON.stringify(v);
                        return (
                          <td
                            key={h}
                            className="px-2 py-1 align-top text-foreground/85 break-words"
                          >
                            {text}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      );
    }

    if (entry.variant === "error") {
      return (
        <div
          key={entry.id}
          className="px-3 py-2 border-b border-border/10"
        >
          <div className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2">
            <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                {tsBadge}
                <span className="text-[10px] uppercase tracking-wider text-red-400 font-semibold">
                  błąd
                </span>
              </div>
              <pre className="font-mono text-[11px] text-red-200 whitespace-pre-wrap break-words">
                {entry.text}
              </pre>
            </div>
          </div>
        </div>
      );
    }

    if (entry.variant === "redirect") {
      return (
        <div
          key={entry.id}
          className="px-3 py-2 border-b border-border/10"
        >
          <div className="flex items-start gap-2 rounded-md border border-sylion-blue/40 bg-sylion-blue/10 px-3 py-2">
            <ArrowRightCircle className="w-4 h-4 text-sylion-blue mt-0.5 shrink-0" />
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                {tsBadge}
                <span className="text-[10px] uppercase tracking-wider text-sylion-blue font-semibold">
                  redirect
                </span>
              </div>
              <div className="font-mono text-[11px] text-foreground/85 whitespace-pre-wrap break-words">
                {entry.text || "redirected"}
                {entry.target && (
                  <>
                    {" → "}
                    <span className="text-sylion-blue">{entry.target}</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      );
    }

    if (entry.variant === "not_implemented") {
      return (
        <div
          key={entry.id}
          className="px-3 py-2 border-b border-border/10"
        >
          <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2">
            <Lightbulb className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                {tsBadge}
                <span className="text-[10px] uppercase tracking-wider text-amber-400 font-semibold">
                  funkcja w fazie G2/G3
                </span>
              </div>
              <pre className="font-mono text-[11px] text-amber-100 whitespace-pre-wrap break-words">
                {entry.text || "Funkcja w fazie G2/G3 — szczegóły w opisie."}
              </pre>
            </div>
          </div>
        </div>
      );
    }

    // system / fallback
    return (
      <div
        key={entry.id}
        className="flex items-start gap-2 px-3 py-1 border-b border-border/10"
      >
        {tsBadge}
        <span className="font-mono text-[11px] text-muted-foreground italic">
          {entry.text}
        </span>
      </div>
    );
  }, []);

  const visibleEvents = useMemo(() => events, [events]);

  /* ============================================================
     Render
     ============================================================ */
  return (
    <div className="space-y-4 p-6">
      {/* ===== Nagłówek ===== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-start justify-between gap-3"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <TerminalIcon className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight flex items-center">
              Terminal Operatora (W18)
              <HelpTip
                text={
                  "Strumień aktywności wszystkich warstw AEIS. Wpisz polecenie jako /<komenda>, aby wykonać akcję " +
                  "operatorską. Sugestie pojawiają się po wpisaniu '/'. Sesje, filtry i historia są zapisywane lokalnie."
                }
                side="bottom"
              />
            </h1>
            <p className="text-sm text-muted-foreground">
              Strumień zdarzeń i komendy ukośnikowe. Wpisz <span className="font-mono">/help</span>{" "}
              aby zobaczyć dostępne komendy. Tab uzupełnia sugestię, Enter wykonuje.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/terminal/replay">
            <Button
              variant="outline"
              size="xs"
              className="border-sylion-blue/40 text-sylion-blue bg-sylion-blue/5 hover:bg-sylion-blue/10"
            >
              <Film className="w-3 h-3 mr-1" />
              Odtwarzanie nagrań (W18 G3)
            </Button>
          </Link>
          {streamConnected ? (
            <Badge
              variant="outline"
              className="text-[10px] border-sylion-green/30 text-sylion-green bg-sylion-green/5"
            >
              <Wifi className="w-3 h-3 mr-1" /> stream OK
            </Badge>
          ) : (
            <Badge
              variant="outline"
              className="text-[10px] border-amber-500/30 text-amber-600 bg-amber-500/5"
            >
              <WifiOff className="w-3 h-3 mr-1" /> niepodłączone
            </Badge>
          )}
          <Badge variant="outline" className="font-mono text-[10px]">
            {visibleEvents.length} zdarzeń
          </Badge>
          <Badge variant="outline" className="font-mono text-[10px]">
            {history.length}/{HISTORY_LIMIT} historia
          </Badge>
        </div>
      </motion.div>

      {/* ===== Toolbar filtrów ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-xs font-semibold">Filtry</span>
            <HelpTip
              text={
                "Filtry strumienia zdarzeń. Pusta lista = brak filtra (wszystko). Filtry działają po stronie backendu " +
                "(query string ?layers=&hosts=&severities=). Stan filtrów jest zapisywany lokalnie i przeżywa reload."
              }
            />
          </div>

          {/* Layers */}
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-[10px] uppercase text-muted-foreground tracking-wider mr-1">
              warstwy
            </span>
            {LAYERS.map((l) => {
              const active = filterLayers.includes(l);
              return (
                <button
                  key={l}
                  type="button"
                  onClick={() => setFilterLayers((arr) => toggleInArray(arr, l))}
                  className={cn(
                    "text-[10px] font-mono px-2 py-0.5 rounded border transition-colors",
                    active
                      ? "border-sylion-blue/60 bg-sylion-blue/15 text-sylion-blue"
                      : "border-border/40 text-muted-foreground hover:bg-muted/30",
                  )}
                >
                  {l}
                </button>
              );
            })}
          </div>

          {/* Hosts */}
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-[10px] uppercase text-muted-foreground tracking-wider mr-1">
              hosty
            </span>
            {HOSTS.map((h) => {
              const active = filterHosts.includes(h);
              return (
                <button
                  key={h}
                  type="button"
                  onClick={() => setFilterHosts((arr) => toggleInArray(arr, h))}
                  className={cn(
                    "text-[10px] font-mono px-2 py-0.5 rounded border transition-colors",
                    active
                      ? "border-sylion-blue/60 bg-sylion-blue/15 text-sylion-blue"
                      : "border-border/40 text-muted-foreground hover:bg-muted/30",
                  )}
                >
                  {h}
                </button>
              );
            })}
          </div>

          {/* Severities */}
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-[10px] uppercase text-muted-foreground tracking-wider mr-1">
              poziom
            </span>
            {SEVERITIES.map((s) => {
              const active = filterSeverities.includes(s);
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() =>
                    setFilterSeverities((arr) => toggleInArray(arr, s))
                  }
                  className={cn(
                    "text-[10px] font-mono px-2 py-0.5 rounded border transition-colors",
                    active
                      ? "border-sylion-blue/60 bg-sylion-blue/15 text-sylion-blue"
                      : "border-border/40 text-muted-foreground hover:bg-muted/30",
                  )}
                >
                  {s}
                </button>
              );
            })}
          </div>
        </div>
      </Card>

      {streamError && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <div className="p-3 flex items-center gap-2 text-amber-600">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs">{streamError}</span>
          </div>
        </Card>
      )}

      {/* ===== Główny layout: terminal + sesje ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
        {/* --- Kolumna terminala --- */}
        <div className="space-y-4">
          {/* Activity stream */}
          <Card className="bg-[#0f1629] border-sylion-border flex flex-col">
            <div className="p-3 border-b border-border/30 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-sylion-blue" />
                <h3 className="text-xs font-semibold">Strumień aktywności</h3>
                <HelpTip
                  text={
                    "Format linii: HH:MM:SS  warstwa·moduł  model@host  komunikat. " +
                    "Bufor pierścieniowy: ostatnie 500 zdarzeń. Automatyczne przewijanie do dołu. Filtry redukują widoczne linie po stronie backendu."
                  }
                />
              </div>
              <Button variant="outline" size="xs" onClick={clearEvents}>
                <Trash2 className="w-3 h-3 mr-1" />
                Wyczyść
              </Button>
            </div>

            <div
              ref={consoleRef}
              className="font-mono text-[11px] leading-relaxed bg-black/60 px-3 py-2 overflow-auto max-h-[50vh] min-h-[30vh]"
            >
              {visibleEvents.length === 0 ? (
                <div className="text-muted-foreground/70 py-12 text-center">
                  Brak zdarzeń. Wpisz polecenie poniżej lub poczekaj na strumień.
                </div>
              ) : (
                visibleEvents.map((ev, idx) => {
                  const layerMod = `${ev.layer ?? "?"}·${ev.module ?? "?"}`;
                  const modelHost = `${ev.model ?? "—"}@${ev.host ?? "local"}`;
                  const meta = ev.extra || {};
                  const badges = [
                    ["project", meta.project_id],
                    ["role", meta.role],
                    ["agent", meta.agent_id || meta.worker_id],
                    ["env", meta.environment_id],
                    ["council", meta.council_session_id],
                    ["phase", meta.phase],
                  ].filter(([, value]) => value !== undefined && value !== null && String(value) !== "");
                  return (
                    <div
                      key={`${ev.ts}-${idx}`}
                      className={cn(
                        "whitespace-pre-wrap break-words",
                        severityColor(ev.severity),
                      )}
                    >
                      <span className="text-muted-foreground">
                        {formatTs(ev.ts)}
                      </span>
                      {"  "}
                      <span className="text-sylion-blue/80">
                        {pad(layerMod, 22)}
                      </span>
                      {"  "}
                      <span className="text-muted-foreground">
                        {pad(modelHost, 24)}
                      </span>
                      {"  "}
                      <span>{ev.message}</span>
                      {badges.length > 0 && (
                        <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
                          {badges.map(([label, value]) => (
                            <span
                              key={`${label}-${value}`}
                              className="rounded border border-sylion-blue/30 px-1 py-0.5 text-[10px] text-sylion-blue/90"
                            >
                              {label}:{String(value)}
                            </span>
                          ))}
                        </span>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </Card>

          {/* Historia komend (kind-aware) */}
          <Card className="bg-[#0f1629] border-sylion-border flex flex-col">
            <div className="p-3 border-b border-border/30 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TerminalIcon className="w-4 h-4 text-sylion-blue" />
                <h3 className="text-xs font-semibold">
                  Historia komend i wyników
                </h3>
                <HelpTip
                  text={
                    "Lokalna historia ostatnich " +
                    String(HISTORY_LIMIT) +
                    " linii: echo komend, wyniki tekstowe i tabelaryczne oraz komunikaty błędów, przekierowań i brakujących implementacji. " +
                    "Zapisywane w localStorage (klucz sylion-v2-terminal-history) — przeżywa reload."
                  }
                />
                <Badge variant="outline" className="font-mono text-[10px]">
                  {history.length}/{HISTORY_LIMIT}
                </Badge>
              </div>
              <Button variant="outline" size="xs" onClick={clearHistory}>
                <Trash2 className="w-3 h-3 mr-1" />
                Wyczyść
              </Button>
            </div>

            <div className="bg-black/40 overflow-auto max-h-[40vh] min-h-[20vh]">
              {history.length === 0 ? (
                <div className="text-muted-foreground/70 py-10 text-center text-xs">
                  Bufor historii pusty. Wpisz komendę aby zacząć.
                </div>
              ) : (
                history.map(renderHistoryEntry)
              )}
            </div>

            {/* Input z palette */}
            <div className="border-t border-border/30 p-2">
              <form
                onSubmit={onFormSubmit}
                className="flex items-center gap-2 relative"
              >
                <span className="font-mono text-xs text-sylion-blue pl-2">$</span>
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onInputKeyDown}
                  placeholder="np. /help, /sessions, /agents — Tab uzupełnia, Enter wykonuje"
                  className="flex-1 bg-transparent outline-none border-0 font-mono text-xs placeholder:text-muted-foreground/50"
                  disabled={submitting}
                  autoComplete="off"
                  spellCheck={false}
                />
                <Button
                  type="submit"
                  size="xs"
                  disabled={submitting || !input.trim()}
                >
                  {submitting ? (
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                  ) : (
                    <Send className="w-3 h-3 mr-1" />
                  )}
                  Wyślij
                </Button>
                <HelpTip
                  text={
                    "Polecenie zostaje wysłane do POST /api/v1/terminal/exec. " +
                    "Wynik jest renderowany w historii zgodnie z typem odpowiedzi: tekst, tabela, błąd, przekierowanie albo brak implementacji. " +
                    "Sugestie ładowane z GET /api/v1/terminal/commands."
                  }
                />

                {/* ----- Command palette dropdown ----- */}
                {paletteOpen && paletteSuggestions.length > 0 && (
                  <div
                    role="listbox"
                    className="absolute bottom-full left-0 right-0 mb-2 z-30 rounded-md border border-sylion-border bg-[#0b1224] shadow-xl overflow-hidden max-h-[40vh] overflow-y-auto"
                  >
                    <div className="px-3 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border/30 flex items-center justify-between">
                      <span>Sugestie ({paletteSuggestions.length})</span>
                      <span className="font-mono">
                        Tab = uzupełnij · Enter = wykonaj · Esc = zamknij
                      </span>
                    </div>
                    {paletteSuggestions.map((cmd, i) => {
                      const active = i === paletteIndex;
                      const implemented = cmd.implemented === "yes";
                      return (
                        <button
                          key={cmd.name}
                          type="button"
                          role="option"
                          aria-selected={active}
                          onMouseEnter={() => setPaletteIndex(i)}
                          onClick={() => {
                            void submitCommand(`/${cmd.name}`);
                          }}
                          className={cn(
                            "w-full text-left px-3 py-2 flex items-start gap-3 border-b border-border/10 transition-colors",
                            active ? "bg-sylion-blue/15" : "hover:bg-muted/20",
                          )}
                        >
                          <span className="font-mono text-[11px] text-sylion-blue shrink-0 w-32 truncate">
                            /{cmd.name}
                            {cmd.args ? (
                              <span className="text-muted-foreground"> {cmd.args}</span>
                            ) : null}
                          </span>
                          <span className="flex-1 text-[11px] text-foreground/80 truncate">
                            {cmd.summary_pl}
                          </span>
                          {!implemented && (
                            <Badge
                              variant="outline"
                              className="text-[9px] border-amber-500/30 text-amber-500 bg-amber-500/5 shrink-0"
                            >
                              G2/G3
                            </Badge>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </form>
            </div>
          </Card>
        </div>

        {/* --- Sesje --- */}
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-3 border-b border-border/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-sylion-blue" />
              <h3 className="text-xs font-semibold">Sesje</h3>
              <HelpTip
                text={
                  "Lista aktywnych sesji terminala. Klik = ustaw aktywną. Nowe zdarze?ia z wykonania komendy są tagowane ID tej sesji. " +
                  "Sesje są cache'owane lokalnie (klucz sylion-v2-terminal-sessions) — przeżywają reload."
                }
              />
            </div>
            <Badge variant="outline" className="font-mono text-[10px]">
              {sessions.length}
            </Badge>
          </div>
          <div className="p-2 space-y-1 max-h-[60vh] overflow-y-auto">
            {sessions.length === 0 && (
              <div className="text-xs text-muted-foreground py-6 text-center">
                Brak sesji. Utwórz pierwszą.
              </div>
            )}
            {sessions.map((s) => {
              const active = s.session_id === activeSessionId;
              return (
                <button
                  key={s.session_id}
                  type="button"
                  onClick={() => setActiveSessionId(s.session_id)}
                  className={cn(
                    "w-full text-left rounded-md px-3 py-2 border transition-colors",
                    active
                      ? "border-sylion-blue/60 bg-sylion-blue/15 ring-1 ring-sylion-blue/30"
                      : "border-transparent hover:bg-muted/30",
                  )}
                >
                  <div className="flex items-center gap-2">
                    {active && (
                      <span className="w-1.5 h-1.5 rounded-full bg-sylion-blue animate-pulse" />
                    )}
                    <div className="text-xs font-medium truncate flex-1">
                      {s.title || s.session_id}
                    </div>
                    {active && (
                      <Badge
                        variant="outline"
                        className="text-[9px] border-sylion-blue/40 text-sylion-blue bg-sylion-blue/10"
                      >
                        aktywna
                      </Badge>
                    )}
                  </div>
                  <div className="text-[10px] text-muted-foreground font-mono truncate">
                    {s.session_id}
                  </div>
                  {s.created_at && (
                    <div className="text-[10px] text-muted-foreground">
                      {formatTs(s.created_at)}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
          <div className="p-2 border-t border-border/30">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={createSession}
              disabled={creatingSession}
            >
              {creatingSession ? (
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : (
                <Plus className="w-3.5 h-3.5 mr-1.5" />
              )}
              Nowa sesja
            </Button>
          </div>
        </Card>
      </div>

      {/* ===== Status bar ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-2 flex flex-wrap items-center justify-between gap-3 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <ServerCog className="w-3.5 h-3.5" />
              strumień:&nbsp;
              <span
                className={cn(
                  "font-semibold",
                  streamConnected ? "text-sylion-green" : "text-amber-500",
                )}
              >
                {streamConnected ? "podłączony" : "niepodłączony"}
              </span>
            </span>
            <span>odebrane: {visibleEvents.length}</span>
            <span>historia: {history.length}/{HISTORY_LIMIT}</span>
            <span>komendy: {commandsCatalog.length}</span>
            <span>
              aktywna sesja:{" "}
              <span className="font-mono">
                {activeSessionId ? activeSessionId.slice(0, 8) : "—"}
              </span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="xs" onClick={clearEvents}>
              <Trash2 className="w-3 h-3 mr-1" />
              Strumień
            </Button>
            <Button variant="ghost" size="xs" onClick={clearHistory}>
              <Trash2 className="w-3 h-3 mr-1" />
              Historia
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
