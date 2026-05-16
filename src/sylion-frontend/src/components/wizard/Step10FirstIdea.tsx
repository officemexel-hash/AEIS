"use client";

import { Lightbulb, Upload, FileText, X } from "lucide-react";
import { useState } from "react";
import { SmartDefault } from "./SmartDefault";
import { PROJECT_DOMAINS } from "./Step4Domain";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export const PROJECT_TYPES: Array<{ id: string; label: string; hint: string }> = [
  { id: "research", label: "Badania", hint: "Eksploracja, prototypy, wnioski." },
  { id: "experiment", label: "Eksperyment", hint: "Walidacja ograniczona czasowo." },
  { id: "production", label: "Produkcja", hint: "Produkt dla klientów albo generujący przychód." },
  { id: "internal_tool", label: "Narzędzie wewnętrzne", hint: "Narzędzie tylko dla organizacji." },
];

// F-016: file types supported by /api/v1/workspace/ideas/upload (50MB limit per file).
// Documents/PDFs/images/archives + arbitrary code so AEIS can verify, expand,
// advise, fix and deploy. Hardware-targeted attachments (Android APK, .ino,
// .py firmware) are accepted as octet-stream.
const ACCEPT_ATTR = [
  ".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md",
  ".zip", ".tar", ".gz", ".7z",
  ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
  ".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".kt", ".swift",
  ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".rb", ".php",
  ".json", ".yaml", ".yml", ".toml", ".ini", ".env",
  ".apk", ".ino", ".bin", ".hex",  // Android / firmware / hardware
  "image/*", "application/pdf", "application/zip",
  "text/*", "application/octet-stream",
].join(",");

export interface Step10Attachment {
  attachment_id: string;
  idea_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  draft_idea?: boolean;
}

export interface Step10AttachmentAnalysis {
  analysis_id: string;
  attachment_id: string;
  idea_id: string;
  filename: string;
  detected_kind: string;
  decision_class: string;
  human_gate_required: boolean;
  tags: string[];
  risks: string[];
  missing_info: string[];
  suggested_skills: string[];
  image_analysis_status?: string;
}

export interface Step10Values {
  first_idea_title?: string;
  first_idea_description?: string;
  first_idea_project_type?: string;
  first_idea_project_domain?: string;
  first_idea_attachments?: Step10Attachment[];
  first_idea_attachment_analysis?: Step10AttachmentAnalysis[];
}

interface Props {
  values: Step10Values;
  defaultDomain?: string;
  onChange: (patch: Step10Values) => void;
}

export function Step10FirstIdea({ values, defaultDomain, onChange }: Props) {
  const showAdvisor =
    !values.first_idea_project_type ||
    !values.first_idea_project_domain;
  const defaultDomainLabel =
    PROJECT_DOMAINS.find((domain) => domain.id === defaultDomain)?.label ??
    defaultDomain ??
    "Oprogramowanie";
  const attachments = values.first_idea_attachments ?? [];
  const [uploading, setUploading] = useState(false);
  const [importingLocal, setImportingLocal] = useState(false);
  const [localImportPath, setLocalImportPath] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  async function handleFileUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadError(null);
    const newAttachments: Step10Attachment[] = [...attachments];
    try {
      for (const file of Array.from(files)) {
        if (file.size > 50 * 1024 * 1024) {
          setUploadError(`${file.name} ma więcej niż 50 MB.`);
          continue;
        }
        const fd = new FormData();
        fd.append("file", file);
        // Reuse first attachment's idea_id so multiple uploads land under
        // the same draft idea record. New uploads with no prior get auto draft id.
        const sharedId = newAttachments[0]?.idea_id;
        if (sharedId) fd.append("idea_id", sharedId);
        const res = await fetch(`${API_BASE}/api/v1/workspace/ideas/upload`, {
          method: "POST",
          body: fd,
        });
        if (!res.ok) {
          const body = await res.text().catch(() => "");
          setUploadError(`Upload nie powiódł się dla ${file.name}: ${res.status} ${body.slice(0, 120)}`);
          continue;
        }
        const json = (await res.json()) as Step10Attachment;
        newAttachments.push(json);
      }
      onChange({ first_idea_attachments: newAttachments });
    } finally {
      setUploading(false);
    }
  }

  async function handleLocalPathImport() {
    const filePath = localImportPath.trim();
    if (!filePath) {
      setUploadError("Podaj sciezke pliku do importu lokalnego.");
      return;
    }
    setImportingLocal(true);
    setUploadError(null);
    try {
      const sharedId = attachments[0]?.idea_id;
      const res = await fetch(`${API_BASE}/api/v1/workspace/ideas/import-local`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: filePath, idea_id: sharedId ?? "" }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        setUploadError(`Local import failed: ${res.status} ${body.slice(0, 180)}`);
        return;
      }
      const json = (await res.json()) as Step10Attachment;
      onChange({ first_idea_attachments: [...attachments, json] });
      setLocalImportPath("");
    } finally {
      setImportingLocal(false);
    }
  }

  function removeAttachment(attachment_id: string) {
    onChange({
      first_idea_attachments: attachments.filter((a) => a.attachment_id !== attachment_id),
      first_idea_attachment_analysis: (values.first_idea_attachment_analysis ?? []).filter(
        (a) => a.attachment_id !== attachment_id,
      ),
    });
    fetch(`${API_BASE}/api/v1/workspace/ideas/attachments/${attachment_id}`, {
      method: "DELETE",
    }).catch(() => {
      // best-effort; UI already removed entry locally
    });
  }

  async function analyzeAttachments() {
    if (attachments.length === 0) return;
    const ideaId = attachments[0]?.idea_id;
    if (!ideaId) {
      setAnalysisError("Nie można analizować: brakuje ID szkicu pomysłu.");
      return;
    }
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/workspace/ideas/${encodeURIComponent(ideaId)}/attachments/analyze`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        setAnalysisError(`Analiza nie powiodła się: ${res.status} ${body.slice(0, 160)}`);
        return;
      }
      const json = (await res.json()) as { analyses?: Step10AttachmentAnalysis[] };
      onChange({ first_idea_attachment_analysis: json.analyses ?? [] });
    } finally {
      setAnalyzing(false);
    }
  }

  function fmtSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 rounded-md border border-sylion-amber/30 bg-sylion-amber/5 p-3 text-xs">
        <Lightbulb className="h-4 w-4 text-sylion-amber" />
        <span className="text-muted-foreground">
          Opcjonalne — możesz pominąć ten krok i utworzyć pierwszy pomysł później w Skarbcu Pomysłów.
        </span>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Tytuł
        </label>
        <input
          type="text"
          value={values.first_idea_title ?? ""}
          onChange={(e) => onChange({ first_idea_title: e.target.value })}
          placeholder="Krótki, konkretny tytuł"
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none transition focus:border-sylion-blue/60"
          data-testid="step10-title"
        />
      </div>

      <div className="space-y-1.5">
        <label className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <span>Pierwsza intencja — co AEIS ma zrobić jako pierwsze?</span>
          <span className="text-[10px] font-normal normal-case opacity-70">
            może być jedno słowo lub akapit
          </span>
        </label>
        <textarea
          value={values.first_idea_description ?? ""}
          onChange={(e) => onChange({ first_idea_description: e.target.value })}
          placeholder='np. „przeanalizuj”, „zrób audyt bezpieczeństwa”, „rozbuduj API o moduł X”, „przepisz frontend w Next.js”…'
          rows={4}
          className="w-full resize-y rounded-md border border-border bg-background px-3 py-2 text-sm outline-none transition focus:border-sylion-blue/60"
          data-testid="step10-description"
        />
        <p className="text-[11px] text-muted-foreground/80">
          Po zakończeniu konfiguracji AEIS otworzy projekt, przeczyta załączone pliki i odpowie na tę intencję
          (zacznie rozmowę / propozycję konfiguracji).
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-1.5">
          <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Typ projektu
          </label>
          <div className="space-y-1.5" data-testid="step10-project-type">
            {PROJECT_TYPES.map((t) => {
              const active = values.first_idea_project_type === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => onChange({ first_idea_project_type: t.id })}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-md border px-2.5 py-1.5 text-left transition",
                    active
                      ? "border-sylion-blue/60 bg-sylion-blue/10 text-sylion-blue"
                      : "border-border hover:bg-muted/30",
                  )}
                  data-testid={`step10-type-${t.id}`}
                  data-active={active}
                >
                  <div>
                    <p className="text-xs font-medium">{t.label}</p>
                    <p className="mt-0.5 text-[10px] text-muted-foreground">{t.hint}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Domena projektu
          </label>
          <select
            value={values.first_idea_project_domain ?? ""}
            onChange={(e) => onChange({ first_idea_project_domain: e.target.value })}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-sylion-blue/60"
            data-testid="step10-project-domain"
          >
            <option value="">— wybierz domenę —</option>
            {PROJECT_DOMAINS.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* F-016: Attachments — pdf/docs/zip/img/code/firmware so AEIS can
          verify, expand, advise, fix, deploy, connect with hardware. */}
      <div className="space-y-2 rounded-md border border-border bg-muted/10 p-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Załączniki (opcjonalne)
          </label>
          <span className="text-[10px] text-muted-foreground">
            PDF / DOCX / ZIP / obrazy / kod źródłowy / firmware / APK · maks. 50 MB każdy
          </span>
        </div>
        <label
          className={cn(
            "flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-border bg-background px-3 py-3 text-xs transition hover:border-sylion-blue/60 hover:bg-sylion-blue/5",
            uploading && "pointer-events-none opacity-50",
          )}
          data-testid="step10-attachment-dropzone"
        >
          <Upload className="h-3.5 w-3.5" />
          <span>
            {uploading
              ? "Wysyłanie…"
              : "Kliknij, aby dodać pliki — trafią do szkicu pomysłu, żeby AEIS mógł je przeczytać, zweryfikować, doradzić, poprawić i wdrożyć."}
          </span>
          <input
            type="file"
            multiple
            accept={ACCEPT_ATTR}
            className="hidden"
            disabled={uploading}
            onChange={(e) => handleFileUpload(e.target.files)}
            data-testid="step10-attachment-input"
          />
        </label>
        <details
          className="rounded-md border border-dashed border-border/60 px-3 py-2 text-[11px]"
          data-testid="step10-local-import"
        >
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            Import pliku lokalnego przez ścieżkę (widoczne w dashboardzie)
          </summary>
          <div className="mt-2 flex flex-col gap-2 md:flex-row">
            <input
              type="text"
              value={localImportPath}
              onChange={(e) => setLocalImportPath(e.target.value)}
              placeholder="C:\\Users\\...\\idea.md"
              className="min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-2 text-xs outline-none focus:border-sylion-blue/60"
              data-testid="step10-local-path-input"
            />
            <button
              type="button"
              onClick={handleLocalPathImport}
              disabled={importingLocal}
              className="rounded-md border border-sylion-blue/40 px-3 py-2 text-xs text-sylion-blue hover:bg-sylion-blue/10 disabled:opacity-50"
              data-testid="step10-local-path-import"
            >
              {importingLocal ? "Importowanie..." : "Importuj ścieżkę"}
            </button>
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">
            Używane w lokalnych audytach, gdy okno wyboru plików przeglądarki nie daje się automatyzować;
            pliki nadal trafiają do tego samego magazynu załączników i tej samej analizy.
          </p>
        </details>
        {uploadError ? (
          <p className="text-[11px] text-red-400" data-testid="step10-attachment-error">
            {uploadError}
          </p>
        ) : null}
        {attachments.length > 0 ? (
          <ul className="space-y-1" data-testid="step10-attachment-list">
            {attachments.map((a) => (
              <li
                key={a.attachment_id}
                className="flex items-center justify-between gap-2 rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5 text-[11px]"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <FileText className="h-3.5 w-3.5 shrink-0 text-sylion-blue" />
                  <span className="truncate font-medium">{a.filename}</span>
                  <span className="shrink-0 text-muted-foreground">
                    {fmtSize(a.file_size)} · {a.file_type}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => removeAttachment(a.attachment_id)}
                  className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                  aria-label={`Remove ${a.filename}`}
                  data-testid={`step10-attachment-remove-${a.attachment_id}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {attachments.length > 0 ? (
          <div className="space-y-2">
            <button
              type="button"
              onClick={analyzeAttachments}
              disabled={analyzing}
              className="rounded-md border border-sylion-blue/40 px-3 py-1.5 text-xs text-sylion-blue hover:bg-sylion-blue/10 disabled:opacity-50"
              data-testid="step10-analyze-attachments"
            >
              {analyzing ? "Analiza załączników..." : "Analizuj załączniki przez AEIS"}
            </button>
            {analysisError ? (
              <p className="text-[11px] text-red-400" data-testid="step10-analysis-error">
                {analysisError}
              </p>
            ) : null}
            {(values.first_idea_attachment_analysis ?? []).length > 0 ? (
              <div className="space-y-1" data-testid="step10-analysis-list">
                {(values.first_idea_attachment_analysis ?? []).map((analysis) => (
                  <div
                    key={analysis.analysis_id}
                    className="rounded-md border border-sylion-green/25 bg-sylion-green/5 px-2.5 py-2 text-[11px]"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-medium">{analysis.filename}</span>
                      <span className="font-mono text-sylion-green">{analysis.decision_class}</span>
                    </div>
                    <div className="mt-1 text-muted-foreground">
                      {analysis.detected_kind}
                      {analysis.human_gate_required ? " · wymagany HumanGate" : " · bez HumanGate"}
                    </div>
                    {analysis.tags.length > 0 ? (
                      <div className="mt-1 text-muted-foreground">
                        tagi: {analysis.tags.join(", ")}
                      </div>
                    ) : null}
                    {analysis.risks.length > 0 ? (
                      <div className="mt-1 text-sylion-amber">
                        ryzyka: {analysis.risks.slice(0, 2).join(" | ")}
                      </div>
                    ) : null}
                    {analysis.missing_info.length > 0 ? (
                      <div className="mt-1 text-sylion-blue">
                        pytania: {analysis.missing_info.slice(0, 2).join(" | ")}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {showAdvisor ? (
        <SmartDefault
          label={`Użyj: Badania + ${defaultDomainLabel}`}
          rationale="Najniższe ryzyko startu; możesz podnieść klasę pomysłu po zakończeniu intake."
          onApply={() =>
            onChange({
              first_idea_project_type: "research",
              first_idea_project_domain: defaultDomain ?? "software",
            })
          }
        />
      ) : null}

      {/* F-025: clear preview of what Complete setup will hand to AEIS. Removes
          the previous black-box behaviour where Complete did "nothing visible"
          even though it had created an empty preferences entry. */}
      {(values.first_idea_title ?? "").trim() || (values.first_idea_description ?? "").trim() ? (
        <div
          className="rounded-md border border-sylion-blue/30 bg-sylion-blue/5 p-3 text-xs"
          data-testid="step10-summary"
        >
          <p className="mb-1 flex items-center gap-1.5 font-semibold text-sylion-blue">
            <Lightbulb className="h-3.5 w-3.5" />
            Po kliknięciu „Zakończ konfigurację” AEIS dostanie:
          </p>
          <ul className="ml-5 list-disc space-y-0.5 text-muted-foreground">
            <li>
              Projekt:{" "}
              <span className="font-mono text-foreground">
                {(values.first_idea_title ?? "").trim() || "(bez tytułu — wygenerujemy)"}
              </span>
              {values.first_idea_project_type
                ? ` · typ: ${values.first_idea_project_type}`
                : ""}
              {values.first_idea_project_domain ? ` · domena: ${values.first_idea_project_domain}` : ""}
            </li>
            <li>
              Intencja:{" "}
              <span className="italic text-foreground">
                „{((values.first_idea_description ?? "").trim() || "(brak — operator skonfiguruje później)").slice(0, 200)}”
              </span>
            </li>
            <li>
              Załączniki:{" "}
              {(values.first_idea_attachments ?? []).length === 0 ? (
                <span className="opacity-70">brak</span>
              ) : (
                <span className="text-foreground">
                  {(values.first_idea_attachments ?? []).length}{" "}
                  {(values.first_idea_attachments ?? []).length === 1 ? "plik" : "plików"}
                  {" "}({((values.first_idea_attachments ?? []).reduce((a, b) => a + b.file_size, 0) / 1024 / 1024).toFixed(1)} MB)
                </span>
              )}
            </li>
            <li>
              Analiza załączników:{" "}
              {(values.first_idea_attachment_analysis ?? []).length === 0 ? (
                <span className="opacity-70">nie uruchomiono</span>
              ) : (
                <span className="text-foreground">
                  {(values.first_idea_attachment_analysis ?? []).length} wyników,
                  najwyższa klasa{" "}
                  {(values.first_idea_attachment_analysis ?? [])
                    .map((a) => a.decision_class)
                    .sort()
                    .at(-1)}
                </span>
              )}
            </li>
          </ul>
          <p className="mt-2 text-[11px] text-sylion-blue/80">
            Następny krok: zostaniesz przekierowany do strony projektu — AEIS przeczyta załączniki
            i odpowie na Twój intent w panelu rozmowy.
          </p>
        </div>
      ) : null}
    </div>
  );
}
