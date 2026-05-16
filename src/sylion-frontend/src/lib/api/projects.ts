const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function readJson<T>(res: Response, fallback: T): Promise<T> {
  const text = await res.text().catch(() => "");
  if (!text.trim()) return fallback;
  try {
    return JSON.parse(text) as T;
  } catch {
    return fallback;
  }
}

export interface ProjectAttachment {
  attachment_id: string;
  filename: string;
  file_type: string;
  file_size: number;
}

export interface Project {
  project_id: string;
  title: string;
  idea: string;
  constraints?: string;
  owner_id?: string;
  team_id?: string;
  project_kind:
    | "application"
    | "research"
    | "audit"
    | "funding"
    | "internal_tool"
    | "experiment"
    | "production"
    | "operator_mobile"
    | "design_tool"
    | "dashboard"
    | "chat_app"
    | "other";
  project_domain?: string;
  status: "draft" | "active" | "in_progress" | "blocked" | "completed" | "archived" | "deleted";
  phase?: string;
  approvals?: { book?: boolean; operating_model?: boolean };
  preferred_stack?: string[];
  attachments?: ProjectAttachment[];
  created_at?: number;
  updated_at?: number;
}

export interface CreateProjectPayload extends Partial<Project> {
  onboarding_config?: Record<string, unknown>;
}

export const projectsApi = {
  list: async (status?: string): Promise<Project[]> => {
    const url = `${API_BASE}/api/v1/projects${status ? `?status=${status}` : ""}`;
    const res = await fetch(url).catch(() => null);
    if (!res?.ok) return [];
    const data = await readJson<{ projects?: Project[] }>(res, {});
    return data.projects ?? [];
  },
  get: async (id: string): Promise<Project | null> => {
    const res = await fetch(`${API_BASE}/api/v1/projects/${id}`).catch(() => null);
    if (!res?.ok) return null;
    return readJson<Project | null>(res, null);
  },
  create: async (payload: CreateProjectPayload): Promise<Project | null> => {
    // F-RUNTIME-001: backend `CreateProjectRequest` uses `name` and `idea_raw`
    // while the frontend `Project` type uses `title` and `idea`. Translate
    // here so existing UI types stay user-friendly.
    const backendPayload: Record<string, unknown> = {
      name: payload.title ?? "",
      idea_raw: payload.idea ?? "",
      constraints: payload.constraints ?? "",
      preferred_stack: payload.preferred_stack ?? [],
      attachments: payload.attachments ?? [],
      onboarding_config: payload.onboarding_config ?? {},
      project_kind: payload.project_kind ?? "",
      project_domain: payload.project_domain ?? "",
      owner_id: payload.owner_id ?? "workspace-default",
      team_id: payload.team_id ?? "",
    };
    const res = await fetch(`${API_BASE}/api/v1/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(backendPayload),
    }).catch(() => null);
    if (!res?.ok) return null;
    const data = await readJson<any>(res, null);
    if (!data) return null;
    // Backend returns project record with `idea` field (not `idea_raw`) — map back if needed.
    const project = data.project ?? data;
    return {
      ...project,
      title: project.title ?? project.name ?? payload.title ?? "",
      idea: project.idea ?? project.idea_raw ?? payload.idea ?? "",
    } as Project;
  },
  update: async (id: string, patch: Partial<Project>): Promise<Project | null> => {
    const res = await fetch(`${API_BASE}/api/v1/projects/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).catch(() => null);
    if (!res?.ok) return null;
    return readJson<Project | null>(res, null);
  },
};
