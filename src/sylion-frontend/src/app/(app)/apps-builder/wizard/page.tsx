"use client";

/**
 * SYLION AEIS v2 - W16 Apps Builder Wizard.
 *
 * "Studio Idei -> Aplikacja". Operator types a free-form Polish
 * description of the app they want, the backend ranks canonical templates,
 * and the selected template is persisted as a real draft manifest.
 *
 * Backend:
 *   - POST /api/v1/apps/match-idea
 *   - POST /api/v1/apps/from-template
 */

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/common/HelpTip";
import { request } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  AlertTriangle,
  ArrowLeft,
  Boxes,
  CheckCircle2,
  Database,
  Info,
  Layers,
  Lightbulb,
  Loader2,
  Send,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";

/* ============================================================
   Types — mirror MatchResult.to_dict() from apps_v2/__init__.py
   ============================================================ */

type CascadeMethod = "tag_overlap" | "embedding" | "llm_generated";

interface TemplateDict {
  id: string;
  name_pl: string;
  description_pl: string;
  object_type_ids: string[];
  widget_ids: string[];
  tags: string[];
}

interface MatchResultDict {
  template: TemplateDict;
  score: number;
  method: CascadeMethod;
  reason_pl: string;
}

interface MatchIdeaResponse {
  idea_text: string;
  match_count: number;
  matches: MatchResultDict[];
  phase: string;
  method_used: CascadeMethod;
}

interface AppEntry {
  id: string;
  name: string;
  status: string;
  source: string;
  template_id: string;
}

interface CreateAppResponse {
  app: AppEntry;
  manifest: Record<string, unknown>;
}

/* ============================================================
   Method badge palette — color-coded per cascade stage
   ============================================================ */

const METHOD_BADGE: Record<
  CascadeMethod,
  { label: string; className: string; tooltip: string }
> = {
  tag_overlap: {
    label: "tag-overlap",
    className: "border-sylion-blue/40 bg-sylion-blue/10 text-sylion-blue",
    tooltip: "Template matching: Jaccard po tagach (PL).",
  },
  embedding: {
    label: "embedding",
    className: "border-amber-500/40 bg-amber-500/10 text-amber-500",
    tooltip: "G1: nomic-embed-text similarity (Ollama lazy).",
  },
  llm_generated: {
    label: "llm-generated",
    className: "border-purple-500/40 bg-purple-500/10 text-purple-400",
    tooltip: "G2: LLM-generated manifest gdy brak szablonu pasuje.",
  },
};

/* ============================================================
   Page
   ============================================================ */

export default function AppsBuilderWizardPage() {
  const [ideaText, setIdeaText] = useState<string>("");
  const [topN, setTopN] = useState<number>(3);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<MatchIdeaResponse | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [creatingTemplateId, setCreatingTemplateId] = useState<string | null>(null);

  const canSubmit = useMemo(
    () => ideaText.trim().length >= 10 && !loading,
    [ideaText, loading],
  );

  const submit = useCallback(async () => {
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const data = await request<MatchIdeaResponse>(
        "/api/v1/apps/match-idea",
        {
          method: "POST",
          body: JSON.stringify({ idea_text: ideaText.trim(), top_n: topN }),
        },
      );
      setResponse(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Nie udało się pobrać dopasowan. Sprobuj ponownie.",
      );
    } finally {
      setLoading(false);
    }
  }, [canSubmit, ideaText, topN]);

  const onPick = useCallback(async (tpl: TemplateDict) => {
    setCreatingTemplateId(tpl.id);
    setError(null);
    try {
      const data = await request<CreateAppResponse>("/api/v1/apps/from-template", {
        method: "POST",
        body: JSON.stringify({
          template_id: tpl.id,
          idea_text: ideaText.trim(),
          operator_id: "operator-main",
        }),
      });
      setToast(`Utworzono draft manifest ${data.app.id} dla "${data.app.name}".`);
      window.setTimeout(() => setToast(null), 4500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się utworzyć manifestu aplikacji.");
    } finally {
      setCreatingTemplateId(null);
    }
  }, [ideaText]);

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
            <Wand2 className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight flex items-center">
              Studio Idei {"→"} Aplikacja (W16 G2)
              <HelpTip
                text={
                  "W16 G2: cascade pipeline operator-typed idea -> matching templates. " +
                  "Template matching = Jaccard tag-overlap (PL). G1 = nomic-embed-text similarity. " +
                  "G2 = LLM-generated manifest."
                }
                side="bottom"
              />
            </h1>
            <p className="text-sm text-muted-foreground">
              Opisz pomysl po polsku, system zwróci najlepiej dopasowane szablony i zapisze wybrany draft manifest.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/apps-builder">
            <Button variant="outline" size="sm">
              <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
              Katalog
            </Button>
          </Link>
        </div>
      </motion.div>

      {/* ===== Cascade banner ===== */}
      <Card className="border-sylion-blue/30 bg-sylion-blue/5">
        <div className="p-3 flex items-start gap-2 text-xs">
          <Info className="w-4 h-4 text-sylion-blue mt-0.5 shrink-0" />
          <div className="space-y-1">
            <div>
              <span className="font-semibold text-sylion-blue">Aktywny przeplyw:</span>{" "}
              cascade kandydat {" → "} <span className="font-mono">template</span>
              {" → "} <span className="font-mono">embeddings</span>
              {" → "} <span className="font-mono">LLM</span>. Wybór szablonu
              zapisuje realny draft manifest w backendzie.
            </div>
            <div className="text-muted-foreground">
              G1 doda retrieval przez{" "}
              <span className="font-mono">nomic-embed-text</span> (Ollama lazy);
              G2 odpali LLM-generated manifest dla pomys??w których żaden szablon
              nie pokrywa. Manifest po G1 trafia na{" "}
              <span className="font-mono">CouncilHybrid</span> (W3) zanim wejdzie
              w produkcje.
            </div>
          </div>
        </div>
      </Card>

      {/* ===== Idea form ===== */}
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-4 space-y-4">
          <div className="flex items-center gap-2">
            <Lightbulb className="w-4 h-4 text-sylion-blue" />
            <h2 className="text-sm font-semibold">Twoj pomysl</h2>
          </div>

          <textarea
            value={ideaText}
            onChange={(e) => setIdeaText(e.target.value)}
            placeholder="Opisz pomysl po polsku... np. Chce aplikacje do inspekcji terenowych z raportami audytu i monitorowaniem zasobow."
            rows={5}
            maxLength={2000}
            className={cn(
              "w-full rounded-md border border-sylion-border bg-[#0a0f1d] px-3 py-2",
              "text-sm leading-relaxed text-foreground placeholder:text-muted-foreground",
              "focus:outline-none focus:ring-2 focus:ring-sylion-blue/40",
              "resize-y",
            )}
            aria-label="Opis pomyslu"
          />

          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>
              <span
                className={cn(
                  "font-mono",
                  ideaText.trim().length < 10 && "text-amber-500",
                )}
              >
                {ideaText.trim().length}
              </span>{" "}
              / 2000 znakow {ideaText.trim().length < 10 && "(min. 10 do submit)"}
            </span>
            <span className="font-mono">
              POST /api/v1/apps/match-idea
            </span>
          </div>

          {/* Slider top_n */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label
                htmlFor="top-n-slider"
                className="text-xs text-muted-foreground"
              >
                Liczba sugestii
              </label>
              <Badge variant="outline" className="font-mono text-[10px]">
                {topN}
              </Badge>
            </div>
            <input
              id="top-n-slider"
              type="range"
              min={1}
              max={10}
              step={1}
              value={topN}
              onChange={(e) => setTopN(parseInt(e.target.value, 10))}
              className="w-full accent-sylion-blue"
              aria-label="Liczba sugestii"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
              <span>1</span>
              <span>10</span>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setIdeaText("");
                setResponse(null);
                setError(null);
              }}
              disabled={loading || (!ideaText && !response && !error)}
            >
              Wyczysc
            </Button>
            <Button
              size="sm"
              onClick={() => void submit()}
              disabled={!canSubmit}
              title={
                ideaText.trim().length < 10
                  ? "Wprowadz min. 10 znakow opisu"
                  : "Znajdz dopasowania"
              }
            >
              {loading ? (
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : (
                <Send className="w-3.5 h-3.5 mr-1.5" />
              )}
              Znajdz dopasowania
            </Button>
          </div>
        </div>
      </Card>

      {/* ===== Error ===== */}
      {error && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <div className="p-3 flex items-center justify-between gap-2 text-amber-600">
            <div className="flex items-center gap-2 text-xs">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void submit()}
              disabled={!canSubmit}
            >
              Pon?w
            </Button>
          </div>
        </Card>
      )}

      {/* ===== Results ===== */}
      {response && (
        <ResultsPanel response={response} onPick={onPick} creatingTemplateId={creatingTemplateId} />
      )}

      {/* ===== Toast ===== */}
      {toast && (
        <div
          className="fixed bottom-6 right-6 z-50 max-w-sm"
          role="status"
          aria-live="polite"
        >
          <Card className="border-sylion-blue/40 bg-sylion-blue/10 shadow-xl">
            <div className="p-3 flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-sylion-blue mt-0.5 shrink-0" />
              <div className="flex-1 text-xs leading-relaxed">{toast}</div>
              <button
                onClick={() => setToast(null)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Zamknij toast"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

/* ============================================================
   Results panel
   ============================================================ */

function ResultsPanel({
  response,
  onPick,
  creatingTemplateId,
}: {
  response: MatchIdeaResponse;
  onPick: (tpl: TemplateDict) => void;
  creatingTemplateId: string | null;
}) {
  if (response.match_count === 0) {
    return (
      <Card className="bg-[#0f1629] border-sylion-border">
        <div className="p-8 flex flex-col items-center justify-center text-muted-foreground">
          <Boxes className="w-7 h-7 mb-2 opacity-40" />
          <p className="text-xs">
            Brak dopasowan {"—"} sprobuj inaczej opisac pomysl.
          </p>
          <p className="text-[10px] mt-1 opacity-60">
            Dopasowanie dziala na lematach PL (np.{" "}
            <span className="font-mono">inspekcja terenowa raport</span>).
          </p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-sylion-blue" />
          <h2 className="text-sm font-semibold">
            Dopasowane szablony
          </h2>
          <Badge variant="outline" className="font-mono text-[10px]">
            {response.match_count} z {response.matches.length}
          </Badge>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "font-mono text-[10px]",
            METHOD_BADGE[response.method_used].className,
          )}
          title={METHOD_BADGE[response.method_used].tooltip}
        >
          method: {METHOD_BADGE[response.method_used].label}
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {response.matches.map((m, i) => (
          <MatchCard
            key={`${m.template.id}-${i}`}
            match={m}
            onPick={() => onPick(m.template)}
            isCreating={creatingTemplateId === m.template.id}
          />
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   MatchCard
   ============================================================ */

function MatchCard({
  match,
  onPick,
  isCreating,
}: {
  match: MatchResultDict;
  onPick: () => void;
  isCreating: boolean;
}) {
  const tpl = match.template;
  const scorePct = Math.max(0, Math.min(100, match.score * 100));
  const badge = METHOD_BADGE[match.method];

  return (
    <Card className="bg-[#0f1629] border-sylion-border flex flex-col">
      <div className="p-4 space-y-3 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Wand2 className="w-4 h-4 text-sylion-blue shrink-0" />
            <h3 className="text-sm font-semibold truncate">{tpl.name_pl}</h3>
          </div>
          <Badge
            variant="outline"
            className={cn("font-mono text-[10px] shrink-0", badge.className)}
            title={badge.tooltip}
          >
            {badge.label}
          </Badge>
        </div>

        {/* Score progress */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px] uppercase text-muted-foreground tracking-wider">
            <span>Score</span>
            <span className="font-mono">{match.score.toFixed(2)}</span>
          </div>
          <div
            className="h-1.5 w-full rounded-full bg-sylion-border/40 overflow-hidden"
            role="progressbar"
            aria-valuenow={scorePct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Score ${match.score.toFixed(2)}`}
          >
            <div
              className="h-full bg-sylion-blue transition-[width] duration-500"
              style={{ width: `${scorePct}%` }}
            />
          </div>
        </div>

        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">
          {tpl.description_pl}
        </p>

        <div className="text-[11px] italic text-muted-foreground border-l-2 border-sylion-blue/30 pl-2">
          {match.reason_pl}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-[10px] uppercase text-muted-foreground tracking-wider">
            <Database className="w-3 h-3" />
            <span>Typy obiektow (W15)</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {tpl.object_type_ids.length === 0 ? (
              <span className="text-[10px] text-muted-foreground">brak</span>
            ) : (
              tpl.object_type_ids.map((t) => (
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
            {tpl.widget_ids.length === 0 ? (
              <span className="text-[10px] text-muted-foreground">brak</span>
            ) : (
              tpl.widget_ids.map((w) => (
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
          id: {tpl.id}
        </div>
      </div>

      <div className="p-3 border-t border-border/30 flex items-center justify-between gap-2">
        <span className="text-[10px] text-muted-foreground">
          Utworzy draft manifest w backendzie
        </span>
        <Button variant="default" size="sm" onClick={onPick} disabled={isCreating}>
          {isCreating ? (
            <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
          ) : (
            <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
          )}
          {isCreating ? "Tworzenie" : "Wybierz"}
        </Button>
      </div>
    </Card>
  );
}
