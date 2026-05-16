"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import { fmtDateTime } from "@/lib/utils";
import { HelpTip } from "@/components/common/HelpTip";
import { FundingReportingPanel } from "./funding-reporting-panel";
import {
  BriefcaseBusiness,
  Building2,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
  Target,
  ShieldCheck,
  Send,
  AlertTriangle,
  FolderKanban,
  CalendarClock,
  Mail,
  Landmark,
} from "lucide-react";

// Funding API payloads are heterogeneous legacy records rendered directly in the cockpit.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyRecord = Record<string, any>;

type ProfileForm = {
  legal_name: string;
  tax_id: string;
  registration_id: string;
  country: string;
  region: string;
  city: string;
  legal_form: string;
  sme_status: string;
  employees: string;
  annual_revenue: string;
  ebitda: string;
  technologies: string;
  products: string;
  services: string;
  team_competencies: string;
  strategic_goals: string;
  representative_name: string;
  representative_email: string;
  export_markets: string;
};

type FundingTab =
  | "company"
  | "calls"
  | "ideas"
  | "matching"
  | "applications"
  | "submission"
  | "reporting";

const COMPANY_ID = "default";

const EMPTY_PROFILE: ProfileForm = {
  legal_name: "",
  tax_id: "",
  registration_id: "",
  country: "Poland",
  region: "",
  city: "",
  legal_form: "",
  sme_status: "SME",
  employees: "",
  annual_revenue: "",
  ebitda: "",
  technologies: "",
  products: "",
  services: "",
  team_competencies: "",
  strategic_goals: "",
  representative_name: "",
  representative_email: "",
  export_markets: "",
};

function toCsv(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : "";
}

function splitCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toEpoch(input: string): number | null {
  if (!input.trim()) return null;
  const parsed = Date.parse(input);
  if (Number.isNaN(parsed)) return null;
  return Math.floor(parsed / 1000);
}

function fmtEpoch(value?: number | null): string {
  if (!value) return "n/a";
  const normalized = value < 1_000_000_000_000 ? value * 1000 : value;
  return fmtDateTime(normalized);
}

function hasRecordPayload(value: unknown): value is AnyRecord {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value) && Object.keys(value as AnyRecord).length > 0;
}

function describeSourceMode(source: AnyRecord): string {
  if (source.available && source.scan_mode === "live_manual") {
    return "Ręczna baza wiedzy";
  }
  if (source.available) {
    return "Źródło aktywne";
  }
  return "Niedostępne";
}

function MetricCard({
  icon: Icon,
  label,
  value,
  hint,
  accent,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  hint: string;
  accent: string;
}) {
  const tip = label === "Gotowość" ? "Procent uzupełnienia profilu firmy. >80% rekomendowane przed składaniem wniosków."
    : label === "Nabory" ? "Liczba aktywnych naborów (call'ów) zindeksowanych w systemie."
    : label === "Wnioski" ? "Liczba pakietów aplikacyjnych w przygotowaniu lub złożonych."
    : label === "Alerty" ? "Aktywne alerty wymagające uwagi (zbliżające się terminy, brakujące dokumenty itp.)."
    : "";
  return (
    <Card className="p-4 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            {label}
            {tip && <HelpTip text={tip} />}
          </p>
          <p className="mt-2 text-2xl font-semibold">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
        </div>
        <div className="rounded-xl p-2.5" style={{ background: `${accent}18` }}>
          <Icon className="w-4 h-4" style={{ color: accent }} />
        </div>
      </div>
    </Card>
  );
}

function Input({
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      type={type}
      placeholder={placeholder}
      className="w-full rounded-lg border border-[rgba(148,163,184,0.12)] bg-[#0a1020] px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary/40"
    />
  );
}

function TextArea({
  value,
  onChange,
  placeholder,
  rows = 4,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <textarea
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full rounded-lg border border-[rgba(148,163,184,0.12)] bg-[#0a1020] px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary/40"
    />
  );
}

export default function FundingPage() {
  const { data: health } = useHealth();
  const backendChecking = health.status === "unknown";
  const backendLive = health.status === "ok" || backendChecking;

  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<FundingTab>("company");

  const [profileForm, setProfileForm] = useState<ProfileForm>(EMPTY_PROFILE);
  const [profileReadiness, setProfileReadiness] = useState<AnyRecord | null>(null);
  const [registrySync, setRegistrySync] = useState<AnyRecord | null>(null);
  const [registryKrs, setRegistryKrs] = useState("");
  const [registryMessage, setRegistryMessage] = useState("");
  const [stateAid, setStateAid] = useState<AnyRecord | null>(null);
  const [documents, setDocuments] = useState<AnyRecord[]>([]);
  const [sources, setSources] = useState<AnyRecord[]>([]);
  const [programmes, setProgrammes] = useState<AnyRecord[]>([]);
  const [calls, setCalls] = useState<AnyRecord[]>([]);
  const [ideas, setIdeas] = useState<AnyRecord[]>([]);
  const [projects, setProjects] = useState<AnyRecord[]>([]);
  const [applications, setApplications] = useState<AnyRecord[]>([]);
  const [deadlines, setDeadlines] = useState<AnyRecord[]>([]);
  const [alerts, setAlerts] = useState<AnyRecord[]>([]);
  const [executiveReport, setExecutiveReport] = useState<AnyRecord | null>(null);

  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [selectedApplicationId, setSelectedApplicationId] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState("");

  const [matchingResults, setMatchingResults] = useState<AnyRecord[]>([]);
  const [scoringResult, setScoringResult] = useState<AnyRecord | null>(null);
  const [consortiumResult, setConsortiumResult] = useState<AnyRecord | null>(null);
  const [partners, setPartners] = useState<AnyRecord[]>([]);
  const [shortlist, setShortlist] = useState<AnyRecord[]>([]);
  const [outreachMessages, setOutreachMessages] = useState<AnyRecord[]>([]);
  const [applicationDetail, setApplicationDetail] = useState<AnyRecord | null>(null);
  const [applicationDocuments, setApplicationDocuments] = useState<AnyRecord | null>(null);
  const [submissionSessions, setSubmissionSessions] = useState<AnyRecord[]>([]);
  const [submissionApprovals, setSubmissionApprovals] = useState<AnyRecord[]>([]);
  const [submissionReceipt, setSubmissionReceipt] = useState<AnyRecord | null>(null);
  const [ideaGateMessage, setIdeaGateMessage] = useState("");

  const [documentForm, setDocumentForm] = useState({ document_type: "financial_statement", filename: "", storage_path: "" });
  const [programmeForm, setProgrammeForm] = useState({ name: "", institution: "", country: "Poland", funding_type: "grant", summary: "" });
  const [callForm, setCallForm] = useState({
    programme_id: "",
    title: "",
    code: "",
    country: "Poland",
    portal_url: "",
    closes_at: "",
    min_project_budget: "500000",
    max_project_budget: "2500000",
    grant_intensity_pct: "60",
    trl_min: "4",
    trl_max: "8",
    target_beneficiaries: "MŚP, mid-cap",
    themes: "AI, automatyzacja, efektywność energetyczna",
    required_documents: "sprawozdanie_finansowe, zaświadczenie_US, zaświadczenie_ZUS, odpis_KRS",
    required_partner_types: "jednostka_badawcza",
    eligible_costs: "personel, sprzęt, podwykonawstwo",
  });
  const [callSearch, setCallSearch] = useState("kryptografia kwantowa AI");
  const [selectedCallCandidateId, setSelectedCallCandidateId] = useState("");
  const [rejectedCallCandidateIds, setRejectedCallCandidateIds] = useState<string[]>([]);
  const [partnerForm, setPartnerForm] = useState({
    name: "",
    partner_type: "research_institute",
    country: "Polska",
    expertise: "",
    grant_track_record: "3",
    contact_email: "",
  });
  const [portalUrl, setPortalUrl] = useState("https://portal.example.test/submission");
  const [approvalNotes, setApprovalNotes] = useState("Finalny przegląd prawny zakończony");
  const [approvedBy, setApprovedBy] = useState("operator@example.com");
  const [submissionReference, setSubmissionReference] = useState("");

  const applyProfile = useCallback((profile: AnyRecord | null) => {
    if (!profile) {
      setProfileForm(EMPTY_PROFILE);
      return;
    }
    setProfileForm({
      legal_name: profile.legal_name ?? "",
      tax_id: profile.tax_id ?? "",
      registration_id: profile.registration_id ?? "",
      country: profile.country ?? "Poland",
      region: profile.region ?? "",
      city: profile.city ?? "",
      legal_form: profile.legal_form ?? "",
      sme_status: profile.sme_status ?? "SME",
      employees: String(profile.employees ?? ""),
      annual_revenue: String(profile.annual_revenue ?? ""),
      ebitda: String(profile.ebitda ?? ""),
      technologies: toCsv(profile.technologies),
      products: toCsv(profile.products),
      services: toCsv(profile.services),
      team_competencies: toCsv(profile.team_competencies),
      strategic_goals: toCsv(profile.strategic_goals),
      representative_name: profile.representative_name ?? "",
      representative_email: profile.representative_email ?? "",
      export_markets: toCsv(profile.export_markets),
    });
  }, []);

  const loadProjectWorkspace = useCallback(async (projectId: string) => {
    if (!projectId) {
      setMatchingResults([]);
      setScoringResult(null);
      setConsortiumResult(null);
      setPartners([]);
      setShortlist([]);
      setOutreachMessages([]);
      return;
    }
    try {
      const [matches, scoring, consortium] = await Promise.all([
        api.getFundingMatchingResults(projectId).catch(() => ({ matches: [] })),
        api.getFundingScoring(projectId).catch(() => null),
        api.analyzeFundingConsortium({ project_id: projectId }).catch(() => null),
      ]);
      setMatchingResults((matches as AnyRecord).matches ?? []);
      setScoringResult(scoring as AnyRecord | null);
      setConsortiumResult(consortium as AnyRecord | null);
      const partnerResults = await api.searchFundingPartners({ project_id: projectId, company_id: COMPANY_ID, candidates: [] }).catch(() => ({ partners: [] }));
      setPartners((partnerResults as AnyRecord).partners ?? []);
    } catch (exc) {
      setError(String(exc));
    }
  }, []);

  const loadApplicationWorkspace = useCallback(async (applicationId: string) => {
    if (!applicationId) {
      setApplicationDetail(null);
      setApplicationDocuments(null);
      setSubmissionSessions([]);
      setSubmissionApprovals([]);
      setSubmissionReceipt(null);
      setSelectedSessionId("");
      return;
    }
    try {
      setApplicationDetail(null);
      setApplicationDocuments(null);
      setSubmissionSessions([]);
      setSubmissionApprovals([]);
      setSubmissionReceipt(null);
      const [detail, docs, sessions, approvals] = await Promise.all([
        api.getFundingApplication(applicationId).catch(() => null),
        api.getFundingApplicationDocuments(applicationId).catch(() => null),
        api.listFundingSubmissionSessions(applicationId).catch(() => ({ sessions: [] })),
        api.listFundingSubmissionApprovals(applicationId).catch(() => ({ approvals: [] })),
      ]);
      setApplicationDetail(detail as AnyRecord | null);
      setApplicationDocuments(docs as AnyRecord | null);
      const sessionItems = ((sessions as AnyRecord).sessions ?? []) as AnyRecord[];
      setSubmissionSessions(sessionItems);
      setSubmissionApprovals(((approvals as AnyRecord).approvals ?? []) as AnyRecord[]);
      const nextSessionId = sessionItems.some((item) => item.session_id === selectedSessionId)
        ? selectedSessionId
        : sessionItems[0]?.session_id || "";
      setSelectedSessionId(nextSessionId);
      if (nextSessionId) {
        const receipt = await api.getFundingSubmissionReceipt(nextSessionId).catch(() => null);
        const receiptPayload = (receipt as AnyRecord)?.receipt;
        setSubmissionReceipt(hasRecordPayload(receiptPayload) ? receiptPayload : null);
      } else {
        setSubmissionReceipt(null);
      }
    } catch (exc) {
      setError(String(exc));
    }
  }, [selectedSessionId]);

  const loadAll = useCallback(async () => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    try {
      const [
        profileResult,
        readinessResult,
        documentsResult,
        stateAidResult,
        registryResult,
        sourcesResult,
        programmesResult,
        callsResult,
        ideasResult,
        projectsResult,
        applicationsResult,
        deadlinesResult,
        alertsResult,
        reportResult,
      ] = await Promise.allSettled([
        api.getFundingCompanyProfile(COMPANY_ID),
        api.getFundingCompanyReadiness(COMPANY_ID),
        api.listFundingCompanyDocuments(COMPANY_ID),
        api.getFundingStateAid(COMPANY_ID),
        api.getFundingCompanyRegistrySync(COMPANY_ID),
        api.listFundingSources(),
        api.listFundingProgrammes(),
        api.listFundingCalls(),
        api.listFundingIdeas(COMPANY_ID),
        api.listFundingProjects(COMPANY_ID),
        api.listFundingCrmApplications(COMPANY_ID),
        api.listFundingDeadlines(COMPANY_ID),
        api.listFundingAlerts(COMPANY_ID),
        api.getFundingExecutiveReport(COMPANY_ID),
      ]);

      applyProfile(profileResult.status === "fulfilled" ? (profileResult.value as AnyRecord) : null);
      setProfileReadiness(readinessResult.status === "fulfilled" ? (readinessResult.value as AnyRecord) : null);
      setDocuments(documentsResult.status === "fulfilled" ? (((documentsResult.value as AnyRecord).documents ?? []) as AnyRecord[]) : []);
      setStateAid(stateAidResult.status === "fulfilled" ? (stateAidResult.value as AnyRecord) : null);
      const loadedRegistry = registryResult.status === "fulfilled" ? ((registryResult.value as AnyRecord).registry_sync ?? null) : null;
      setRegistrySync(loadedRegistry);
      if (!registryKrs && loadedRegistry?.krs) {
        setRegistryKrs(String(loadedRegistry.krs));
      }
      setSources(sourcesResult.status === "fulfilled" ? (((sourcesResult.value as AnyRecord).sources ?? []) as AnyRecord[]) : []);
      const loadedProgrammes = programmesResult.status === "fulfilled" ? (((programmesResult.value as AnyRecord).programmes ?? []) as AnyRecord[]) : [];
      setProgrammes(loadedProgrammes);
      const loadedCalls = callsResult.status === "fulfilled" ? (((callsResult.value as AnyRecord).calls ?? []) as AnyRecord[]) : [];
      setCalls(loadedCalls);
      setIdeas(ideasResult.status === "fulfilled" ? (((ideasResult.value as AnyRecord).ideas ?? []) as AnyRecord[]) : []);
      const loadedProjects = projectsResult.status === "fulfilled" ? (((projectsResult.value as AnyRecord).projects ?? []) as AnyRecord[]) : [];
      setProjects(loadedProjects);
      const loadedApplications = applicationsResult.status === "fulfilled" ? (((applicationsResult.value as AnyRecord).applications ?? []) as AnyRecord[]) : [];
      setApplications(loadedApplications);
      setDeadlines(deadlinesResult.status === "fulfilled" ? (((deadlinesResult.value as AnyRecord).deadlines ?? []) as AnyRecord[]) : []);
      setAlerts(alertsResult.status === "fulfilled" ? (((alertsResult.value as AnyRecord).alerts ?? []) as AnyRecord[]) : []);
      setExecutiveReport(reportResult.status === "fulfilled" ? (reportResult.value as AnyRecord) : null);

      if (!callForm.programme_id && loadedProgrammes[0]?.programme_id) {
        setCallForm((prev) => ({ ...prev, programme_id: loadedProgrammes[0].programme_id }));
      }
      if (!selectedProjectId && loadedProjects[0]?.project_id) {
        setSelectedProjectId(loadedProjects[0].project_id);
      }
      if (!selectedApplicationId && loadedApplications[0]?.application_id) {
        setSelectedApplicationId(loadedApplications[0].application_id);
      }
      setLastUpdated(Date.now());
    } finally {
      setLoading(false);
    }
  }, [applyProfile, backendLive, callForm.programme_id, registryKrs, selectedApplicationId, selectedProjectId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadAll();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadAll]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadProjectWorkspace(selectedProjectId);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadProjectWorkspace, selectedProjectId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadApplicationWorkspace(selectedApplicationId);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadApplicationWorkspace, selectedApplicationId]);

  const activeProject = useMemo(
    () => projects.find((item) => item.project_id === selectedProjectId) ?? null,
    [projects, selectedProjectId]
  );
  const activeApplication = useMemo(
    () => applications.find((item) => item.application_id === selectedApplicationId) ?? null,
    [applications, selectedApplicationId]
  );
  const activeSession = useMemo(
    () => submissionSessions.find((item) => item.session_id === selectedSessionId) ?? submissionSessions[0] ?? null,
    [selectedSessionId, submissionSessions]
  );
  const activeSessionValidation = useMemo(
    () => ((activeSession?.validation_json ?? activeSession?.validation ?? {}) as AnyRecord),
    [activeSession]
  );
  const submissionMissingDocuments = useMemo(
    () => (Array.isArray(activeSessionValidation.missing_documents) ? (activeSessionValidation.missing_documents as string[]) : []),
    [activeSessionValidation]
  );
  const submissionReviewReadiness = useMemo(
    () => String(activeSessionValidation.review_readiness ?? "not_reviewed"),
    [activeSessionValidation]
  );
  const latestSessionApproval = useMemo(
    () => submissionApprovals.find((item) => item.session_id === selectedSessionId) ?? null,
    [selectedSessionId, submissionApprovals]
  );
  const latestSessionApprovalPayload = useMemo(
    () => ((latestSessionApproval?.payload_json ?? latestSessionApproval?.payload ?? {}) as AnyRecord),
    [latestSessionApproval]
  );
  const latestSessionGovernanceTicketId = String(latestSessionApprovalPayload.governance_ticket_id ?? "");
  const submissionGateReasons = useMemo(() => {
    const reasons: string[] = [];
    if (submissionMissingDocuments.length > 0) {
      reasons.push(`Brakujące dokumenty: ${submissionMissingDocuments.join(", ")}`);
    }
    if (submissionReviewReadiness !== "ready") {
      reasons.push(`Gotowość przeglądu wniosku: ${submissionReviewReadiness}`);
    }
    return reasons;
  }, [submissionMissingDocuments, submissionReviewReadiness]);
  const canRequestApproval = Boolean(
    selectedSessionId &&
      submissionGateReasons.length === 0 &&
      latestSessionApproval?.status !== "pending" &&
      busyAction !== "request-approval"
  );
  const canSubmit = Boolean(
    selectedSessionId &&
      submissionGateReasons.length === 0 &&
      latestSessionApproval?.status === "pending" &&
      submissionReference.trim() &&
      busyAction !== "submit-application"
  );

  const runAction = useCallback(async (label: string, fn: () => Promise<void>) => {
    setBusyAction(label);
    setError(null);
    try {
      await fn();
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusyAction(null);
    }
  }, []);

  const handleRegistrySync = useCallback(async () => {
    await runAction("registry-sync", async () => {
      const response = await api.syncFundingCompanyRegistry({
        company_id: COMPANY_ID,
        krs: registryKrs,
        apply_profile: true,
      });
      const data = response as AnyRecord;
      setRegistrySync(data.registry_sync ?? null);
      setRegistryMessage(`KRS ${data.registry_sync?.krs ?? registryKrs} pobrany i zastosowany do profilu firmy.`);
      if (data.company_profile) {
        applyProfile(data.company_profile as AnyRecord);
      }
      await loadAll();
    });
  }, [applyProfile, loadAll, registryKrs, runAction]);

  const handleSaveProfile = useCallback(async () => {
    await runAction("save-profile", async () => {
      await api.saveFundingCompanyProfile({
        company_id: COMPANY_ID,
        legal_name: profileForm.legal_name,
        tax_id: profileForm.tax_id,
        registration_id: profileForm.registration_id,
        country: profileForm.country,
        region: profileForm.region,
        city: profileForm.city,
        legal_form: profileForm.legal_form,
        sme_status: profileForm.sme_status,
        employees: Number(profileForm.employees || 0),
        annual_revenue: Number(profileForm.annual_revenue || 0),
        ebitda: Number(profileForm.ebitda || 0),
        technologies: splitCsv(profileForm.technologies),
        products: splitCsv(profileForm.products),
        services: splitCsv(profileForm.services),
        team_competencies: splitCsv(profileForm.team_competencies),
        strategic_goals: splitCsv(profileForm.strategic_goals),
        representative_name: profileForm.representative_name,
        representative_email: profileForm.representative_email,
        export_markets: splitCsv(profileForm.export_markets),
      });
      await loadAll();
    });
  }, [loadAll, profileForm, runAction]);

  const handleAddDocument = useCallback(async () => {
    await runAction("add-document", async () => {
      await api.addFundingCompanyDocument({
        company_id: COMPANY_ID,
        document_type: documentForm.document_type,
        filename: documentForm.filename,
        storage_path: documentForm.storage_path,
      });
      setDocumentForm({ document_type: "financial_statement", filename: "", storage_path: "" });
      await loadAll();
    });
  }, [documentForm, loadAll, runAction]);

  const handleCreateProgramme = useCallback(async () => {
    await runAction("create-programme", async () => {
      await api.createFundingProgramme(programmeForm);
      setProgrammeForm({ name: "", institution: "", country: "Poland", funding_type: "grant", summary: "" });
      await loadAll();
    });
  }, [loadAll, programmeForm, runAction]);

  const handleCreateCall = useCallback(async () => {
    await runAction("create-call", async () => {
      await api.createFundingCall({
        programme_id: callForm.programme_id,
        title: callForm.title,
        code: callForm.code,
        country: callForm.country,
        portal_url: callForm.portal_url,
        closes_at: toEpoch(callForm.closes_at),
        min_project_budget: Number(callForm.min_project_budget || 0),
        max_project_budget: Number(callForm.max_project_budget || 0),
        grant_intensity_pct: Number(callForm.grant_intensity_pct || 0),
        trl_min: Number(callForm.trl_min || 0),
        trl_max: Number(callForm.trl_max || 9),
        target_beneficiaries: splitCsv(callForm.target_beneficiaries),
        themes: splitCsv(callForm.themes),
        required_documents: splitCsv(callForm.required_documents),
        required_partner_types: splitCsv(callForm.required_partner_types),
        eligible_costs: splitCsv(callForm.eligible_costs),
      });
      setCallForm((prev) => ({
        ...prev,
        title: "",
        code: "",
        portal_url: "",
      }));
      await loadAll();
    });
  }, [callForm, loadAll, runAction]);

  const handleScanSources = useCallback(async () => {
    await runAction("scan-sources", async () => {
      await api.triggerFundingScan({ force_refresh: true, since_days: 180 });
      await loadAll();
    });
  }, [loadAll, runAction]);

  const handleSearchCalls = useCallback(async () => {
    await runAction("search-calls", async () => {
      const response = await api.searchFundingCalls({
        company_id: COMPANY_ID,
        query: callSearch,
        beneficiary_type: profileForm.sme_status.toLowerCase(),
      });
      setCalls(((response as AnyRecord).calls ?? []) as AnyRecord[]);
      setSelectedCallCandidateId("");
      setRejectedCallCandidateIds([]);
    });
  }, [callSearch, profileForm.sme_status, runAction]);

  const handleGenerateIdeas = useCallback(async () => {
    await runAction("generate-ideas", async () => {
      const response = await api.generateFundingIdeas({ company_id: COMPANY_ID, limit: 5 });
      setIdeas(((response as AnyRecord).ideas ?? []) as AnyRecord[]);
      await loadAll();
    });
  }, [loadAll, runAction]);

  const handleConvertIdea = useCallback(async (ideaId: string, callId?: string) => {
    await runAction(`convert-idea-${ideaId}`, async () => {
      const response = await api.convertFundingIdeaToProject(ideaId, { company_id: COMPANY_ID, call_id: callId || null, target_trl: 5 });
      const projectId = (response as AnyRecord).project?.project_id as string;
      const ticketId = (response as AnyRecord).governance_ticket_id as string;
      if ((response as AnyRecord).status === "pending_human_gate") {
        setIdeaGateMessage(`Konwersja czeka w Human Gate: ${ticketId}`);
      }
      await loadAll();
      if (projectId) {
        setSelectedProjectId(projectId);
      }
    });
  }, [loadAll, runAction]);

  const handleRunMatching = useCallback(async () => {
    if (!selectedProjectId) return;
    await runAction("run-matching", async () => {
      const response = await api.runFundingMatching({ project_id: selectedProjectId, top_k: 5 });
      setMatchingResults(((response as AnyRecord).matches ?? []) as AnyRecord[]);
      const scoring = await api.getFundingScoring(selectedProjectId);
      setScoringResult(scoring as AnyRecord);
      const consortium = await api.analyzeFundingConsortium({ project_id: selectedProjectId });
      setConsortiumResult(consortium as AnyRecord);
      await loadAll();
    });
  }, [loadAll, runAction, selectedProjectId]);

  const handleAddPartner = useCallback(async () => {
    if (!selectedProjectId) return;
    await runAction("add-partner", async () => {
      const response = await api.searchFundingPartners({
        project_id: selectedProjectId,
        company_id: COMPANY_ID,
        candidates: [
          {
            name: partnerForm.name,
            partner_type: partnerForm.partner_type,
            country: partnerForm.country,
            expertise: splitCsv(partnerForm.expertise),
            grant_track_record: Number(partnerForm.grant_track_record || 0),
            contact_email: partnerForm.contact_email,
          },
        ],
      });
      setPartners(((response as AnyRecord).partners ?? []) as AnyRecord[]);
      setPartnerForm({ name: "", partner_type: "research_institute", country: "Polska", expertise: "", grant_track_record: "3", contact_email: "" });
    });
  }, [partnerForm, runAction, selectedProjectId]);

  const handleShortlistPartners = useCallback(async () => {
    if (!selectedProjectId) return;
    await runAction("shortlist-partners", async () => {
      const response = await api.shortlistFundingPartners({ project_id: selectedProjectId, limit: 5 });
      setShortlist(((response as AnyRecord).shortlist ?? []) as AnyRecord[]);
    });
  }, [runAction, selectedProjectId]);

  const handleGenerateOutreach = useCallback(async () => {
    if (!selectedProjectId) return;
    const partnerIds = (shortlist.length > 0 ? shortlist : partners).slice(0, 3).map((item) => item.partner_id);
    if (partnerIds.length === 0) return;
    await runAction("generate-outreach", async () => {
      const response = await api.generateFundingOutreach({ project_id: selectedProjectId, partner_ids: partnerIds });
      setOutreachMessages(((response as AnyRecord).messages ?? []) as AnyRecord[]);
    });
  }, [partners, runAction, selectedProjectId, shortlist]);

  const handleCreateApplication = useCallback(async () => {
    if (!selectedProjectId) return;
    await runAction("create-application", async () => {
      const callId = matchingResults[0]?.call_id ?? activeProject?.call_id ?? null;
      const response = await api.createFundingApplication({ project_id: selectedProjectId, company_id: COMPANY_ID, call_id: callId });
      const applicationId = (response as AnyRecord).application_id as string;
      await loadAll();
      setSelectedApplicationId(applicationId);
    });
  }, [activeProject?.call_id, loadAll, matchingResults, runAction, selectedProjectId]);

  const handleReviewApplication = useCallback(async () => {
    if (!selectedApplicationId) return;
    await runAction("review-application", async () => {
      await api.reviewFundingApplication(selectedApplicationId, { review_modes: ["formal", "financial", "technical", "market"] });
      await loadApplicationWorkspace(selectedApplicationId);
      await loadAll();
    });
  }, [loadAll, loadApplicationWorkspace, runAction, selectedApplicationId]);

  const handleExportApplication = useCallback(async () => {
    if (!selectedApplicationId) return;
    await runAction("export-application", async () => {
      await api.exportFundingApplication(selectedApplicationId);
      await loadApplicationWorkspace(selectedApplicationId);
    });
  }, [loadApplicationWorkspace, runAction, selectedApplicationId]);

  const handlePrepareSubmission = useCallback(async () => {
    if (!selectedApplicationId) return;
    await runAction("prepare-submission", async () => {
      const response = await api.prepareFundingSubmission({ application_id: selectedApplicationId, portal_url: portalUrl });
      const sessionId = (response as AnyRecord).session_id as string;
      await loadApplicationWorkspace(selectedApplicationId);
      setSelectedSessionId(sessionId);
    });
  }, [loadApplicationWorkspace, portalUrl, runAction, selectedApplicationId]);

  const handleFillSubmission = useCallback(async () => {
    if (!selectedSessionId) return;
    await runAction("fill-submission", async () => {
      await api.fillFundingSubmission({ session_id: selectedSessionId });
      await loadApplicationWorkspace(selectedApplicationId);
    });
  }, [loadApplicationWorkspace, runAction, selectedApplicationId, selectedSessionId]);

  const handleSaveDraft = useCallback(async () => {
    if (!selectedSessionId) return;
    await runAction("save-draft", async () => {
      await api.saveFundingSubmissionDraft({ session_id: selectedSessionId });
      await loadApplicationWorkspace(selectedApplicationId);
    });
  }, [loadApplicationWorkspace, runAction, selectedApplicationId, selectedSessionId]);

  const handleRequestApproval = useCallback(async () => {
    if (!selectedSessionId) return;
    await runAction("request-approval", async () => {
      await api.requestFundingSubmissionApproval({ session_id: selectedSessionId, notes: approvalNotes });
      await loadApplicationWorkspace(selectedApplicationId);
    });
  }, [approvalNotes, loadApplicationWorkspace, runAction, selectedApplicationId, selectedSessionId]);

  const handleSubmit = useCallback(async () => {
    if (!selectedSessionId) return;
    await runAction("submit-application", async () => {
      await api.submitFundingApplication({
        session_id: selectedSessionId,
        approved_by: approvedBy,
        confirm_legal: true,
        confirm_budget: true,
        confirm_documents: true,
        portal_submission_reference: submissionReference,
      });
      await loadApplicationWorkspace(selectedApplicationId);
      await loadAll();
    });
  }, [approvedBy, loadAll, loadApplicationWorkspace, runAction, selectedApplicationId, selectedSessionId, submissionReference]);

  if (!backendLive) {
    return (
      <div className="flex h-full min-h-[60vh] items-center justify-center">
        <Card className="max-w-xl p-6 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
          <p className="text-sm font-medium">Backend niedostępny</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Autopilot finansowania wymaga backendu AEIS do pobrania danych firmy, naborów, oceny i procesu składania.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-primary">
            <Landmark className="w-3.5 h-3.5" />
            Autopilot finansowania
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">
            Finansowanie
            <HelpTip text="Granty, dotacje, finansowanie projektów. Auto-matching pomysłów do otwartych call'ów; auto-generowanie wniosków z masterplanu projektu. Pełen pipeline: profil firmy, nabory, pomysły, dopasowanie, ocena, wniosek, bramka zatwierdzenia, złożenie." />
          </h1>
          <p className="mt-2 max-w-4xl text-sm text-muted-foreground">
            Ten kokpit obsługuje rzeczywisty workflow finansowania: gotowość profilu, ewidencję naborów, generowanie pomysłów, dopasowanie, ocenę, budowę pakietu wniosku, kontrolę dokumentów, przygotowanie konsorcjum oraz złożenie zatwierdzone przez człowieka.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated !== null && <Badge variant="outline" className="text-[10px]">Aktualizacja {fmtEpoch(lastUpdated)}</Badge>}
          <Button variant="outline" size="sm" onClick={() => void loadAll()} disabled={loading}>
            {loading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
            Odśwież
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-sylion-red/30 bg-sylion-red/10 p-3 text-sm text-sylion-red">
          {error}
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Building2} label="Gotowość" value={`${Math.round(profileReadiness?.readiness_score ?? 0)}%`} hint={`${profileReadiness?.missing_fields?.length ?? 0} brakujących pól profilu`} accent="#17C964" />
        <MetricCard icon={Target} label="Nabory" value={String(calls.length)} hint={`${ideas.length} wygenerowanych pomysłów`} accent="#2F6BFF" />
        <MetricCard icon={FolderKanban} label="Wnioski" value={String(applications.length)} hint={`${submissionSessions.length} sesji składania`} accent="#F59E0B" />
        <MetricCard icon={AlertTriangle} label="Alerty" value={String(alerts.length)} hint={`${deadlines.length} śledzonych terminów`} accent="#F31260" />
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as FundingTab)}
        className="space-y-4"
      >
        <HelpTip text="Firma: profil i dokumenty. Nabory: ewidencja open-call. Pomysły: wygenerowane idee projektowe. Dopasowanie: matching pomysłów do naborów. Wnioski: pakiety aplikacji. Złożenie i CRM: bramka zatwierdzenia + składanie. Raporty: wykresy, eksporty i powiadomienia." />
        <TabsList className="flex h-auto w-full items-center gap-1 overflow-x-auto rounded-lg bg-[#0f1629] p-1">
          <TabsTrigger value="company" className="min-w-[132px] justify-center gap-2 px-3 py-2 text-sm">
            <Building2 className="h-3.5 w-3.5" />
            Firma
          </TabsTrigger>
          <TabsTrigger value="calls" className="min-w-[132px] justify-center gap-2 px-3 py-2 text-sm">
            <Landmark className="h-3.5 w-3.5" />
            Nabory
          </TabsTrigger>
          <TabsTrigger value="ideas" className="min-w-[132px] justify-center gap-2 px-3 py-2 text-sm">
            <Sparkles className="h-3.5 w-3.5" />
            Pomysły
          </TabsTrigger>
          <TabsTrigger value="matching" className="min-w-[132px] justify-center gap-2 px-3 py-2 text-sm">
            <Target className="h-3.5 w-3.5" />
            Dopasowanie
          </TabsTrigger>
          <TabsTrigger value="applications" className="min-w-[132px] justify-center gap-2 px-3 py-2 text-sm">
            <FileText className="h-3.5 w-3.5" />
            Wnioski
          </TabsTrigger>
          <TabsTrigger value="submission" className="min-w-[148px] justify-center gap-2 px-3 py-2 text-sm">
            <Send className="h-3.5 w-3.5" />
            Złożenie i CRM
          </TabsTrigger>
          <TabsTrigger value="reporting" className="min-w-[132px] justify-center gap-2 px-3 py-2 text-sm">
            <FileText className="h-3.5 w-3.5" />
            Raporty
          </TabsTrigger>
        </TabsList>

        <TabsContent value="company" className="space-y-4">
          <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="max-w-2xl">
                <div className="flex items-center gap-2">
                  <Landmark className="h-4 w-4 text-primary" />
                  <h2 className="text-lg font-semibold">
                    KRS, RDF i dokumenty finansowe
                    <HelpTip text="Pobranie aktualnego odpisu z oficjalnego API KRS Ministerstwa Sprawiedliwości. Historia złożonych sprawozdań finansowych jest czytana z działu 3 odpisu KRS i linkowana do RDF/MSiG do dalszej analizy dokumentów." />
                  </h2>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Wpisz KRS, a system uzupełni dane rejestrowe profilu i pokaże sygnały z historii sprawozdań finansowych.
                </p>
              </div>
              <div className="flex w-full flex-col gap-2 sm:flex-row lg:max-w-md">
                <Input value={registryKrs} onChange={setRegistryKrs} placeholder="Numer KRS, np. 0000123343" />
                <Button onClick={() => void handleRegistrySync()} disabled={!registryKrs.trim() || busyAction === "registry-sync"}>
                  {busyAction === "registry-sync" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Landmark className="w-3.5 h-3.5 mr-1.5" />}
                  Pobierz z KRS
                </Button>
              </div>
            </div>
            {(registryMessage || registrySync) && (
              <div className="mt-4 grid gap-4 lg:grid-cols-[1fr,1fr]">
                <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{registrySync?.source ?? "KRS"}</Badge>
                    {registrySync?.krs && <Badge variant="outline">KRS {registrySync.krs}</Badge>}
                    {registrySync?.registry_state_date && <Badge variant="outline">Stan {registrySync.registry_state_date}</Badge>}
                  </div>
                  {registryMessage && <p className="mt-3 text-sylion-green">{registryMessage}</p>}
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    {registrySync?.source_url && (
                      <a className="text-primary hover:underline" href={registrySync.source_url} target="_blank" rel="noreferrer">Odpis KRS JSON</a>
                    )}
                    {registrySync?.rdf_search_url && (
                      <a className="text-primary hover:underline" href={registrySync.rdf_search_url} target="_blank" rel="noreferrer">Przeglądarka RDF</a>
                    )}
                    {registrySync?.imsig_reports_url && (
                      <a className="text-primary hover:underline" href={registrySync.imsig_reports_url} target="_blank" rel="noreferrer">MSiG sprawozdania</a>
                    )}
                  </div>
                </div>
                <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4 text-sm">
                  <p className="font-semibold">Ostatnie wzmianki o sprawozdaniach</p>
                  <div className="mt-3 space-y-2">
                    {(registrySync?.financial_filings ?? []).length === 0 ? (
                      <p className="text-muted-foreground">Brak pobranej historii sprawozdań.</p>
                    ) : (
                      (registrySync?.financial_filings ?? []).map((item: AnyRecord, index: number) => (
                        <div key={`${item.filed_at}-${index}`} className="flex items-center justify-between gap-3 rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-2 text-xs">
                          <span>{item.period || "okres n/a"}</span>
                          <Badge variant="outline">{item.filed_at || "data n/a"}</Badge>
                        </div>
                      ))
                    )}
                  </div>
                  {(registrySync?.risk_flags ?? []).length > 0 && (
                    <div className="mt-3 space-y-1 text-xs text-sylion-amber">
                      {(registrySync?.risk_flags ?? []).map((item: string) => <p key={item}>- {item}</p>)}
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>
          <div className="grid gap-4 xl:grid-cols-[1.5fr,0.9fr]">
            <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">
                    Profil mojej firmy
                    <HelpTip text="Dane prawne, finansowe i kompetencyjne firmy. Wymagane przed dopasowaniem do naborów i generowaniem wniosków." />
                  </h2>
                  <p className="text-sm text-muted-foreground">Podstawowy profil grantowy używany do kwalifikowalności, scoringu i generowania pakietu.</p>
                </div>
                <Button size="sm" onClick={() => void handleSaveProfile()} disabled={busyAction === "save-profile"}>
                  {busyAction === "save-profile" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <BriefcaseBusiness className="w-3.5 h-3.5 mr-1.5" />}
                  Zapisz profil
                </Button>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Input value={profileForm.legal_name} onChange={(value) => setProfileForm((prev) => ({ ...prev, legal_name: value }))} placeholder="Pełna nazwa firmy" />
                <Input value={profileForm.tax_id} onChange={(value) => setProfileForm((prev) => ({ ...prev, tax_id: value }))} placeholder="NIP" />
                <Input value={profileForm.registration_id} onChange={(value) => setProfileForm((prev) => ({ ...prev, registration_id: value }))} placeholder="KRS / CEIDG" />
                <Input value={profileForm.legal_form} onChange={(value) => setProfileForm((prev) => ({ ...prev, legal_form: value }))} placeholder="Forma prawna" />
                <Input value={profileForm.country} onChange={(value) => setProfileForm((prev) => ({ ...prev, country: value }))} placeholder="Kraj" />
                <Input value={profileForm.region} onChange={(value) => setProfileForm((prev) => ({ ...prev, region: value }))} placeholder="Region" />
                <Input value={profileForm.city} onChange={(value) => setProfileForm((prev) => ({ ...prev, city: value }))} placeholder="Miasto" />
                <Input value={profileForm.sme_status} onChange={(value) => setProfileForm((prev) => ({ ...prev, sme_status: value }))} placeholder="MŚP / duża firma" />
                <Input value={profileForm.employees} onChange={(value) => setProfileForm((prev) => ({ ...prev, employees: value }))} placeholder="Liczba pracowników" type="number" />
                <Input value={profileForm.annual_revenue} onChange={(value) => setProfileForm((prev) => ({ ...prev, annual_revenue: value }))} placeholder="Roczny przychód" type="number" />
                <Input value={profileForm.ebitda} onChange={(value) => setProfileForm((prev) => ({ ...prev, ebitda: value }))} placeholder="EBITDA" type="number" />
                <Input value={profileForm.export_markets} onChange={(value) => setProfileForm((prev) => ({ ...prev, export_markets: value }))} placeholder="Rynki eksportowe, po przecinku" />
                <TextArea value={profileForm.technologies} onChange={(value) => setProfileForm((prev) => ({ ...prev, technologies: value }))} placeholder="Technologie, po przecinku" rows={3} />
                <TextArea value={profileForm.products} onChange={(value) => setProfileForm((prev) => ({ ...prev, products: value }))} placeholder="Produkty, po przecinku" rows={3} />
                <TextArea value={profileForm.services} onChange={(value) => setProfileForm((prev) => ({ ...prev, services: value }))} placeholder="Usługi, po przecinku" rows={3} />
                <TextArea value={profileForm.team_competencies} onChange={(value) => setProfileForm((prev) => ({ ...prev, team_competencies: value }))} placeholder="Kompetencje zespołu, po przecinku" rows={3} />
                <TextArea value={profileForm.strategic_goals} onChange={(value) => setProfileForm((prev) => ({ ...prev, strategic_goals: value }))} placeholder="Cele strategiczne, po przecinku" rows={3} />
                <Input value={profileForm.representative_name} onChange={(value) => setProfileForm((prev) => ({ ...prev, representative_name: value }))} placeholder="Imię i nazwisko reprezentanta" />
                <Input value={profileForm.representative_email} onChange={(value) => setProfileForm((prev) => ({ ...prev, representative_email: value }))} placeholder="E-mail reprezentanta" />
              </div>
            </Card>

            <div className="space-y-4">
              <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold">Gotowość firmy</h3>
                    <p className="text-xs text-muted-foreground">Brakujące pola i dokumenty realnie wpływają na wynik gotowości.</p>
                  </div>
                  <Badge variant="outline">{Math.round(profileReadiness?.readiness_score ?? 0)}%</Badge>
                </div>
                <Progress className="mt-4" value={profileReadiness?.readiness_score ?? 0} />
                <div className="mt-4 space-y-3 text-xs">
                  <div>
                    <p className="font-medium">Brakujące pola</p>
                    {(profileReadiness?.missing_fields ?? []).length === 0 ? (
                      <p className="text-muted-foreground">Brak krytycznych luk w profilu.</p>
                    ) : (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {(profileReadiness?.missing_fields ?? []).map((item: string) => <Badge key={item} variant="outline">{item}</Badge>)}
                      </div>
                    )}
                  </div>
                  <div>
                    <p className="font-medium">Brakujące dokumenty</p>
                    {(profileReadiness?.missing_documents ?? []).length === 0 ? (
                      <p className="text-muted-foreground">Podstawowe dokumenty są dostępne.</p>
                    ) : (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {(profileReadiness?.missing_documents ?? []).map((item: string) => <Badge key={item} variant="outline" className="border-sylion-red/30 text-sylion-red">{item}</Badge>)}
                      </div>
                    )}
                  </div>
                  {stateAid && (
                    <div className="rounded-lg border border-[rgba(148,163,184,0.08)] p-3">
                      <p className="font-medium">Ekspozycja na pomoc publiczną</p>
                      <p className="mt-1 text-muted-foreground">Pomoc publiczna: EUR {Number(stateAid.state_aid_total_eur ?? 0).toLocaleString()}</p>
                      <p className="text-muted-foreground">de minimis: EUR {Number(stateAid.de_minimis_total_eur ?? 0).toLocaleString()}</p>
                    </div>
                  )}
                </div>
              </Card>

              <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold">Sejf dokumentów</h3>
                    <p className="text-xs text-muted-foreground">Rejestruj dokumenty używane w kwalifikowalności i finalnym pakiecie wniosku.</p>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => void handleAddDocument()} disabled={busyAction === "add-document"}>
                    {busyAction === "add-document" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <FileText className="w-3.5 h-3.5 mr-1.5" />}
                    Dodaj dokument
                  </Button>
                </div>
                <div className="grid gap-2">
                  <Input value={documentForm.document_type} onChange={(value) => setDocumentForm((prev) => ({ ...prev, document_type: value }))} placeholder="Typ dokumentu" />
                  <Input value={documentForm.filename} onChange={(value) => setDocumentForm((prev) => ({ ...prev, filename: value }))} placeholder="Nazwa pliku" />
                  <Input value={documentForm.storage_path} onChange={(value) => setDocumentForm((prev) => ({ ...prev, storage_path: value }))} placeholder="Ścieżka zapisu" />
                </div>
                <div className="space-y-2">
                  {documents.length === 0 ? (
                    <p className="text-xs text-muted-foreground">Brak zarejestrowanych dokumentów.</p>
                  ) : (
                    documents.map((item) => (
                      <div key={item.document_id} className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-2 text-xs">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="font-medium">{item.document_type}</p>
                            <p className="text-muted-foreground">{item.filename}</p>
                          </div>
                          <Badge variant="outline">{item.status}</Badge>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="calls" className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[0.95fr,1.2fr]">
            <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">
                    Programmy i ewidencja naborów
                    <HelpTip text="Ewidencja programów grantowych i otwartych naborów. Wprowadzaj kody naborów, deadliny, budżety i wymagane dokumenty." />
                  </h2>
                  <p className="text-sm text-muted-foreground">Ręczne wprowadzanie jest realne i zapisuje dane w bazie wiedzy modułu.</p>
                </div>
                <Button variant="outline" onClick={() => void handleScanSources()} disabled={busyAction === "scan-sources"}>
                  {busyAction === "scan-sources" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
                  Skanuj źródła
                </Button>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Program</p>
                <Input value={programmeForm.name} onChange={(value) => setProgrammeForm((prev) => ({ ...prev, name: value }))} placeholder="Nazwa programu" />
                <Input value={programmeForm.institution} onChange={(value) => setProgrammeForm((prev) => ({ ...prev, institution: value }))} placeholder="Instytucja" />
                <Input value={programmeForm.country} onChange={(value) => setProgrammeForm((prev) => ({ ...prev, country: value }))} placeholder="Kraj" />
                <Input value={programmeForm.funding_type} onChange={(value) => setProgrammeForm((prev) => ({ ...prev, funding_type: value }))} placeholder="Typ finansowania" />
                <TextArea value={programmeForm.summary} onChange={(value) => setProgrammeForm((prev) => ({ ...prev, summary: value }))} placeholder="Opis programu" rows={3} />
                <Button className="w-full" onClick={() => void handleCreateProgramme()} disabled={busyAction === "create-programme"}>
                  {busyAction === "create-programme" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Building2 className="w-3.5 h-3.5 mr-1.5" />}
                  Utwórz program
                </Button>
              </div>

              <div className="space-y-2 border-t border-[rgba(148,163,184,0.08)] pt-4">
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Nabór</p>
                <select
                  value={callForm.programme_id}
                  onChange={(event) => setCallForm((prev) => ({ ...prev, programme_id: event.target.value }))}
                  className="w-full rounded-lg border border-[rgba(148,163,184,0.12)] bg-[#0a1020] px-3 py-2 text-sm"
                >
                  <option value="">Wybierz program</option>
                  {programmes.map((programme) => (
                    <option key={programme.programme_id} value={programme.programme_id}>{programme.name}</option>
                  ))}
                </select>
                <Input value={callForm.title} onChange={(value) => setCallForm((prev) => ({ ...prev, title: value }))} placeholder="Tytuł naboru" />
                <Input value={callForm.code} onChange={(value) => setCallForm((prev) => ({ ...prev, code: value }))} placeholder="Kod naboru" />
                <Input value={callForm.portal_url} onChange={(value) => setCallForm((prev) => ({ ...prev, portal_url: value }))} placeholder="Adres portalu" />
                <Input value={callForm.closes_at} onChange={(value) => setCallForm((prev) => ({ ...prev, closes_at: value }))} placeholder="Data zamknięcia (RRRR-MM-DD)" />
                <div className="grid gap-2 md:grid-cols-2">
                  <Input value={callForm.min_project_budget} onChange={(value) => setCallForm((prev) => ({ ...prev, min_project_budget: value }))} placeholder="Minimalny budżet" type="number" />
                  <Input value={callForm.max_project_budget} onChange={(value) => setCallForm((prev) => ({ ...prev, max_project_budget: value }))} placeholder="Maksymalny budżet" type="number" />
                </div>
                <div className="grid gap-2 md:grid-cols-3">
                  <Input value={callForm.grant_intensity_pct} onChange={(value) => setCallForm((prev) => ({ ...prev, grant_intensity_pct: value }))} placeholder="Poziom dotacji %" type="number" />
                  <Input value={callForm.trl_min} onChange={(value) => setCallForm((prev) => ({ ...prev, trl_min: value }))} placeholder="TRL min" type="number" />
                  <Input value={callForm.trl_max} onChange={(value) => setCallForm((prev) => ({ ...prev, trl_max: value }))} placeholder="TRL max" type="number" />
                </div>
                <TextArea value={callForm.target_beneficiaries} onChange={(value) => setCallForm((prev) => ({ ...prev, target_beneficiaries: value }))} placeholder="Beneficjenci, po przecinku" rows={2} />
                <TextArea value={callForm.themes} onChange={(value) => setCallForm((prev) => ({ ...prev, themes: value }))} placeholder="Tematy, po przecinku" rows={2} />
                <TextArea value={callForm.required_documents} onChange={(value) => setCallForm((prev) => ({ ...prev, required_documents: value }))} placeholder="Wymagane dokumenty, po przecinku" rows={2} />
                <TextArea value={callForm.required_partner_types} onChange={(value) => setCallForm((prev) => ({ ...prev, required_partner_types: value }))} placeholder="Wymagane typy partnerów, po przecinku" rows={2} />
                <Button className="w-full" onClick={() => void handleCreateCall()} disabled={busyAction === "create-call" || !callForm.programme_id}>
                  {busyAction === "create-call" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Landmark className="w-3.5 h-3.5 mr-1.5" />}
                  Utwórz nabór
                </Button>
              </div>
            </Card>

            <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">
                    Sugerowane granty
                    <HelpTip text="Granty rekomendowane na podstawie profilu firmy. Auto-generowane przez engine dopasowania." />
                  </h2>
                  <p className="text-sm text-muted-foreground">Przeszukuj aktualną bazę naborów z profilem firmy jako kontekstem.</p>
                </div>
                <div className="flex gap-2">
                  <Input value={callSearch} onChange={setCallSearch} placeholder="Szukaj naborów" />
                  <Button
                    variant="outline"
                    aria-label="Szukaj naborów"
                    title="Szukaj naborów"
                    onClick={() => void handleSearchCalls()}
                    disabled={busyAction === "search-calls"}
                  >
                    {busyAction === "search-calls" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                    <span className="sr-only">Szukaj naborów</span>
                  </Button>
                </div>
              </div>
              <div className="grid gap-3">
                {calls.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Brak naborów w bazie wiedzy.</p>
                ) : (
                  calls.map((call) => {
                    const programme = programmes.find((item) => item.programme_id === call.programme_id);
                    const source = sources.find((item) => item.source_id === programme?.source_id);
                    const portalUrl = String(call.portal_url || "");
                    const freshnessTs = Number(call.updated_at || call.created_at || 0);
                    const isSelectedCandidate = selectedCallCandidateId === call.call_id;
                    const isRejectedCandidate = rejectedCallCandidateIds.includes(String(call.call_id));
                    return (
                    <div key={call.call_id} className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div>
                          <p className="text-sm font-semibold">{call.title}</p>
                          <p className="text-xs text-muted-foreground">{call.code || call.call_id}</p>
                          <p className="mt-2 text-sm text-muted-foreground">{(call.themes_json ?? []).join(", ")}</p>
                          <div className="mt-3 grid gap-1 text-xs text-muted-foreground">
                            <p>Źródło: {source?.label || programme?.institution || programme?.name || call.programme_id || "n/a"}</p>
                            <p>
                              Portal: {portalUrl ? (
                                <a className="text-sylion-cyan underline-offset-2 hover:underline" href={portalUrl} target="_blank" rel="noreferrer">
                                  {portalUrl}
                                </a>
                              ) : "brak URL"}
                            </p>
                            <p>Sygnał aktualności: {freshnessTs ? fmtEpoch(freshnessTs) : "brak daty"}</p>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {isSelectedCandidate && <Badge variant="outline">Wybrany kandydat</Badge>}
                          {isRejectedCandidate && <Badge variant="destructive">Odrzucony ręcznie</Badge>}
                          {call.fit_hint !== undefined && <Badge variant="outline">Wstępne dopasowanie {Math.round(call.fit_hint)}%</Badge>}
                          <Badge variant="outline">Dotacja {Number(call.grant_intensity_pct ?? 0)}%</Badge>
                          <Badge variant="outline">Termin {fmtEpoch(call.closes_at)}</Badge>
                        </div>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setRejectedCallCandidateIds((prev) => Array.from(new Set([...prev, String(call.call_id)])));
                            if (selectedCallCandidateId === call.call_id) {
                              setSelectedCallCandidateId("");
                            }
                          }}
                        >
                          <AlertTriangle className="w-3.5 h-3.5 mr-1.5" />
                          Odrzuć wynik
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => {
                            setSelectedCallCandidateId(String(call.call_id));
                            setRejectedCallCandidateIds((prev) => prev.filter((item) => item !== String(call.call_id)));
                          }}
                        >
                          <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />
                          Wybierz kandydata
                        </Button>
                      </div>
                    </div>
                    );
                  })
                )}
              </div>
              {selectedCallCandidateId && (
                <div className="rounded-xl border border-[rgba(16,185,129,0.24)] bg-[rgba(16,185,129,0.08)] px-4 py-3 text-sm text-sylion-green">
                  Wybrany kandydat funding: {selectedCallCandidateId}. Złożenie lub eksport nadal wymaga osobnego HumanGate.
                </div>
              )}
              <div className="grid gap-3 md:grid-cols-3">
                {sources.map((source) => (
                  <div key={source.source_id} className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-3 text-xs">
                    <p className="font-medium">{source.label}</p>
                    <p className="mt-1 text-muted-foreground">{describeSourceMode(source)}</p>
                    <p className="mt-2 text-muted-foreground">{source.programmes} programów / {source.calls} naborów</p>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="ideas" className="space-y-4">
          <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">
                  Sugerowane pomysły projektów
                  <HelpTip text="Pomysły projektów wygenerowane przez AI na podstawie kompetencji firmy i otwartych naborów. Zaakceptowane idee przechodzą do faz dopasowania i wniosku." />
                </h2>
                <p className="text-sm text-muted-foreground">Generuj koncepcje projektów bezpośrednio z potencjału firmy i dostępnych naborów.</p>
              </div>
              <Button onClick={() => void handleGenerateIdeas()} disabled={busyAction === "generate-ideas"}>
                {busyAction === "generate-ideas" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
                    Generuj pomysły
              </Button>
            </div>
            <div className="grid gap-4 xl:grid-cols-2">
              {ideaGateMessage && (
                <div className="xl:col-span-2 rounded-xl border border-[rgba(245,158,11,0.24)] bg-[rgba(245,158,11,0.08)] px-4 py-3 text-sm text-sylion-amber">
                  {ideaGateMessage}
                </div>
              )}
              {ideas.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nie wygenerowano jeszcze pomysłów.</p>
              ) : (
                ideas.map((idea) => (
                  <Card key={idea.idea_id} className="p-4 bg-[#0a1020] border-[rgba(148,163,184,0.08)]">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold">{idea.title}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{idea.category}</p>
                      </div>
                      <Badge variant="outline">{Math.round(idea.chance_pct ?? 0)}%</Badge>
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">{idea.solution}</p>
                    <div className="mt-4 flex flex-wrap gap-2 text-xs">
                      <Badge variant="outline">{idea.recommendation}</Badge>
                          <Badge variant="outline">Budżet EUR {Number(idea.budget_estimate ?? 0).toLocaleString()}</Badge>
                          {idea.recommended_call_id && <Badge variant="outline">Nabór {idea.recommended_call_id}</Badge>}
                    </div>
                    <div className="mt-4 flex gap-2">
                      <Button size="sm" onClick={() => void handleConvertIdea(idea.idea_id, idea.recommended_call_id)}>
                    Zamień na projekt
                      </Button>
                    </div>
                  </Card>
                ))
              )}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="matching" className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[0.8fr,1.2fr]">
            <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">
                    Projekty i konsorcjum
                    <HelpTip text="Lista projektów grantowych z konfiguracją konsorcjum (partnerów). Składa się z wybranych pomysłów + dopasowań." />
                  </h2>
                  <p className="text-sm text-muted-foreground">Wybierz projekt, oceń go i przygotuj kontakt z partnerami.</p>
                </div>
                <Button onClick={() => void handleRunMatching()} disabled={!selectedProjectId || busyAction === "run-matching"}>
                  {busyAction === "run-matching" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Target className="w-3.5 h-3.5 mr-1.5" />}
                  Uruchom dopasowanie
                </Button>
              </div>
              <select
                value={selectedProjectId}
                onChange={(event) => setSelectedProjectId(event.target.value)}
                className="w-full rounded-lg border border-[rgba(148,163,184,0.12)] bg-[#0a1020] px-3 py-2 text-sm"
              >
                <option value="">Select project</option>
                {projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>{project.title}</option>
                ))}
              </select>
              {activeProject ? (
                <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4 text-sm">
                  <p className="font-semibold">{activeProject.title}</p>
                  <p className="mt-1 text-muted-foreground">{activeProject.summary}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <Badge variant="outline">{activeProject.status}</Badge>
                    <Badge variant="outline">TRL {activeProject.trl ?? "n/a"}</Badge>
                  <Badge variant="outline">Budżet EUR {Number(activeProject.budget_total ?? 0).toLocaleString()}</Badge>
                  </div>
                </div>
              ) : (
                  <p className="text-sm text-muted-foreground">Najpierw utwórz albo zamień pomysł na projekt.</p>
              )}

              <div className="space-y-2 border-t border-[rgba(148,163,184,0.08)] pt-4">
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Kandydat na partnera</p>
                <Input value={partnerForm.name} onChange={(value) => setPartnerForm((prev) => ({ ...prev, name: value }))} placeholder="Nazwa partnera" />
                <Input value={partnerForm.partner_type} onChange={(value) => setPartnerForm((prev) => ({ ...prev, partner_type: value }))} placeholder="Typ partnera" />
                <Input value={partnerForm.country} onChange={(value) => setPartnerForm((prev) => ({ ...prev, country: value }))} placeholder="Kraj" />
                <TextArea value={partnerForm.expertise} onChange={(value) => setPartnerForm((prev) => ({ ...prev, expertise: value }))} placeholder="Ekspertyza, po przecinku" rows={2} />
                <Input value={partnerForm.grant_track_record} onChange={(value) => setPartnerForm((prev) => ({ ...prev, grant_track_record: value }))} placeholder="Doświadczenie grantowe" type="number" />
                <Input value={partnerForm.contact_email} onChange={(value) => setPartnerForm((prev) => ({ ...prev, contact_email: value }))} placeholder="E-mail kontaktowy" />
                <div className="flex gap-2">
                  <Button className="flex-1" variant="outline" onClick={() => void handleAddPartner()} disabled={!selectedProjectId || busyAction === "add-partner"}>
                  Dodaj kandydata
                  </Button>
                  <Button className="flex-1" variant="outline" onClick={() => void handleShortlistPartners()} disabled={!selectedProjectId || busyAction === "shortlist-partners"}>
                  Zbuduj shortlistę
                  </Button>
                </div>
                <Button className="w-full" variant="outline" onClick={() => void handleGenerateOutreach()} disabled={!selectedProjectId || busyAction === "generate-outreach"}>
                  <Mail className="w-3.5 h-3.5 mr-1.5" />
                Wygeneruj wiadomości do partnerów
                </Button>
              </div>
            </Card>

            <div className="space-y-4">
              <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">
                    Wynik prawdopodobieństwa grantu
                    <HelpTip text="Algorytmiczna ocena szansy sukcesu wniosku. Bierze pod uwagę dopasowanie tematyczne, gotowość firmy, jakość konsorcjum i historyczne dane." />
                  </h2>
                  {scoringResult && <Badge variant="outline">{Math.round(scoringResult.grant_success_probability ?? 0)}%</Badge>}
                </div>
                {!scoringResult ? (
                <p className="mt-3 text-sm text-muted-foreground">Uruchom dopasowanie, aby uzyskać scoring, ryzyka i symulację usprawnień.</p>
                ) : (
                  <div className="mt-4 space-y-4">
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="rounded-lg border border-[rgba(148,163,184,0.08)] p-3 text-sm">
                        <p className="text-muted-foreground">Wynik dopasowania do grantu</p>
                        <p className="mt-1 text-xl font-semibold">{Math.round(scoringResult.grant_fit_score ?? 0)}%</p>
                      </div>
                      <div className="rounded-lg border border-[rgba(148,163,184,0.08)] p-3 text-sm">
                        <p className="text-muted-foreground">Prawdopodobieństwo sukcesu</p>
                        <p className="mt-1 text-xl font-semibold">{Math.round(scoringResult.grant_success_probability ?? 0)}%</p>
                      </div>
                      <div className="rounded-lg border border-[rgba(148,163,184,0.08)] p-3 text-sm">
                        <p className="text-muted-foreground">Pewność</p>
                        <p className="mt-1 text-xl font-semibold">{Math.round(scoringResult.confidence ?? 0)}%</p>
                      </div>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                    <p className="text-sm font-medium">Mocne strony</p>
                        <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                          {(scoringResult.strengths ?? []).map((item: string) => <li key={item}>- {item}</li>)}
                        </ul>
                      </div>
                      <div>
                    <p className="text-sm font-medium">Ryzyka</p>
                        <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                          {(scoringResult.risks ?? []).map((item: string) => <li key={item}>- {item}</li>)}
                        </ul>
                      </div>
                    </div>
                    <div>
                    <p className="text-sm font-medium">Symulacja usprawnień</p>
                      <div className="mt-2 space-y-2">
                        {(scoringResult.simulation ?? []).map((item: AnyRecord) => (
                          <div key={item.scenario} className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-2 text-sm">
                            <span>{item.scenario}</span>
                            <span className="float-right font-medium">{Math.round(item.projected_probability ?? 0)}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </Card>

              <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">
                    Dopasowanie do programów
                    <HelpTip text="Wyniki dopasowania projektu do otwartych programów grantowych — wynik + uzasadnienie." />
                  </h2>
                  {(consortiumResult?.required_partner_types?.length ?? 0) > 0 && (
                  <Badge variant="outline">{consortiumResult?.required_partner_types?.length ?? 0} luk partnerskich</Badge>
                  )}
                </div>
                <div className="mt-4 space-y-3">
                  {matchingResults.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Brak wyników dopasowania.</p>
                  ) : (
                    matchingResults.map((item) => (
                      <div key={item.call_id} className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold">{item.call_id}</p>
                          <div className="flex flex-wrap gap-2 text-xs">
                            <Badge variant="outline">Dopasowanie {Math.round(item.fit_score ?? 0)}%</Badge>
                            <Badge variant="outline">Sukces {Math.round(item.success_probability ?? 0)}%</Badge>
                            <Badge variant="outline">Ryzyko {Math.round(item.risk_score ?? 0)}%</Badge>
                          </div>
                        </div>
                        <div className="mt-3 grid gap-4 md:grid-cols-2">
                          <div>
                            <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Usprawnienia</p>
                            <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                              {(item.improvements ?? []).map((improvement: AnyRecord) => (
                                <li key={improvement.action}>- {improvement.action}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Brakujące dokumenty / partnerzy</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {(item.missing_documents ?? []).map((missing: string) => <Badge key={missing} variant="outline" className="border-sylion-red/30 text-sylion-red">{missing}</Badge>)}
                              {(item.missing_partner_types ?? []).map((missing: string) => <Badge key={missing} variant="outline" className="border-sylion-amber/30 text-sylion-amber">{missing}</Badge>)}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </Card>

              <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
                <div className="grid gap-4 md:grid-cols-3">
                  <div>
                    <p className="text-sm font-medium">Partnerzy</p>
                    <div className="mt-2 space-y-2">
                      {partners.slice(0, 5).map((item) => (
                        <div key={item.partner_id} className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-2 text-xs">
                          <p className="font-medium">{item.name}</p>
                          <p className="text-muted-foreground">{item.partner_type}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Shortlista</p>
                    <div className="mt-2 space-y-2">
                      {shortlist.slice(0, 5).map((item) => (
                        <div key={item.partner_id} className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-2 text-xs">
                          <p className="font-medium">{item.name}</p>
                          <p className="text-muted-foreground">Wynik {Math.round(item.score ?? 0)}%</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Wiadomości do partnerów</p>
                    <div className="mt-2 space-y-2">
                      {outreachMessages.slice(0, 3).map((item) => (
                        <div key={item.message_id} className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-2 text-xs">
                          <p className="font-medium">{item.subject}</p>
                          <p className="mt-1 line-clamp-3 text-muted-foreground">{item.body}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="applications" className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[0.8fr,1.2fr]">
            <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">
                    Budowniczy wniosku
                    <HelpTip text="Generowanie pakietu wniosku grantowego z masterplanu projektu, profilu firmy i dokumentacji." />
                  </h2>
                  <p className="text-sm text-muted-foreground">Utwórz i zwaliduj pakiet na podstawie dopasowanego projektu.</p>
                </div>
                <Button onClick={() => void handleCreateApplication()} disabled={!selectedProjectId || busyAction === "create-application"}>
                  {busyAction === "create-application" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <FolderKanban className="w-3.5 h-3.5 mr-1.5" />}
                  Utwórz wniosek
                </Button>
              </div>
              <select
                value={selectedApplicationId}
                onChange={(event) => setSelectedApplicationId(event.target.value)}
                className="w-full rounded-lg border border-[rgba(148,163,184,0.12)] bg-[#0a1020] px-3 py-2 text-sm"
              >
                <option value="">Wybierz wniosek</option>
                {applications.map((application) => (
                  <option key={application.application_id} value={application.application_id}>
                    {application.application_id} - {application.status}
                  </option>
                ))}
              </select>
              <div className="flex gap-2">
                <Button className="flex-1" variant="outline" onClick={() => void handleReviewApplication()} disabled={!selectedApplicationId || busyAction === "review-application"}>
                  <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />
                  Przegląd
                </Button>
                <Button className="flex-1" variant="outline" onClick={() => void handleExportApplication()} disabled={!selectedApplicationId || busyAction === "export-application"}>
                  <FileText className="w-3.5 h-3.5 mr-1.5" />
                  Eksport
                </Button>
              </div>
              {applicationDocuments && (
                <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4 text-sm">
                  <p className="font-semibold">Wymagane dokumenty</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(applicationDocuments.required_documents ?? []).map((item: string) => (
                      <Badge key={item} variant="outline">{item}</Badge>
                    ))}
                  </div>
                  <p className="mt-4 font-semibold">Brakujące dokumenty</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(applicationDocuments.missing_documents ?? []).length === 0 ? (
                      <Badge variant="outline" className="border-sylion-green/30 text-sylion-green">Brak brakujących dokumentów</Badge>
                    ) : (
                      (applicationDocuments.missing_documents ?? []).map((item: string) => (
                        <Badge key={item} variant="outline" className="border-sylion-red/30 text-sylion-red">{item}</Badge>
                      ))
                    )}
                  </div>
                </div>
              )}
            </Card>

            <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
              {!applicationDetail ? (
                <p className="text-sm text-muted-foreground">Wybierz lub utwórz wniosek, aby sprawdźić wygenerowany pakiet.</p>
              ) : (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h2 className="text-lg font-semibold">{activeApplication?.application_id ?? applicationDetail.application_id}</h2>
                      <p className="text-sm text-muted-foreground">Status: {applicationDetail.status}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {Object.keys(applicationDetail.export_json ?? {}).map((key) => (
                        <Badge key={key} variant="outline">{key}</Badge>
                      ))}
                    </div>
                  </div>
                  <div className="grid gap-4 lg:grid-cols-2">
                    <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                      <p className="text-sm font-semibold">Streszczenie wykonawcze</p>
                      <p className="mt-3 text-sm text-muted-foreground">{applicationDetail.package_json?.executive_summary ?? "n/a"}</p>
                    </div>
                    <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                      <p className="text-sm font-semibold">Budżet</p>
                      <div className="mt-3 space-y-2 text-sm text-muted-foreground">
                        <p>Razem: EUR {Number(applicationDetail.package_json?.budget?.budget_total ?? 0).toLocaleString()}</p>
                        <p>Wnioskowana dotacja: EUR {Number(applicationDetail.package_json?.budget?.grant_requested ?? 0).toLocaleString()}</p>
                        <p>Wkład własny: EUR {Number(applicationDetail.package_json?.budget?.own_contribution ?? 0).toLocaleString()}</p>
                      </div>
                    </div>
                    <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                      <p className="text-sm font-semibold">Ustalenia przeglądu</p>
                      {(applicationDetail.review_json?.findings ?? []).length === 0 ? (
                        <p className="mt-3 text-sm text-muted-foreground">Brak ustaleń przeglądu.</p>
                      ) : (
                        <div className="mt-3 space-y-2">
                          {(applicationDetail.review_json?.findings ?? []).map((item: AnyRecord, index: number) => (
                            <div key={`${item.reviewer}-${index}`} className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-2 text-sm">
                              <span className="font-medium">{item.reviewer}</span>: {item.message}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                      <p className="text-sm font-semibold">Wyeksportowane pliki</p>
                      <div className="mt-3 space-y-2 text-sm text-muted-foreground">
                        {Object.entries(applicationDetail.export_json ?? {}).length === 0 ? (
                          <p>Nie wygenerowano jeszcze pakietu eksportu.</p>
                        ) : (
                          Object.entries(applicationDetail.export_json ?? {}).map(([key, value]) => (
                            <p key={key}>{key}: {String(value)}</p>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="submission" className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[0.85fr,1.15fr]">
            <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)] space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">
                    Bramka złożenia i zatwierdzenia
                    <HelpTip text="Finalna bramka — wymaga walidacji dokumentów, gotowości przeglądu i zatwierdzenia operatora przed złożeniem." />
                  </h2>
                  <p className="text-sm text-muted-foreground">Zatwierdzenie człowieka jest wymagane zanim moduł zapisze formalne złożenie.</p>
                </div>
              </div>

              <Input value={portalUrl} onChange={setPortalUrl} placeholder="Adres portalu" />
              <div className="grid gap-2 md:grid-cols-2">
                <Button variant="outline" onClick={() => void handlePrepareSubmission()} disabled={!selectedApplicationId || busyAction === "prepare-submission"}>
                  <Send className="w-3.5 h-3.5 mr-1.5" />
                  Przygotuj złożenie
                </Button>
                <Button variant="outline" onClick={() => void handleFillSubmission()} disabled={!selectedSessionId || busyAction === "fill-submission"}>
                  Wypełnij mapowanie
                </Button>
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                <Button variant="outline" onClick={() => void handleSaveDraft()} disabled={!selectedSessionId || busyAction === "save-draft"}>
                  Zapisz szkic
                </Button>
                <Button variant="outline" onClick={() => void handleRequestApproval()} disabled={!canRequestApproval}>
                  Poproś o zatwierdzenie
                </Button>
              </div>
              {submissionGateReasons.length > 0 && (
                <div className="rounded-xl border border-[rgba(245,158,11,0.24)] bg-[rgba(245,158,11,0.08)] px-4 py-3 text-sm text-sylion-amber">
                  Złożenie jest zablokowane do czasu rozwiązania problemów: {submissionGateReasons.join(" | ")}
                </div>
              )}
              {submissionGateReasons.length === 0 && latestSessionApproval?.status === "pending" && (
                <div className="rounded-xl border border-[rgba(16,185,129,0.24)] bg-[rgba(16,185,129,0.08)] px-4 py-3 text-sm text-sylion-green">
                  Prośba o zatwierdzenie oczekuje w Human Gate{latestSessionGovernanceTicketId ? `: ${latestSessionGovernanceTicketId}` : ""}. Wpisz referencję portalu, aby zapisać finalne złożenie.
                </div>
              )}
              <Input value={approvalNotes} onChange={setApprovalNotes} placeholder="Notatki zatwierdzenia" />
              <Input value={approvedBy} onChange={setApprovedBy} placeholder="Zatwierdzone przez" />
              <Input value={submissionReference} onChange={setSubmissionReference} placeholder="Numer referencyjny z portalu" />
              <Button className="w-full" onClick={() => void handleSubmit()} disabled={!canSubmit}>
                {busyAction === "submit-application" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5 mr-1.5" />}
                Zapisz finalne złożenie
              </Button>

              <select
                value={selectedSessionId}
                onChange={(event) => setSelectedSessionId(event.target.value)}
                className="w-full rounded-lg border border-[rgba(148,163,184,0.12)] bg-[#0a1020] px-3 py-2 text-sm"
              >
                <option value="">Wybierz sesję złożenia</option>
                {submissionSessions.map((session) => (
                  <option key={session.session_id} value={session.session_id}>
                    {session.session_id} - {session.status}
                  </option>
                ))}
              </select>
            </Card>

            <div className="space-y-4">
              <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">
                    Bieżąca sesja
                    <HelpTip text="Aktywna sesja składania — z walidacją dokumentów, statusem zatwierdzenia i numerem referencyjnym." />
                  </h2>
                  {activeSession && <Badge variant="outline">{activeSession.status}</Badge>}
                </div>
                {!activeSession ? (
                  <p className="mt-3 text-sm text-muted-foreground">Brak sesji złożenia.</p>
                ) : (
                  <div className="mt-4 space-y-4 text-sm">
                    <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                      <p className="font-medium">Portal</p>
                      <p className="mt-1 text-muted-foreground">{activeSession.portal_url || "n/a"}</p>
                      <p className="mt-3 font-medium">Referencja szkicu</p>
                      <p className="mt-1 text-muted-foreground">{activeSession.draft_reference || "n/a"}</p>
                      {hasRecordPayload(submissionReceipt) && (
                        <>
                          <p className="mt-3 font-medium">Potwierdzenie złożenia</p>
                          <p className="mt-1 text-muted-foreground">{String(submissionReceipt.portal_submission_reference ?? submissionReceipt.receipt_id ?? "zapisane")}</p>
                        </>
                      )}
                    </div>
                    <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                      <p className="font-medium">Przygotowane pola</p>
                      <pre className="mt-3 overflow-auto text-xs text-muted-foreground">{JSON.stringify(activeSession.prepared_fields_json ?? {}, null, 2)}</pre>
                    </div>
                    <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                      <p className="font-medium">Walidacja</p>
                      <pre className="mt-3 overflow-auto text-xs text-muted-foreground">{JSON.stringify(activeSession.validation_json ?? {}, null, 2)}</pre>
                    </div>
                  </div>
                )}
              </Card>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
                  <div className="flex items-center gap-2">
                    <CalendarClock className="w-4 h-4 text-primary" />
                    <h2 className="text-lg font-semibold">
                      Terminy
                      <HelpTip text="Śledzone terminy aplikacyjne, raportowe i kontraktowe. Automatyczne alerty na 30/14/7 dni przed deadlinem." />
                    </h2>
                  </div>
                  <div className="mt-4 space-y-2">
                    {deadlines.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Brak śledzonych terminów.</p>
                    ) : (
                      deadlines.map((item, index) => (
                        <div key={`${item.type}-${index}`} className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-2 text-sm">
                          <p className="font-medium">{item.label}</p>
                          <p className="text-muted-foreground">{fmtEpoch(item.due_at)}</p>
                        </div>
                      ))
                    )}
                  </div>
                </Card>

                <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-sylion-amber" />
                    <h2 className="text-lg font-semibold">
                      Alerty i zatwierdzenia
                      <HelpTip text="Aktywne alerty (brakujące dokumenty, terminy, błędy walidacji) i historia decyzji operatora." />
                    </h2>
                  </div>
                  <div className="mt-4 space-y-2">
                    {alerts.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Brak aktywnych alertów.</p>
                    ) : (
                      alerts.map((item, index) => (
                        <div key={`${item.kind}-${index}`} className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-2 text-sm">
                          <p className="font-medium">{item.kind}</p>
                          <p className="text-muted-foreground">{item.message}</p>
                        </div>
                      ))
                    )}
                    {submissionApprovals.map((item) => (
                      <div key={item.approval_event_id} className="rounded-lg border border-[rgba(148,163,184,0.08)] px-3 py-2 text-sm">
                        <p className="font-medium">{item.action_type}</p>
                        <p className="text-muted-foreground">{item.status} przez {item.requested_by || "n/a"}</p>
                        {item.payload_json?.governance_ticket_id && (
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                            <span>Ticket Human Gate: <span className="font-mono text-foreground">{item.payload_json.governance_ticket_id}</span></span>
                            <Badge variant="outline">{String(item.payload_json.human_gate_state ?? "pending")}</Badge>
                            <a className="text-primary hover:underline" href={`/human-gate?ticket=${encodeURIComponent(String(item.payload_json.governance_ticket_id))}`}>
                              Otworz w Human Gate
                            </a>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </Card>
              </div>

              <Card className="p-5 bg-[#0f1629] border-[rgba(148,163,184,0.08)]">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">
                    Raport wykonawczy
                    <HelpTip text="Skondensowany raport dla zarządu — status pipeline'u, gotowość, ryzyka, prognozowane przychody z grantów." />
                  </h2>
                  {executiveReport && <Badge variant="outline">{Math.round(executiveReport.readiness_score ?? 0)}%</Badge>}
                </div>
                {!executiveReport ? (
                  <p className="mt-3 text-sm text-muted-foreground">Brak raportu wykonawczego.</p>
                ) : (
                  <div className="mt-4 grid gap-4 md:grid-cols-2 text-sm">
                    <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                      <p className="font-medium">{executiveReport.company_name}</p>
                      <p className="mt-1 text-muted-foreground">Otwarte projekty: {executiveReport.open_projects}</p>
                      <p className="text-muted-foreground">Wnioski: {executiveReport.applications}</p>
                    </div>
                    <div className="rounded-xl border border-[rgba(148,163,184,0.08)] bg-[#0a1020] p-4">
                      <p className="font-medium">Najważniejsze ryzyka</p>
                      <ul className="mt-2 space-y-2 text-muted-foreground">
                        {(executiveReport.top_risks ?? []).slice(0, 5).map((item: string) => <li key={item}>- {item}</li>)}
                      </ul>
                    </div>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="reporting" className="space-y-4">
          <FundingReportingPanel
            calls={calls}
            ideas={ideas}
            projects={projects}
            applications={applications}
            deadlines={deadlines}
            alerts={alerts}
            executiveReport={executiveReport}
            selectedApplicationId={selectedApplicationId}
            representativeEmail={profileForm.representative_email}
            referenceTimeMs={lastUpdated}
            exporting={busyAction === "export-application"}
            onExportApplication={() => void handleExportApplication()}
            exportUrlFor={api.fundingApplicationExportUrl}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
