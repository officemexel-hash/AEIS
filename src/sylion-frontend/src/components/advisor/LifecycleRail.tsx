"use client";

import { useProjectLifecycle } from "@/lib/hooks/advisor";

const PHASE_LABELS: Record<string, string> = {
  idea_intake: "1 Intake",
  clarification: "2 Klaryfikacja",
  council_vote: "3 Rada",
  memory_match: "4 Pamiec",
  skills_binding: "5 Skills",
  operator_approval: "6 Zatwierdzenie",
  sot_setup: "7 SoT",
  masterplan: "8 Masterplan",
  plan_hg: "9 Plan HG",
  runtime_selection: "10 Runtime",
  execution: "11 Wykonanie",
  risk_hg: "12 Ryzyko HG",
  testing: "13 Testy",
  final_review: "14 Final",
  memory_update: "15 Pamiec+",
};

type PhaseState = "done" | "now" | "blocked" | "";

function phaseState(status: string): PhaseState {
  if (status === "approved") return "done";
  if (status === "in_progress") return "now";
  if (status === "blocked") return "blocked";
  return "";
}

const DEMO_PHASES = [
  ["1 Intake", "idea accepted", "done"],
  ["2 Klaryfikacja", "zamkniete", "done"],
  ["3 Rada", "4/5 akceptuje", "done"],
  ["4 Pamiec", "3 dopasowania", "done"],
  ["5 Skills", "7 powiazan", "done"],
  ["6 Zatwierdzenie", "podpisane", "done"],
  ["7 SoT", "zatwierdzone", "done"],
  ["8 Masterplan", "v3", "done"],
  ["9 Plan HG", "D3 ok", "done"],
  ["10 Runtime", "hybrid", "done"],
  ["11 Wykonanie", "ukonezone", "done"],
  ["12 Ryzyko HG", "bezpieczenstwo", "blocked"],
  ["13 Testy", "nieudane", "now"],
  ["14 Final", "oczekiwanie", ""],
  ["15 Pamiec+", "oczekujace", ""],
] as const;

interface Props {
  projectId: string;
}

export function LifecycleRail({ projectId }: Props) {
  const { lifecycle, loading } = useProjectLifecycle(projectId);

  if (loading) {
    return (
      <div className="lifecycle-rail">
        {Array.from({ length: 15 }, (_, i) => (
          <div key={i} className="phase-tile">
            <b>Faza {i + 1}</b>
            <span>ladowanie...</span>
          </div>
        ))}
      </div>
    );
  }

  if (!lifecycle || lifecycle.phases.length === 0) {
    return (
      <div className="lifecycle-rail">
        {DEMO_PHASES.map(([name, detail, state]) => (
          <div key={name} className={`phase-tile ${state}`}>
            <b>{name}</b>
            <span>{detail}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="lifecycle-rail">
      {lifecycle.phases.map((phase, idx) => {
        const label = PHASE_LABELS[phase.hook_event_type] ?? `Faza ${idx + 1}`;
        const state = phaseState(phase.status);
        const detail =
          phase.cards.length > 0
            ? `${phase.cards.length} kart`
            : phase.status;
        return (
          <div key={phase.hook_id} className={`phase-tile ${state}`}>
            <b>{label}</b>
            <span>{detail}</span>
          </div>
        );
      })}
    </div>
  );
}
