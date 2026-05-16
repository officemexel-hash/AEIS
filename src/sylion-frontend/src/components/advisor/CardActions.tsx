"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Check,
  X,
  Pencil,
  Clock,
  ThumbsDown,
  ShieldCheck,
  Map,
  BookmarkPlus,
  EyeOff,
} from "lucide-react";
import type { CardAction, AdvisorCardEnvelope } from "@/lib/api/advisor";
import { useCardActions } from "@/lib/hooks/advisor";

interface Props {
  card: AdvisorCardEnvelope;
  onActionComplete?: (action: CardAction) => void;
  className?: string;
  layout?: "horizontal" | "grid";
}

export function CardActions({ card, onActionComplete, className, layout = "horizontal" }: Props) {
  const { submit, submitting, error } = useCardActions();
  const [biometricVerified, setBiometricVerified] = useState(false);
  const [done, setDone] = useState<CardAction | null>(null);
  const [modifyOpen, setModifyOpen] = useState(false);
  const [modifyDraft, setModifyDraft] = useState(() =>
    String(bodyValue(card, "recommendation") ?? card.header.rationale ?? ""),
  );

  const requiresBio = card.header.requires_biometric;
  const dLevelHigh = card.header.d_level === "D3" || card.header.d_level === "D4" || card.header.d_level === "D5";

  async function run(
    action: CardAction,
    payload?: {
      operator_note?: string;
      modified_recommendation?: string;
      preference_key?: string;
      preference_project_type?: string;
      preference_project_domain?: string;
      preference_value?: unknown;
      dont_learn_flag?: boolean;
    },
  ) {
    if (action === "modify" && !payload?.modified_recommendation) {
      setModifyOpen(true);
      return;
    }
    if ((requiresBio || dLevelHigh) && !biometricVerified) {
      setBiometricVerified(true);
      return;
    }
    const res = await submit(card.header.card_id, action, payload, biometricVerified || !requiresBio);
    if (res) {
      setDone(action);
      onActionComplete?.(action);
    }
  }

  const buttons: Array<{
    action: CardAction;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    variant?: "default" | "destructive" | "outline" | "ghost" | "secondary";
    primary?: boolean;
  }> = [
    { action: "accept", label: "Akceptuj", icon: Check, variant: "default", primary: true },
    { action: "reject", label: "Odrzuć", icon: X, variant: "outline" },
    { action: "modify", label: "Zmień", icon: Pencil, variant: "outline" },
    { action: "remind_later", label: "Przypomnij", icon: Clock, variant: "ghost" },
    { action: "not_useful", label: "Nietrafne", icon: ThumbsDown, variant: "ghost" },
    { action: "convert_to_human_gate", label: "Human Gate", icon: ShieldCheck, variant: "outline" },
    { action: "convert_to_masterplan_change", label: "Masterplan", icon: Map, variant: "ghost" },
    { action: "save_as_preference", label: "Zapisz pref.", icon: BookmarkPlus, variant: "ghost" },
    { action: "dont_learn_from_this", label: "Nie ucz", icon: EyeOff, variant: "ghost" },
  ];

  if (done) {
    return (
      <div
        data-testid="advisor-action-result"
        data-card-id={card.header.card_id}
        data-action={done}
        className={cn("rounded-md border border-sylion-green/30 bg-sylion-green/5 px-3 py-2 text-xs text-sylion-green", className)}
      >
        Akcja zapisana: <span className="font-medium">{actionLabel(done)}</span>
      </div>
    );
  }

  return (
    <div data-testid="advisor-card-actions" data-card-id={card.header.card_id} className={cn("flex flex-col gap-2", className)}>
      {(requiresBio || dLevelHigh) && !biometricVerified ? (
        <div
          data-testid="advisor-action-step-up"
          data-card-id={card.header.card_id}
          className="rounded-md border border-orange-400/30 bg-orange-400/5 px-3 py-2 text-[11px] text-orange-400"
        >
          Wymagane potwierdzenie step-up dla akcji {card.header.d_level}. Kliknij wybraną akcję ponownie, aby potwierdzić.
        </div>
      ) : null}
      {error ? (
        <div
          data-testid="advisor-action-error"
          data-card-id={card.header.card_id}
          className="rounded-md border border-sylion-red/30 bg-sylion-red/5 px-3 py-2 text-[11px] text-sylion-red"
        >
          Nie zapisano akcji: {error}
        </div>
      ) : null}
      <div className={cn(layout === "grid" ? "grid grid-cols-3 gap-2" : "flex flex-wrap gap-2", "text-xs")}>
        {buttons.map(({ action, label, icon: Icon, variant, primary }) => (
          <Button
            key={action}
            type="button"
            variant={variant}
            size="sm"
            disabled={submitting}
            onClick={() => run(action, action === "save_as_preference" ? buildPreferencePayload(card) : undefined)}
            aria-label={`${label} - karta ${card.header.card_id}`}
            data-testid={`advisor-action-${action}`}
            data-card-id={card.header.card_id}
            data-action={action}
            className={cn("gap-1.5", primary && "shadow-sm")}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </Button>
        ))}
      </div>
      {modifyOpen ? (
        <div data-testid="advisor-modify-form" data-card-id={card.header.card_id} className="space-y-2 rounded-md border border-border/60 bg-background/60 p-2">
          <label className="text-[11px] font-medium text-muted-foreground" htmlFor={`modify-${card.header.card_id}`}>
            Zmieniona rekomendacja operatora
          </label>
          <textarea
            id={`modify-${card.header.card_id}`}
            value={modifyDraft}
            onChange={(event) => setModifyDraft(event.target.value)}
            rows={4}
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs outline-none focus:border-sylion-blue"
          />
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              disabled={submitting || modifyDraft.trim().length < 8}
              onClick={() => run("modify", { modified_recommendation: modifyDraft.trim(), operator_note: "modified from lifecycle card" })}
              data-testid="advisor-modify-save"
              data-card-id={card.header.card_id}
            >
              Zapisz zmianę
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setModifyOpen(false)}
              data-testid="advisor-modify-cancel"
              data-card-id={card.header.card_id}
            >
              Anuluj
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function actionLabel(action: CardAction): string {
  if (action === "accept") return "Akceptuj";
  if (action === "reject") return "Odrzuć";
  if (action === "modify") return "Zmień";
  if (action === "remind_later") return "Przypomnij";
  if (action === "not_useful") return "Nietrafne";
  if (action === "convert_to_human_gate") return "Human Gate";
  if (action === "convert_to_masterplan_change") return "Masterplan";
  if (action === "save_as_preference") return "Zapisz preferencję";
  if (action === "dont_learn_from_this") return "Nie ucz";
  return String(action).replace(/_/g, " ");
}

function bodyValue(card: AdvisorCardEnvelope, key: string): unknown {
  const body = card.body as Record<string, unknown> | undefined;
  return body?.[key];
}

function buildPreferencePayload(card: AdvisorCardEnvelope) {
  const recommendationType = String(bodyValue(card, "recommendation_type") ?? card.header.card_type ?? "advisor_card");
  return {
    preference_key: `advisor.saved_card.${recommendationType}`,
    preference_project_type: card.header.project_type || undefined,
    preference_project_domain: card.header.project_domain || undefined,
    preference_value: {
      card_id: card.header.card_id,
      title: card.header.title,
      d_level: card.header.d_level,
      risk_level: card.header.risk_level,
      recommendation_type: recommendationType,
      saved_at: new Date().toISOString(),
    },
    operator_note: "saved from advisor card action",
  };
}
