"use client";

import { useState, useEffect, createContext, useContext, useCallback } from "react";
import { projectsApi } from "@/lib/api/projects";
import { ProjectSwitcher } from "./ProjectSwitcher";
import { NewProjectModal } from "./NewProjectModal";
import { RecentProjectsStrip } from "./RecentProjectsStrip";
import type { Project } from "@/lib/api/projects";

const LS_KEY = "sylion.cockpit.active_project";

interface ProjectHubCtx {
  activeProjectId: string | null;
  setActiveProjectId: (id: string) => void;
  showNewModal: boolean;
  setShowNewModal: (v: boolean) => void;
}

const ProjectHubContext = createContext<ProjectHubCtx>({
  activeProjectId: null,
  setActiveProjectId: () => {},
  showNewModal: false,
  setShowNewModal: () => {},
});

export function useProjectHub() {
  return useContext(ProjectHubContext);
}

interface HeroRowProps {
  activeProjectId: string | null;
  onSelectProject: (id: string) => void;
  onNewProject: () => void;
}

export function ProjectHubHeroRow({ activeProjectId, onSelectProject, onNewProject }: HeroRowProps) {
  return (
    <ProjectSwitcher
      activeProjectId={activeProjectId}
      onSelectProject={onSelectProject}
      onNewProject={onNewProject}
    />
  );
}

interface StripProps {
  activeProjectId: string | null;
  onSelectProject: (id: string) => void;
}

export function ProjectHubStrip({ activeProjectId, onSelectProject }: StripProps) {
  return (
    <RecentProjectsStrip
      activeProjectId={activeProjectId}
      onSelectProject={onSelectProject}
    />
  );
}

interface ProviderProps {
  children: (ctx: ProjectHubCtx) => React.ReactNode;
}

export function ProjectHubProvider({ children }: ProviderProps) {
  const [activeProjectId, setActiveProjectIdState] = useState<string | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [bootstrapped, setBootstrapped] = useState(false);

  useEffect(() => {
    const stored = typeof localStorage !== "undefined"
      ? localStorage.getItem(LS_KEY)
      : null;

    if (stored) {
      setActiveProjectIdState(stored);
      setBootstrapped(true);
    } else {
      void projectsApi.list().then((all) => {
        const first = all.find((p) => p.status === "active" || p.status === "in_progress") ?? all[0] ?? null;
        if (first) {
          setActiveProjectIdState(first.project_id);
          localStorage.setItem(LS_KEY, first.project_id);
        }
        setBootstrapped(true);
      });
    }
  }, []);

  const setActiveProjectId = useCallback((id: string) => {
    setActiveProjectIdState(id);
    localStorage.setItem(LS_KEY, id);
  }, []);

  const handleCreated = useCallback((p: Project) => {
    setActiveProjectId(p.project_id);
    setShowNewModal(false);
  }, [setActiveProjectId]);

  const ctx: ProjectHubCtx = {
    activeProjectId,
    setActiveProjectId,
    showNewModal,
    setShowNewModal,
  };

  if (!bootstrapped) return null;

  return (
    <ProjectHubContext.Provider value={ctx}>
      {children(ctx)}
      <NewProjectModal
        open={showNewModal}
        onClose={() => setShowNewModal(false)}
        onCreated={handleCreated}
      />
    </ProjectHubContext.Provider>
  );
}
