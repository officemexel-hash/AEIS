import type { FullConfig } from "@playwright/test";

type SeedResult = {
  kind: "proposal" | "programme" | "call" | "project" | "application" | "build" | "deployment";
  id: string;
};

type JsonRecord = Record<string, unknown>;

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";
const STATE_ENV_KEY = "PLAYWRIGHT_SEED_STATE";
const RUN_ID_ENV_KEY = "PLAYWRIGHT_SEED_RUN_ID";

function getBackendUrl(): string {
  return process.env.BACKEND_URL?.trim() || DEFAULT_BACKEND_URL;
}

function toIsoDate(offsetDays = 0): string {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() + offsetDays);
  return value.toISOString().slice(0, 10);
}

async function parseJson(response: Response): Promise<JsonRecord> {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text) as JsonRecord;
  } catch {
    return { raw: text };
  }
}

async function fetchJson(
  path: string,
  init?: RequestInit,
  searchParams?: Record<string, string | number | boolean | undefined>,
): Promise<{ response: Response; data: JsonRecord }> {
  const url = new URL(path, getBackendUrl());
  for (const [key, value] of Object.entries(searchParams ?? {})) {
    if (value !== undefined) {
      url.searchParams.set(key, String(value));
    }
  }

  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const data = await parseJson(response);
  return { response, data };
}

async function postWithFallback(
  path: string,
  body: JsonRecord,
  queryFallback?: Record<string, string | number | boolean | undefined>,
): Promise<{ response: Response; data: JsonRecord }> {
  const primary = await fetchJson(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (primary.response.ok) {
    return primary;
  }

  if (!queryFallback) {
    return primary;
  }

  return fetchJson(path, { method: "POST" }, queryFallback);
}

function requireId(data: JsonRecord, keys: string[]): string {
  for (const key of keys) {
    const value = data[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  throw new Error(`Missing identifier in response. Expected one of: ${keys.join(", ")}`);
}

async function seedProposals(seedRunId: string): Promise<SeedResult[]> {
  const variants = [
    { scope: "pipeline", level: "D0" },
    { scope: "security", level: "D1" },
    { scope: "council", level: "D2" },
  ];

  const results: SeedResult[] = [];

  for (const variant of variants) {
    const payload = {
      title: `[seed:${seedRunId}] ${variant.level} live proposal`,
      description: `Playwright live-data seed for ${variant.level}. seed_run_id=${seedRunId}`,
      scope: variant.scope,
      source_plan: variant.level,
      proposed_by: "playwright-global-setup",
    };

    const { response, data } = await postWithFallback("/api/v1/governance/proposals", payload, {
      title: String(payload.title),
      description: String(payload.description),
      scope: String(payload.scope),
      source_plan: String(payload.source_plan),
      proposed_by: String(payload.proposed_by),
    });

    if (!response.ok) {
      throw new Error(`Failed to seed proposal ${variant.level}: ${response.status} ${JSON.stringify(data)}`);
    }

    results.push({
      kind: "proposal",
      id: requireId(data, ["proposal_id", "id"]),
    });
  }

  return results;
}

async function seedFunding(seedRunId: string): Promise<SeedResult[]> {
  const country = "Poland";
  const programmeName = `Seed programme ${seedRunId}`;
  const callCode = `SEED-${seedRunId.slice(-8).toUpperCase()}`;
  const closesAt = Date.parse(`${toIsoDate(180)}T12:00:00.000Z`) / 1000;

  const programmePayload = {
    source_id: "manual",
    name: programmeName,
    country,
    institution: "PARP",
    funding_type: "grant",
    summary: `Playwright live-data seed. seed_run_id=${seedRunId}`,
  };
  const programme = await fetchJson("/api/v1/funding/programmes", {
    method: "POST",
    body: JSON.stringify(programmePayload),
  });
  if (!programme.response.ok) {
    throw new Error(`Failed to seed funding programme: ${programme.response.status} ${JSON.stringify(programme.data)}`);
  }
  const programmeId = requireId(programme.data, ["programme_id"]);

  const callPayload = {
    programme_id: programmeId,
    title: `Seed funding call ${seedRunId}`,
    code: callCode,
    country,
    portal_url: `https://portal.example.test/${seedRunId}`,
    closes_at: closesAt,
    min_project_budget: 250000,
    max_project_budget: 2500000,
    grant_intensity_pct: 60,
    trl_min: 4,
    trl_max: 8,
    target_beneficiaries: ["sme", "mid-cap"],
    themes: ["AI", "automation", `seed_run_id:${seedRunId}`],
    required_documents: [
      "financial_statement",
      "tax_clearance",
      "social_security_clearance",
      "incorporation_document",
    ],
    required_partner_types: ["research_institute"],
    eligible_costs: ["personnel", "equipment", "subcontracting"],
  };
  const call = await fetchJson("/api/v1/funding/calls", {
    method: "POST",
    body: JSON.stringify(callPayload),
  });
  if (!call.response.ok) {
    throw new Error(`Failed to seed funding call: ${call.response.status} ${JSON.stringify(call.data)}`);
  }
  const callId = requireId(call.data, ["call_id"]);

  const results: SeedResult[] = [
    { kind: "programme", id: programmeId },
    { kind: "call", id: callId },
  ];

  for (const index of [1, 2]) {
    const projectPayload = {
      company_id: "default",
      title: `Seed funding project ${index} ${seedRunId}`,
      summary: `Live-data seed project ${index}. seed_run_id=${seedRunId}`,
      objective: `Validate live CRM/application rendering ${index}`,
      category: "projekt AI",
      budget_total: 500000 + index * 100000,
      grant_requested: 300000 + index * 50000,
      trl: 5,
      call_id: callId,
    };
    const project = await fetchJson("/api/v1/funding/projects", {
      method: "POST",
      body: JSON.stringify(projectPayload),
    });
    if (!project.response.ok) {
      throw new Error(`Failed to seed funding project ${index}: ${project.response.status} ${JSON.stringify(project.data)}`);
    }

    const projectRecord = (project.data.project ?? {}) as JsonRecord;
    const projectId = requireId(projectRecord, ["project_id"]);
    results.push({ kind: "project", id: projectId });

    const applicationPayload = {
      project_id: projectId,
      company_id: "default",
      call_id: callId,
    };
    const application = await fetchJson("/api/v1/funding/application/create", {
      method: "POST",
      body: JSON.stringify(applicationPayload),
    });
    if (!application.response.ok) {
      throw new Error(
        `Failed to seed funding application ${index}: ${application.response.status} ${JSON.stringify(application.data)}`,
      );
    }

    results.push({
      kind: "application",
      id: requireId(application.data, ["application_id"]),
    });
  }

  return results;
}

async function seedBuild(seedRunId: string): Promise<SeedResult> {
  const payload = {
    name: `Seed build ${seedRunId}`,
    description: `Playwright live-data seed build. seed_run_id=${seedRunId}`,
    patch_ids: [`seed-patch-${seedRunId}`],
    module_ids: ["core.worker"],
    metadata: {
      seed_run_id: seedRunId,
      seeded_by: "playwright-global-setup",
    },
  };

  const build = await fetchJson("/api/v1/integration/builds", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!build.response.ok) {
    throw new Error(`Failed to seed candidate build: ${build.response.status} ${JSON.stringify(build.data)}`);
  }

  return {
    kind: "build",
    id: requireId(build.data, ["build_id"]),
  };
}

async function seedDeployment(seedRunId: string): Promise<SeedResult> {
  const moduleId = `seed.module.${seedRunId.replace(/[^a-zA-Z0-9]/g, "_")}`;
  const deployment = await fetchJson(
    "/api/v1/deployments",
    { method: "POST" },
    {
      module_id: moduleId,
      from_stage: "draft",
      to_stage: "build",
      strategy: "canary",
    },
  );
  if (!deployment.response.ok) {
    throw new Error(`Failed to seed deployment: ${deployment.response.status} ${JSON.stringify(deployment.data)}`);
  }

  return {
    kind: "deployment",
    id: requireId(deployment.data, ["deployment_id"]),
  };
}

export default async function globalSetup(_config: FullConfig): Promise<void> {
  const seedRunId = new Date().toISOString().replace(/[^\dTZ]/g, "");
  process.env[RUN_ID_ENV_KEY] = seedRunId;

  const health = await fetchJson("/health");
  if (!health.response.ok) {
    throw new Error(`Backend health check failed: ${health.response.status} ${JSON.stringify(health.data)}`);
  }

  const seeded: SeedResult[] = [];
  seeded.push(...await seedProposals(seedRunId));
  seeded.push(...await seedFunding(seedRunId));

  try {
    seeded.push(await seedBuild(seedRunId));
  } catch {
    seeded.push(await seedDeployment(seedRunId));
  }

  process.env[STATE_ENV_KEY] = JSON.stringify({
    backendUrl: getBackendUrl(),
    seed_run_id: seedRunId,
    seeded,
    created_at: new Date().toISOString(),
  });

  console.log(
    `[playwright-global-setup] Seeded ${seeded.length} records for ${seedRunId} against ${getBackendUrl()}`,
  );
}
