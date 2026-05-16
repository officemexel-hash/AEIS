"use client";

import { useState, useRef, KeyboardEvent } from "react";
import { X, Plus, Upload, FileText } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { projectsApi, type Project, type ProjectAttachment } from "@/lib/api/projects";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (project: Project) => void;
}

interface UploadedProjectAttachment extends ProjectAttachment {
  idea_id: string;
}

const KIND_OPTIONS: { value: Project["project_kind"]; label: string }[] = [
  { value: "application", label: "Aplikacja" },
  { value: "research", label: "Badania" },
  { value: "audit", label: "Audyt" },
  { value: "funding", label: "Funding" },
  { value: "other", label: "Inne" },
];

const ACCEPT_ATTR = [
  ".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md",
  ".zip", ".tar", ".gz", ".7z",
  ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
  ".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".kt", ".swift",
  ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".rb", ".php",
  ".json", ".yaml", ".yml", ".toml", ".ini", ".env",
  ".apk", ".ino", ".bin", ".hex",
  "image/*", "application/pdf", "application/zip",
  "text/*", "application/octet-stream",
].join(",");

export function NewProjectModal({ open, onClose, onCreated }: Props) {
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [kind, setKind] = useState<Project["project_kind"]>("application");
  const [constraints, setConstraints] = useState("");
  const [stackInput, setStackInput] = useState("");
  const [stack, setStack] = useState<string[]>([]);
  const [attachments, setAttachments] = useState<UploadedProjectAttachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const stackRef = useRef<HTMLInputElement>(null);

  function addTag() {
    const val = stackInput.trim();
    if (val && !stack.includes(val)) setStack((s) => [...s, val]);
    setStackInput("");
  }

  function handleStackKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag();
    } else if (e.key === "Backspace" && stackInput === "" && stack.length > 0) {
      setStack((s) => s.slice(0, -1));
    }
  }

  async function handleFileUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadError(null);
    const nextAttachments: UploadedProjectAttachment[] = [...attachments];
    try {
      for (const file of Array.from(files)) {
        if (file.size > 50 * 1024 * 1024) {
          setUploadError(`${file.name} przekracza limit 50MB.`);
          continue;
        }
        try {
          const uploaded = await api.uploadIdeaFile(file, nextAttachments[0]?.idea_id);
          const attachment = uploaded as UploadedProjectAttachment;
          nextAttachments.push(attachment);
        } catch (uploadErr) {
          const message = uploadErr instanceof Error ? uploadErr.message : "Nieznany blad uploadu.";
          setUploadError(`Upload nieudany dla ${file.name}: ${message}`);
        }
      }
      setAttachments(nextAttachments);
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) { setError("Tytul jest wymagany."); return; }
    if (!idea.trim()) { setError("Opis pomyslu jest wymagany."); return; }
    if (uploading) { setError("Poczekaj na zakonczenie uploadu plikow."); return; }
    setError(null);
    setSubmitting(true);
    const result = await projectsApi.create({
      title: title.trim(),
      idea: idea.trim(),
      project_kind: kind,
      constraints: constraints.trim() || undefined,
      preferred_stack: stack.length > 0 ? stack : undefined,
      attachments: attachments.map((attachment) => ({
        attachment_id: attachment.attachment_id,
        filename: attachment.filename,
        file_type: attachment.file_type,
        file_size: attachment.file_size,
      })),
      status: "draft",
    });
    setSubmitting(false);
    if (!result) {
      setError("Błąd tworzenia projektu. SprawdŹ połączenie z backendem.");
      return;
    }
    resetForm();
    onCreated(result);
  }

  async function removeAttachment(attachmentId: string) {
    setAttachments((current) => current.filter((item) => item.attachment_id !== attachmentId));
    try {
      await api.deleteIdeaAttachment(attachmentId);
    } catch {
      // Best-effort cleanup only.
    }
  }

  function fmtSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function resetForm() {
    setTitle("");
    setIdea("");
    setKind("application");
    setConstraints("");
    setStack([]);
    setStackInput("");
    setAttachments([]);
    setError(null);
    setUploadError(null);
    setUploading(false);
  }

  function handleClose() {
    resetForm();
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(o: boolean) => { if (!o) handleClose(); }}>
      <DialogContent className="sm:max-w-lg" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Nowy projekt</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-1">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Tytul <span className="text-red-400">*</span>
            </label>
            <input
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-blue-500/40 focus:border-blue-500/60 focus:ring-1"
              placeholder="np. Platforma analityki AI"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={120}
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Pomysl / opis <span className="text-red-400">*</span>
            </label>
            <textarea
              className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-blue-500/40 focus:border-blue-500/60 focus:ring-1"
              placeholder="Chce system AEIS ktory..."
              rows={3}
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Rodzaj projektu</label>
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-blue-500/60"
              value={kind}
              onChange={(e) => setKind(e.target.value as Project["project_kind"])}
            >
              {KIND_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Ograniczenia (opcjonalnie)</label>
            <textarea
              className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-blue-500/40 focus:border-blue-500/60 focus:ring-1"
              placeholder="local-first; no external submit; bounded cost"
              rows={2}
              value={constraints}
              onChange={(e) => setConstraints(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Stack technologiczny (opcjonalnie) - Enter lub przecinek
            </label>
            <div
              className="flex min-h-[38px] flex-wrap items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1.5 focus-within:border-blue-500/60 focus-within:ring-1 focus-within:ring-blue-500/40"
              onClick={() => stackRef.current?.focus()}
            >
              {stack.map((tag) => (
                <span
                  key={tag}
                  className="flex items-center gap-1 rounded-md border border-border bg-muted/60 px-2 py-0.5 text-xs"
                >
                  {tag}
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); setStack((s) => s.filter((t) => t !== tag)); }}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </span>
              ))}
              <input
                ref={stackRef}
                className="min-w-[80px] flex-1 bg-transparent text-sm outline-none"
                placeholder={stack.length === 0 ? "Python, FastAPI, React..." : ""}
                value={stackInput}
                onChange={(e) => setStackInput(e.target.value)}
                onKeyDown={handleStackKey}
                onBlur={addTag}
              />
            </div>
          </div>

          <div className="space-y-2 rounded-lg border border-border bg-muted/10 p-3">
            <div className="flex items-center justify-between gap-2">
              <label className="text-xs font-medium text-muted-foreground">
                Zalaczniki (opcjonalnie)
              </label>
              <span className="text-[10px] text-muted-foreground">
                PDF / DOCX / ZIP / obrazy / kod / firmware / APK - max 50MB na plik
              </span>
            </div>
            <label
              className={`flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-background px-3 py-3 text-xs transition hover:border-blue-500/60 hover:bg-blue-500/5 ${uploading ? "pointer-events-none opacity-50" : ""}`}
            >
              <Upload className="h-3.5 w-3.5" />
              <span>{uploading ? "Uploadowanie..." : "Kliknij, aby dolaczyc pliki do draftu projektu."}</span>
              <input
                type="file"
                multiple
                accept={ACCEPT_ATTR}
                className="hidden"
                disabled={uploading || submitting}
                onChange={(e) => {
                  void handleFileUpload(e.target.files);
                  e.currentTarget.value = "";
                }}
              />
            </label>
            {uploadError && (
              <p className="text-[11px] text-red-400">{uploadError}</p>
            )}
            {attachments.length > 0 && (
              <ul className="space-y-1">
                {attachments.map((attachment) => (
                  <li
                    key={attachment.attachment_id}
                    className="flex items-center justify-between gap-2 rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5 text-[11px]"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <FileText className="h-3.5 w-3.5 shrink-0 text-blue-500" />
                      <span className="truncate font-medium">{attachment.filename}</span>
                      <span className="shrink-0 text-muted-foreground">
                        {fmtSize(attachment.file_size)} - {attachment.file_type}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => void removeAttachment(attachment.attachment_id)}
                      className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                      aria-label={`Usun ${attachment.filename}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {error && (
            <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
              {error}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose} disabled={submitting || uploading}>
              Anuluj
            </Button>
            <Button type="submit" disabled={submitting || uploading}>
              {submitting ? "Tworzenie..." : uploading ? "Uploadowanie..." : (
                <><Plus className="mr-1.5 h-3.5 w-3.5" /> Utworz projekt</>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
