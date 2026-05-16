"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  BellRing,
  Download,
  FileArchive,
  FileSpreadsheet,
  FileText,
  Mail,
  PieChart as PieChartIcon,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HelpTip } from "@/components/common/HelpTip";

// Funding records still arrive as heterogeneous legacy payloads from the API.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyRecord = Record<string, any>;

type NotificationDraft = {
  id: string;
  severity: string;
  subject: string;
  body: string;
  dueAt?: number | null;
};

type FundingReportingPanelProps = {
  calls: AnyRecord[];
  ideas: AnyRecord[];
  projects: AnyRecord[];
  applications: AnyRecord[];
  deadlines: AnyRecord[];
  alerts: AnyRecord[];
  executiveReport: AnyRecord | null;
  selectedApplicationId: string;
  representativeEmail: string;
  referenceTimeMs: number | null;
  exporting: boolean;
  onExportApplication: () => void;
  exportUrlFor: (applicationId: string, artifactType: string) => string;
};

const CHART_COLORS = ["#2F6BFF", "#17C964", "#F59E0B", "#F31260", "#7C3AED", "#06B6D4"];

function ChartFrame({
  height,
  children,
}: {
  height: number;
  children: (size: { width: number; height: number }) => ReactNode;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 0, height });

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const updateSize = () => {
      const rect = node.getBoundingClientRect();
      setSize({
        width: Math.max(1, Math.floor(rect.width)),
        height: Math.max(1, Math.floor(rect.height || height)),
      });
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(node);
    return () => observer.disconnect();
  }, [height]);

  return (
    <div ref={ref} className="mt-4 w-full" style={{ height }}>
      {size.width > 1 && size.height > 1 ? children(size) : null}
    </div>
  );
}

function asNumber(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function fmtMoney(value: number): string {
  return new Intl.NumberFormat("pl-PL", {
    currency: "PLN",
    maximumFractionDigits: 0,
    style: "currency",
  }).format(value);
}

function fmtEpoch(value?: number | null): string {
  if (!value) return "n/a";
  const normalized = value < 1_000_000_000_000 ? value * 1000 : value;
  return new Intl.DateTimeFormat("pl-PL", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(normalized));
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: "Szkic",
    needs_documents: "Braki",
    reviewed: "Po przeglądzie",
    submitted: "Złożony",
  };
  return labels[status] ?? (status || "n/a");
}

function statusColor(status: string): string {
  if (status === "submitted") return "#17C964";
  if (status === "reviewed") return "#2F6BFF";
  if (status === "needs_documents") return "#F31260";
  return "#F59E0B";
}

function csvValue(value: unknown): string {
  const text = Array.isArray(value) ? value.join("; ") : String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

function downloadTextFile(filename: string, body: string, type: string): void {
  const blob = new Blob([body], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function applicationBudget(application: AnyRecord): AnyRecord {
  return (application.package_json?.budget ?? application.package?.budget ?? {}) as AnyRecord;
}

function projectBudget(project: AnyRecord): { grant: number; own: number; total: number } {
  const total = asNumber(project.budget_total);
  const grant = asNumber(project.grant_requested);
  return { grant, own: Math.max(total - grant, 0), total };
}

function buildNotificationDrafts(alerts: AnyRecord[], deadlines: AnyRecord[]): NotificationDraft[] {
  const alertDrafts = alerts.slice(0, 4).map((item, index) => ({
    id: String(item.alert_id ?? `alert-${index}`),
    severity: String(item.severity ?? "warning"),
    subject: `AEIS Funding: ${String(item.kind ?? "alert")}`,
    body: String(item.message ?? "Wymagana jest weryfikacja alertu w kokpicie finansowania."),
    dueAt: item.due_at ?? null,
  }));
  const deadlineDrafts = deadlines.slice(0, Math.max(0, 4 - alertDrafts.length)).map((item, index) => ({
    id: String(item.deadline_id ?? `deadline-${index}`),
    severity: "deadline",
    subject: `AEIS Funding: termin ${String(item.label ?? item.type ?? "wniosku")}`,
    body: `Zbliża się termin: ${String(item.label ?? "zadanie funding")}. Data: ${fmtEpoch(item.due_at)}.`,
    dueAt: item.due_at ?? null,
  }));
  return [...alertDrafts, ...deadlineDrafts];
}

function mailtoHref(to: string, draft: NotificationDraft): string {
  const params = new URLSearchParams({
    body: draft.body,
    subject: draft.subject,
  });
  return `mailto:${encodeURIComponent(to || "operator@example.com")}?${params.toString()}`;
}

export function FundingReportingPanel({
  calls,
  ideas,
  projects,
  applications,
  deadlines,
  alerts,
  executiveReport,
  selectedApplicationId,
  representativeEmail,
  referenceTimeMs,
  exporting,
  onExportApplication,
  exportUrlFor,
}: FundingReportingPanelProps) {
  const pipelineData = useMemo(
    () => [
      { stage: "Nabory", count: calls.length },
      { stage: "Pomysły", count: ideas.length },
      { stage: "Projekty", count: projects.length },
      { stage: "Wnioski", count: applications.length },
      { stage: "Terminy", count: deadlines.length },
    ],
    [applications.length, calls.length, deadlines.length, ideas.length, projects.length],
  );

  const statusData = useMemo(() => {
    const counts = applications.reduce<Record<string, number>>((acc, item) => {
      const status = String(item.status ?? "draft");
      acc[status] = (acc[status] ?? 0) + 1;
      return acc;
    }, {});
    const entries = Object.entries(counts);
    return entries.length > 0 ? entries.map(([status, count]) => ({ status, label: statusLabel(status), count })) : [{ status: "empty", label: "Brak wniosków", count: 1 }];
  }, [applications]);

  const roiData = useMemo(() => {
    const applicationRows = applications.map((item, index) => {
      const budget = applicationBudget(item);
      const total = asNumber(budget.budget_total);
      const grant = asNumber(budget.grant_requested);
      return {
        name: String(item.application_id ?? `Wniosek ${index + 1}`).slice(0, 18),
        grant,
        own: Math.max(total - grant, 0),
        total,
      };
    });
    if (applicationRows.length > 0) return applicationRows.slice(0, 8);
    return projects.map((item, index) => {
      const budget = projectBudget(item);
      return {
        name: String(item.title ?? item.project_id ?? `Projekt ${index + 1}`).slice(0, 18),
        ...budget,
      };
    }).slice(0, 8);
  }, [applications, projects]);

  const deadlineTrendData = useMemo(() => {
    const nowSeconds = referenceTimeMs ? referenceTimeMs / 1000 : asNumber(executiveReport?.generated_at);
    const buckets = [
      { label: "7 dni", maxDays: 7, count: 0 },
      { label: "14 dni", maxDays: 14, count: 0 },
      { label: "30 dni", maxDays: 30, count: 0 },
      { label: ">30 dni", maxDays: Number.POSITIVE_INFINITY, count: 0 },
    ];
    deadlines.forEach((item) => {
      const dueAt = asNumber(item.due_at);
      const days = dueAt > 0 ? Math.max(0, (dueAt - nowSeconds) / 86400) : Number.POSITIVE_INFINITY;
      const bucket = buckets.find((candidate) => days <= candidate.maxDays) ?? buckets[buckets.length - 1];
      bucket.count += 1;
    });
    return buckets;
  }, [deadlines, executiveReport?.generated_at, referenceTimeMs]);

  const successRate = applications.length
    ? Math.round((applications.filter((item) => ["reviewed", "submitted"].includes(String(item.status ?? ""))).length / applications.length) * 100)
    : 0;
  const totalGrant = roiData.reduce((sum, item) => sum + asNumber(item.grant), 0);
  const totalBudget = roiData.reduce((sum, item) => sum + asNumber(item.total), 0);
  const notificationDrafts = useMemo(() => buildNotificationDrafts(alerts, deadlines), [alerts, deadlines]);

  const downloadCsv = () => {
    const rows = [
      ["sekcja", "metryka", "wartosc"],
      ["pipeline", "nabory", calls.length],
      ["pipeline", "pomysly", ideas.length],
      ["pipeline", "projekty", projects.length],
      ["pipeline", "wnioski", applications.length],
      ["pipeline", "terminy", deadlines.length],
      ["pipeline", "alerty", alerts.length],
      ["wynik", "gotowosc", executiveReport?.readiness_score ?? ""],
      ["wynik", "success_rate_pct", successRate],
      ["budzet", "grant_total", totalGrant],
      ["budzet", "budget_total", totalBudget],
      ...applications.map((item) => [
        "wniosek",
        String(item.application_id ?? ""),
        String(item.status ?? ""),
      ]),
    ];
    downloadTextFile(
      "funding-report.csv",
      rows.map((row) => row.map(csvValue).join(",")).join("\n"),
      "text/csv;charset=utf-8",
    );
  };

  const exportLinkClass = buttonVariants({ variant: "outline", size: "sm" });

  return (
    <div className="space-y-4" data-testid="funding-reporting-panel">
      <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <PieChartIcon className="h-4 w-4 text-primary" />
              <h2 className="text-lg font-semibold">
                Raportowanie funding
                <HelpTip text="Widok raportowy łączy pipeline, skuteczność, budżet, eksporty i powiadomienia dla operatora." />
              </h2>
            </div>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              Dane pochodzą z realnych endpointów funding: nabory, pomysły, projekty, wnioski, terminy, alerty i raport wykonawczy.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">Gotowość {Math.round(executiveReport?.readiness_score ?? 0)}%</Badge>
            <Badge variant="outline">Skuteczność {successRate}%</Badge>
            <Badge variant="outline">{fmtMoney(totalGrant)} grantów</Badge>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
        <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]" data-testid="funding-pipeline-chart">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold">Pipeline finansowania</h3>
              <p className="text-xs text-muted-foreground">Liczebność aktywnych elementów na kolejnych etapach.</p>
            </div>
            <TrendingUp className="h-4 w-4 text-primary" />
          </div>
          <ChartFrame height={288}>
            {({ width, height }) => (
              <BarChart width={width} height={height} data={pipelineData}>
                <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
                <XAxis dataKey="stage" tick={{ fill: "#94A3B8", fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fill: "#94A3B8", fontSize: 12 }} />
                <Tooltip contentStyle={{ background: "#0a1020", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 8 }} />
                <Bar dataKey="count" name="Liczba" radius={[6, 6, 0, 0]} fill="#2F6BFF" />
              </BarChart>
            )}
          </ChartFrame>
        </Card>

        <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]" data-testid="funding-success-chart">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold">Status i skuteczność</h3>
              <p className="text-xs text-muted-foreground">Udział wniosków gotowych, złożonych i wymagających pracy.</p>
            </div>
            <Badge variant="outline">{successRate}% gotowe</Badge>
          </div>
          <ChartFrame height={288}>
            {({ width, height }) => (
              <PieChart width={width} height={height}>
                <Pie data={statusData} dataKey="count" nameKey="label" innerRadius={54} outerRadius={88} paddingAngle={3}>
                  {statusData.map((item, index) => (
                    <Cell key={item.status} fill={statusColor(item.status) || CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: "#0a1020", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 8 }} />
                <Legend wrapperStyle={{ color: "#CBD5E1", fontSize: 12 }} />
              </PieChart>
            )}
          </ChartFrame>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]" data-testid="funding-roi-chart">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold">ROI i budżet grantowy</h3>
              <p className="text-xs text-muted-foreground">Porównanie wnioskowanego grantu i wkładu własnego.</p>
            </div>
            <Badge variant="outline">{fmtMoney(totalBudget)} budżetu</Badge>
          </div>
          <ChartFrame height={288}>
            {({ width, height }) => (
              <BarChart width={width} height={height} data={roiData}>
                <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: "#94A3B8", fontSize: 11 }} />
                <YAxis tick={{ fill: "#94A3B8", fontSize: 12 }} tickFormatter={(value) => `${Math.round(Number(value) / 1000)}k`} />
                <Tooltip formatter={(value) => fmtMoney(asNumber(value))} contentStyle={{ background: "#0a1020", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 8 }} />
                <Legend wrapperStyle={{ color: "#CBD5E1", fontSize: 12 }} />
                <Bar dataKey="grant" name="Grant" stackId="budget" fill="#17C964" radius={[6, 6, 0, 0]} />
                <Bar dataKey="own" name="Wkład własny" stackId="budget" fill="#F59E0B" radius={[6, 6, 0, 0]} />
              </BarChart>
            )}
          </ChartFrame>
        </Card>

        <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]" data-testid="funding-export-panel">
          <div className="flex items-center gap-2">
            <Download className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold">Eksporty raportowe</h3>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            CSV obejmuje cały kokpit. PDF, XLSX i ZIP są generowane dla wybranego wniosku przez backend funding.
          </p>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <Button variant="outline" size="sm" onClick={downloadCsv}>
              <FileSpreadsheet className="h-3.5 w-3.5" />
              CSV pipeline
            </Button>
            <Button variant="outline" size="sm" onClick={onExportApplication} disabled={!selectedApplicationId || exporting}>
              <FileArchive className="h-3.5 w-3.5" />
              {exporting ? "Generowanie..." : "Generuj pakiet"}
            </Button>
            {selectedApplicationId ? (
              <a className={exportLinkClass} href={exportUrlFor(selectedApplicationId, "pdf")} download>
                <FileText className="h-3.5 w-3.5" />
                PDF wniosku
              </a>
            ) : (
              <Button variant="outline" size="sm" disabled>
                <FileText className="h-3.5 w-3.5" />
                PDF wniosku
              </Button>
            )}
            {selectedApplicationId ? (
              <a className={exportLinkClass} href={exportUrlFor(selectedApplicationId, "xlsx")} download>
                <FileSpreadsheet className="h-3.5 w-3.5" />
                XLSX budżetu
              </a>
            ) : (
              <Button variant="outline" size="sm" disabled>
                <FileSpreadsheet className="h-3.5 w-3.5" />
                XLSX budżetu
              </Button>
            )}
          </div>
          <div className="mt-4 rounded-lg border border-[rgba(148,163,184,0.08)] bg-[#0a1020] px-3 py-2 text-xs text-muted-foreground">
            Wybrany wniosek: <span className="font-mono text-foreground">{selectedApplicationId || "brak"}</span>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.95fr,1.05fr]">
        <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]" data-testid="funding-deadline-chart">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold">Presja terminów</h3>
              <p className="text-xs text-muted-foreground">Rozkład terminów w horyzoncie 7/14/30 dni.</p>
            </div>
            <AlertTriangle className="h-4 w-4 text-sylion-amber" />
          </div>
          <ChartFrame height={256}>
            {({ width, height }) => (
              <LineChart width={width} height={height} data={deadlineTrendData}>
                <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "#94A3B8", fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fill: "#94A3B8", fontSize: 12 }} />
                <Tooltip contentStyle={{ background: "#0a1020", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 8 }} />
                <Line type="monotone" dataKey="count" name="Terminy" stroke="#F59E0B" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            )}
          </ChartFrame>
        </Card>

        <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]" data-testid="funding-notifications-panel">
          <div className="flex items-center gap-2">
            <BellRing className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold">Powiadomienia e-mail</h3>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Szkice powiadomień powstają z aktywnych alertów i terminów. Operator kontroluje wysyłkę przed opuszczeniem systemu.
          </p>
          <div className="mt-4 space-y-2">
            {notificationDrafts.length === 0 ? (
              <p className="text-sm text-muted-foreground">Brak alertów i terminów do powiadomień.</p>
            ) : (
              notificationDrafts.map((draft) => (
                <div key={draft.id} className="rounded-lg border border-[rgba(148,163,184,0.08)] bg-[#0a1020] px-3 py-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{draft.subject}</p>
                    <Badge variant="outline">{draft.dueAt ? fmtEpoch(draft.dueAt) : draft.severity}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{draft.body}</p>
                  <a className={`${exportLinkClass} mt-3`} href={mailtoHref(representativeEmail, draft)}>
                    <Mail className="h-3.5 w-3.5" />
                    Otwórz e-mail
                  </a>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
