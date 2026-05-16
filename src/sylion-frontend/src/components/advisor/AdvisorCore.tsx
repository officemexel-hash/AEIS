"use client";

import type { AdvisorCardEnvelope } from "@/lib/api/advisor";

interface Props {
  criticalCard: AdvisorCardEnvelope | null;
}

export function AdvisorCore({ criticalCard }: Props) {
  const title = criticalCard?.header.title ?? "System monitoruje projekty.";
  const body = criticalCard
    ? criticalCard.header.rationale
    : "Brak pilnych decyzji. Advisor analizuje dane w tle.";

  const dLevel = criticalCard?.header.d_level ?? null;
  const dNum = dLevel ? parseInt(dLevel.replace("D", ""), 10) : 0;
  const humanGate = criticalCard?.header.human_gate_required ?? false;
  const evidencePackId = criticalCard?.header.evidence_pack_id ?? null;

  return (
    <div className="panel advisor-core">
      <div className="panel-content">
        <span className="eyebrow">Live Advisor Bubble</span>
        <div className="core-stage">
          <div className="core-orb" />
          <div className="core-label l1">koszty · ROI</div>
          <div className="core-label l2">modele · routing</div>
          <div className="core-label l3">testy · fixer</div>
          <div className="core-label l4">Council · audit</div>
        </div>
        <div className="advisor-speech">
          <h3>{title}</h3>
          <p>{body}</p>
          <div className="priority-strip">
            {dLevel && (
              <span className={`chip ${dNum >= 4 ? "red" : dNum >= 3 ? "amber" : "cyan"}`}>
                {dLevel} priorytet
              </span>
            )}
            {humanGate && <span className="chip amber">HG wymagany</span>}
            {evidencePackId && <span className="chip cyan">Evidence Pack gotowy</span>}
            {!criticalCard && <span className="chip green">Brak blokad</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
