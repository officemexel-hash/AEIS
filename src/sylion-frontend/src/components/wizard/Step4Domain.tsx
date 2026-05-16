"use client";

import { SmartDefault } from "./SmartDefault";
import { cn } from "@/lib/utils";

export const PROJECT_DOMAINS: Array<{ id: string; label: string; hint: string }> = [
  { id: "funding", label: "Finansowanie", hint: "Granty, konkursy, konsorcja." },
  { id: "software", label: "Oprogramowanie", hint: "Rozwój aplikacji i usług." },
  { id: "audit", label: "Audyt", hint: "Audyty zgodności wewnętrzne i zewnętrzne." },
  { id: "mobile", label: "Mobile", hint: "Android / iOS / KMP." },
  { id: "infrastructure", label: "Infrastruktura", hint: "VPS, sieci, DevOps." },
  { id: "data_analytics", label: "Dane i analityka", hint: "Pipelines, dashboardy, ETL." },
  { id: "security", label: "Bezpieczeństwo", hint: "AppSec, bezpieczeństwo infrastruktury, IR." },
  { id: "governance", label: "Governance", hint: "Polityki, decyzję, zatwierdzenia." },
  { id: "research", label: "Badania", hint: "Eksperymenty, prototypy." },
  { id: "marketing", label: "Marketing", hint: "Marka, treści, wzrost." },
  { id: "legal", label: "Prawo", hint: "Umowy, zgodność." },
  { id: "product_management", label: "Zarządzanie produktem", hint: "Discovery, roadmapa." },
  { id: "finance", label: "Finanse", hint: "Budżetowanie, raportowanie." },
  { id: "operations", label: "Operacje", hint: "Codzienna realizacja pracy." },
];

export interface Step4Values {
  default_project_domain?: string;
  custom_domain_prefix?: string;
}

interface Props {
  values: Step4Values;
  onChange: (patch: Step4Values) => void;
}

export function Step4Domain({ values, onChange }: Props) {
  const advisorDomain = values.default_project_domain ? null : "software";

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        Wybierz domenę, która najlepiej pasuje do większości Twojej pracy. Nowe projekty
        startują z tym ustawieńiem; później możesz wybrać inną domenę dla konkretnego projektu.
      </p>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-3" data-testid="step4-domains">
        {PROJECT_DOMAINS.map((d) => {
          const active = values.default_project_domain === d.id;
          return (
            <button
              key={d.id}
              type="button"
              onClick={() => onChange({ default_project_domain: d.id })}
              className={cn(
                "rounded-md border px-3 py-2 text-left transition",
                active
                  ? "border-sylion-blue/60 bg-sylion-blue/10 text-sylion-blue"
                  : "border-border hover:bg-muted/30",
              )}
              data-testid={`step4-domain-${d.id}`}
              data-active={active}
            >
              <p className="text-sm font-medium">{d.label}</p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">{d.hint}</p>
            </button>
          );
        })}
      </div>

      {advisorDomain ? (
        <SmartDefault
          label="Oprogramowanie"
          rationale="Większość operatorów zaczyna od oprogramowania; Doradca może później zasugerować zmianę, jeśli profil projektów się przesunie."
          onApply={() => onChange({ default_project_domain: advisorDomain })}
        />
      ) : null}

      <div className="space-y-1.5 border-t border-border pt-4">
        <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Opcjonalny prefiks domeny niestandardowej
        </label>
        <input
          type="text"
          value={values.custom_domain_prefix ?? ""}
          onChange={(e) => onChange({ custom_domain_prefix: e.target.value })}
          placeholder="np. moja_firma / org_xyz"
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none transition focus:border-sylion-blue/60"
          data-testid="step4-prefix"
        />
        <p className="text-[11px] text-muted-foreground">
          Przydatne, jeśli chcesz oddzielić własne domeny od 14 domen bazowych.
        </p>
      </div>
    </div>
  );
}
