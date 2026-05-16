"use client";

import { Card } from "@/components/ui/card";
import { FolderSearch } from "lucide-react";

interface Props {
  projectId: string;
}

export function EmptyState({ projectId }: Props) {
  return (
    <Card className="flex flex-col items-center justify-center gap-2 border-dashed bg-card px-6 py-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted/30">
        <FolderSearch className="h-6 w-6 text-muted-foreground" />
      </div>
      <h2 className="text-base font-semibold">Brak danych lifecycle dla tego projektu</h2>
      <p className="max-w-md text-xs text-muted-foreground">
        Projekt <span className="font-mono">{projectId || "(brak)"}</span> nie wyemitowa? jeszcze żadnego
        z 16 hookow lifecycle. Po zakonczeniu onboardingu i przyjeciu pierwszego pomyslu aktywuje sie faza H01.
      </p>
    </Card>
  );
}
