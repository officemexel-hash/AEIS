"use client";

/**
 * SubscriptionAdvisorBanner — surfaces active subscription advisor cards.
 *
 * The engine emits AdvisorCardEnvelope items whose `recommendation_type` is one
 * of REC_TYPE_PURCHASE_PLAN / REC_TYPE_DOWNGRADE_PLAN / REC_TYPE_CANCEL_PLAN.
 * Per master-spec §4.1 D-ladder, purchase recommendations are D3+ and require
 * Evidence Pack — we link straight to /advisor/[cardId] so the operator can
 * inspect the pack before approving.
 *
 * Returns `null` when there are no subscription cards so the parent can render
 * the panel conditionally without extra logic.
 */

import { motion } from "framer-motion";
import { CreditCard, ArrowRight, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RiskBadge } from "@/components/advisor/RiskBadge";
import { DLevelBadge } from "@/components/advisor/DLevelBadge";
import type { AdvisorCardEnvelope } from "@/lib/api/advisor";
import { cn } from "@/lib/utils";

interface Props {
  recommendations: AdvisorCardEnvelope[];
}

const ACTION_LABEL: Record<string, string> = {
  REC_TYPE_PURCHASE_PLAN: "Purchase",
  REC_TYPE_UPGRADE_PLAN: "Upgrade",
  REC_TYPE_DOWNGRADE_PLAN: "Downgrade",
  REC_TYPE_CANCEL_PLAN: "Cancel",
  REC_TYPE_RENEW_PLAN: "Renew",
};

export function SubscriptionAdvisorBanner({ recommendations }: Props) {
  if (!recommendations || recommendations.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <Card
        className="border-sylion-blue/30 bg-gradient-to-br from-sylion-blue/10 via-[#0f1629] to-[#0f1629] ring-1 ring-sylion-blue/20"
        data-testid="subscription-banner"
      >
        <header className="flex items-center justify-between px-4 pt-1 pb-2">
          <div className="flex items-center gap-2">
            <CreditCard className="h-4 w-4 text-sylion-blue" />
            <div>
              <h2 className="text-sm font-semibold tracking-tight">Subscription advisor</h2>
              <p className="text-[10px] text-muted-foreground">
                ROI-driven plan recommendations · always Human Gate before purchase
              </p>
            </div>
          </div>
          <Badge variant="outline" className="border-sylion-blue/30 bg-sylion-blue/10 text-sylion-blue text-[10px]">
            <Sparkles className="mr-1 h-3 w-3" />
            {recommendations.length} active
          </Badge>
        </header>

        <ul className="space-y-2 px-4 pb-3">
          {recommendations.map((card) => {
            const body = card.body as { recommendation_type?: string; expected_benefit?: string; recommendation?: string } | undefined;
            const action = body?.recommendation_type ? ACTION_LABEL[body.recommendation_type] ?? "Review" : "Review";
            return (
              <li key={card.header.card_id}>
                <a
                  href={`/advisor/${encodeURIComponent(card.header.card_id)}`}
                  className={cn(
                    "group flex items-center justify-between gap-3 rounded-lg border border-[rgba(148,163,184,0.1)] bg-[rgba(20,27,45,0.6)] px-3 py-2 transition-colors hover:border-sylion-blue/40 hover:bg-sylion-blue/5",
                  )}
                  data-testid={`subscription-card-${card.header.card_id}`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-1.5">
                      <Badge variant="outline" className="border-sylion-blue/30 text-sylion-blue text-[10px]">
                        {action}
                      </Badge>
                      <RiskBadge level={card.header.risk_level} />
                      <DLevelBadge level={card.header.d_level} />
                      {card.header.evidence_pack_id ? (
                        <Badge variant="outline" className="border-orange-400/30 text-orange-400 text-[10px]">
                          Evidence required
                        </Badge>
                      ) : null}
                    </div>
                    <p className="truncate text-sm font-medium text-foreground">{card.header.title}</p>
                    {body?.expected_benefit ? (
                      <p className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground">
                        {body.expected_benefit}
                      </p>
                    ) : null}
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-sylion-blue" />
                </a>
              </li>
            );
          })}
        </ul>
      </Card>
    </motion.div>
  );
}
