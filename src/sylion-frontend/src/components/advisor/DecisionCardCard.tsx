"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { cn, fmtDateTime } from "@/lib/utils";
import { Sparkles, Database, BookOpen, Vote, Brain, History } from "lucide-react";
import type { AdvisorCardEnvelope, CardSource, DecisionCardBody, FundingCardBody } from "@/lib/api/advisor";
import { RiskBadge } from "./RiskBadge";
import { DLevelBadge } from "./DLevelBadge";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { CardActions } from "./CardActions";

const SOURCE_ICONS: Record<CardSource, React.ComponentType<{ className?: string }>> = {
  rule_engine: Database,
  llm_judge: Brain,
  history_match: History,
  council_vote: Vote,
  hybrid: Sparkles,
};

interface Props {
  envelope: AdvisorCardEnvelope;
  variant?: "full" | "compact";
  showActions?: boolean;
  onOpenEvidence?: (packId: string) => void;
  onActionComplete?: () => void;
  className?: string;
}

export function DecisionCardCard({
  envelope,
  variant = "full",
  showActions,
  onOpenEvidence,
  onActionComplete,
  className,
}: Props) {
  const { header, body } = envelope;
  const isDecision = header.card_type === "decision";
  const decisionBody = (isDecision ? body : null) as DecisionCardBody | null;
  const fundingBody = (header.card_type === "funding" ? body : null) as FundingCardBody | null;
  const compact = variant === "compact";
  const resolution = resolutionLabel(header.tags);

  return (
    <motion.div
      data-testid="advisor-card"
      data-card-id={header.card_id}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card data-testid="advisor-card-surface" data-card-id={header.card_id} className={cn("relative overflow-hidden", className)}>
        <div className={cn("absolute inset-x-0 top-0 h-0.5", riskAccent(header.risk_level))} />
        <div className="flex flex-col gap-3 p-4">
          <header className="flex flex-wrap items-start justify-between gap-2">
            <div className="flex flex-col gap-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <RiskBadge level={header.risk_level} />
                <DLevelBadge level={header.d_level} />
                {header.evidence_pack_id ? (
                  <Badge
                    variant="outline"
                    className="cursor-pointer border-sylion-blue/30 text-sylion-blue text-[10px] hover:bg-sylion-blue/10"
                    onClick={() => header.evidence_pack_id && onOpenEvidence?.(header.evidence_pack_id)}
                  >
                    <BookOpen className="mr-1 h-3 w-3" />
                    Dowody
                  </Badge>
                ) : null}
                {header.history_based ? (
                  <Badge variant="outline" className="border-muted-foreground/20 text-[10px] text-muted-foreground">
                    zgodne z historią
                  </Badge>
                ) : null}
                {header.used_local_fallback ? (
                  <Badge variant="outline" className="border-orange-400/30 text-[10px] text-orange-400">
                    lokalny fallback
                  </Badge>
                ) : null}
                {resolution ? (
                  <Badge variant="outline" className="border-sylion-green/30 text-[10px] text-sylion-green">
                    {resolution}
                  </Badge>
                ) : null}
              </div>
              <h3 className="text-base font-semibold leading-tight">{header.title}</h3>
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                <span>{fmtDateTime(new Date(header.created_at * 1000).toISOString())}</span>
                <span className="text-muted-foreground/40">·</span>
                <span>{header.project_domain || "system"}</span>
                {header.project_type ? (
                  <>
                    <span className="text-muted-foreground/40">·</span>
                    <span>{header.project_type}</span>
                  </>
                ) : null}
                <span className="text-muted-foreground/40">·</span>
                <SourceList sources={header.sources} />
              </div>
            </div>
            <ConfidenceMeter
              score={header.confidence_score}
              label={header.confidence_label}
              compact={variant === "compact"}
              className="min-w-[160px]"
            />
          </header>

          <p className="text-sm leading-relaxed text-foreground/90">
            {compact ? compactText(header.rationale, 420) : header.rationale}
          </p>

          {decisionBody ? (
            <DecisionBodyView body={decisionBody} compact={compact} />
          ) : fundingBody ? (
            <FundingBodyView body={fundingBody} compact={compact} />
          ) : null}

          {(variant === "full" || showActions) && !resolution ? (
            <>
              <Separator />
              <CardActions
                card={envelope}
                onActionComplete={() => onActionComplete?.()}
                layout={variant === "compact" ? "grid" : "horizontal"}
              />
            </>
          ) : null}
        </div>
      </Card>
    </motion.div>
  );
}

function SourceList({ sources }: { sources: CardSource[] }) {
  return (
    <span className="inline-flex items-center gap-1">
      {sources.map((s) => {
        const Icon = SOURCE_ICONS[s] ?? Sparkles;
        return (
          <span key={s} className="inline-flex items-center gap-1">
            <Icon className="h-3 w-3" />
            <span className="text-[11px]">{sourceLabel(s)}</span>
          </span>
        );
      })}
    </span>
  );
}

function DecisionBodyView({ body, compact = false }: { body: DecisionCardBody; compact?: boolean }) {
  const alternatives = Array.isArray(body.alternatives) ? body.alternatives : [];

  if (compact) {
    return (
      <div className="grid gap-2 rounded-md border border-border/50 bg-muted/10 p-3 text-sm">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Rekomendacja</p>
          <p className="mt-1 text-foreground">{compactText(body.recommendation, 260)}</p>
        </div>
        <div className="grid gap-3 text-xs">
          <Metric label="Korzyść" value={body.expected_benefit} maxLength={150} />
          <Metric label="Ryzyko / minus" value={body.expected_downside} maxLength={150} />
          <Metric label="Jakość" value={body.quality_impact} maxLength={150} />
        </div>
        {alternatives.length ? (
          <p className="border-t border-border/40 pt-2 text-[11px] text-muted-foreground">
            Alternatywy: {alternatives.length}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="grid gap-2 rounded-md border border-border/50 bg-muted/10 p-3 text-sm">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Rekomendacja</p>
        <p className="mt-1 text-foreground">
          {compact ? compactText(body.recommendation, 260) : body.recommendation}
        </p>
      </div>
      <div className={cn("grid gap-3 text-xs", compact ? "grid-cols-1" : "grid-cols-2 sm:grid-cols-3")}>
        <Metric label="Korzyść" value={body.expected_benefit} />
        <Metric label="Ryzyko / minus" value={body.expected_downside} />
        <Metric label="Jakość" value={body.quality_impact} />
      </div>
      <div className="grid grid-cols-3 gap-2 text-[11px] text-muted-foreground">
        <ImpactCell label="Koszt" impact={body.cost_impact} />
        <ImpactCell label="Tokeny" impact={body.token_impact} />
        <ImpactCell label="Czas" impact={body.time_impact} />
      </div>
      {body.alternatives.length ? (
        <div className="border-t border-border/40 pt-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Alternatywy</p>
          <ul className="mt-1 space-y-1.5 text-xs">
            {body.alternatives.slice(0, 3).map((alt, i) => (
              <li key={i} className="rounded border border-border/40 bg-background/40 px-2 py-1">
                <p className="font-medium">{alt.title}</p>
                <p className="text-muted-foreground">{alt.short_description}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function FundingBodyView({ body, compact = false }: { body: FundingCardBody; compact?: boolean }) {
  const gaps = Array.isArray(body.gaps_to_qualify) ? body.gaps_to_qualify : [];

  return (
    <div className="grid gap-2 rounded-md border border-border/50 bg-muted/10 p-3 text-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Dopasowanie grantu</p>
          <p className="mt-1 font-medium">
            {compact
              ? compactText(body.headline_recommendation || body.grant_program_name, 220)
              : body.headline_recommendation || body.grant_program_name}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-muted-foreground">Kwalifikowalność</p>
          <p className="font-mono text-base font-semibold">{body.eligibility_score.toFixed(1)}</p>
        </div>
      </div>
      {gaps.length ? (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Braki</p>
          <ul className="mt-1 list-disc pl-4 text-xs">
            {gaps.slice(0, compact ? 2 : 4).map((g, i) => (
              <li key={i}>{compact ? compactText(g, 140) : g}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value, maxLength }: { label: string; value: string; maxLength?: number }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-foreground/90">{maxLength ? compactText(value, maxLength) : value}</p>
    </div>
  );
}

function ImpactCell({ label, impact }: { label: string; impact: { absolute_value: string; unit: string; delta_vs_baseline_pct: number; is_assumption: boolean } }) {
  const pct = impact.delta_vs_baseline_pct;
  const tone = pct < 0 ? "text-sylion-green" : pct > 0 ? "text-orange-400" : "text-muted-foreground";
  return (
    <div className="rounded border border-border/40 bg-background/40 px-2 py-1">
      <p className="text-[10px] uppercase">{label}</p>
      <p className={cn("font-mono tabular-nums", tone)}>
        {pct > 0 ? "+" : ""}
        {pct.toFixed(0)}%
      </p>
      <p className="text-[10px] text-muted-foreground">
        {impact.absolute_value} {impact.unit}
        {impact.is_assumption ? " · ZAŁOŻENIE" : ""}
      </p>
    </div>
  );
}

function compactText(value: string, maxLength: number): string {
  const normalized = String(value || "").replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, maxLength).trimEnd()}...`;
}

function resolutionLabel(tags: string[] | undefined): string {
  const set = new Set(tags ?? []);
  if (set.has("accepted")) return "zaakceptowane";
  if (set.has("rejected")) return "odrzucone";
  if (set.has("not_useful")) return "nietrafne";
  if (set.has("human_gate")) return "Human Gate";
  if (set.has("masterplan")) return "Masterplan";
  return "";
}

function sourceLabel(source: CardSource): string {
  if (source === "rule_engine") return "silnik reguł";
  if (source === "llm_judge") return "sędzia LLM";
  if (source === "history_match") return "historia";
  if (source === "council_vote") return "głos Rady";
  return "hybryda";
}

function riskAccent(level: string): string {
  if (level === "critical") return "bg-sylion-red";
  if (level === "high") return "bg-orange-400";
  if (level === "medium") return "bg-sylion-amber";
  return "bg-sylion-blue";
}
