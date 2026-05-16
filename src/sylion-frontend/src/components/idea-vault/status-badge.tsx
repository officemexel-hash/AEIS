"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { IdeaStatus } from "@/lib/api/ideas";
import { STATUS_LABELS } from "@/lib/api/ideas";

const STATUS_VARIANTS: Record<IdeaStatus, string> = {
  draft: "border-muted-foreground/30 text-muted-foreground bg-muted/20",
  created: "border-blue-400/30 text-blue-400 bg-blue-400/5",
  clarification: "border-amber-400/30 text-amber-400 bg-amber-400/5",
  submitted: "border-blue-500/30 text-blue-500 bg-blue-500/5",
  council_review: "border-purple-400/30 text-purple-400 bg-purple-400/5",
  awaiting_approval: "border-orange-400/30 text-orange-400 bg-orange-400/5",
  accepted: "border-green-400/30 text-green-400 bg-green-400/5",
  approved: "border-green-500/30 text-green-500 bg-green-500/5",
  implemented: "border-emerald-400/30 text-emerald-400 bg-emerald-400/5",
  rejected: "border-red-400/30 text-red-400 bg-red-400/5",
  stale: "border-yellow-600/30 text-yellow-600 bg-yellow-600/5",
  abandoned: "border-muted-foreground/20 text-muted-foreground/60 bg-muted/10",
  archived: "border-slate-400/30 text-slate-400 bg-slate-400/5",
  deleted_soft: "border-red-300/20 text-red-300/60 bg-red-300/5",
  deleted_hard: "border-red-600/30 text-red-600 bg-red-600/5",
};

interface StatusBadgeProps {
  status: IdeaStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-[10px] font-medium px-1.5 py-0 border",
        STATUS_VARIANTS[status] ?? STATUS_VARIANTS.draft,
        className
      )}
    >
      {STATUS_LABELS[status] ?? status}
    </Badge>
  );
}
