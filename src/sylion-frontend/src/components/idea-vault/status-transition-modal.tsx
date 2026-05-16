"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { IdeaStatus } from "@/lib/api/ideas";
import { STATUS_LABELS, TRANSITION_LABELS, setIdeaStatus } from "@/lib/api/ideas";
import type { Idea } from "@/lib/api/ideas";
import { StatusBadge } from "./status-badge";

const DANGEROUS: IdeaStatus[] = ["deleted_soft", "deleted_hard", "rejected", "abandoned"];
const HG_TRANSITION: IdeaStatus = "awaiting_approval";

interface StatusTransitionModalProps {
  open: boolean;
  idea: Idea | null;
  targetStatus: IdeaStatus | null;
  onClose: () => void;
  onTransitioned: (idea: Idea) => void;
}

export function StatusTransitionModal({
  open,
  idea,
  targetStatus,
  onClose,
  onTransitioned,
}: StatusTransitionModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDangerous = targetStatus ? DANGEROUS.includes(targetStatus) : false;
  const isHGHandoff = targetStatus === HG_TRANSITION;

  async function handleConfirm() {
    if (!idea || !targetStatus) return;
    setError(null);
    setLoading(true);
    try {
      const updated = await setIdeaStatus(idea.idea_id, targetStatus);
      onTransitioned(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd podczas zmiany statusu");
    } finally {
      setLoading(false);
    }
  }

  function handleClose() {
    setError(null);
    onClose();
  }

  if (!idea || !targetStatus) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="max-w-sm bg-card border border-border/60">
        <DialogHeader>
          <DialogTitle className="text-base font-semibold">
            {TRANSITION_LABELS[targetStatus] ?? `Zmien status na: ${STATUS_LABELS[targetStatus]}`}
          </DialogTitle>
        </DialogHeader>

        <div className="mt-2 space-y-3">
          <p className="text-sm text-muted-foreground">
            Pomysl:{" "}
            <span className="text-foreground font-medium">{idea.title}</span>
          </p>

          <div className="flex items-center gap-2 text-sm">
            <StatusBadge status={idea.status} />
            <span className="text-muted-foreground/60">-&gt;</span>
            <StatusBadge status={targetStatus} />
          </div>

          {isHGHandoff && (
            <div className="rounded-md border border-orange-400/20 bg-orange-400/5 px-3 py-2 text-xs text-orange-400">
              Spowoduje to utworzenie wniosku w Human Gate.
              Operator będzie musiał zatwierdzić lub odrzucić pomysł
              przed przejsciem do kolejnego etapu.
            </div>
          )}

          {isDangerous && (
            <div className={cn(
              "rounded-md border px-3 py-2 text-xs",
              targetStatus === "deleted_soft"
                ? "border-red-400/20 bg-red-400/5 text-red-400"
                : "border-red-600/20 bg-red-600/5 text-red-500"
            )}>
              {targetStatus === "deleted_soft"
                ? "Pomysl zostanie przeniesiony do kosza. Mozna go odtworzyc przez 30 dni."
                : targetStatus === "deleted_hard"
                ? "Trwałe usunięcie jest nieodwracalne. Historia audytu zostanie zachowana."
                : `Zmiana na status "${STATUS_LABELS[targetStatus]}" jest trudna do cofniecia.`}
            </div>
          )}

          {error && (
            <p className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex gap-2 justify-end pt-1">
            <Button variant="ghost" size="sm" onClick={handleClose} disabled={loading}>
              Anuluj
            </Button>
            <Button
              size="sm"
              variant={isDangerous ? "destructive" : "default"}
              onClick={handleConfirm}
              disabled={loading}
            >
              {loading && <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />}
              Potwierdz
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
