"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowRight, Compass, Layers, Tag } from "lucide-react";
import type { ProjectLifecycleState } from "@/lib/api/advisor";

interface Props {
  lifecycle: ProjectLifecycleState | null;
  projectId: string;
}

export function LifecycleHeader({ lifecycle, projectId }: Props) {
  const projectType = lifecycle?.project_type ?? "—";
  const projectDomain = lifecycle?.project_domain ?? "—";

  return (
    <Card className="flex flex-wrap items-center justify-between gap-3 bg-card p-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
          <Compass className="h-5 w-5 text-primary" />
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold tracking-tight">Lifecycle projektu</h1>
          <p className="truncate text-xs text-muted-foreground">
            Widok doradcy 16 faz dla projektu <span className="font-mono">{projectId}</span>
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="gap-1 border-sylion-blue/30 text-sylion-blue">
          <Layers className="h-3 w-3" />
          {projectType}
        </Badge>
        <Badge variant="outline" className="gap-1 border-sylion-amber/30 text-sylion-amber">
          <Tag className="h-3 w-3" />
          {projectDomain}
        </Badge>
        <Link href="/agents" data-testid="tech-mode-link">
          <Button variant="outline" size="sm" className="gap-1">
            Przejdz do trybu technicznego
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </Link>
      </div>
    </Card>
  );
}
