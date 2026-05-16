"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Trash2, Eye, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Idea } from "@/lib/api/ideas";
import { DOMAIN_LABELS, getDomain, getDisplayTags, isStaleIdea, type Domain } from "@/lib/api/ideas";
import { StatusBadge } from "./status-badge";

function formatRelative(ts: number): string {
  if (!ts) return "--";
  const diff = Date.now() - ts * 1000;
  if (diff < 60000) return "przed chwilą";
  if (diff < 3600000) return `${Math.floor(diff / 60000)} min temu`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} h temu`;
  return `${Math.floor(diff / 86400000)} d temu`;
}

interface IdeaCardProps {
  idea: Idea;
  onView: (idea: Idea) => void;
  onSoftDelete: (idea: Idea) => void;
  className?: string;
}

export function IdeaCard({ idea, onView, onSoftDelete, className }: IdeaCardProps) {
  const stale = isStaleIdea(idea);
  const domain = getDomain(idea);
  const domainLabel = domain && domain in DOMAIN_LABELS
    ? DOMAIN_LABELS[domain as Domain]
    : domain;
  const displayTags = getDisplayTags(idea);
  const inTrash = idea.status === "deleted_soft";

  return (
    <Card
      className={cn(
        "group relative px-4 py-3 border border-border/40 bg-card/60 hover:bg-card/80",
        "transition-all duration-150 hover:border-border/70",
        inTrash && "opacity-60",
        className
      )}
    >
      <div className="flex items-start gap-3">
        {/* Left: stale indicator */}
        {stale && (
          <span className="mt-0.5 shrink-0">
            <AlertTriangle className="w-3.5 h-3.5 text-yellow-600" />
          </span>
        )}

        {/* Middle: content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-foreground truncate max-w-xs">
              {idea.title || "(bez tytułu)"}
            </span>
            <StatusBadge status={idea.status} />
            {stale && (
              <span className="text-[10px] text-yellow-600 border border-yellow-600/30 px-1.5 py-0 rounded-full">
                nieaktywny
              </span>
            )}
          </div>

          <div className="mt-1 flex items-center gap-3 flex-wrap text-[11px] text-muted-foreground">
            {domainLabel && (
              <span>{domainLabel}</span>
            )}
            {displayTags.slice(0, 3).map((tag) => (
              <span key={tag} className="bg-muted/40 px-1.5 py-0 rounded text-[10px]">
                {tag}
              </span>
            ))}
            {displayTags.length > 3 && (
              <span className="text-[10px] text-muted-foreground/60">
                +{displayTags.length - 3}
              </span>
            )}
          </div>

          <div className="mt-1 text-[11px] text-muted-foreground/50">
            Utworzony {formatRelative(idea.created_at)}
            {idea.updated_at !== idea.created_at && (
              <> &middot; edytowany {formatRelative(idea.updated_at)}</>
            )}
            {idea.author && <> &middot; {idea.author}</>}
          </div>
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          {idea.status !== "deleted_soft" && idea.status !== "deleted_hard" && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-red-400 hover:bg-red-400/10"
              onClick={(e) => { e.stopPropagation(); onSoftDelete(idea); }}
              title="Przenieś do kosza"
            >
              <Trash2 className="w-3 h-3" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-muted-foreground hover:text-primary hover:bg-primary/10"
            onClick={(e) => { e.stopPropagation(); onView(idea); }}
            title="Szczegóły"
          >
            <Eye className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Clickable overlay */}
      <button
        className="absolute inset-0 rounded-xl"
        onClick={() => onView(idea)}
        aria-label={`Otwórz: ${idea.title}`}
      />
    </Card>
  );
}
