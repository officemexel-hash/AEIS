"use client";

import { Card } from "@/components/ui/card";
import { Sparkles } from "lucide-react";

interface Props {
  filtered: boolean;
}

export function EmptyState({ filtered }: Props) {
  return (
    <Card className="flex flex-col items-center justify-center gap-3 border-dashed border-border/60 bg-card/50 p-10 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sylion-blue/10">
        <Sparkles className="h-5 w-5 text-sylion-blue" />
      </div>
      <div className="space-y-1">
        <h2 className="text-sm font-semibold">
          {filtered ? "Brak kart pasujących do filtrów" : "Brak aktywnych rekomendacji"}
        </h2>
        <p className="max-w-md text-xs text-muted-foreground">
          {filtered
            ? "Wyczyść filtry ryzyka, domeny lub historii powyżej, aby rozszerzyć widok."
            : "Doradca pokaże tu rekomendacje, gdy tylko zadziała pierwszy hook cyklu życia. Pracuj dalej — karty pojawiają się w czasie rzeczywistym."}
        </p>
      </div>
    </Card>
  );
}
