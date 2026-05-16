"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Sparkles, RefreshCw, AlertOctagon } from "lucide-react";

interface Props {
  totalCards: number;
  filteredCount: number;
  source: "live" | "error" | "loading";
  criticalCount: number;
  onRefresh: () => void;
}

export function FeedHeader({ totalCards, filteredCount, source, criticalCount, onRefresh }: Props) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
          <Sparkles className="h-4 w-4 text-primary" />
        </div>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Strumień Doradcy</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Karty rekomendacji na żywo ze wszystkich aktywnych cykli życia projektów.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant="outline"
          data-testid="feed-source-indicator"
          className={cn(
            "text-[10px]",
            source === "live"
              ? "border-sylion-green/30 text-sylion-green"
              : source === "error"
                ? "border-sylion-red/30 text-sylion-red"
                : "border-muted-foreground/30 text-muted-foreground",
          )}
        >
          <span
            className={cn(
              "mr-1.5 inline-block h-1.5 w-1.5 rounded-full",
              source === "live" ? "bg-sylion-green" : source === "error" ? "bg-sylion-red" : "bg-muted-foreground",
            )}
          />
          {source === "live" ? "NA ŻYWO" : source === "error" ? "BŁĄD" : "ŁADOWANIE"}
        </Badge>
        <Badge variant="outline" className="text-[10px] text-muted-foreground" data-testid="feed-count-total">
          {filteredCount} / {totalCards} kart
        </Badge>
        {criticalCount > 0 ? (
          <Badge
            variant="outline"
            data-testid="feed-count-critical"
            className="border-sylion-red/30 text-[10px] text-sylion-red"
          >
            <AlertOctagon className="mr-1 h-3 w-3" />
            {criticalCount} krytyczne
          </Badge>
        ) : null}
        <Button variant="outline" size="sm" onClick={onRefresh} data-testid="feed-refresh">
          <RefreshCw className="h-3.5 w-3.5" />
          Odśwież
        </Button>
      </div>
    </div>
  );
}
