"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  ArrowLeft, Edit2, Check, Loader2, Trash2, RotateCcw,
  Clock, ChevronRight, ExternalLink, AlertTriangle,
  MessageSquarePlus, Rocket, Sparkles, FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  getIdea, updateIdea, setIdeaStatus, hardDeleteIdea,
  getIdeaHistory, getDomain, getDisplayTags,
  ALLOWED_TRANSITIONS, TRANSITION_LABELS, STATUS_LABELS,
  DOMAIN_LABELS, canHardDelete, isStaleIdea,
  startIdeaDiscussion, getIdeaDiscussion, promoteIdeaToProject,
  submitClarificationAnswer, listIdeaAttachments,
  analyzeIdeaAttachments, listIdeaAttachmentAnalysis,
} from "@/lib/api/ideas";
import type {
  Idea, IdeaStatus, IdeaLifecycleEntry, IdeaDiscussionSession,
  IdeaAttachment, IdeaAttachmentAnalysis,
} from "@/lib/api/ideas";
import { HelpTip } from "@/components/common/HelpTip";
import { StatusBadge } from "@/components/idea-vault/status-badge";
import { StatusTransitionModal } from "@/components/idea-vault/status-transition-modal";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTs(ts: number): string {
  if (!ts) return "--";
  return new Date(ts * 1000).toLocaleString("pl-PL", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function formatRelative(ts: number): string {
  if (!ts) return "--";
  const diff = Date.now() - ts * 1000;
  if (diff < 60000) return "przed chwilą";
  if (diff < 3600000) return `${Math.floor(diff / 60000)} min temu`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} h temu`;
  return `${Math.floor(diff / 86400000)} d temu`;
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const PRIORITY_LABELS: Record<string, string> = {
  low: "niski",
  normal: "normalny",
  medium: "średni",
  high: "wysoki",
  urgent: "pilny",
  critical: "krytyczny",
};

const ATTACHMENT_KIND_LABELS: Record<string, string> = {
  text_document: "dokument tekstowy",
  image: "obraz",
  pdf: "PDF",
  spreadsheet: "arkusz",
  unknown: "nieznany",
};

const IMAGE_STATUS_LABELS: Record<string, string> = {
  not_applicable: "nie dotyczy",
  pending: "oczekuje",
  analyzed: "przeanalizowano",
  failed: "błąd analizy",
};

const ATTACHMENT_TAG_LABELS: Record<string, string> = {
  external_sources: "źródła zewnętrzne",
  funding: "finansowanie",
  human_gate_expected: "wymagany HumanGate",
  text_attachment: "załącznik tekstowy",
  security_review: "przegląd bezpieczeństwa",
  runtime_review: "przegląd runtime",
};

const ATTACHMENT_SKILL_LABELS: Record<string, string> = {
  file_upload_validator: "walidacja uploadu",
  funding_research: "research finansowania",
  grant_deadline_verifier: "weryfikacja terminów grantów",
  idea_attachment_reader: "czytanie załączników intake",
  source_citation_checker: "kontrola cytowania źródeł",
  operator_console: "konsola operatora",
  source_of_truth: "Source of Truth / Księga",
  model_council: "Rada modeli",
};

const ATTACHMENT_RISK_LABELS: Record<string, string> = {
  "Grant deadlines and eligibility must be source-backed and current.":
    "Terminy i kwalifikowalność grantów muszą mieć aktualne źródła.",
  "External sources must be verified before promotion.":
    "Źródła zewnętrzne muszą być zweryfikowane przed promocją.",
};

const MISSING_INFO_LABELS: Record<string, string> = {
  "Missing source citations.": "Brakuje cytowań źródeł.",
  "Missing budget constraints.": "Brakuje ograniczeń budżetowych.",
  "Missing runtime constraints.": "Brakuje ograniczeń runtime.",
};

function labelFromMap(value: string | null | undefined, labels: Record<string, string>): string {
  if (!value) return "--";
  return labels[value] ?? value.replace(/_/g, " ");
}

function labelList(values: string[], labels: Record<string, string>): string {
  return values.map((value) => labelFromMap(value, labels)).join(", ");
}

function sentenceList(values: string[], labels: Record<string, string>): string {
  return values.map((value) => labelFromMap(value, labels)).join("; ");
}

// ---------------------------------------------------------------------------
// Edit form
// ---------------------------------------------------------------------------

interface EditFormProps {
  idea: Idea;
  onSave: (updated: Idea) => void;
  onCancel: () => void;
}

function EditForm({ idea, onSave, onCancel }: EditFormProps) {
  const [title, setTitle] = useState(idea.title);
  const [description, setDescription] = useState(idea.description);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!title.trim()) return;
    setError(null);
    setLoading(true);
    try {
      const updated = await updateIdea(idea.idea_id, {
        title: title.trim(),
        description: description.trim(),
      });
      onSave(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd zapisu");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-muted-foreground mb-1 block">Tytuł</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className={cn(
            "w-full rounded-md border border-border/50 bg-background/60",
            "px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary/50"
          )}
        />
      </div>

      <div>
        <label className="text-xs text-muted-foreground mb-1 block">Opis</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={5}
          className={cn(
            "w-full rounded-md border border-border/50 bg-background/60",
            "px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-primary/50"
          )}
        />
      </div>

      {error && (
        <p className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded px-3 py-2">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <Button size="sm" onClick={handleSave} disabled={!title.trim() || loading}>
          {loading && <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />}
          <Check className="w-3.5 h-3.5 mr-1" />
          Zapisz
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={loading}>
          Anuluj
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Lifecycle log entry
// ---------------------------------------------------------------------------

function LogEntry({ entry }: { entry: IdeaLifecycleEntry }) {
  return (
    <div className="flex items-start gap-3 py-2">
      <div className="mt-0.5 w-4 shrink-0 flex justify-center">
        <div className="w-1.5 h-1.5 rounded-full bg-border mt-1" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap text-xs">
          {entry.from_status && (
            <>
              <StatusBadge status={entry.from_status as IdeaStatus} />
              <ChevronRight className="w-3 h-3 text-muted-foreground/40" />
            </>
          )}
          <StatusBadge status={entry.to_status as IdeaStatus} />
          {entry.actor && (
            <span className="text-muted-foreground/60">&middot; {entry.actor}</span>
          )}
        </div>
        {entry.rationale && (
          <p className="text-[11px] text-muted-foreground/60 mt-0.5">{entry.rationale}</p>
        )}
        <p className="text-[10px] text-muted-foreground/40 mt-0.5">
          {formatTs(entry.logged_at)}
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hard-delete confirmation dialog
// ---------------------------------------------------------------------------

interface HardDeleteDialogProps {
  open: boolean;
  idea: Idea;
  onClose: () => void;
  onDeleted: () => void;
}

function HardDeleteDialog({ open, idea, onClose, onDeleted }: HardDeleteDialogProps) {
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const isReady = confirm === "USUŃ" || confirm === "USUN";

  async function handleDelete() {
    if (!isReady) return;
    setLoading(true);
    try {
      await hardDeleteIdea(idea.idea_id);
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd usuwania");
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <Card className="max-w-sm w-full mx-4 p-5 border border-red-500/30 bg-card space-y-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-500" />
          <h3 className="text-sm font-semibold text-red-500">Trwale usuń pomysł</h3>
        </div>

        <p className="text-xs text-muted-foreground">
          Tej operacji nie można cofnąć. Pomysł{" "}
          <span className="text-foreground font-medium">{idea.title}</span>{" "}
          zostanie bezpowrotnie usunięty (historia audytu zostanie zachowana w logach).
        </p>

        <div>
          <label className="text-xs text-muted-foreground mb-1 block">
            Wpisz <span className="font-mono text-red-400">USUŃ</span> aby potwierdzić
          </label>
          <input
            type="text"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className={cn(
              "w-full rounded-md border border-border/50 bg-background/60",
              "px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-red-500/50"
            )}
          />
        </div>

        {error && (
          <p className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded px-3 py-2">
            {error}
          </p>
        )}

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={loading}>
            Anuluj
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleDelete}
            disabled={!isReady || loading}
          >
            {loading && <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />}
            Usuń trwale
          </Button>
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main detail page
// ---------------------------------------------------------------------------

export default function IdeaDetailPage() {
  const router = useRouter();
  const params = useParams();
  const ideaId = params?.id as string;

  const [idea, setIdea] = useState<Idea | null>(null);
  const [history, setHistory] = useState<IdeaLifecycleEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const [transitionTarget, setTransitionTarget] = useState<IdeaStatus | null>(null);
  const [showHardDelete, setShowHardDelete] = useState(false);

  // F-032: discussion + promote-to-project state
  const [discussions, setDiscussions] = useState<IdeaDiscussionSession[]>([]);
  const [discussionLoading, setDiscussionLoading] = useState(false);
  const [discussionError, setDiscussionError] = useState<string | null>(null);
  const [discussionPrompt, setDiscussionPrompt] = useState<string>("");
  const [showPromoteModal, setShowPromoteModal] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  // FE-1 (round_meta_orchestration): clarification answer form state
  const [clarificationAnswer, setClarificationAnswer] = useState<string>("");
  const [clarificationLoading, setClarificationLoading] = useState(false);
  const [clarificationError, setClarificationError] = useState<string | null>(null);
  const [clarificationSuccess, setClarificationSuccess] = useState<string | null>(null);

  // Attachments uploaded during intake must stay visible after the idea is created.
  const [attachments, setAttachments] = useState<IdeaAttachment[]>([]);
  const [attachmentAnalyses, setAttachmentAnalyses] = useState<IdeaAttachmentAnalysis[]>([]);
  const [attachmentsLoading, setAttachmentsLoading] = useState(false);
  const [attachmentsAnalyzing, setAttachmentsAnalyzing] = useState(false);
  const [attachmentsError, setAttachmentsError] = useState<string | null>(null);

  // ---- Fetch ----

  const fetchIdea = useCallback(async () => {
    if (!ideaId) return;
    setError(null);
    setLoading(true);
    try {
      const [ideaData, histData] = await Promise.all([
        getIdea(ideaId),
        getIdeaHistory(ideaId),
      ]);
      if (!ideaData) {
        setError("Pomysł nie został znaleziony");
        setLoading(false);
        return;
      }
      setIdea(ideaData);
      setHistory(histData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd ładowania");
    } finally {
      setLoading(false);
    }
  }, [ideaId]);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchIdea();
    });
  }, [fetchIdea]);

  const fetchAttachments = useCallback(async () => {
    if (!ideaId) return;
    setAttachmentsLoading(true);
    setAttachmentsError(null);
    try {
      const [attachmentData, analysisData] = await Promise.all([
        listIdeaAttachments(ideaId),
        listIdeaAttachmentAnalysis(ideaId),
      ]);
      setAttachments(attachmentData.attachments ?? []);
      setAttachmentAnalyses(analysisData.analyses ?? []);
    } catch (err) {
      setAttachmentsError(err instanceof Error ? err.message : "Błąd ładowania załączników");
    } finally {
      setAttachmentsLoading(false);
    }
  }, [ideaId]);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchAttachments();
    });
  }, [fetchAttachments]);

  // F-032: load existing discussions in parallel with the idea body
  useEffect(() => {
    if (!ideaId) return;
    getIdeaDiscussion(ideaId)
      .then((r) => setDiscussions(r.sessions ?? []))
      .catch(() => setDiscussions([]));
  }, [ideaId]);

  async function handleStartDiscussion() {
    if (!idea) return;
    setDiscussionError(null);
    setDiscussionLoading(true);
    try {
      const r = await startIdeaDiscussion(idea.idea_id, {
        prompt: discussionPrompt.trim() || undefined,
      });
      // Optimistic prepend so the operator sees the new thread instantly.
      setDiscussions((prev) => [
        {
          session_id: r.session_id ?? undefined,
          title: `Dyskusja: ${idea.title}`,
          model_ids: r.model_ids,
          created_at: Math.floor(Date.now() / 1000),
        },
        ...prev,
      ]);
      setDiscussionPrompt("");
    } catch (err) {
      setDiscussionError(err instanceof Error ? err.message : "Błąd uruchamiania dyskusji");
    } finally {
      setDiscussionLoading(false);
    }
  }

  async function handleAnalyzeAttachments() {
    if (!idea) return;
    setAttachmentsAnalyzing(true);
    setAttachmentsError(null);
    try {
      const result = await analyzeIdeaAttachments(idea.idea_id);
      setAttachmentAnalyses(result.analyses ?? []);
      await fetchAttachments();
    } catch (err) {
      setAttachmentsError(err instanceof Error ? err.message : "Błąd analizy załączników");
    } finally {
      setAttachmentsAnalyzing(false);
    }
  }

  async function handlePromote(payload: { project_name: string }) {
    if (!idea) return;
    setPromoteError(null);
    setPromoting(true);
    try {
      const r = await promoteIdeaToProject(idea.idea_id, {
        project_name: payload.project_name.trim() || idea.title,
      });
      // Navigate user straight to the new project (project detail page).
      router.push(`/projects/${encodeURIComponent(r.project.project_id)}`);
    } catch (err) {
      setPromoteError(err instanceof Error ? err.message : "Błąd promocji");
      setPromoting(false);
    }
  }

  // FE-1 (round_meta_orchestration): submit clarification answer
  async function handleClarificationSubmit() {
    if (!idea) return;
    const trimmed = clarificationAnswer.trim();
    if (!trimmed) return;
    setClarificationError(null);
    setClarificationSuccess(null);
    setClarificationLoading(true);
    try {
      const r = await submitClarificationAnswer(idea.idea_id, {
        answer: trimmed,
        author: idea.author || undefined,
      });
      // Optimistic update: append answer locally so operator sees the result.
      setIdea((prev) =>
        prev
          ? {
              ...prev,
              clarification_notes:
                r.clarification_notes ??
                (prev.clarification_notes
                  ? `${prev.clarification_notes}\n\nOdpowiedź: ${trimmed}`
                  : `Odpowiedź: ${trimmed}`),
              status: r.status ?? prev.status,
            }
          : prev,
      );
      setClarificationAnswer("");
      setClarificationSuccess("Odpowiedź wysłana");
      // Refresh history so the audit log reflects the new event when ready.
      getIdeaHistory(ideaId).then(setHistory).catch((historyErr) => {
        setClarificationError(
          historyErr instanceof Error
            ? `Odpowiedź zapisana, ale nie odświeżono historii: ${historyErr.message}`
            : "Odpowiedź zapisana, ale nie odświeżono historii",
        );
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Błąd wysyłania";
      setClarificationError(msg);
    } finally {
      setClarificationLoading(false);
    }
  }

  // ---- Actions ----

  function handleSaved(updated: Idea) {
    setIdea(updated);
    setEditing(false);
  }

  function handleTransitioned(updated: Idea) {
    setIdea(updated);
    setTransitionTarget(null);
    // Refresh history
    getIdeaHistory(ideaId).then(setHistory).catch((historyErr) => {
      setError(historyErr instanceof Error ? historyErr.message : "Błąd odświeżania historii");
    });
  }

  async function handleSoftDelete() {
    if (!idea) return;
    setTransitionTarget("deleted_soft");
  }

  async function handleRestore() {
    if (!idea) return;
    try {
      const updated = await setIdeaStatus(idea.idea_id, "draft");
      setIdea(updated);
      getIdeaHistory(ideaId).then(setHistory).catch((historyErr) => {
        setError(historyErr instanceof Error ? historyErr.message : "Błąd odświeżania historii");
      });
    } catch (restoreErr) {
      setError(restoreErr instanceof Error ? restoreErr.message : "Błąd przywracania");
    }
  }

  function handleDeleted() {
    router.push("/idea-vault");
  }

  // ---- Render ----

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !idea) {
    return (
      <div className="px-6 py-6">
        <Button variant="ghost" size="sm" onClick={() => router.push("/idea-vault")} className="mb-4">
          <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
          Powrót
        </Button>
        <p className="text-sm text-red-400">{error ?? "Nie znaleziono pomysłu"}</p>
      </div>
    );
  }

  const domain = getDomain(idea);
  const displayTags = getDisplayTags(idea);
  const allowedTransitions = ALLOWED_TRANSITIONS[idea.status] ?? [];
  const stale = isStaleIdea(idea);
  const inTrash = idea.status === "deleted_soft";
  const hardDeleteAllowed = canHardDelete(idea);

  return (
    <div className="flex flex-col min-h-full px-6 py-6 space-y-5 max-w-3xl">
      {/* Back */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push("/idea-vault")}
        className="self-start -ml-2 h-8"
      >
        <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
        Skarbiec Pomysłów
      </Button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-semibold text-foreground truncate">
              {idea.title || "(bez tytułu)"}
            </h1>
            <StatusBadge status={idea.status} />
            {stale && (
              <span className="flex items-center gap-1 text-[11px] text-yellow-600 border border-yellow-600/30 px-2 py-0.5 rounded-full">
                <AlertTriangle className="w-3 h-3" />
                nieaktywny
              </span>
            )}
          </div>
        </div>

        {!editing && idea.status !== "deleted_hard" && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setEditing(true)}
            className="h-8 shrink-0"
          >
            <Edit2 className="w-3.5 h-3.5 mr-1.5" />
            Edytuj
          </Button>
        )}
      </div>

      {/* Edit form */}
      {editing ? (
        <Card className="p-4 border border-border/40">
          <EditForm
            idea={idea}
            onSave={handleSaved}
            onCancel={() => setEditing(false)}
          />
        </Card>
      ) : (
        <>
          {/* Info grid */}
          <Card className="p-4 border border-border/40 space-y-3">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <InfoRow label="Autor" value={idea.author || "--"} />
              <InfoRow label="Domena" value={domain ? (DOMAIN_LABELS[domain as keyof typeof DOMAIN_LABELS] ?? domain) : "--"} />
              <InfoRow label="Priorytet" value={labelFromMap(idea.priority || "normal", PRIORITY_LABELS)} />
              <InfoRow label="Źródło" value={idea.source || "--"} />
              <InfoRow label="Utworzony" value={formatTs(idea.created_at)} />
              <InfoRow label="Ostatnia aktywność" value={formatRelative(idea.last_activity_at || idea.updated_at)} />
            </div>

            {displayTags.length > 0 && (
              <div>
                <span className="text-[11px] text-muted-foreground/60 block mb-1">Tagi</span>
                <div className="flex flex-wrap gap-1">
                  {displayTags.map((tag) => (
                    <span key={tag} className="bg-muted/40 text-xs px-2 py-0.5 rounded">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {/* Description */}
          {idea.description && (
            <Card className="p-4 border border-border/40">
              <h2 className="text-xs font-medium text-muted-foreground mb-2">Opis</h2>
              <p className="text-sm text-foreground/80 whitespace-pre-wrap">{idea.description}</p>
            </Card>
          )}

          <Card
            className="p-4 border border-sylion-blue/20 bg-sylion-blue/5 space-y-3"
            data-testid="idea-attachments-card"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xs font-medium text-sylion-blue flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5" />
                  Załączniki i analiza AEIS
                </h2>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Pliki dodane w intake muszą być widoczne, analizowalne i użyte do klasyfikacji decyzji oraz dobóru skills.
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={fetchAttachments}
                disabled={attachmentsLoading}
                className="h-7 text-xs"
              >
                {attachmentsLoading && <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />}
                Odśwież
              </Button>
            </div>

            {attachmentsError && (
              <p
                className="text-[11px] text-red-400 bg-red-400/10 border border-red-400/20 rounded px-2 py-1.5"
                data-testid="idea-attachments-error"
              >
                {attachmentsError}
              </p>
            )}

            {attachments.length === 0 && !attachmentsLoading ? (
              <p className="text-xs text-muted-foreground" data-testid="idea-attachments-empty">
                Brak załączników dla tego pomysłu.
              </p>
            ) : (
              <div className="space-y-2" data-testid="idea-attachments-list">
                {attachments.map((attachment) => (
                  <div
                    key={attachment.attachment_id}
                    className="flex items-center justify-between gap-3 rounded border border-border/40 bg-background/50 px-3 py-2 text-[11px]"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-foreground">{attachment.filename}</p>
                      <p className="text-muted-foreground">
                        {attachment.file_type || "application/octet-stream"} - {formatBytes(attachment.file_size)}
                      </p>
                    </div>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {attachment.attachment_id.slice(0, 8)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {attachments.length > 0 && (
              <Button
                size="sm"
                data-testid="idea-analyze-attachments"
                onClick={handleAnalyzeAttachments}
                disabled={attachmentsAnalyzing}
                className="h-7 text-xs bg-sylion-blue/15 text-sylion-blue hover:bg-sylion-blue/25 border-sylion-blue/30"
              >
                {attachmentsAnalyzing && <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />}
                Analizuj załączniki przez AEIS
              </Button>
            )}

            {attachmentAnalyses.length > 0 && (
              <div className="space-y-2" data-testid="idea-attachment-analysis-list">
                {attachmentAnalyses.map((analysis) => (
                  <div
                    key={analysis.analysis_id}
                    className="rounded border border-sylion-green/25 bg-sylion-green/5 px-3 py-2 text-[11px] space-y-1"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-foreground truncate">{analysis.filename}</span>
                      <span className="flex items-center gap-1.5">
                        <Badge variant="outline" className="text-[10px]">
                          {analysis.decision_class}
                        </Badge>
                        {analysis.human_gate_required && (
                          <Badge variant="outline" className="border-amber-400/40 text-amber-400 text-[10px]">
                            HumanGate
                          </Badge>
                        )}
                      </span>
                    </div>
                    <p className="text-muted-foreground">
                      Typ: {labelFromMap(analysis.detected_kind, ATTACHMENT_KIND_LABELS)} - obraz: {labelFromMap(analysis.image_analysis_status, IMAGE_STATUS_LABELS)}
                    </p>
                    {analysis.tags.length > 0 && (
                      <p className="text-muted-foreground">Tagi: {labelList(analysis.tags, ATTACHMENT_TAG_LABELS)}</p>
                    )}
                    {analysis.suggested_skills.length > 0 && (
                      <p className="text-muted-foreground">Skills: {labelList(analysis.suggested_skills, ATTACHMENT_SKILL_LABELS)}</p>
                    )}
                    {analysis.risks.length > 0 && (
                      <p className="text-amber-300">Ryzyka: {sentenceList(analysis.risks, ATTACHMENT_RISK_LABELS)}</p>
                    )}
                    {analysis.missing_info.length > 0 && (
                      <p className="text-red-300">Braki: {sentenceList(analysis.missing_info, MISSING_INFO_LABELS)}</p>
                    )}
                    {analysis.extracted_text_preview && (
                      <p className="text-muted-foreground/80 line-clamp-3">
                        Podgląd: {analysis.extracted_text_preview}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Clarification notes */}
          {idea.clarification_notes && (
            <Card className="p-4 border border-amber-400/20 bg-amber-400/5">
              <h2 className="text-xs font-medium text-amber-400 mb-2">Notatki wyjaśniające</h2>
              <p className="text-sm text-foreground/80 whitespace-pre-wrap">{idea.clarification_notes}</p>
            </Card>
          )}

          {/* AR-1: baner Rundy 1 - pomysł -> Księga */}
          {(idea.status === "clarification" || idea.status === "council_review") && discussions.length > 0 && (
            <Card
              className="p-4 border-sylion-blue/30 bg-sylion-blue/5 space-y-3"
              data-testid="round-1-banner"
            >
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="border-sylion-blue/40 text-sylion-blue">
                  RUNDA 1
                </Badge>
                <h2 className="text-sm font-semibold text-sylion-blue flex items-center gap-1.5">
                  Pomysł -&gt; Księga
                  <HelpTip text="Pierwszy punkt kontroli: zatwierdzasz skład Rady i limit kosztu, zanim Rada wytworzy Księgę (Source of Truth). Po promocji pomysł staje się projektem i nie da się bez śladu cofnąć składu Rady." />
                </h2>
              </div>
              <p className="text-xs text-muted-foreground">
                Modele dyskutują nad pomysłem. Zatwierdź skład Rady i limit kosztu, żeby Rada
                mogła zaproponować Księgę (Source of Truth).
              </p>
              <ul className="text-xs space-y-1 ml-4 list-disc text-muted-foreground">
                <li>Skład Rady OK? ({discussions[0]?.model_ids?.length ?? 0} modeli)</li>
                <li>Pytania doprecyzowujące odpowiedziane?</li>
                <li>Limit kosztu ustawiony?</li>
              </ul>
              <Button
                onClick={() => setShowPromoteModal(true)}
                data-testid="approve-round-1"
                className="bg-sylion-blue/20 text-sylion-blue hover:bg-sylion-blue/30"
              >
                Zatwierdź Rundę 1 i promuj do projektu
              </Button>
            </Card>
          )}

          {/* FE-1 (round_meta): clarification answer form */}
          {(idea.status === "clarification" || idea.status === "council_review") && (
            <Card
              className="p-4 border border-amber-400/20 bg-amber-400/5 space-y-3"
              data-testid="clarification-answer-card"
            >
              <h2 className="text-xs font-medium text-amber-400 flex items-center gap-1.5">
                Twoja odpowiedź na pytania doprecyzowujące
                <HelpTip text="Modele zadały pytania doprecyzowujące - odpowiedz krótko i konkretnie, żeby Rada mogła zaproponować Księgę (Source of Truth). Tekst zostanie dołączony do notatek wyjaśniających i widoczny dla wszystkich modeli." />
              </h2>
              <p className="text-[11px] text-muted-foreground">
                Po wysłaniu odpowiedzi Rada wraca do pracy i przygotowuje
                propozycję Księgi (Runda 1 -&gt; Source of Truth).
              </p>
              <textarea
                data-testid="clarification-answer"
                value={clarificationAnswer}
                onChange={(e) => setClarificationAnswer(e.target.value)}
                rows={4}
                placeholder="Odpowiedz na pytania doprecyzowujące..."
                disabled={clarificationLoading}
                className={cn(
                  "w-full rounded-md border border-border/50 bg-background/60",
                  "px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-amber-400/50",
                )}
              />
              {clarificationError && (
                <p
                  data-testid="clarification-error"
                  className="text-[11px] text-red-400 bg-red-400/10 border border-red-400/20 rounded px-2 py-1.5"
                >
                  {clarificationError}
                </p>
              )}
              {clarificationSuccess && !clarificationError && (
                <p
                  data-testid="clarification-success"
                  className="text-[11px] text-sylion-green bg-sylion-green/10 border border-sylion-green/20 rounded px-2 py-1.5"
                >
                  {clarificationSuccess}
                </p>
              )}
              <div className="flex items-center justify-end">
                <Button
                  size="sm"
                  data-testid="clarification-submit"
                  onClick={handleClarificationSubmit}
                  disabled={clarificationLoading || !clarificationAnswer.trim()}
                  className="h-7 text-xs bg-amber-400/20 text-amber-400 hover:bg-amber-400/30 border border-amber-400/40"
                >
                  {clarificationLoading && (
                    <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />
                  )}
                  Wyślij odpowiedź
                </Button>
              </div>
            </Card>
          )}

          {/* F-032: Discussion with models BEFORE promoting */}
          {!inTrash && idea.status !== "deleted_hard" && (
            <Card className="p-4 border border-sylion-blue/20 bg-sylion-blue/5 space-y-3">
              <h2 className="text-xs font-medium text-sylion-blue flex items-center gap-1.5">
                <MessageSquarePlus className="w-3.5 h-3.5" />
                Dyskusja z modelami
                <HelpTip text="To jest szybka dyskusja przed promocją pomysłu. Pełny audyt V10 wymaga po promocji projektu osobnej Rady projektu z barierami odpowiedzi, sentynelami, podpisem krytyka i HumanGate." />
              </h2>
              <p className="text-[11px] text-muted-foreground">
                Szybka dyskusja sprawdźa ryzyka, braki opisu i rekomendacje przed
                promocją. Nie zastępuje pełnej Rady V10 ani Bariery Odpowiedzi Modeli.
              </p>
              <textarea
                value={discussionPrompt}
                onChange={(e) => setDiscussionPrompt(e.target.value)}
                rows={2}
                placeholder="Co konkretnie chcesz przedyskutować? (puste = ogólna rada doradcza)"
                className={cn(
                  "w-full rounded-md border border-border/50 bg-background/60",
                  "px-3 py-2 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-sylion-blue/50",
                )}
              />
              {discussionError && (
                <p className="text-[11px] text-red-400 bg-red-400/10 border border-red-400/20 rounded px-2 py-1.5">
                  {discussionError}
                </p>
              )}
              {discussionLoading && (
                <p className="text-[11px] text-sylion-blue bg-sylion-blue/10 border border-sylion-blue/20 rounded px-2 py-1.5">
                  Trwa realne wywołanie modeli. Nie zamykaj ekranu; wynik pojawi się jako sesja workspace.
                </p>
              )}
              <div className="flex items-center justify-between gap-2">
                <Button
                  size="sm"
                  className="h-7 text-xs bg-sylion-blue/15 text-sylion-blue hover:bg-sylion-blue/25 border-sylion-blue/30"
                  onClick={handleStartDiscussion}
                  disabled={discussionLoading}
                >
                  {discussionLoading && <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />}
                  <Sparkles className="w-3 h-3 mr-1" />
                  Uruchom szybką dyskusję
                </Button>
                <span className="text-[10px] text-muted-foreground">
                  {discussionLoading
                    ? "Modele odpowiadają..."
                    : discussions.length === 0
                    ? "Brak wcześniejszych dyskusji"
                    : `${discussions.length} ${discussions.length === 1 ? "dyskusja" : "dyskusje"}`}
                </span>
              </div>

              {discussions.length > 0 && (
                <div className="space-y-1 pt-1">
                  {discussions.slice(0, 5).map((s, i) => (
                    <div
                      key={s.session_id || `${i}`}
                      className="flex items-center justify-between rounded border border-border/40 bg-background/40 px-2 py-1.5 text-[11px]"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-foreground/90">{s.title || "Dyskusja"}</p>
                        <p className="text-[10px] text-muted-foreground/70 truncate">
                          {(s.model_ids || []).join(" + ") || "modele domyślne"}
                          {s.created_at ? ` · ${formatRelative(s.created_at)}` : ""}
                        </p>
                      </div>
                      {s.session_id && (
                        <a
                          href={`/workspace?session=${encodeURIComponent(s.session_id)}`}
                          className="ml-2 shrink-0 text-sylion-blue hover:underline inline-flex items-center gap-0.5"
                        >
                          Otwórz <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* F-032: Promote idea to a real project */}
          {!inTrash && idea.status !== "deleted_hard" && idea.status !== "implemented" && (
            <Card className="p-4 border border-sylion-green/30 bg-sylion-green/5 space-y-3">
              <h2 className="text-xs font-medium text-sylion-green flex items-center gap-1.5">
                <Rocket className="w-3.5 h-3.5" />
                Promuj do projektu
                <HelpTip text="Zamienia ten pomysł w pełny projekt z domyślnym planem (Rada, plan workerów, Masterplan, plan audytu, kanon). Po kliknięciu przejdziesz na stronę projektu i tam możesz nadpisać każdą meta-orkiestrację projektu: Radę, modele, budżet i autonomię. Pomysł zostanie oznaczony jako wdrożony." />
              </h2>
              <p className="text-[11px] text-muted-foreground">
                Stworzy pełny projekt z domyślnym planem: Rada, worker, Masterplan
                i audyt. Ten ekran zostanie zastąpiony stroną projektu, gdzie możesz
                ustawić Radę modeli i budżet projektu.
              </p>
              <Button
                size="sm"
                className="h-7 text-xs bg-sylion-green/20 text-sylion-green hover:bg-sylion-green/30 border-sylion-green/40"
                onClick={() => setShowPromoteModal(true)}
              >
                <Rocket className="w-3 h-3 mr-1" />
                Promuj do projektu...
              </Button>
            </Card>
          )}

          {/* Human Gate section */}
          {idea.human_gate_required === 1 && (
            <Card className="p-4 border border-orange-400/20 bg-orange-400/5 space-y-2">
              <h2 className="text-xs font-medium text-orange-400">Human Gate</h2>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <InfoRow label="Wniosek ID" value={idea.human_gate_request_id || "--"} />
                <InfoRow label="Decyzja" value={idea.human_gate_decision || "oczekuje"} />
                {idea.human_gate_decided_by && (
                  <InfoRow label="Podjęte przez" value={idea.human_gate_decided_by} />
                )}
                {idea.human_gate_decided_at && (
                  <InfoRow label="Data decyzji" value={formatTs(idea.human_gate_decided_at)} />
                )}
              </div>
              {!idea.human_gate_decision && (
                <a
                  href="/human-gate"
                  className="inline-flex items-center gap-1 text-[11px] text-orange-400 hover:underline mt-1"
                >
                  Przejdź do Human Gate
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </Card>
          )}
        </>
      )}

      {/* Status transitions */}
      {!editing && allowedTransitions.length > 0 && (
        <div>
          <h2 className="text-xs font-medium text-muted-foreground mb-2">Zmiana statusu</h2>
          <div className="flex flex-wrap gap-2">
            {allowedTransitions
              .filter((t) => t !== "deleted_soft" && t !== "deleted_hard")
              .map((target) => (
                <Button
                  key={target}
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setTransitionTarget(target)}
                >
                  {TRANSITION_LABELS[target] ?? STATUS_LABELS[target]}
                </Button>
              ))}
          </div>
        </div>
      )}

      {/* Delete zone */}
      {!editing && idea.status !== "deleted_hard" && (
        <div className="pt-2">
          <Separator className="mb-4" />
          <h2 className="text-xs font-medium text-muted-foreground mb-2">Akcje usunięcia</h2>
          <div className="flex flex-wrap gap-2">
            {!inTrash && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs border-red-400/30 text-red-400 hover:bg-red-400/10"
                onClick={handleSoftDelete}
              >
                <Trash2 className="w-3 h-3 mr-1.5" />
                Przenieś do kosza
              </Button>
            )}

            {inTrash && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={handleRestore}
                >
                  <RotateCcw className="w-3 h-3 mr-1.5" />
                  Przywróć z kosza
                </Button>

                <Button
                  variant="destructive"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setShowHardDelete(true)}
                  disabled={!hardDeleteAllowed}
                  title={!hardDeleteAllowed ? "Dostępne po 30 dniach w koszu" : undefined}
                >
                  <Trash2 className="w-3 h-3 mr-1.5" />
                  Usuń trwale
                  {!hardDeleteAllowed && <span className="ml-1 opacity-60">(30 dni)</span>}
                </Button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Audit log */}
      <div className="pt-2">
        <Separator className="mb-4" />
        <h2 className="text-xs font-medium text-muted-foreground mb-2">
          Dziennik zdarze?
        </h2>

        {history.length === 0 ? (
          <p className="text-xs text-muted-foreground/50 py-2">
            {idea.human_gate_required || idea.previous_status
              ? "Historia ?ycia jest pusta mimo znacznikow statusu \u2014 sprawdź audit chain."
              : "Brak wpis?w w dzienniku."}
          </p>
        ) : (
          <div className="divide-y divide-border/30">
            {history.map((entry) => (
              <LogEntry key={entry.log_id} entry={entry} />
            ))}
          </div>
        )}

        {/* Derived timeline from idea fields (always shown) */}
        <div className="mt-3 space-y-1">
          <MiniTimelineEntry
            label="Pomysl utworzony"
            ts={idea.created_at}
            status="draft"
          />
          {idea.archived_at && (
            <MiniTimelineEntry label="Zarchiwizowany" ts={idea.archived_at} status="archived" />
          )}
          {idea.abandoned_at && (
            <MiniTimelineEntry label="Porzucony" ts={idea.abandoned_at} status="abandoned" />
          )}
          {idea.deleted_at && (
            <MiniTimelineEntry label="Przeniesiony do kosza" ts={idea.deleted_at} status="deleted_soft" />
          )}
          {idea.stale_at && (
            <MiniTimelineEntry label="Oznaczony jako nieaktywny" ts={idea.stale_at} status="stale" />
          )}
        </div>
      </div>

      {/* Modals */}
      <StatusTransitionModal
        open={!!transitionTarget}
        idea={idea}
        targetStatus={transitionTarget}
        onClose={() => setTransitionTarget(null)}
        onTransitioned={handleTransitioned}
      />

      <HardDeleteDialog
        open={showHardDelete}
        idea={idea}
        onClose={() => setShowHardDelete(false)}
        onDeleted={handleDeleted}
      />

      {/* F-032: promote-to-project modal */}
      <PromoteToProjectDialog
        open={showPromoteModal}
        idea={idea}
        loading={promoting}
        error={promoteError}
        onClose={() => {
          if (!promoting) {
            setShowPromoteModal(false);
            setPromoteError(null);
          }
        }}
        onConfirm={handlePromote}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// F-032: Promote-to-project modal
// ---------------------------------------------------------------------------

interface PromoteDialogProps {
  open: boolean;
  idea: Idea;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: (payload: { project_name: string }) => void;
}

function PromoteToProjectDialog({
  open, idea, loading, error, onClose, onConfirm,
}: PromoteDialogProps) {
  const [projectName, setProjectName] = useState(idea.title);

  useEffect(() => {
    if (open) {
      queueMicrotask(() => setProjectName(idea.title));
    }
  }, [open, idea.title]);

  if (!open) return null;

  const promotionBlocked =
    Boolean(idea.human_gate_required) && idea.human_gate_decision !== "approved";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <Card className="max-w-md w-full mx-4 p-5 border border-sylion-green/30 bg-card space-y-4">
        <div className="flex items-center gap-2">
          <Rocket className="w-4 h-4 text-sylion-green" />
          <h3 className="text-sm font-semibold text-sylion-green">Promuj do projektu</h3>
        </div>

        <p className="text-xs text-muted-foreground">
          Z pomysłu <span className="text-foreground font-medium">{idea.title}</span>{" "}
          zostanie utworzony pełny projekt. Po kliknięciu &quot;Stwórz projekt&quot;
          przejdziesz na jego stronę, gdzie możesz dostosować:
        </p>
        <ul className="text-[11px] text-muted-foreground/80 list-disc ml-5 space-y-0.5">
          <li>Radę modeli (per projekt, doradca zasugeruje skład)</li>
          <li>Budżet i poziom autonomii</li>
          <li>Stack technologiczny i dependencies</li>
          <li>Plan audytu i rytm fixera</li>
        </ul>

        {promotionBlocked && (
          <p
            className="text-xs text-amber-300 bg-amber-400/10 border border-amber-400/25 rounded px-3 py-2"
            data-testid="promote-humangate-block"
          >
            Ten pomysł wymaga zatwierdzonego HumanGate przed promocją do projektu.
            Najpierw przejdź do Human Gate i zatwierdź wniosek{" "}
            <span className="font-mono">{idea.human_gate_request_id || "--"}</span>.
          </p>
        )}

        <div>
          <label className="text-xs text-muted-foreground mb-1 block flex items-center gap-1">
            Nazwa projektu
            <HelpTip text="Możesz przemianować pomysł na coś bardziej projektowego, np. 'Tailor' zamiast 'Pomysł na asystenta krawca AI'. Domyślnie używany jest tytuł pomysłu." />
          </label>
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            disabled={loading}
            className={cn(
              "w-full rounded-md border border-border/50 bg-background/60",
              "px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-sylion-green/50",
            )}
          />
        </div>

        {error && (
          <p className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded px-3 py-2">
            {error}
          </p>
        )}

        <div className="flex gap-2 justify-end">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={loading}>
            Anuluj
          </Button>
          <Button
            size="sm"
            className="bg-sylion-green/25 text-sylion-green hover:bg-sylion-green/35 border border-sylion-green/40"
            onClick={() => onConfirm({ project_name: projectName })}
            disabled={loading || promotionBlocked || !projectName.trim()}
          >
            {loading && <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />}
            <Rocket className="w-3.5 h-3.5 mr-1" />
            Stwórz projekt
          </Button>
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-muted-foreground/60 block">{label}</span>
      <span className="text-foreground/90">{value}</span>
    </div>
  );
}

function MiniTimelineEntry({
  label, ts, status,
}: { label: string; ts: number; status: IdeaStatus }) {
  return (
    <div className="flex items-center gap-2 text-[11px] text-muted-foreground/50">
      <Clock className="w-3 h-3 shrink-0" />
      <StatusBadge status={status} className="text-[10px]" />
      <span>{label}</span>
      <span className="ml-auto">{formatTs(ts)}</span>
    </div>
  );
}
