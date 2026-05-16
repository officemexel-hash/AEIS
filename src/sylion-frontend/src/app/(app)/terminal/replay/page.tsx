"use client";

/**
 * SYLION AEIS v2 — W18 G3 step 2: Replay-as-Film operator UI.
 *
 * Timeline scrub with 1x/2x/4x/8x replay over a recorded slice of the
 * terminal activity stream.
 *
 * Backend contract (G3 step 1, commit e9d5e507):
 *   GET /api/v1/terminal/replay/days
 *     -> { count: number, days: string[] }   (YYYY-MM-DD, newest first)
 *   GET /api/v1/terminal/replay/slice?start_ts=&end_ts=&session_id=&layer=&max_events=
 *     -> ReplaySlice {
 *          events: TerminalEvent[],          (chronological)
 *          start_ts: number,
 *          end_ts: number,
 *          total_count: number,
 *          truncated: boolean,
 *          filter_session_id: string | null,
 *          filter_layer: string | null,
 *        }
 *
 * Note: TerminalEvent.ts is **epoch seconds** (server time). All scrub
 * math + setTimeout deltas convert to ms locally.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/common/HelpTip";
import { request } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  Film,
  Play,
  Pause,
  RotateCcw,
  Clock,
  Layers,
  Loader2,
  AlertTriangle,
  ArrowLeft,
  Download,
  Gauge,
} from "lucide-react";

/* ============================================================
   Typy
   ============================================================ */

type Severity = "info" | "warn" | "error" | "debug" | "hg";

interface ReplayEvent {
  ts: number;
  layer?: string;
  module?: string;
  model?: string;
  host?: string;
  message: string;
  severity?: Severity;
  session_id?: string;
  cost_usd?: number;
  event_id?: string;
  extra?: Record<string, unknown>;
}

interface ReplaySliceResponse {
  events: ReplayEvent[];
  start_ts: number;
  end_ts: number;
  total_count: number;
  truncated: boolean;
  filter_session_id: string | null;
  filter_layer: string | null;
}

interface ReplayDaysResponse {
  count: number;
  days: string[];
}

type Speed = 1 | 2 | 4 | 8;

/* ============================================================
   Stałe
   ============================================================ */

// Layer dropdown matches the live terminal page LAYERS plus an "all"
// sentinel. Backend treats empty layer query as no filter, so "all"
// maps to "".
const LAYER_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "wszystkie" },
  { value: "W7", label: "W7" },
  { value: "W11", label: "W11" },
  { value: "W15", label: "W15" },
  { value: "W17", label: "W17" },
  { value: "W18", label: "W18" },
];

const SPEED_OPTIONS: Speed[] = [1, 2, 4, 8];

// Cap any single setTimeout delay to avoid pathological multi-minute
// gaps in recorded data freezing the UI. If two events are 10 minutes
// apart we still want play to advance after a sane wait.
const MAX_STEP_DELAY_MS = 5_000;

/* ============================================================
   Helpers
   ============================================================ */

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

/** Format epoch seconds as HH:MM:SS (local). */
function formatTsHMS(tsSec: number | undefined): string {
  if (!tsSec || !Number.isFinite(tsSec)) return "--:--:--";
  // ReplayEvent.ts is epoch seconds, but be defensive against
  // accidental ms (>1e12 => already ms).
  const ms = tsSec > 1e12 ? tsSec : tsSec * 1000;
  const d = new Date(ms);
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

/** YYYY-MM-DD => epoch seconds at local midnight. */
function dayToStartSec(day: string): number {
  // Parse explicitly to avoid TZ surprises with new Date(string).
  const [y, m, d] = day.split("-").map((s) => Number(s));
  if (!y || !m || !d) return Math.floor(Date.now() / 1000);
  return Math.floor(new Date(y, m - 1, d, 0, 0, 0, 0).getTime() / 1000);
}

/** epoch seconds -> "YYYY-MM-DDTHH:MM" for <input type=datetime-local>. */
function secToLocalInput(tsSec: number): string {
  const d = new Date(tsSec * 1000);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** "YYYY-MM-DDTHH:MM" -> epoch seconds. */
function localInputToSec(s: string): number {
  if (!s) return 0;
  const t = new Date(s).getTime();
  return Number.isFinite(t) ? Math.floor(t / 1000) : 0;
}

function severityColor(sev?: Severity): string {
  switch (sev) {
    case "warn":
      return "text-amber-400";
    case "error":
      return "text-red-400";
    case "debug":
      return "text-muted-foreground";
    case "hg":
      return "text-fuchsia-400";
    case "info":
    default:
      return "text-foreground/85";
  }
}

function pad(value: string, length: number): string {
  if (value.length >= length) return value.slice(0, length);
  return value + " ".repeat(length - value.length);
}

/** Binary search: smallest index whose ev.ts >= targetSec.
 *  Returns events.length if none. */
function findIndexAtTs(events: ReplayEvent[], targetSec: number): number {
  let lo = 0;
  let hi = events.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (events[mid].ts < targetSec) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  return lo;
}

/* ============================================================
   Strona
   ============================================================ */

export default function TerminalReplayPage() {
  /* ---------- Stan ---------- */
  // Day picker
  const [days, setDays] = useState<string[]>([]);
  const [daysLoading, setDaysLoading] = useState<boolean>(false);
  const [daysError, setDaysError] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<string>("");

  // Time range (epoch seconds, server time interpretation)
  const [startSec, setStartSec] = useState<number>(0);
  const [endSec, setEndSec] = useState<number>(0);

  // Filters
  const [filterSession, setFilterSession] = useState<string>("");
  const [filterLayer, setFilterLayer] = useState<string>("");

  // Slice
  const [slice, setSlice] = useState<ReplaySliceResponse | null>(null);
  const [sliceLoading, setSliceLoading] = useState<boolean>(false);
  const [sliceError, setSliceError] = useState<string | null>(null);

  // Playback
  const [playIdx, setPlayIdx] = useState<number>(0);
  const [playing, setPlaying] = useState<boolean>(false);
  const [speed, setSpeed] = useState<Speed>(1);

  // Selection (click-to-highlight)
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  /* ---------- Refy ---------- */
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const eventListRef = useRef<HTMLDivElement>(null);
  // Ref to the visible row for the "play head" so auto-scroll and
  // click-to-highlight share the same anchor.
  const playRowRef = useRef<HTMLDivElement | null>(null);
  // Most recent slice events kept in a ref so the playback timer can
  // read them without re-binding setTimeout when React re-renders.
  const eventsRef = useRef<ReplayEvent[]>([]);
  eventsRef.current = slice?.events ?? [];
  // Same trick for speed -- pause/play loop reads via ref so changing
  // speed mid-playback takes effect on the NEXT step instead of after a
  // full timer reset.
  const speedRef = useRef<Speed>(speed);
  speedRef.current = speed;

  /* ---------- 1) Załaduj listę dni ---------- */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setDaysLoading(true);
      setDaysError(null);
      try {
        const data = await request<ReplayDaysResponse>(
          "/api/v1/terminal/replay/days",
        );
        if (cancelled) return;
        const list = Array.isArray(data?.days) ? data.days : [];
        setDays(list);
        if (list.length > 0 && !selectedDay) {
          // Newest day first per backend contract.
          setSelectedDay(list[0]);
        }
      } catch (err) {
        if (cancelled) return;
        setDaysError(err instanceof Error ? err.message : "fetch failed");
      } finally {
        if (!cancelled) setDaysLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // We intentionally only run this on mount. selectedDay seeding is a
    // one-shot side effect; the user can change it freely afterwards.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---------- 2) Default range = last 1h of selected day ---------- */
  useEffect(() => {
    if (!selectedDay) return;
    const dayStart = dayToStartSec(selectedDay);
    // "Last 1h of selected day" — for a past day, that's [23:00, 24:00).
    // For today, default to [now-1h, now] so the operator sees the most
    // recent activity, which is the common "I just saw a glitch" path.
    const todayDay = (() => {
      const now = new Date();
      return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
    })();
    if (selectedDay === todayDay) {
      const now = Math.floor(Date.now() / 1000);
      setStartSec(now - 3600);
      setEndSec(now);
    } else {
      // Whole day shown in the picker as 23:00 - 24:00 of that day.
      setStartSec(dayStart + 23 * 3600);
      setEndSec(dayStart + 24 * 3600);
    }
  }, [selectedDay]);

  /* ---------- 3) Stop timer on unmount ---------- */
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  /* ---------- 4) Wczytaj slice ---------- */
  const loadSlice = useCallback(async () => {
    if (!startSec || !endSec || endSec < startSec) {
      setSliceError("Niepoprawny zakres czasu (end_ts < start_ts).");
      return;
    }
    // Stop playback before swapping the dataset under the timer.
    setPlaying(false);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setSliceLoading(true);
    setSliceError(null);
    try {
      const params = new URLSearchParams();
      params.set("start_ts", String(startSec));
      params.set("end_ts", String(endSec));
      if (filterSession.trim()) params.set("session_id", filterSession.trim());
      if (filterLayer) params.set("layer", filterLayer);
      params.set("max_events", "10000");
      const data = await request<ReplaySliceResponse>(
        `/api/v1/terminal/replay/slice?${params.toString()}`,
      );
      setSlice(data);
      setPlayIdx(0);
      setSelectedEventId(null);
    } catch (err) {
      setSliceError(err instanceof Error ? err.message : "fetch failed");
      setSlice(null);
    } finally {
      setSliceLoading(false);
    }
  }, [startSec, endSec, filterSession, filterLayer]);

  /* ---------- 5) Playback loop ----------
   * setTimeout-driven step. Each tick:
   *   1. render current event (already on screen via playIdx)
   *   2. if there is a next event, schedule next tick at
   *      (next.ts - current.ts) * 1000 / speed ms (capped at MAX).
   *   3. if at the end, stop playing.
   * Pause clears the timer; play resumes from current playIdx.
   */
  const scheduleNextStep = useCallback(
    (fromIdx: number) => {
      const events = eventsRef.current;
      if (fromIdx >= events.length - 1) {
        // End of slice — stop.
        setPlaying(false);
        return;
      }
      const cur = events[fromIdx];
      const nxt = events[fromIdx + 1];
      const deltaSec = Math.max(0, nxt.ts - cur.ts);
      const baseMs = deltaSec * 1000;
      const scaled = baseMs / Math.max(1, speedRef.current);
      // 16ms floor so a burst of identical-ts events doesn't starve the
      // event loop. MAX_STEP_DELAY_MS guards against multi-minute gaps.
      const ms = Math.min(MAX_STEP_DELAY_MS, Math.max(16, scaled));
      timerRef.current = setTimeout(() => {
        // Bump index; the effect below will pick this up and chain.
        setPlayIdx((idx) => Math.min(events.length - 1, idx + 1));
      }, ms);
    },
    [],
  );

  // Whenever playing toggles or the play head moves while playing,
  // (re)arm the next tick. Splitting "play" + "advance" into separate
  // effects keeps the timer state in sync with React state without a
  // tangled imperative chain.
  useEffect(() => {
    if (!playing) return;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    scheduleNextStep(playIdx);
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [playing, playIdx, scheduleNextStep]);

  /* ---------- 6) Auto-scroll do play head ---------- */
  useEffect(() => {
    if (!playing) return;
    const el = playRowRef.current;
    if (el && typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [playIdx, playing]);

  /* ---------- 7) Controls handlers ---------- */
  const togglePlay = useCallback(() => {
    const events = eventsRef.current;
    if (events.length === 0) return;
    setPlaying((p) => {
      const next = !p;
      // If we toggle back on at the end, rewind to the start so a
      // second click on Play after a finish "replays from the top".
      if (next && playIdx >= events.length - 1) {
        setPlayIdx(0);
      }
      return next;
    });
  }, [playIdx]);

  const handleRestart = useCallback(() => {
    setPlaying(false);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setPlayIdx(0);
  }, []);

  const handleSpeedChange = useCallback((s: Speed) => {
    setSpeed(s);
    // The effect on [playing, playIdx] will re-arm the next timer when
    // the index advances. To make the speed change feel immediate while
    // playing, force a fresh tick by clearing the pending timer; the
    // playing effect will re-arm with the new speedRef.
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const handleScrub = useCallback((evt: ChangeEvent<HTMLInputElement>) => {
    const events = eventsRef.current;
    if (events.length === 0) return;
    const value = Number(evt.target.value);
    if (!Number.isFinite(value)) return;
    // value is a fraction in [0, 1] of the slice timeline.
    const span = events[events.length - 1].ts - events[0].ts;
    const targetSec = events[0].ts + span * value;
    const idx = findIndexAtTs(events, targetSec);
    setPlayIdx(Math.min(events.length - 1, Math.max(0, idx)));
  }, []);

  /* ---------- 8) Derived ---------- */
  const events = slice?.events ?? [];
  const totalEvents = events.length;
  const truncated = slice?.truncated ?? false;
  const currentEvent = totalEvents > 0 ? events[Math.min(playIdx, totalEvents - 1)] : null;
  const firstTs = totalEvents > 0 ? events[0].ts : 0;
  const lastTs = totalEvents > 0 ? events[totalEvents - 1].ts : 0;
  const span = Math.max(0, lastTs - firstTs);
  const scrubFrac = useMemo(() => {
    if (!currentEvent || span <= 0) return 0;
    return Math.min(1, Math.max(0, (currentEvent.ts - firstTs) / span));
  }, [currentEvent, firstTs, span]);

  const startInputValue = useMemo(
    () => (startSec > 0 ? secToLocalInput(startSec) : ""),
    [startSec],
  );
  const endInputValue = useMemo(
    () => (endSec > 0 ? secToLocalInput(endSec) : ""),
    [endSec],
  );

  /* ---------- 9) Render row ---------- */
  const renderRow = useCallback(
    (ev: ReplayEvent, idx: number) => {
      const isPlayHead = idx === playIdx;
      const isSelected = ev.event_id != null && ev.event_id === selectedEventId;
      const layerMod = `${ev.layer ?? "?"}·${ev.module ?? "?"}`;
      const modelHost = `${ev.model ?? "—"}@${ev.host ?? "local"}`;
      const ok = ev.severity !== "error";
      const marker = ok ? "✓" : "✗";
      const refForRow = isPlayHead ? playRowRef : undefined;
      return (
        <div
          key={ev.event_id ?? `${ev.ts}-${idx}`}
          ref={refForRow}
          onClick={() => {
            setSelectedEventId(ev.event_id ?? null);
            setPlayIdx(idx);
          }}
          className={cn(
            "whitespace-pre-wrap break-words cursor-pointer px-2 py-0.5 rounded transition-colors",
            severityColor(ev.severity),
            isPlayHead && "bg-sylion-blue/15 ring-1 ring-sylion-blue/40",
            !isPlayHead && isSelected && "bg-muted/30",
          )}
        >
          <span className="text-muted-foreground">{formatTsHMS(ev.ts)}</span>
          {"  "}
          <span className="text-sylion-blue/80">{pad(layerMod, 22)}</span>
          {"  "}
          <span className="text-muted-foreground">{pad(modelHost, 24)}</span>
          {"  "}
          <span>{ev.message}</span>
          {"  "}
          <span className={ok ? "text-emerald-400" : "text-red-400"}>{marker}</span>
        </div>
      );
    },
    [playIdx, selectedEventId],
  );

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
            <Film className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight flex items-center">
              Odtwarzanie nagrań (W18 G3)
              <HelpTip
                text={
                  "Operatorskie przewijanie nagrania strumienia SSE. " +
                  "Backend zapisuje każdy TerminalEvent do daily JSONL; " +
                  "ten widok wczytuje wycinek [start_ts, end_ts] z opcjonalnym " +
                  "filtrem identyfikatora sesji lub warstwy i renderuje go w formacie PDF §7.2 " +
                  "z osią czasu oraz prędkościami 1×/2×/4×/8×."
                }
                side="bottom"
              />
            </h1>
            <p className="text-sm text-muted-foreground">
              Podgląd nagrań SSE bez edycji. Przełącznik nagrywania jest po
              stronie terminala na żywo — tu nie sterujemy nagrywaniem.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/terminal">
            <Button variant="outline" size="sm">
              <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
              Terminal na żywo
            </Button>
          </Link>
        </div>
      </motion.div>

      {/* ===== Status banner ===== */}
      <Card className="border-sky-500/40 bg-sky-500/10">
        <div className="p-3 flex items-start gap-2 text-sky-200">
          <Film className="w-4 h-4 mt-0.5 shrink-0 text-sky-400" />
          <div className="text-xs leading-relaxed">
            <span className="font-semibold">Podgląd nagrań SSE bez edycji.</span>{" "}
            Wybierz dzień, ustaw zakres początku i końca, opcjonalnie zawęź filtrem
            identyfikatora sesji lub warstwy, kliknij <span className="font-mono">Wczytaj</span>{" "}
            i użyj kontrolek odtwarzania. Przełącznik nagrywania znajduje się przy
            terminalu na żywo — w tym widoku nie zmieniamy stanu nagrywania.
          </div>
        </div>
      </Card>

      {/* ===== Kontrolki: dzień + zakres + filtry ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3 grid grid-cols-1 lg:grid-cols-[180px_1fr_1fr_180px_140px_auto] gap-3 items-end">
          {/* Day picker */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase text-muted-foreground tracking-wider flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Dzień
              <HelpTip
                text={
                  "Lista pochodzi z GET /api/v1/terminal/replay/days — " +
                  "newest first. Wybór dnia auto-ustawia zakres czasowy " +
                  "na ostatnią godzinę (dzisiaj) albo 23:00–24:00 (przeszły dzień)."
                }
              />
            </label>
            <select
              value={selectedDay}
              onChange={(e) => setSelectedDay(e.target.value)}
              disabled={daysLoading || days.length === 0}
              className="w-full bg-black/40 border border-sylion-border rounded px-2 py-1.5 text-xs font-mono"
            >
              {daysLoading && <option value="">Ładowanie…</option>}
              {!daysLoading && days.length === 0 && (
                <option value="">brak nagrań</option>
              )}
              {days.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          {/* Start ts */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase text-muted-foreground tracking-wider">
              Start
            </label>
            <input
              type="datetime-local"
              value={startInputValue}
              onChange={(e) => setStartSec(localInputToSec(e.target.value))}
              className="w-full bg-black/40 border border-sylion-border rounded px-2 py-1.5 text-xs font-mono"
            />
          </div>

          {/* End ts */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase text-muted-foreground tracking-wider">
              Koniec
            </label>
            <input
              type="datetime-local"
              value={endInputValue}
              onChange={(e) => setEndSec(localInputToSec(e.target.value))}
              className="w-full bg-black/40 border border-sylion-border rounded px-2 py-1.5 text-xs font-mono"
            />
          </div>

          {/* Session filter */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase text-muted-foreground tracking-wider">
              ID sesji
            </label>
            <input
              type="text"
              value={filterSession}
              onChange={(e) => setFilterSession(e.target.value)}
              placeholder="(opcjonalnie)"
              className="w-full bg-black/40 border border-sylion-border rounded px-2 py-1.5 text-xs font-mono placeholder:text-muted-foreground/40"
            />
          </div>

          {/* Layer filter */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase text-muted-foreground tracking-wider flex items-center gap-1">
              <Layers className="w-3 h-3" />
              warstwa
            </label>
            <select
              value={filterLayer}
              onChange={(e) => setFilterLayer(e.target.value)}
              className="w-full bg-black/40 border border-sylion-border rounded px-2 py-1.5 text-xs font-mono"
            >
              {LAYER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Load button */}
          <div>
            <Button
              size="sm"
              onClick={() => void loadSlice()}
              disabled={sliceLoading || !startSec || !endSec || endSec < startSec}
            >
              {sliceLoading ? (
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5 mr-1.5" />
              )}
              Wczytaj
            </Button>
          </div>
        </div>
      </Card>

      {/* ===== Komunikaty błędów ===== */}
      {daysError && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <div className="p-3 flex items-center gap-2 text-amber-600">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs">
              Błąd ładowania listy dni: {daysError}
            </span>
          </div>
        </Card>
      )}
      {sliceError && (
        <Card className="border-red-500/30 bg-red-500/5">
          <div className="p-3 flex items-center gap-2 text-red-400">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs">Błąd slice: {sliceError}</span>
          </div>
        </Card>
      )}
      {truncated && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <div className="p-3 flex items-center gap-2 text-amber-400">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs">
              Wycinek obcięty na 10 000 zdarzeń — zawęź zakres lub dodaj filtr
              sesji albo warstwy, aby zobaczyć starsze.
            </span>
          </div>
        </Card>
      )}

      {/* ===== Kontrolki odtwarzania ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              size="sm"
              variant={playing ? "outline" : "default"}
              onClick={togglePlay}
              disabled={totalEvents === 0}
            >
              {playing ? (
                <>
                  <Pause className="w-3.5 h-3.5 mr-1.5" />
                  Pauza
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 mr-1.5" />
                  Odtwórz
                </>
              )}
            </Button>

            <Button
              size="sm"
              variant="outline"
              onClick={handleRestart}
              disabled={totalEvents === 0}
            >
              <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
              Restart
            </Button>

            <div className="flex items-center gap-1">
              <Gauge className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-[10px] uppercase text-muted-foreground tracking-wider mr-1">
                prędkość
              </span>
              {SPEED_OPTIONS.map((s) => {
                const active = speed === s;
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => handleSpeedChange(s)}
                    className={cn(
                      "text-[10px] font-mono px-2 py-0.5 rounded border transition-colors",
                      active
                        ? "border-sylion-blue/60 bg-sylion-blue/15 text-sylion-blue"
                        : "border-border/40 text-muted-foreground hover:bg-muted/30",
                    )}
                  >
                    {s}×
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-3 text-[11px] font-mono text-muted-foreground">
              <span>
                clock:{" "}
                <span className="text-foreground/85">
                  {formatTsHMS(currentEvent?.ts)}
                </span>
              </span>
              <span>
                event:{" "}
                <span className="text-foreground/85">
                  {totalEvents === 0 ? 0 : Math.min(playIdx + 1, totalEvents)}
                </span>
                /{totalEvents}
              </span>
              <span>
                truncated:{" "}
                <span className={truncated ? "text-amber-400" : "text-emerald-400"}>
                  {truncated ? "yes" : "no"}
                </span>
              </span>
              <span>
                Total events: <span className="text-foreground/85">{totalEvents}</span>
              </span>
            </div>
          </div>

          {/* Scrub bar */}
          <div className="flex items-center gap-3">
            <span className="text-[10px] font-mono text-muted-foreground w-20 shrink-0">
              {formatTsHMS(firstTs)}
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.0001}
              value={scrubFrac}
              onChange={handleScrub}
              disabled={totalEvents <= 1}
              className="flex-1 accent-sylion-blue"
              aria-label="Replay scrub bar"
            />
            <span className="text-[10px] font-mono text-muted-foreground w-20 shrink-0 text-right">
              {formatTsHMS(lastTs)}
            </span>
          </div>
        </div>
      </Card>

      {/* ===== Event log ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-3 border-b border-border/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Film className="w-4 h-4 text-sylion-blue" />
            <h3 className="text-xs font-semibold">Replay log</h3>
            <HelpTip
              text={
                "Format linii: HH:MM:SS  warstwa·moduł  model@host  message  ✓/✗. " +
                "Klik = highlight + skok play heada. ✓ = severity ≠ error, ✗ = error. " +
                "Kolory severity: info (neutral), warn (amber), error (red), debug (muted), hg (fuchsia)."
              }
            />
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-[10px]">
              {totalEvents} zdarzeń
            </Badge>
            {slice?.filter_session_id && (
              <Badge variant="outline" className="font-mono text-[10px]">
                sesja={slice.filter_session_id.slice(0, 8)}
              </Badge>
            )}
            {slice?.filter_layer && (
              <Badge variant="outline" className="font-mono text-[10px]">
                warstwa={slice.filter_layer}
              </Badge>
            )}
          </div>
        </div>
        <div
          ref={eventListRef}
          className="font-mono text-[11px] leading-relaxed bg-black/60 px-1 py-2 overflow-auto max-h-[55vh] min-h-[30vh]"
        >
          {totalEvents === 0 ? (
            <div className="text-muted-foreground/70 py-12 text-center">
              {sliceLoading
                ? "Ładowanie slice…"
                : slice
                ? "Brak zdarzeń w wybranym oknie. Zmień zakres lub usuń filtry."
                : "Wybierz zakres i kliknij Wczytaj, aby pobrać nagranie."}
            </div>
          ) : (
            events.map((ev, idx) => renderRow(ev, idx))
          )}
        </div>
      </Card>
    </div>
  );
}
