"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/common/HelpTip";
import { FileText, Loader2, Upload, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { encodeDomain, DOMAINS, DOMAIN_LABELS } from "@/lib/api/ideas";
import type { Idea } from "@/lib/api/ideas";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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

interface IdeaAttachment {
  attachment_id: string;
  idea_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  draft_idea?: boolean;
  analysis?: IdeaAttachmentAnalysis;
}

interface IdeaAttachmentAnalysis {
  analysis_id: string;
  decision_class: string;
  human_gate_required: boolean;
  tags: string[];
  risks: string[];
  missing_info: string[];
  suggested_skills: string[];
  detected_kind: string;
  image_analysis_status: string;
}

interface CreateIdeaModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (idea: Idea) => void;
}

export function CreateIdeaModal({ open, onClose, onCreated }: CreateIdeaModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [domain, setDomain] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [attachments, setAttachments] = useState<IdeaAttachment[]>([]);
  const [localPath, setLocalPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [importingLocal, setImportingLocal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  function addTag(raw: string) {
    const val = raw.trim().toLowerCase().replace(/\s+/g, "-");
    if (val && !tags.includes(val) && !val.startsWith("domain:")) {
      setTags((prev) => [...prev, val]);
    }
    setTagInput("");
  }

  function removeTag(tag: string) {
    setTags((prev) => prev.filter((t) => t !== tag));
  }

  async function analyzeAttachment(attachment: IdeaAttachment): Promise<IdeaAttachment> {
    const res = await fetch(
      `${API_BASE}/api/v1/workspace/ideas/attachments/${encodeURIComponent(attachment.attachment_id)}/analyze`,
      { method: "POST" },
    );
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`Analiza nie powiodła się dla ${attachment.filename}: ${res.status} ${body.slice(0, 120)}`);
    }
    const analysis = (await res.json()) as IdeaAttachmentAnalysis;
    return { ...attachment, analysis };
  }

  async function addAttachmentRecord(record: IdeaAttachment, list: IdeaAttachment[]) {
    list.push(await analyzeAttachment(record));
  }

  async function handleFileUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadError(null);
    const nextAttachments: IdeaAttachment[] = [...attachments];
    try {
      for (const file of Array.from(files)) {
        if (file.size > 50 * 1024 * 1024) {
          setUploadError(`${file.name} przekracza limit 50 MB.`);
          continue;
        }
        const fd = new FormData();
        fd.append("file", file);
        const sharedId = nextAttachments[0]?.idea_id;
        if (sharedId) fd.append("idea_id", sharedId);
        const res = await fetch(`${API_BASE}/api/v1/workspace/ideas/upload`, {
          method: "POST",
          body: fd,
        });
        if (!res.ok) {
          const body = await res.text().catch(() => "");
          setUploadError(`Wgranie pliku ${file.name} nie powiodło się: ${res.status} ${body.slice(0, 120)}`);
          continue;
        }
        const json = (await res.json()) as IdeaAttachment;
        await addAttachmentRecord(json, nextAttachments);
      }
      setAttachments(nextAttachments);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Błąd wgrywania lub analizy pliku");
    } finally {
      setUploading(false);
    }
  }

  async function handleLocalImport() {
    const trimmedPath = localPath.trim();
    if (!trimmedPath) return;
    setImportingLocal(true);
    setUploadError(null);
    const nextAttachments: IdeaAttachment[] = [...attachments];
    try {
      const sharedId = nextAttachments[0]?.idea_id;
      const res = await fetch(`${API_BASE}/api/v1/workspace/ideas/import-local`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: trimmedPath, idea_id: sharedId || "" }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`Import lokalny nie powiódł się: ${res.status} ${body.slice(0, 160)}`);
      }
      const json = (await res.json()) as IdeaAttachment;
      await addAttachmentRecord(json, nextAttachments);
      setAttachments(nextAttachments);
      setLocalPath("");
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Błąd importu lokalnego pliku");
    } finally {
      setImportingLocal(false);
    }
  }

  function removeAttachment(attachmentId: string) {
    setAttachments((prev) => prev.filter((item) => item.attachment_id !== attachmentId));
    fetch(`${API_BASE}/api/v1/workspace/ideas/attachments/${attachmentId}`, {
      method: "DELETE",
    }).catch(() => {
      // best-effort; UI already removed entry locally
    });
  }

  function fmtSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setError(null);
    setLoading(true);
    try {
      const allTags = encodeDomain(domain, tags);
      const res = await fetch(`${API_BASE}/api/v1/ideas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          author: "",
          tags: allTags,
          attachments: attachments.map((attachment) => ({
            attachment_id: attachment.attachment_id,
            idea_id: attachment.idea_id,
            filename: attachment.filename,
            file_type: attachment.file_type,
            file_size: attachment.file_size,
          })),
        }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`${res.status}: ${body || res.statusText}`);
      }
      const idea = (await res.json()) as Idea;
      onCreated(idea);
      resetForm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd podczas tworzenia");
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setTitle("");
    setDescription("");
    setDomain("");
    setTagInput("");
    setTags([]);
    setAttachments([]);
    setLocalPath("");
    setLoading(false);
    setUploading(false);
    setImportingLocal(false);
    setError(null);
    setUploadError(null);
  }

  function handleClose() {
    resetForm();
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto border border-border/60 bg-card">
        <DialogHeader>
          <DialogTitle className="text-base font-semibold flex items-center gap-1.5">
            Nowy pomysł
            <HelpTip text="Wypełnij krótki opis ręcznie, a pełny brief lub dokumentację dodaj jako załącznik. AEIS analizuje załączniki przed zapisem, oznacza decyzję D0-D5 i w razie ryzyka tworzy bramkę człowieka." />
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="mt-2 space-y-4">
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">
              Tytuł <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              data-testid="idea-create-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Krótki tytuł pomysłu"
              required
              className={cn(
                "w-full rounded-md border border-border/50 bg-background/60",
                "px-3 py-2 text-sm placeholder:text-muted-foreground/50",
                "focus:outline-none focus:ring-1 focus:ring-primary/50"
              )}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Opis</label>
            <textarea
              value={description}
              data-testid="idea-create-description"
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Szczegóły, motywacja, kontekst..."
              rows={4}
              className={cn(
                "w-full resize-none rounded-md border border-border/50 bg-background/60",
                "px-3 py-2 text-sm placeholder:text-muted-foreground/50",
                "focus:outline-none focus:ring-1 focus:ring-primary/50"
              )}
            />
          </div>

          <div>
              <label className="mb-1 flex items-center gap-1 text-xs text-muted-foreground">
                Domena
                <HelpTip text="Domena pomaga dobrać Radę modeli, skills i domyślne polityki. W V10 wybór domeny nie zastępuje analizy załącznika - system nadal musi wykryć braki i ryzyko." />
              </label>
            <select
              value={domain}
              data-testid="idea-create-domain"
              onChange={(e) => setDomain(e.target.value)}
              className={cn(
                "w-full rounded-md border border-border/50 bg-background/60",
                "px-3 py-2 text-sm text-foreground",
                "focus:outline-none focus:ring-1 focus:ring-primary/50"
              )}
            >
              <option value="">-- wybierz domenę --</option>
              {DOMAINS.map((d) => (
                <option key={d} value={d}>
                  {DOMAIN_LABELS[d]}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Tagi</label>
            {tags.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-1">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="flex items-center gap-1 rounded-full bg-muted/50 px-2 py-0.5 text-xs"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="text-muted-foreground/60 transition-colors hover:text-red-400"
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <input
              type="text"
              data-testid="idea-create-tag"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === ",") {
                  e.preventDefault();
                  addTag(tagInput);
                }
              }}
              onBlur={() => tagInput && addTag(tagInput)}
              placeholder="Wpisz tag i naciśnij Enter"
              className={cn(
                "w-full rounded-md border border-border/50 bg-background/60",
                "px-3 py-2 text-sm placeholder:text-muted-foreground/50",
                "focus:outline-none focus:ring-1 focus:ring-primary/50"
              )}
            />
          </div>

          <div className="space-y-2 rounded-md border border-border/60 bg-muted/10 p-3">
            <div className="flex items-center justify-between gap-3">
              <label className="flex items-center gap-1 text-xs text-muted-foreground">
                Załączniki
                <HelpTip text="Załączniki są materiałem wejściowym przyjęcia projektu. Dla dokumentów V10 system powinien odczytać treść, wykryć decyzję D3/D4/D5, zaproponować umiejętności i przygotować bramkę człowieka, zanim pomysł stanie się projektem." />
              </label>
              <span className="text-[10px] text-muted-foreground">
                PDF / DOCX / ZIP / obrazy / kod / firmware - maks. 50MB na plik
              </span>
            </div>
            <label
              className={cn(
                "flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-border bg-background px-3 py-3 text-xs transition hover:border-primary/60 hover:bg-primary/5",
                uploading && "pointer-events-none opacity-50"
              )}
            >
              <Upload className="h-3.5 w-3.5" />
              <span>
                {uploading
                  ? "Wgrywanie i analiza..."
                  : "Kliknij, aby wgrać plik przed utworzeniem pomysłu. Pliki trafiają najpierw do szkicu."}
              </span>
              <input
                type="file"
                multiple
                accept={ACCEPT_ATTR}
                className="hidden"
                disabled={uploading}
                onChange={(e) => handleFileUpload(e.target.files)}
              />
            </label>
            <div className="grid gap-2 rounded-md border border-border/50 bg-background/40 p-2">
              <label className="text-[11px] text-muted-foreground">
                Import lokalnego pliku po ścieżce (fallback dla testów dashboardu bez systemowego pickera)
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  data-testid="idea-create-local-path"
                  value={localPath}
                  onChange={(e) => setLocalPath(e.target.value)}
                  placeholder="C:\\Users\\...\\pomysł.txt"
                  className={cn(
                    "min-w-0 flex-1 rounded-md border border-border/50 bg-background/60",
                    "px-2 py-1.5 text-xs placeholder:text-muted-foreground/50",
                    "focus:outline-none focus:ring-1 focus:ring-primary/50"
                  )}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!localPath.trim() || importingLocal || uploading}
                  data-testid="idea-create-import-local"
                  onClick={handleLocalImport}
                >
                  {importingLocal && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                  Importuj
                </Button>
              </div>
            </div>
            {uploadError && (
              <p className="rounded border border-red-400/20 bg-red-400/10 px-3 py-2 text-xs text-red-400">
                {uploadError}
              </p>
            )}
            {attachments.length > 0 && (
              <ul className="space-y-1">
                {attachments.map((attachment) => (
                  <li
                    key={attachment.attachment_id}
                    className="grid gap-1 rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5 text-[11px]"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <FileText className="h-3.5 w-3.5 shrink-0 text-primary" />
                      <span className="truncate font-medium">{attachment.filename}</span>
                      <span className="shrink-0 text-muted-foreground">
                          {fmtSize(attachment.file_size)} - {attachment.file_type}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeAttachment(attachment.attachment_id)}
                      className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                       aria-label={`Usuń ${attachment.filename}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                    {attachment.analysis && (
                      <div className="text-[10px] text-muted-foreground">
                        Analiza: {attachment.analysis.decision_class}
                        {attachment.analysis.human_gate_required ? " - bramka człowieka wymagana" : ""}
                        {attachment.analysis.suggested_skills.length
                          ? ` - skills: ${attachment.analysis.suggested_skills.slice(0, 4).join(", ")}`
                          : ""}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {attachments.length > 0 && (
            <div className="rounded-md border border-border/60 bg-background/40 px-3 py-2 text-xs text-muted-foreground">
              Podsumowanie: {attachments.length} załącznik{attachments.length === 1 ? "" : "i"} gotowe przed zapisem.
            </div>
          )}

          {error && (
            <p className="rounded border border-red-400/20 bg-red-400/10 px-3 py-2 text-xs text-red-400">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" size="sm" onClick={handleClose}>
              Anuluj
            </Button>
            <Button
              type="submit"
              size="sm"
              data-testid="idea-create-submit"
              disabled={!title.trim() || loading || uploading || importingLocal}
            >
              {loading && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Dodaj pomysł
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
