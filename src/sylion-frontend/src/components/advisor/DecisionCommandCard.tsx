"use client";

import type { AdvisorCardEnvelope, DecisionCardBody } from "@/lib/api/advisor";

interface Props {
  card: AdvisorCardEnvelope;
  variant: "featured" | "compact";
}

function dLevelTone(level: string): string {
  if (level === "D5") return "d5";
  if (level === "D4") return "d4";
  if (level === "D3") return "d3";
  return "";
}

export function DecisionCommandCard({ card, variant }: Props) {
  const { header } = card;
  const body = card.body as DecisionCardBody;
  const tone = dLevelTone(header.d_level);
  const alts = body.alternatives ?? [];
  const dNum = parseInt(header.d_level.replace("D", ""), 10);

  if (variant === "featured") {
    return (
      <article className="decision-card featured">
        <div className="card-meta">
          <span className={`badge2 ${tone}`}>{header.d_level}</span>
          <span className="badge2">{header.card_type}</span>
          <span className="badge2">{header.risk_level}</span>
          {header.evidence_pack_id && <span className="badge2 cyan">Evidence Pack</span>}
          {header.human_gate_required && <span className="badge2 d3">HG</span>}
        </div>
        <h3>{header.title}</h3>
        <p>{header.rationale}</p>
        <div className="alt-panel">
          {alts.length >= 3
            ? alts.slice(0, 3).map((alt, i) => (
                <div className="alt-tile" key={i}>
                  <b>{alt.title}</b>
                  <span>{alt.trade_off_summary}</span>
                </div>
              ))
            : (
              <>
                <div className="alt-tile">
                  <b>Koszczędny</b>
                  <span>
                    {body.cost_impact?.absolute_value
                      ? `Koszt: ${body.cost_impact.absolute_value}`
                      : "Niższe koszty, wolniejsze wykonanie."}
                  </span>
                </div>
                <div className="alt-tile">
                  <b>Zrównoważony</b>
                  <span>Rekomendowany przez Advisor — najlepszy trade-off.</span>
                </div>
                <div className="alt-tile">
                  <b>Agresywny</b>
                  <span>Wyższe koszty, szybszy czas i pełna walidacja.</span>
                </div>
              </>
            )}
        </div>
        <div className="card-actions">
          <button className="small-btn primary">Akceptuj</button>
          {header.evidence_pack_id && (
            <button className="small-btn">Evidence Pack</button>
          )}
          <button className="small-btn">Modyfikuj</button>
          {dNum >= 4 && (
            <button className="small-btn danger">Override {header.d_level}</button>
          )}
        </div>
      </article>
    );
  }

  return (
    <article className="decision-card">
      <div className="card-meta">
        <span className={`badge2 ${tone}`}>{header.d_level}</span>
        <span className="badge2">{header.card_type}</span>
        {(header.confidence_label === "high" ||
          header.confidence_label === "very_high" ||
          header.confidence_label === "certain") && (
          <span className="badge2 ok">
            conf {header.confidence_score.toFixed(2)}
          </span>
        )}
      </div>
      <h3>{header.title}</h3>
      <p>{header.rationale}</p>
      <div className="card-actions">
        <button className="small-btn primary">Akceptuj</button>
        <button className="small-btn">Odrzuć</button>
      </div>
    </article>
  );
}
