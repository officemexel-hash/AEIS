"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { useDeploySummary, useDeployTopologies, useHealth } from "@/lib/api/hooks";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, fmtDateTime } from "@/lib/utils";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Download,
  ExternalLink,
  FileCode2,
  Layers3,
  Loader2,
  Rocket,
  Server,
} from "lucide-react";

type DeployFileRef = {
  key: string;
  label: string;
  path: string;
  exists: boolean;
  size_bytes: number;
};

type DeployProject = {
  project_id: string;
  title: string;
  project_kind: string;
  status: string;
  phase: string;
  created_at?: number;
  updated_at?: number;
  launch_status: string;
  launched_at?: number;
  artifact: DeployFileRef & {
    sha256?: string;
    format?: string;
  };
  bundle: {
    status: "ready" | "partial" | "missing";
    files: DeployFileRef[];
  };
  validation: {
    success: boolean;
    stages: Record<string, unknown>;
  };
  audit: {
    result_count: number;
  };
  module_output_count: number;
  deployment_mode: string;
  provisioning_mode: string;
  pending_question_count: number;
  reason: string;
  recommended_action: string;
};

type ActiveDeployment = {
  deployment_id: string;
  module_id: string;
  from_stage: string;
  to_stage: string;
  strategy: string;
  status: string;
  started_at?: number;
  step_summary: {
    total: number;
    completed: number;
    in_progress: number;
    pending: number;
    failed: number;
    current_step: string;
  };
};

type CloudConnector = {
  connector_id: string;
  provider: string;
  name?: string;
};

type HetznerHealthProbe = {
  ok?: boolean;
  url?: string;
  status_code?: number | null;
  body_excerpt?: string;
  error?: string;
  checked_at?: number;
};

type HetznerDeployment = {
  deployment_id: string;
  project_id: string;
  server_name: string;
  status: string;
  public_ipv4?: string;
  health_url?: string;
  artifact_sha256?: string;
  raw?: {
    health_probe?: HetznerHealthProbe;
    deployment_group_id?: string;
    environment_name?: string;
    environment_index?: number;
    server_index?: number;
    environment_count?: number;
    vps_per_environment?: number;
    total_servers?: number;
    [key: string]: unknown;
  };
};

type DeploySummary = {
  surface_status: string;
  stats: {
    tracked_projects: number;
    ready_projects: number;
    pending_projects: number;
    active_deployments: number;
  };
  ready_projects: DeployProject[];
  pending_projects: DeployProject[];
  active_deployments: ActiveDeployment[];
};

type DeployTopologyVariant = {
  variant: string;
  server_count: number;
  servers: Array<{
    name: string;
    role: string;
    components: string[];
  }>;
};

type DeployTopologiesResponse = {
  variants: DeployTopologyVariant[];
};

function humanize(value: string | undefined): string {
  const raw = String(value || "unknown");
  const labels: Record<string, string> = {
    unknown: "nieznane",
    manual: "ręcznie",
    not_recorded: "brak wpisu",
    ready: "gotowe",
    partial: "częściowe",
    missing: "brak",
    pending: "oczekuje",
    completed: "ukończone",
    complete: "ukończone",
    failed: "nieudane",
    in_progress: "w toku",
    blocked: "zablokowane",
    definition_in_progress: "definicja w toku",
    launched: "uruchomione",
    launch_ready: "gotowe do uruchomienia",
    manual_launch_required: "wymagane ręczne uruchomienie",
    deploy_ready: "gotowe do wdrożenia",
    local_first: "local-first",
    local_only: "tylko lokalnie",
    canary: "canary",
    production: "produkcja",
  };
  return labels[raw] ?? raw.replace(/_/g, " ");
}

function bundleTone(status: string): string {
  if (status === "ready") return "border-sylion-green/20 bg-sylion-green/10 text-sylion-green";
  if (status === "partial") return "border-sylion-amber/20 bg-sylion-amber/10 text-sylion-amber";
  return "border-border bg-muted/40 text-muted-foreground";
}

function surfaceTone(status: "live" | "degraded" | "offline"): string {
  if (status === "live") return "border-sylion-green/30 text-sylion-green";
  if (status === "degraded") return "border-sylion-amber/30 text-sylion-amber";
  return "border-border text-muted-foreground";
}

function shortHash(value: string | undefined): string {
  const hash = String(value || "").trim();
  return hash ? `${hash.slice(0, 12)}...` : "brak wpisu";
}

function formatHealthProbe(probe: HetznerHealthProbe | undefined, fallbackUrl?: string): string {
  if (!probe) return fallbackUrl ? `brak szczegółów probe (${fallbackUrl})` : "brak szczegółów probe";
  const verdict = probe.ok ? "PRZECHODZI" : "NIE PRZECHODZI";
  const status = typeof probe.status_code === "number" ? `HTTP ${probe.status_code}` : "HTTP brak statusu";
  const url = probe.url || fallbackUrl || "brak URL";
  return `${verdict} ${status} ${url}`;
}

function boundedInt(value: string | number, fallback: number, min = 1, max = 10): number {
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

function downloadFile(content: string, filename: string) {
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function DeployPage() {
  const { data: health, loading: healthLoading } = useHealth();
  const { data: summaryData, loading: summaryLoading, error: summaryError } = useDeploySummary();
  const { data: topologięsData, loading: topologięsLoading, error: topologięsError } = useDeployTopologies();
  const summary = summaryData as DeploySummary;
  const topologięs = (topologięsData as DeployTopologiesResponse)?.variants ?? [];
  const readyProjects = summary.ready_projects ?? [];
  const pendingProjects = summary.pending_projects ?? [];
  const activeDeployments = summary.active_deployments ?? [];
  const [generating, setGenerating] = useState<string | null>(null);
  const [generated, setGenerated] = useState<Record<string, { terraform: string; inventory: string; playbook: string }>>({});
  const [cloudConnectors, setCloudConnectors] = useState<CloudConnector[]>([]);
  const [hetznerDeployments, setHetznerDeployments] = useState<HetznerDeployment[]>([]);
  const [hetznerHealthProofs, setHetznerHealthProofs] = useState<Record<string, HetznerHealthProbe>>({});
  const [hetznerForm, setHetznerForm] = useState({
    project_id: "",
    connector_id: "",
    server_name: "",
    server_type: "cx23",
    location: "fsn1",
    image: "ubuntu-24.04",
    environment_count: "1",
    vps_per_environment: "1",
    confirm_financial_action: false,
    confirm_delete: false,
  });
  const [hetznerBusy, setHetznerBusy] = useState<string | null>(null);
  const [hetznerMessage, setHetznerMessage] = useState<string>("");

  const backendLive = health.status === "ok";
  const surfaceStatus: "live" | "degraded" | "offline" = !healthLoading && !backendLive
    ? "offline"
    : summaryError
      ? "degraded"
      : "live";
  const hetznerConnectors = cloudConnectors.filter((connector) => String(connector.provider || "").toLowerCase() === "hetzner");
  const plannedEnvironmentCount = boundedInt(hetznerForm.environment_count, 1, 1, 10);
  const plannedVpsPerEnvironment = boundedInt(hetznerForm.vps_per_environment, 1, 1, 10);
  const plannedTotalVps = plannedEnvironmentCount * plannedVpsPerEnvironment;

  const refreshHetzner = async () => {
    const [connectorsPayload, deploymentsPayload] = await Promise.all([
      api.listCloudConnectors(),
      api.listHetznerDeployments(),
    ]);
    setCloudConnectors(connectorsPayload.connectors ?? []);
    setHetznerDeployments(deploymentsPayload.deployments ?? []);
  };

  useEffect(() => {
    void refreshHetzner();
  }, []);

  const handleGenerate = async (variant: string) => {
    setGenerating(variant);
    try {
      const response = await api.generateDeployTopology(variant);
      setGenerated((previous) => ({
        ...previous,
        [variant]: {
          terraform: response.files.terraform_main_tf,
          inventory: response.files.ansible_inventory_ini,
          playbook: response.files.ansible_playbook_yml,
        },
      }));
    } finally {
      setGenerating(null);
    }
  };

  const handleHetznerProvision = async () => {
    if (!hetznerForm.project_id || !hetznerForm.connector_id) {
      setHetznerMessage("Wybierz projekt i konektor Hetzner przed wdrożeniem.");
      return;
    }
    if (!hetznerForm.confirm_financial_action) {
      setHetznerMessage("Zaznacz potwierdzenie utworzenia płatnego zasobu Hetzner przed wdrożeniem.");
      return;
    }
    setHetznerBusy("provision");
    setHetznerMessage("");
    try {
      const response = await api.provisionHetznerProject({
        project_id: hetznerForm.project_id,
        connector_id: hetznerForm.connector_id,
        server_name: hetznerForm.server_name,
        server_type: hetznerForm.server_type,
        location: hetznerForm.location,
        image: hetznerForm.image,
        environment_count: plannedEnvironmentCount,
        vps_per_environment: plannedVpsPerEnvironment,
        confirm_financial_action: hetznerForm.confirm_financial_action,
        wait_for_health: true,
      });
      const deploymentId = response.deployment?.deployment_id;
      const probe = response.public_probe ?? response.deployment?.raw?.health_probe;
      const group = response.deployment_group;
      const totalServers = Number(group?.total_servers || response.deployments?.length || 1);
      const environmentCount = Number(group?.environment_count || plannedEnvironmentCount);
      const vpsPerEnvironment = Number(group?.vps_per_environment || plannedVpsPerEnvironment);
      if (deploymentId && probe) {
        setHetznerHealthProofs((previous) => ({ ...previous, [deploymentId]: probe }));
      }
      setHetznerMessage(
        `Wdrożenie Hetzner: ${humanize(response.deployment?.status ?? "utworzono")}; utworzono ${totalServers} VPS (${environmentCount} środ. × ${vpsPerEnvironment} VPS); publiczna kontrola zdrowia: ${formatHealthProbe(probe, response.deployment?.health_url)}`,
      );
      await refreshHetzner();
    } catch (error: unknown) {
      setHetznerMessage(`Wdrożenie Hetzner zablokowane lub nieudane: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setHetznerBusy(null);
    }
  };

  const handleHetznerHealth = async (deploymentId: string) => {
    setHetznerBusy(deploymentId);
    try {
      const response = await api.checkHetznerDeploymentHealth(deploymentId);
      const probe = response.public_probe ?? response.deployment?.raw?.health_probe;
      if (probe) {
        setHetznerHealthProofs((previous) => ({ ...previous, [deploymentId]: probe }));
      }
      setHetznerMessage(`Kontrola zdrowia: ${formatHealthProbe(probe, response.health_url ?? response.deployment?.health_url)}`);
      await refreshHetzner();
    } finally {
      setHetznerBusy(null);
    }
  };

  const handleHetznerDelete = async (deploymentId: string) => {
    if (!hetznerForm.confirm_delete) {
      setHetznerMessage("Zaznacz potwierdzenie usunięcia zasobu Hetzner przed rollbackiem albo usunięciem.");
      return;
    }
    setHetznerBusy(deploymentId);
    try {
      const response = await api.deleteHetznerDeployment(deploymentId, hetznerForm.confirm_delete);
      setHetznerHealthProofs((previous) => {
        const next = { ...previous };
        delete next[deploymentId];
        return next;
      });
      setHetznerMessage(`Rollback/usunięcie: ${response.deleted ? "wysłano żądanie usunięcia VPS" : "brak potwierdzenia"}`);
      await refreshHetzner();
    } catch (error: unknown) {
      setHetznerMessage(`Rollback/usunięcie zablokowane lub nieudane: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setHetznerBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
              <Rocket className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Wdrożenia</h1>
              <p className="text-sm text-muted-foreground">
                Powierzchnia operatora dla realnie uruchomionych artefaktów i pakietów wdrożeniowych.
              </p>
            </div>
          </div>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Tylko uruchomione projekty z zapisanymi artefaktami, zaliczoną walidacją i wygenerowanymi pakietami wdrożeniowymi pojawiają się tutaj jako gotowe.
            Jeśli nic nie jest gotowe, strona pozostaje pusta zamiast wymyślać placeholdery, cele albo fałszywe adresy repozytoriów.
          </p>
        </div>
        <Badge variant="outline" className={cn("mt-1 text-[10px]", surfaceTone(surfaceStatus))}>
          {surfaceStatus === "live" ? "DZIAŁA" : surfaceStatus === "degraded" ? "ZDEGRADOWANE" : "OFFLINE"}
        </Badge>
      </div>

      {!healthLoading && surfaceStatus === "offline" ? (
        <Card className="border-border bg-muted/30">
          <CardContent className="flex items-start gap-3 pt-4">
            <AlertTriangle className="mt-0.5 h-4 w-4 text-muted-foreground" />
            <div className="space-y-1">
              <p className="text-sm font-medium">Backend offline</p>
              <p className="text-xs text-muted-foreground">
                Dane wdrożeń są niedostępne, ponieważ endpoint zdrowia backendu nie zwraca statusu `ok`.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {summaryError && surfaceStatus !== "offline" ? (
        <Card className="border-sylion-amber/30 bg-sylion-amber/10">
          <CardContent className="flex items-start gap-3 pt-4">
            <AlertTriangle className="mt-0.5 h-4 w-4 text-sylion-amber" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-sylion-amber">Powierzchnia wdrożeń działa w trybie zdegradowanym</p>
              <p className="text-xs text-muted-foreground">{summaryError}</p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Śledzone projekty</CardDescription>
            <CardTitle>{summary.stats?.tracked_projects ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Gotowe wdrożenia</CardDescription>
            <CardTitle className="text-sylion-green">{summary.stats?.ready_projects ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Oczekująca gotowość</CardDescription>
            <CardTitle className="text-sylion-amber">{summary.stats?.pending_projects ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Aktywne wydania</CardDescription>
            <CardTitle>{summary.stats?.active_deployments ?? 0}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Gotowe do wdrożenia przez operatora</h2>
            <p className="text-sm text-muted-foreground">
              Realne artefakty z walidacją i kompletnym pakietem wdrożeniowym.
            </p>
          </div>
          {summaryLoading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Ładowanie podsumowania wdrożeń...
            </div>
          ) : null}
        </div>

        {readyProjects.length === 0 ? (
          <Card className="border-border bg-muted/20">
            <CardContent className="space-y-3 pt-4">
              <p className="text-sm font-medium">Nie ma jeszcze gotowych artefaktów do wdrożenia.</p>
              <p className="text-xs text-muted-foreground">
                Projekt pojawia się tutaj dopiero wtedy, gdy backend zapisze realną ścieżkę artefaktu, walidacja przejdzie,
                a pakiet wdrożeniowy zawiera pliki Docker, skrypt, Terraform, inventory i PLAN.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {readyProjects.map((project) => (
              <Card key={project.project_id} className="border-sylion-green/20">
                <CardHeader className="gap-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <CardTitle className="flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-sylion-green" />
                        {project.title || project.project_id}
                      </CardTitle>
                      <CardDescription className="font-mono text-[11px]">
                        {project.project_id}
                      </CardDescription>
                    </div>
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      <Badge variant="outline" className="text-[10px]">
                        {humanize(project.phase)}
                      </Badge>
                      <Badge variant="outline" className="text-[10px]">
                        {humanize(project.deployment_mode || "manual")}
                      </Badge>
                      <Badge variant="outline" className="text-[10px]">
                        {humanize(project.provisioning_mode || "not_recorded")}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 lg:grid-cols-2">
                    <div className="space-y-2 rounded-lg border border-border/60 bg-muted/20 p-3">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <FileCode2 className="h-4 w-4 text-primary" />
                        Artefakt
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Format: <span className="font-medium text-foreground">{humanize(project.artifact.format)}</span>
                      </p>
                      <p className="break-all font-mono text-[11px] text-muted-foreground">
                        {project.artifact.path}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        SHA256: <span className="font-mono text-foreground">{shortHash(project.artifact.sha256)}</span>
                      </p>
                    </div>

                    <div className="space-y-2 rounded-lg border border-border/60 bg-muted/20 p-3">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <Layers3 className="h-4 w-4 text-primary" />
                        Pakiet wdrożeniowy
                      </div>
                      <div className={cn("inline-flex rounded-full border px-2 py-1 text-[10px]", bundleTone(project.bundle.status))}>
                        {humanize(project.bundle.status)}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Walidacja:{" "}
                        <span className={project.validation.success ? "text-sylion-green" : "text-sylion-red"}>
                          {project.validation.success ? "przeszła" : "nie przeszła"}
                        </span>
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Wyniki audytu: <span className="text-foreground">{project.audit.result_count}</span>
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Wyniki modułów: <span className="text-foreground">{project.module_output_count}</span>
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    {project.bundle.files.map((file) => (
                      <div key={file.key} className="rounded-lg border border-border/50 px-3 py-2">
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-xs font-medium">{file.label}</span>
                          <Badge variant="outline" className={cn("text-[10px]", file.exists ? "text-sylion-green" : "text-sylion-red")}>
                            {file.exists ? "JEST" : "BRAK"}
                          </Badge>
                        </div>
                        <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
                          {file.path || "nie wygenerowano"}
                        </p>
                      </div>
                    ))}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/50 pt-4">
                    <div className="text-xs text-muted-foreground">
                      {project.launched_at ? `Uruchomiono ${fmtDateTime(project.launched_at)}` : "Brak czasu uruchomienia"}
                    </div>
                    <Link
                      href={`/projects/${project.project_id}`}
                      className={buttonVariants({ variant: "outline", size: "sm" })}
                    >
                      Otwórz projekt
                      <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Oczekujące albo zablokowane</h2>
          <p className="text-sm text-muted-foreground">
            Konkretne powody, przez które projekt nie jest jeszcze gotowy do wdrożenia.
          </p>
        </div>

        {pendingProjects.length === 0 ? (
          <Card>
            <CardContent className="pt-4 text-xs text-muted-foreground">
              Żaden oczekujący projekt nie blokuje teraz powierzchni wdrożeń.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {pendingProjects.map((project) => (
              <Card key={project.project_id}>
                <CardHeader className="gap-2">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle className="text-base">{project.title || project.project_id}</CardTitle>
                      <CardDescription className="font-mono text-[11px]">{project.project_id}</CardDescription>
                    </div>
                    <Badge variant="outline" className="text-[10px]">
                      {humanize(project.launch_status || project.status)}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-start gap-2 rounded-lg border border-sylion-amber/20 bg-sylion-amber/10 p-3">
                    <AlertTriangle className="mt-0.5 h-4 w-4 text-sylion-amber" />
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-sylion-amber">Nie gotowe do wdrożenia</p>
                      <p className="text-xs text-muted-foreground">{humanize(project.reason)}</p>
                    </div>
                  </div>
                  <div className="grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
                    <div>Faza: <span className="text-foreground">{humanize(project.phase)}</span></div>
                    <div>Pytania oczekujące: <span className="text-foreground">{project.pending_question_count}</span></div>
                    <div>Ścieżka artefaktu: <span className="text-foreground">{project.artifact.path ? "zapisana" : "brak"}</span></div>
                    <div>Status pakietu: <span className="text-foreground">{humanize(project.bundle.status)}</span></div>
                  </div>
                  <div className="rounded-lg border border-border/50 bg-muted/20 p-3">
                    <p className="text-xs font-medium">Rekomendowana kolejna akcja</p>
                    <p className="mt-1 text-xs text-muted-foreground">{humanize(project.recommended_action)}</p>
                  </div>
                  <Link
                    href={`/projects/${project.project_id}`}
                    className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "px-0")}
                  >
                    Otwórz projekt
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Aktywna kolejka wydań</h2>
          <p className="text-sm text-muted-foreground">
            Wdrożenia środowiska wykonania aktualnie śledzone przez orkiestrator wdrożeń.
          </p>
        </div>

        {activeDeployments.length === 0 ? (
          <Card>
            <CardContent className="pt-4 text-xs text-muted-foreground">
              Brak aktywnych wpisów w kolejce wdrożeń.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {activeDeployments.map((deployment) => (
              <Card key={deployment.deployment_id}>
                <CardContent className="flex flex-col gap-3 pt-4 md:flex-row md:items-center md:justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Server className="h-4 w-4 text-primary" />
                      <span className="text-sm font-medium">{deployment.module_id}</span>
                      <Badge variant="outline" className="text-[10px]">
                        {humanize(deployment.strategy)}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {deployment.from_stage} {"->"} {deployment.to_stage}
                    </p>
                    <p className="font-mono text-[11px] text-muted-foreground">{deployment.deployment_id}</p>
                  </div>
                  <div className="grid gap-1 text-xs text-muted-foreground md:text-right">
                    <div>Status: <span className="text-foreground">{humanize(deployment.status)}</span></div>
                    <div>Aktualny krok: <span className="text-foreground">{humanize(deployment.step_summary.current_step || "complete")}</span></div>
                    <div>
                      Kroki: <span className="text-foreground">{deployment.step_summary.completed}/{deployment.step_summary.total}</span>
                    </div>
                    <div className="flex items-center gap-1 md:justify-end">
                      <Clock3 className="h-3 w-3" />
                      <span>{deployment.started_at ? fmtDateTime(deployment.started_at) : "nie rozpoczęto"}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Hetzner VPS: realne wdrożenie artefaktu</h2>
          <p className="text-sm text-muted-foreground">
            Ten panel używa zapisanego konektora Hetzner, tworzy prawdziwy VPS, publikuje artefakt przez nginx i wykonuje kontrolę zdrowia HTTP. Akcja jest finansowa i wymaga jawnego zaznaczenia zgody.
          </p>
        </div>

        <Card className="border-sylion-amber/20">
          <CardContent className="space-y-4 pt-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <label className="space-y-1 text-xs text-muted-foreground">
                Projekt do wdrożenia
                <select
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                  value={hetznerForm.project_id}
                  onChange={(event) => setHetznerForm((previous) => ({ ...previous, project_id: event.target.value }))}
                >
                  <option value="">Wybierz projekt gotowy do wdrożenia</option>
                  {readyProjects.map((project) => (
                    <option key={project.project_id} value={project.project_id}>
                      {project.title || project.project_id}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 text-xs text-muted-foreground">
                Konektor Hetzner
                <select
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                  value={hetznerForm.connector_id}
                  onChange={(event) => setHetznerForm((previous) => ({ ...previous, connector_id: event.target.value }))}
                >
                  <option value="">Wybierz zapisany konektor</option>
                  {hetznerConnectors.map((connector) => (
                    <option key={connector.connector_id} value={connector.connector_id}>
                      {connector.name || connector.connector_id}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 text-xs text-muted-foreground">
                Nazwa serwera
                <input
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                  value={hetznerForm.server_name}
                  placeholder="aeis-audit-idea6"
                  onChange={(event) => setHetznerForm((previous) => ({ ...previous, server_name: event.target.value }))}
                />
              </label>
              <label className="space-y-1 text-xs text-muted-foreground">
                Typ serwera
                <input
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                  value={hetznerForm.server_type}
                  onChange={(event) => setHetznerForm((previous) => ({ ...previous, server_type: event.target.value }))}
                />
              </label>
              <label className="space-y-1 text-xs text-muted-foreground">
                Lokalizacja
                <input
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                  value={hetznerForm.location}
                  onChange={(event) => setHetznerForm((previous) => ({ ...previous, location: event.target.value }))}
                />
              </label>
              <label className="space-y-1 text-xs text-muted-foreground">
                Obraz
                <input
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                  value={hetznerForm.image}
                  onChange={(event) => setHetznerForm((previous) => ({ ...previous, image: event.target.value }))}
                />
              </label>
              <label className="space-y-1 text-xs text-muted-foreground">
                Liczba środowisk
                <input
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                  type="number"
                  min={1}
                  max={10}
                  value={hetznerForm.environment_count}
                  onChange={(event) => setHetznerForm((previous) => ({ ...previous, environment_count: event.target.value }))}
                />
              </label>
              <label className="space-y-1 text-xs text-muted-foreground">
                VPS na środowisko
                <input
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                  type="number"
                  min={1}
                  max={10}
                  value={hetznerForm.vps_per_environment}
                  onChange={(event) => setHetznerForm((previous) => ({ ...previous, vps_per_environment: event.target.value }))}
                />
              </label>
            </div>

            <div className={cn(
              "rounded-lg border p-3 text-xs",
              plannedTotalVps > 10 ? "border-sylion-red/30 bg-sylion-red/10 text-sylion-red" : "border-sylion-amber/20 bg-sylion-amber/10 text-muted-foreground",
            )}>
              Planowana skala: <span className="font-medium text-foreground">{plannedEnvironmentCount}</span> środowisk ×{" "}
              <span className="font-medium text-foreground">{plannedVpsPerEnvironment}</span> VPS ={" "}
              <span className="font-medium text-foreground">{plannedTotalVps}</span> VPS. Limit jednego żądania: 10 VPS.
              {plannedTotalVps > 10 ? (
                <div className="mt-1 font-medium">
                  Zmniejsz liczbę VPS do maksymalnie 10 w jednym żądaniu.
                </div>
              ) : null}
            </div>

            <label className="flex items-start gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={hetznerForm.confirm_financial_action}
                onChange={(event) => setHetznerForm((previous) => ({ ...previous, confirm_financial_action: event.target.checked }))}
              />
              <span>Potwierdzam utworzenie płatnego zasobu Hetzner Cloud VPS dla tego testu audytu.</span>
            </label>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                onClick={() => void handleHetznerProvision()}
                disabled={
                  hetznerBusy === "provision"
                  || !hetznerForm.project_id
                  || !hetznerForm.connector_id
                  || !hetznerForm.confirm_financial_action
                  || plannedTotalVps > 10
                }
              >
                {hetznerBusy === "provision" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
                Utwórz VPS i wdróż artefakt
              </Button>
              <Button type="button" variant="outline" onClick={() => void refreshHetzner()}>
                Odśwież Hetzner
              </Button>
              <Link href="/connectors" className={buttonVariants({ variant: "ghost", size: "sm" })}>
                Zarządzaj konektorami
              </Link>
            </div>

            {hetznerMessage ? (
              <p className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">{hetznerMessage}</p>
            ) : null}
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          {hetznerDeployments.length === 0 ? (
            <Card>
              <CardContent className="pt-4 text-xs text-muted-foreground">
                Brak zarejestrowanych wdrożeń Hetzner w bieżącym profilu audytu.
              </CardContent>
            </Card>
          ) : (
            hetznerDeployments.map((deployment) => {
              const deploymentStatus = String(deployment.status || "").toLowerCase();
              const deletionState = deploymentStatus === "delete_requested" || deploymentStatus === "deleted";
              const probe = deletionState
                ? undefined
                : hetznerHealthProofs[deployment.deployment_id] ?? deployment.raw?.health_probe;
              const probeOk = Boolean(probe?.ok);
              return (
                <Card key={deployment.deployment_id}>
                <CardHeader>
                  <CardTitle className="text-base">{deployment.server_name}</CardTitle>
                  <CardDescription className="font-mono text-[11px]">{deployment.deployment_id}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid gap-1 text-xs text-muted-foreground">
                    <div>Projekt: <span className="text-foreground">{deployment.project_id}</span></div>
                    <div>Status: <span className="text-foreground">{humanize(deployment.status)}</span></div>
                    <div>IPv4: <span className="font-mono text-foreground">{deployment.public_ipv4 || "-"}</span></div>
                    <div>Adres kontroli zdrowia: <span className="font-mono text-foreground">{deployment.health_url || probe?.url || "-"}</span></div>
                    <div>SHA artefaktu: <span className="font-mono text-foreground">{shortHash(deployment.artifact_sha256)}</span></div>
                    <div>Środowisko: <span className="text-foreground">{deployment.raw?.environment_name || "-"}</span></div>
                    <div>Indeks VPS: <span className="text-foreground">{deployment.raw?.server_index || "-"}</span></div>
                    <div>Grupa wdrożenia: <span className="font-mono text-foreground">{deployment.raw?.deployment_group_id || "-"}</span></div>
                  </div>
                  <div className={cn(
                    "rounded-lg border p-3 text-xs",
                    probeOk ? "border-sylion-green/20 bg-sylion-green/10" : "border-border bg-muted/20",
                  )}>
                    <div className="font-medium">
                      Publiczny probe HTTP: <span className={probeOk ? "text-sylion-green" : "text-muted-foreground"}>{deletionState ? "WYŁĄCZONY PO ROLLBACKU" : probe ? (probe.ok ? "PRZECHODZI" : "NIE PRZECHODZI") : "nieuruchomiony"}</span>
                    </div>
                    <div className="mt-1 grid gap-1 text-muted-foreground">
                      <div>URL: <span className="font-mono text-foreground">{probe?.url || deployment.health_url || "-"}</span></div>
                      <div>Status HTTP: <span className="font-mono text-foreground">{typeof probe?.status_code === "number" ? probe.status_code : "-"}</span></div>
                      <div>Odpowiedź: <span className="font-mono text-foreground">{deletionState ? "VPS został usunięty albo oczekuje na usunięcie; wcześniejszy probe nie jest już dowodem aktywnego wdrożenia." : probe?.body_excerpt || probe?.error || "Kliknij kontrolę zdrowia, aby zapisać publiczny probe."}</span></div>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" size="sm" variant="outline" onClick={() => void handleHetznerHealth(deployment.deployment_id)} disabled={deletionState || hetznerBusy === deployment.deployment_id}>
                      Sprawdź zdrowie
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      onClick={() => void handleHetznerDelete(deployment.deployment_id)}
                      disabled={deletionState || hetznerBusy === deployment.deployment_id || !hetznerForm.confirm_delete}
                    >
                      {deletionState ? "Rollback wysłany" : "Usuń VPS / rollback"}
                    </Button>
                  </div>
                </CardContent>
                </Card>
              );
            })
          )}
        </div>

        <label className="flex items-start gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={hetznerForm.confirm_delete}
            onChange={(event) => setHetznerForm((previous) => ({ ...previous, confirm_delete: event.target.checked }))}
          />
          <span>Potwierdzam, że przyciski „Usuń VPS / rollback” mogą usunąć wskazany zasób Hetzner Cloud.</span>
        </label>
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Szablony provisioningu</h2>
          <p className="text-sm text-muted-foreground">
            Pliki pomocnicze generowane na żądanie. Wspierają planowanie i provisioning, ale nie są dowodem gotowego artefaktu wdrożeniowego.
          </p>
        </div>

        {topologięsError ? (
          <Card className="border-sylion-amber/30 bg-sylion-amber/10">
            <CardContent className="pt-4 text-xs text-muted-foreground">
              Pomocniki topologii są niedostępne: {topologięsError}
            </CardContent>
          </Card>
        ) : null}

        {topologięsLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Ładowanie pomocników topologii...
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {topologięs.map((variant) => (
            <Card key={variant.variant}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Server className="h-4 w-4" />
                  {humanize(variant.variant)}
                </CardTitle>
                <CardDescription>{variant.server_count} serwerów</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1">
                  {variant.servers.slice(0, 3).map((server) => (
                    <div key={server.name} className="text-xs text-muted-foreground">
                      {server.name} ({humanize(server.role)})
                    </div>
                  ))}
                  {variant.servers.length > 3 ? (
                    <div className="text-xs text-muted-foreground">
                      +{variant.servers.length - 3} więcej
                    </div>
                  ) : null}
                </div>

                <Button
                  size="sm"
                  className="w-full"
                  onClick={() => void handleGenerate(variant.variant)}
                  disabled={generating === variant.variant}
                >
                  {generating === variant.variant ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="mr-2 h-4 w-4" />
                  )}
                  Wygeneruj pliki
                </Button>

                {generated[variant.variant] ? (
                  <div className="space-y-1 border-t pt-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full justify-start text-xs"
                      onClick={() => downloadFile(generated[variant.variant].terraform, `main_${variant.variant}.tf`)}
                    >
                      Pobierz main.tf
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full justify-start text-xs"
                      onClick={() => downloadFile(generated[variant.variant].inventory, `inventory_${variant.variant}.ini`)}
                    >
                      Pobierz inventory.ini
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full justify-start text-xs"
                      onClick={() => downloadFile(generated[variant.variant].playbook, `playbook_${variant.variant}.yml`)}
                    >
                      Pobierz playbook.yml
                    </Button>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
