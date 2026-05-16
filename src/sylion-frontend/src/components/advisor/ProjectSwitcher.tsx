"use client";

import { ChevronsUpDown, Plus, FolderOpen, Pencil } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { projectsApi, type Project } from "@/lib/api/projects";

interface Props {
  activeProjectId: string | null;
  onSelectProject: (id: string) => void;
  onNewProject: () => void;
}

export function ProjectSwitcher({ activeProjectId, onSelectProject, onNewProject }: Props) {
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    void projectsApi.list().then((all) => {
      const visible = all.filter(
        (p) => p.status !== "deleted" && p.status !== "archived",
      );
      setProjects(visible);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const active = projects.find((p) => p.project_id === activeProjectId);
  const activeName = active?.title ?? "— wybierz projekt —";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg border border-border bg-card/60 px-3 py-1.5 text-sm font-medium hover:border-blue-500/60 transition-colors"
        data-testid="cockpit-project-switcher"
      >
        <FolderOpen className="h-4 w-4 text-blue-400" />
        <span className="max-w-[200px] truncate">{loading ? "Ładowanie..." : activeName}</span>
        <ChevronsUpDown className="h-3.5 w-3.5 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1.5 w-80 rounded-xl border border-border bg-card shadow-2xl">
          <div className="border-b border-border p-2">
            <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Projekty ({projects.length})
            </p>
            <ul className="max-h-60 overflow-y-auto">
              {loading ? (
                <li className="px-3 py-2 text-xs text-muted-foreground">Ładowanie projektów...</li>
              ) : projects.length === 0 ? (
                <li className="px-3 py-2 text-xs text-muted-foreground">Brak projektów</li>
              ) : (
                projects.map((p) => (
                  <li key={p.project_id}>
                    <button
                      type="button"
                      onClick={() => {
                        onSelectProject(p.project_id);
                        setOpen(false);
                      }}
                      className={`flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-xs transition-colors hover:bg-blue-500/10 ${
                        p.project_id === activeProjectId
                          ? "bg-blue-500/15 text-blue-400"
                          : "text-foreground"
                      }`}
                    >
                      <span className="min-w-0 flex-1 truncate font-medium">{p.title}</span>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <StatusDot status={p.status} />
                        <span className="text-[10px] text-muted-foreground">{p.project_kind}</span>
                      </div>
                    </button>
                  </li>
                ))
              )}
            </ul>
          </div>
          <div className="space-y-0.5 p-2">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onNewProject();
              }}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold text-blue-400 transition-colors hover:bg-blue-500/10"
            >
              <Plus className="h-3.5 w-3.5" /> Nowy projekt
            </button>
            <Link
              href="/projects"
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs text-muted-foreground transition-colors hover:bg-card hover:text-foreground"
              onClick={() => setOpen(false)}
            >
              <FolderOpen className="h-3.5 w-3.5" /> Wszystkie projekty
            </Link>
            {active && (
              <Link
                href={`/projects/${active.project_id}`}
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-xs text-muted-foreground transition-colors hover:bg-card hover:text-foreground"
                onClick={() => setOpen(false)}
              >
                <Pencil className="h-3.5 w-3.5" /> Edytuj aktywny projekt
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function StatusDot({ status }: { status: Project["status"] }) {
  const colors: Record<string, string> = {
    active: "bg-green-500",
    in_progress: "bg-blue-400",
    draft: "bg-muted-foreground",
    blocked: "bg-red-500",
    completed: "bg-green-700",
    archived: "bg-muted-foreground",
    deleted: "bg-muted-foreground",
  };
  return (
    <span className={`inline-block h-1.5 w-1.5 rounded-full ${colors[status] ?? "bg-muted-foreground"}`} />
  );
}
