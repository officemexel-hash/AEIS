"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, CheckCircle2, Clock3, RefreshCw, ShieldAlert, TicketCheck, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { cn, fmtDateTime } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";

type TicketState = "pending" | "approved" | "rejected" | "expired" | "withdrawn" | "escalated";

type GovernanceTicket = {
  ticket_id: string;
  origin: string;
  project_id?: string | null;
  decision_class: string;
  gate_type: string;
  priority: string;
  title: string;
  summary: string;
  payload?: Record<string, unknown>;
  requested_by?: string;
  created_at: number;
  sla_deadline?: number;
  state: TicketState;
  resolved_by?: string | null;
  resolved_at?: number | null;
  resolution_reason?: string | null;
};

type FundingTicketLabel = {
  ideaTitle?: string;
  callTitle?: string;
  companyName?: string;
  ideaId?: string;
  callId?: string;
  companyId?: string;
};

function compactId(value: unknown): string {
  const text = String(value || "");
  if (!text) return "---";
  return text.length > 18 ? `${text.slice(0, 14)}...` : text;
}

function cleanOperatorText(value: unknown): string {
  return String(value || "")
    .replace(/^Review council change proposal:\s*/i, "Przegląd zmiany po Radzie: ")
    .replace(/\bCouncil V10\b/g, "Rady V10")
    .replace(/\bModel Council\b/g, "Rada modeli")
    .trim();
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function parseRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object") return value as Record<string, unknown>;
  if (typeof value === "string" && value.trim()) {
    try {
      const parsed = JSON.parse(value);
      return asRecord(parsed);
    } catch {
      return {};
    }
  }
  return {};
}

function asTextList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function boolLabel(value: unknown): string {
  return value ? "tak" : "nie";
}

function usdLabel(value: unknown): string {
  const amount = Number(value ?? 0);
  return Number.isFinite(amount) ? `${amount.toFixed(2)} USD` : "---";
}

function riskLevelLabel(value: unknown): string {
  return {
    low: "niski",
    medium: "średni",
    high: "wysoki",
    critical: "krytyczny",
  }[String(value || "")] || "---";
}

function changeTypeLabel(value: unknown): string {
  return {
    v10_audit_project_readiness: "Audyt gotowości Rady V10",
    project_change_review: "Przegląd zmiany projektu",
  }[String(value || "")] || String(value || "---").replace(/_/g, " ");
}

function riskFlagLabel(value: string): string {
  return {
    affects_architecture: "architektura",
    affects_masterplan: "Masterplan",
    affects_source_of_truth: "źródło prawdy",
    external_action: "akcja zewnętrzna",
    production_deploy: "wdrożenie produkcyjne",
    final_action: "akcja finalna",
    legal_or_financial_action: "czynność prawna lub finansowa",
    cost_delta_gt_25_usd: "koszt powyżej 25 USD",
    monthly_cost_delta_gt_100_usd: "miesięczny koszt powyżej 100 USD",
    vps_workers_gt_3: "więcej niż 3 workery VPS",
    risk_level_high: "wysokie ryzyko",
    risk_level_critical: "krytyczne ryzyko",
  }[value] || value.replace(/_/g, " ");
}

function ideaTagLabel(value: string): string {
  const domainLabels: Record<string, string> = {
    engineering: "Inżynieria",
    product: "Produkt",
    design: "Design",
    research: "Badania",
    infrastructure: "Infrastruktura",
    security: "Bezpieczeństwo",
    compliance: "Compliance",
    finance: "Finanse",
    marketing: "Marketing",
    sales: "Sprzedaż",
    operations: "Operacje",
    data: "Dane",
    strategy: "Strategia",
    other: "Inne",
  };
  if (value.startsWith("domain:")) {
    const domain = value.slice("domain:".length);
    return `Domena: ${domainLabels[domain] || domain}`;
  }
  return value.replace(/_/g, " ");
}

function governancePriorityLabel(value: unknown): string {
  const text = String(value || "");
  const labels: Record<string, string> = {
    attachment_d3: "załącznik D3",
    manual_transition: "ręczna zmiana statusu",
    project_change_review: "przegląd zmiany projektu",
  };
  return labels[text] || text.replace(/_/g, " ") || "---";
}

function toneForPriority(priority: string): string {
  if (priority === "P0" || priority === "P1") return "border-sylion-red/30 text-sylion-red bg-sylion-red/5";
  if (priority === "P2") return "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5";
  return "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5";
}

function toneForState(state: string): string {
  if (state === "approved") return "border-sylion-green/30 text-sylion-green bg-sylion-green/5";
  if (state === "rejected" || state === "expired") return "border-sylion-red/30 text-sylion-red bg-sylion-red/5";
  if (state === "escalated") return "border-sylion-amber/30 text-sylion-amber bg-sylion-amber/5";
  return "border-sylion-blue/30 text-sylion-blue bg-sylion-blue/5";
}

const HIGH_RISK_GATE_TYPES = [
  "production",
  "legal",
  "financial",
  "external_action",
  "final",
  "security",
  "direction_gate",
  "source_of_truth_gate",
  "masterplan_gate",
];

const BLOCKING_GATE_TYPES = [
  "blocking",
  "emergency",
  "direction_gate",
  "source_of_truth_gate",
  "masterplan_gate",
  "production",
  "external_action",
  "final",
];

function toneForGate(gateType: string): string {
  if (["production", "legal", "financial", "external_action", "final", "source_of_truth_gate", "masterplan_gate"].includes(gateType)) {
    return "border-sylion-red/30 text-sylion-red";
  }
  if (["security", "emergency", "blocking", "direction_gate"].includes(gateType)) {
    return "border-sylion-amber/30 text-sylion-amber";
  }
  return "border-muted-foreground/30 text-muted-foreground";
}

function formatTime(value?: number | null): string {
  if (!value) return "---";
  const normalized = value < 1_000_000_000_000 ? value * 1000 : value;
  return fmtDateTime(normalized);
}

function payloadSummary(payload?: Record<string, unknown>): string {
  if (!payload || Object.keys(payload).length === 0) return "Brak szczegółów.";
  return Object.entries(payload)
    .slice(0, 5)
    .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
    .join(" | ");
}

function stateLabel(state: string): string {
  if (state === "pending") return "OCZEKUJE";
  if (state === "approved") return "ZATWIERDZONE";
  if (state === "rejected") return "ODRZUCONE";
  if (state === "expired") return "WYGASŁE";
  if (state === "withdrawn") return "WYCOFANE";
  if (state === "escalated") return "ESKALOWANE";
  return state.toUpperCase();
}

function gateLabel(gateType: string): string {
  if (gateType === "blocking") return "blokujące";
  if (gateType === "financial") return "finansowe";
  if (gateType === "security") return "bezpieczeństwo";
  if (gateType === "production") return "produkcja";
  if (gateType === "external_action") return "zewnętrzne";
  if (gateType === "final") return "finalne";
  if (gateType === "legal") return "prawne";
  if (gateType === "emergency") return "awaryjne";
  if (gateType === "direction_gate") return "kierunek";
  if (gateType === "source_of_truth_gate") return "Źródło Prawdy";
  if (gateType === "masterplan_gate") return "Masterplan";
  return gateType.replace(/_/g, " ");
}

function originLabel(origin: string): string {
  if (origin === "funding") return "finansowanie";
  if (origin === "workspace") return "workspace";
  if (origin === "council") return "rada";
  if (origin === "autonomy") return "autonomia";
  return origin;
}

function ticketTitle(ticket: GovernanceTicket, label?: FundingTicketLabel): string {
  if (ticket.payload?.action === "project_build_authorize") {
    return "Autoryzacja budowy projektu (runda 3)";
  }
  if (ticket.payload?.action === "idea_conversion") {
    const idea = label?.ideaTitle || compactId(ticket.payload.idea_id);
    return `Zamiana pomysłu fundingowego „${idea}” na projekt`;
  }
  if (ticket.payload?.legacy_gate_id || /^Idea approval:/i.test(ticket.title || "")) {
    const title = String(ticket.title || "").replace(/^Idea approval:\s*/i, "").trim();
    return `Zatwierdzenie pomysłu${title ? `: ${title}` : ""}`;
  }
  if (ticket.payload?.action === "project_change_review") {
    const proposal = asRecord(ticket.payload.proposal);
    const title = cleanOperatorText(proposal.title || ticket.title || "zmiana projektu");
    return `Decyzja po Radzie V10: ${title}`;
  }
  return cleanOperatorText(ticket.title) || "(bilet bez tytułu)";
}

function ticketSummary(ticket: GovernanceTicket, label?: FundingTicketLabel): string {
  if (ticket.payload?.action === "project_build_authorize") {
    return "Runda 3 wymaga zgody operatora przed budową, kosztem, akcją zewnętrzną albo wejściem w produkcję. Akceptacja odblokuje tylko wskazany etap zgodnie z limitem kosztu i polityką Human Gate.";
  }
  if (ticket.payload?.action === "idea_conversion") {
    if (label?.callTitle) {
      return `Akceptacja utworzy śledzony projekt grantowy dla naboru „${label.callTitle}” i uruchomi formalne przygotowanie zasobów, dopasowania oraz wniosku.`;
    }
    return "Akceptacja utworzy śledzony projekt grantowy i uruchomi formalne przygotowanie zasobów, dopasowania oraz wniosku.";
  }
  if (ticket.payload?.action === "project_change_review") {
    const proposal = asRecord(ticket.payload.proposal);
    const title = cleanOperatorText(proposal.title || "oceniony krok projektu");
    const flags = asTextList(ticket.payload.risk_flags).map(riskFlagLabel);
    const risks = flags.length ? ` Zakres uwagi: ${flags.join(", ")}.` : "";
    return `Rada zatrzymała krok „${title}” do decyzji operatora. Akceptacja pozwala kontynuować wskazany etap, odrzucenie zatrzyma go do poprawy lub ponownej Rady.${risks}`;
  }
  if (ticket.payload?.legacy_gate_id || /^Idea approval:/i.test(ticket.title || "")) {
    const payload = asRecord(ticket.payload);
    const description = cleanOperatorText(payload.description || ticket.summary);
    return description || "Akceptacja odblokuje dalszą pracę z pomysłem i pozwoli przejść do promocji projektu.";
  }
  return cleanOperatorText(ticket.summary) || "Brak podsumowania.";
}

function FundingPayloadDetails({
  label,
  payload,
}: {
  label?: FundingTicketLabel;
  payload?: Record<string, unknown>;
}) {
  const cells = [
    ["Pomysł", label?.ideaTitle || compactId(payload?.idea_id)],
    ["Nabór", label?.callTitle || compactId(payload?.call_id)],
    ["Firma", label?.companyName || String(payload?.company_id || "default")],
    ["TRL", String(payload?.target_trl || "---")],
  ];
  return (
    <div className="grid gap-2 md:grid-cols-2">
      {cells.map(([name, value]) => (
        <div key={name} className="min-w-0 rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2">
          <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{name}</p>
          <p className="mt-1 break-words text-xs text-foreground/90">{value}</p>
        </div>
      ))}
    </div>
  );
}

function CouncilPayloadDetails({ payload }: { payload?: Record<string, unknown> }) {
  const proposal = asRecord(payload?.proposal);
  const riskFlags = asTextList(payload?.risk_flags);
  const analysesFailures = asTextList(payload?.analysis_failures);
  const cells = [
    ["Co jest oceniane", cleanOperatorText(proposal.title || "Decyzja projektowa")],
    ["Typ sprawy", changeTypeLabel(proposal.change_type || payload?.action)],
    ["Poziom ryzyka", riskLevelLabel(proposal.risk_level)],
    ["Koszt jednorazowy", usdLabel(proposal.cost_delta_usd)],
    ["Koszt miesięczny", usdLabel(proposal.monthly_cost_delta_usd)],
    ["Workery VPS", String(proposal.vps_workers ?? 0)],
  ];
  const decisions = [
    ["Akcja zewnętrzna", boolLabel(proposal.external_action)],
    ["Wdrożenie produkcyjne", boolLabel(proposal.production_deploy)],
    ["Akcja finalna", boolLabel(proposal.final_action)],
    ["Czynność prawna/finansowa", boolLabel(proposal.legal_or_financial_action)],
    ["Dotyka architektury", boolLabel(proposal.affects_architecture)],
    ["Dotyka Masterplanu", boolLabel(proposal.affects_masterplan)],
    ["Dotyka źródła prawdy", boolLabel(proposal.affects_source_of_truth)],
  ];

  return (
    <div className="space-y-3" data-testid="human-gate-operator-payload">
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {cells.map(([name, value]) => (
          <div key={name} className="min-w-0 rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{name}</p>
            <p className="mt-1 break-words text-xs text-foreground/90">{value}</p>
          </div>
        ))}
      </div>

      <div className="rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2">
        <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Co wymaga uwagi</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {riskFlags.length ? (
            riskFlags.map((flag) => (
              <Badge key={flag} variant="outline" className="border-sylion-amber/30 text-sylion-amber">
                {riskFlagLabel(flag)}
              </Badge>
            ))
          ) : (
            <span className="text-xs text-muted-foreground">Brak blokujących flag.</span>
          )}
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {decisions.map(([name, value]) => (
          <div key={name} className="rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2 text-xs">
            <span className="text-muted-foreground">{name}: </span>
            <span className="font-medium text-foreground/90">{value}</span>
          </div>
        ))}
      </div>

      {analysesFailures.length ? (
        <div className="rounded-md border border-sylion-red/25 bg-sylion-red/5 px-3 py-2 text-xs text-sylion-red">
          Nie wszystkie analizy modeli zakończyły się poprawnie: {analysesFailures.join(", ")}
        </div>
      ) : null}

      <details className="rounded-md border border-border/40 bg-black/10 px-3 py-2 text-xs text-muted-foreground">
        <summary className="cursor-pointer text-foreground/80">Podgląd techniczny dla audytu</summary>
        <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap break-words text-[10px]">
          {JSON.stringify(payload || {}, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function IdeaApprovalPayloadDetails({ payload }: { payload?: Record<string, unknown> }) {
  const context = parseRecord(payload?.context);
  const tags = asTextList(context.tags).map(ideaTagLabel);
  const cells = [
    ["Klasa decyzji", String(payload?.decision_class || context.decision_class || "---")],
    ["Priorytet governance", governancePriorityLabel(payload?.governance_priority || context.governance_priority)],
    ["ID pomysłu", compactId(context.idea_id || payload?.idea_id)],
    ["ID bramki", compactId(payload?.legacy_gate_id)],
    ["Autor", String(context.author || "---")],
    ["Tagi", tags.length ? tags.join(", ") : "---"],
  ];

  return (
    <div className="space-y-3" data-testid="human-gate-idea-payload">
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {cells.map(([name, value]) => (
          <div key={name} className="min-w-0 rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{name}</p>
            <p className="mt-1 break-words text-xs text-foreground/90">{value}</p>
          </div>
        ))}
      </div>

      {payload?.description ? (
        <div className="rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2 text-xs">
          <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Powód bramki</p>
          <p className="mt-1 text-foreground/90">{cleanOperatorText(payload.description)}</p>
        </div>
      ) : null}

      <details className="rounded-md border border-border/40 bg-black/10 px-3 py-2 text-xs text-muted-foreground">
        <summary className="cursor-pointer text-foreground/80">Podgląd techniczny dla audytu</summary>
        <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap break-words text-[10px]">
          {JSON.stringify(payload || {}, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function ProjectBuildPayloadDetails({ payload }: { payload?: Record<string, unknown> }) {
  const gateTypes = asTextList(payload?.gate_types).map(gateLabel);
  const cells = [
    ["Akcja", "Autoryzacja budowy projektu"],
    ["Cel", String(payload?.target || "budowa")],
    ["Wymaga Human Gate", boolLabel(payload?.requires_human_gate ?? true)],
    ["Limit kosztu", usdLabel(payload?.cost_cap_usd)],
    ["Autonomia", String(payload?.autonomy_level || "---")],
    ["Bramki", gateTypes.length ? gateTypes.join(", ") : "---"],
  ];
  return (
    <div className="space-y-3" data-testid="human-gate-build-payload">
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {cells.map(([name, value]) => (
          <div key={name} className="min-w-0 rounded-md border border-[rgba(148,163,184,0.08)] bg-black/10 px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">{name}</p>
            <p className="mt-1 break-words text-xs text-foreground/90">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function TicketPayloadDetails({
  label,
  payload,
}: {
  label?: FundingTicketLabel;
  payload?: Record<string, unknown>;
}) {
  if (payload?.action === "project_build_authorize") {
    return <ProjectBuildPayloadDetails payload={payload} />;
  }
  if (payload?.action === "idea_conversion") {
    return <FundingPayloadDetails label={label} payload={payload} />;
  }
  if (payload?.action === "project_change_review") {
    return <CouncilPayloadDetails payload={payload} />;
  }
  if (payload?.legacy_gate_id) {
    return <IdeaApprovalPayloadDetails payload={payload} />;
  }
  return <span>{payloadSummary(payload)}</span>;
}

export default function HumanGatePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const focusedTicketId = searchParams.get("ticket") || "";
  const { data: health, loading: healthLoading, refresh: refreshHealth } = useHealth();
  const backendLive = health.status === "ok";
  const backendChecking = healthLoading || health.status === "unknown";
  const [stateFilter, setStateFilter] = useState<"pending" | "all">("pending");
  const [tickets, setTickets] = useState<GovernanceTicket[]>([]);
  const [focusedTicket, setFocusedTicket] = useState<GovernanceTicket | null>(null);
  const [fundingLabels, setFundingLabels] = useState<Record<string, FundingTicketLabel>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyTicketId, setBusyTicketId] = useState<string | null>(null);

  const hydrateFundingLabels = useCallback(async (items: GovernanceTicket[]) => {
    const fundingTickets = items.filter((ticket) => ticket.payload?.action === "idea_conversion");
    if (fundingTickets.length === 0) return;
    const entries = await Promise.all(
      fundingTickets.map(async (ticket) => {
        const payload = ticket.payload ?? {};
        const ideaId = String(payload.idea_id || "");
        const callId = String(payload.call_id || "");
        const companyId = String(payload.company_id || "default");
        const [idea, call, company] = await Promise.all([
          ideaId ? api.getFundingIdea(ideaId).catch(() => null) : Promise.resolve(null),
          callId ? api.getFundingCall(callId).catch(() => null) : Promise.resolve(null),
          api.getFundingCompanyProfile(companyId).catch(() => null),
        ]);
        const ideaRecord = asRecord(idea);
        const callRecord = asRecord(call);
        const companyRecord = asRecord(company);
        return [
          ticket.ticket_id,
          {
            ideaId,
            callId,
            companyId,
            ideaTitle: String(ideaRecord.title || ""),
            callTitle: String(callRecord.title || ""),
            companyName: String(companyRecord.legal_name || companyRecord.name || companyId),
          },
        ] as const;
      }),
    );
    setFundingLabels((prev) => ({ ...prev, ...Object.fromEntries(entries) }));
  }, []);

  const fetchTickets = useCallback(async () => {
    setLoading(true);
    try {
      const [data, focused] = await Promise.all([
        api.governanceTicketsList(undefined, stateFilter === "pending" ? "pending" : undefined),
        focusedTicketId ? api.governanceTicketGet(focusedTicketId).catch(() => null) : Promise.resolve(null),
      ]);
      const items = (data.tickets ?? []) as GovernanceTicket[];
      const focusedItem = focused ? (focused as GovernanceTicket) : null;
      setTickets(items);
      setFocusedTicket(focusedItem);
      void hydrateFundingLabels(focusedItem ? [focusedItem, ...items] : items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Human Gate tickets");
    } finally {
      setLoading(false);
    }
  }, [focusedTicketId, hydrateFundingLabels, stateFilter]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchTickets();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchTickets]);

  const visibleTickets = useMemo(() => {
    const items =
      focusedTicket && !tickets.some((ticket) => ticket.ticket_id === focusedTicket.ticket_id)
        ? [focusedTicket, ...tickets]
        : tickets;
    if (!focusedTicketId) return items;
    return [...items].sort((left, right) => {
      if (left.ticket_id === focusedTicketId) return -1;
      if (right.ticket_id === focusedTicketId) return 1;
      return 0;
    });
  }, [focusedTicket, focusedTicketId, tickets]);

  const stats = useMemo(() => {
    const pending = visibleTickets.filter((ticket) => ticket.state === "pending").length;
    const highRisk = visibleTickets.filter((ticket) => HIGH_RISK_GATE_TYPES.includes(ticket.gate_type)).length;
    const blocking = visibleTickets.filter((ticket) =>
      BLOCKING_GATE_TYPES.includes(ticket.gate_type) || ticket.priority === "P0" || ticket.priority === "P1"
    ).length;
    return { pending, highRisk, blocking, total: visibleTickets.length };
  }, [visibleTickets]);

  const nextProjectId = focusedTicket?.project_id || visibleTickets.find((ticket) => ticket.project_id)?.project_id || "";
  const focusedTicketApproved = focusedTicket?.state === "approved";
  const pendingCount = visibleTickets.filter((ticket) => ticket.state === "pending").length;

  const refreshAll = () => {
    refreshHealth();
    fetchTickets();
  };

  const decide = async (ticketId: string, decision: "approved" | "rejected") => {
    setBusyTicketId(ticketId);
    try {
      await api.governanceTicketResolve(
        ticketId,
        decision,
        "operator-console",
        `operator-console ${decision}`,
      );
      await fetchTickets();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${decision} ticket`);
    } finally {
      setBusyTicketId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-sylion-amber/30 bg-sylion-amber/10">
              <ShieldAlert className="h-5 w-5 text-sylion-amber" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                Bramka człowieka
                <HelpTip text="Kolejka decyzji wymagających zatwierdzenia operatora (D4-D5, security-sensitive). Każda decyzja: kontekst + opcje + rekomendacja rady. Można Zatwierdzić, Odrzucić, Odłożyć." />
              </h1>
              <p className="text-sm text-muted-foreground">
                Ujednolicona kolejka akceptacji operatora dla działań strategicznych, ryzykownych, kosztownych, zewnętrznych, produkcyjnych i finałowych.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className={backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red"}>
              {backendLive ? "BACKEND DZIAŁA" : backendChecking ? "SPRAWDZANIE BACKENDU" : "BACKEND NIEDOSTĘPNY"}
            </Badge>
            <Badge variant="outline" className="border-sylion-blue/30 text-sylion-blue">
              UJEDNOLICONE BILETY
            </Badge>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant={stateFilter === "pending" ? "default" : "outline"}
            size="sm"
            onClick={() => setStateFilter("pending")}
          >
            Oczekujące
          </Button>
          <Button
            variant={stateFilter === "all" ? "default" : "outline"}
            size="sm"
            onClick={() => setStateFilter("all")}
          >
            Wszystkie
          </Button>
          <Button variant="outline" size="sm" onClick={refreshAll}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Odśwież
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Widoczne bilety
            <HelpTip text="Liczba biletów widocznych przy obecnym filtrze (Oczekujące / Wszystkie)." />
          </p>
          <p className="mt-2 text-2xl font-semibold">{stats.total}</p>
        </Card>
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Oczekujące
            <HelpTip text="Bilety czekające na decyzję operatora (Zatwierdź / Odrzuć)." />
          </p>
          <p className="mt-2 text-2xl font-semibold text-sylion-blue">{stats.pending}</p>
        </Card>
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Wysokie ryzyko
            <HelpTip text="Bilety klasyfikowane jako produkcja, prawo, finanse, akcje zewnętrzne, final, security, kierunek, Źródło Prawdy albo Masterplan." />
          </p>
          <p className="mt-2 text-2xl font-semibold text-sylion-red">{stats.highRisk}</p>
        </Card>
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Blokujące/P1
            <HelpTip text="Bilety o priorytecie P0/P1 albo typie blokującym: kierunek, Źródło Prawdy, Masterplan, produkcja, akcja zewnętrzna, final lub emergency." />
          </p>
          <p className="mt-2 text-2xl font-semibold text-sylion-amber">{stats.blocking}</p>
        </Card>
      </div>

      {error && (
        <Card className="border-sylion-red/30 bg-sylion-red/5 p-4 text-sm text-sylion-red">
          <AlertTriangle className="mr-2 inline h-4 w-4" />
          {error}
        </Card>
      )}

      {focusedTicketId && (
        <Card className="border-sylion-amber/35 bg-sylion-amber/10 p-4 text-sm" data-testid="human-gate-focused-ticket-banner">
          <p className="font-medium text-sylion-amber">Otworzono z Rady V10</p>
          <p className="mt-1 text-muted-foreground">
            Szukany bilet: <span className="font-mono text-foreground">{focusedTicketId}</span>. Jeżeli jest widoczny w kolejce, został przeniesiony na górę listy.
          </p>
        </Card>
      )}

      {!backendChecking && !backendLive && (
        <Card className="border-sylion-red/30 bg-sylion-red/5 p-6">
          <p className="font-medium text-sylion-red">Backend niedostępny.</p>
          <p className="mt-1 text-sm text-muted-foreground">Bramka człowieka nie może zatwierdzać ani odrzucać działań bez działającego API.</p>
        </Card>
      )}

      {!loading && (focusedTicketApproved || (pendingCount === 0 && stateFilter === "pending")) && (
        <Card className="border-sylion-green/35 bg-sylion-green/10 p-4" data-testid="human-gate-next-step">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="font-semibold text-sylion-green">
                {focusedTicketApproved ? "HumanGate zatwierdzony" : "Brak oczekujących decyzji"}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {focusedTicketApproved
                  ? "Ten bilet został zatwierdzony. Następny krok to sprawdźenie lifecycle projektu i kontynuacja pracy z miejsca, które HumanGate odblokował."
                  : "Kolejka oczekujących biletów jest pusta. Możesz wrócić do projektu albo lifecycle i sprawdźić, który etap jest teraz aktywny."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {nextProjectId ? (
                <>
                  <Button
                    className="bg-sylion-green/20 text-sylion-green hover:bg-sylion-green/30 border border-sylion-green/40"
                    data-testid="human-gate-open-lifecycle"
                    onClick={() => router.push(`/projects/${encodeURIComponent(nextProjectId)}/lifecycle`)}
                  >
                    Przejdź do lifecycle
                  </Button>
                  <Button
                    variant="outline"
                    data-testid="human-gate-open-project-directions"
                    onClick={() => router.push(`/projects/${encodeURIComponent(nextProjectId)}#project-directions`)}
                  >
                    Dyskusja i kierunki
                  </Button>
                  <Button
                    variant="outline"
                    data-testid="human-gate-open-orchestration"
                    onClick={() => router.push(`/projects/${encodeURIComponent(nextProjectId)}/orchestration`)}
                  >
                    Wróć do orkiestracji
                  </Button>
                  <Button
                    variant="outline"
                    data-testid="human-gate-open-project"
                    onClick={() => router.push(`/projects/${encodeURIComponent(nextProjectId)}`)}
                  >
                    Otwórz projekt
                  </Button>
                </>
              ) : (
                <Button variant="outline" onClick={() => router.push("/projects")}>
                  Otwórz projekty
                </Button>
              )}
            </div>
          </div>
        </Card>
      )}

      {loading ? (
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-8 text-center text-sm text-muted-foreground">
          Ładowanie biletów zarządczych...
        </Card>
      ) : (
        <div className="grid gap-4">
          {visibleTickets.map((ticket) => {
            const isFocusedTicket = focusedTicketId === ticket.ticket_id;
            return (
            <Card
              key={ticket.ticket_id}
              data-ticket-id={ticket.ticket_id}
              data-testid={isFocusedTicket ? "human-gate-focused-ticket" : undefined}
              className={cn(
                "border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5",
                isFocusedTicket && "border-sylion-amber/70 bg-sylion-amber/10 shadow-[0_0_0_1px_rgba(245,158,11,0.25)]",
              )}
            >
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="min-w-0 flex-1 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className={toneForPriority(ticket.priority)}>
                      {ticket.priority}
                    </Badge>
                    <Badge variant="outline" className={toneForState(ticket.state)}>
                      <Clock3 className="mr-1 h-3 w-3" />
                      {stateLabel(ticket.state)}
                    </Badge>
                    <Badge variant="outline" className={toneForGate(ticket.gate_type)}>
                      {gateLabel(ticket.gate_type)}
                    </Badge>
                    <Badge variant="outline" className="border-border/40 text-muted-foreground">
                      {ticket.decision_class}
                    </Badge>
                    <Badge variant="outline" className="border-border/40 text-muted-foreground">
                      {originLabel(ticket.origin)}
                    </Badge>
                  </div>

                  <div>
                    <h2 className="text-base font-semibold">{ticketTitle(ticket, fundingLabels[ticket.ticket_id])}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">{ticketSummary(ticket, fundingLabels[ticket.ticket_id])}</p>
                  </div>

                  <div className="grid gap-2 text-[11px] text-muted-foreground md:grid-cols-2 xl:grid-cols-4">
                    <span>Bilet: <span className="font-mono text-foreground/80">{ticket.ticket_id.slice(0, 12)}</span></span>
                    <span>Projekt: <span className="font-mono text-foreground/80">{ticket.project_id || "---"}</span></span>
                    <span>Utworzono: {formatTime(ticket.created_at)}</span>
                    <span>SLA: {formatTime(ticket.sla_deadline)}</span>
                  </div>

                  <div className="rounded-lg border border-[rgba(148,163,184,0.08)] bg-black/5 p-3 text-[11px] text-muted-foreground">
                    <TicketPayloadDetails label={fundingLabels[ticket.ticket_id]} payload={ticket.payload} />
                  </div>
                </div>

                <div className="flex min-w-[220px] flex-col gap-2">
                  <Button variant="outline" className="w-full justify-between" disabled>
                    Szczegóły audytu
                    <TicketCheck className="h-4 w-4" />
                  </Button>
                  <Button
                    className="w-full justify-between bg-sylion-green/90 text-black hover:bg-sylion-green"
                    disabled={ticket.state !== "pending" || busyTicketId === ticket.ticket_id}
                    onClick={() => decide(ticket.ticket_id, "approved")}
                  >
                    Zatwierdź
                    <CheckCircle2 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    className={cn("w-full justify-between border-sylion-red/30 text-sylion-red hover:bg-sylion-red/10")}
                    disabled={ticket.state !== "pending" || busyTicketId === ticket.ticket_id}
                    onClick={() => decide(ticket.ticket_id, "rejected")}
                  >
                    Odrzuć
                    <XCircle className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Card>
            );
          })}

          {visibleTickets.length === 0 && (
            <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-8 text-center">
              <p className="text-sm text-muted-foreground">Brak {stateFilter === "pending" ? "oczekujących " : ""}biletów Bramki człowieka.</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
