"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FolderOpen, AlertCircle, CheckCircle2, Clock, CircleDot, ArrowRight } from "lucide-react";
import { projectsApi, type Project } from "@/lib/api/projects";

interface Props {
  activeProjectId: string | null;
  onSelectProject: (id: string) => void;
}

function fmt(ts?: number): string {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  const now = Date.now();
  const diff = now - d.getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m temu`;
  const hrs = Math.floor(diff / 3_600_000);
  if (hrs < 24) return `${hrs}h temu`;
  return d.toLocaleDateString("pl", { day: "numeric", month: "short" });
}

const STATUS_CONFIG: Record<
  Project["status"],
  { label: string; icon: React.ElementType; cls: string }
> = {
  active:      { label: "Aktywny",   icon: CircleDot,    cls: "text-green-400 bg-green-500/10 border-green-500/20" },
  in_progress: { label: "W toku",    icon: CircleDot,    cls: "text-blue-400 bg-blue-500/10 border-blue-500/20" },
  draft:       { label: "Szkic",     icon: Clock,        cls: "text-muted-foreground bg-muted/50 border-border" },
  blocked:     { label: "Zablok.",   icon: AlertCircle,  cls: "text-red-400 bg-red-500/10 border-red-500/20" },
  completed:   { label: "Gotowy",    icon: CheckCircle2, cls: "text-green-600 bg-green-900/20 border-green-600/20" },
  archived:    { label: "Arch.",     icon: FolderOpen,   cls: "text-muted-foreground bg-muted/40 border-border" },
  deleted:     { label: "Usuniety", icon: FolderOpen,   cls: "text-muted-foreground bg-muted/40 border-border" },
};

export function RecentProjectsStrip({ activeProjectId, onSelectProject }: Props) {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void projectsApi.list().then((all) => {
      const sorted = all
        .filter((p) => p.status !== "deleted")
        .sort((a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0))
        .slice(0, 5);
      setProjects(sorted);
      setLoading(false);
    });
  }, []);

  // F-bug-cockpit: clicking a project card now (a) marks it active in
  // cockpit context AND (b) navigates to the project detail page. Before:
  // it only updated local state, so the click felt dead.
  const handleSelect = (projectId: string) => {
    onSelectProject(projectId);
    router.push(`/projects/${encodeURIComponent(projectId)}`);
  };

  if (loading) {
    return (
      <div className="flex gap-3 overflow-x-auto pb-1">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 w-52 shrink-0 animate-pulse rounded-xl border border-border bg-card/40" />
        ))}
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/20 px-6 py-4 text-sm text-muted-foreground">
        Brak projektów. Użyj &ldquo;Nowy projekt&rdquo; aby zacząć.
      </div>
    );
  }

  return (
    <div className="flex items-stretch gap-3 overflow-x-auto pb-1">
      {projects.map((p) => {
        const cfg = STATUS_CONFIG[p.status] ?? STATUS_CONFIG.draft;
        const Icon = cfg.icon;
        const isActive = p.project_id === activeProjectId;
        return (
          <button
            key={p.project_id}
            type="button"
            onClick={() => handleSelect(p.project_id)}
            className={`flex w-52 shrink-0 flex-col gap-2 rounded-xl border p-3.5 text-left transition-all hover:shadow-md ${
              isActive
                ? "border-blue-500/50 bg-blue-500/10 shadow-blue-500/5"
                : "border-border bg-card/60 hover:border-border/80 hover:bg-card"
            }`}
          >
            <div className="flex items-start justify-between gap-1">
              <span className="line-clamp-2 text-xs font-semibold leading-snug">{p.title}</span>
              <span
                className={`ml-1 flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${cfg.cls}`}
              >
                <Icon className="h-2.5 w-2.5" />
                {cfg.label}
              </span>
            </div>
            <div className="flex items-center justify-between gap-1 text-[10px] text-muted-foreground">
              <span className="rounded bg-muted/60 px-1 py-0.5">{p.project_kind}</span>
              <span>{fmt(p.updated_at)}</span>
            </div>
          </button>
        );
      })}
      <Link
        href="/projects"
        className="flex w-32 shrink-0 flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed border-border bg-transparent text-xs text-muted-foreground transition-colors hover:border-blue-400/40 hover:text-blue-400"
      >
        <ArrowRight className="h-4 w-4" />
        <span>Wszystkie</span>
      </Link>
    </div>
  );
}
