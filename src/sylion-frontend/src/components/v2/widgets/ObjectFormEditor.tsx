"use client";

/**
 * SYLION AEIS v2 — W16 G1 widget: ObjectFormEditor.
 *
 * CRUD form for a W15 ontology instance, auto-derived from
 * `spec.dedicated_columns` of the type manifest. Phase 0: persistence is
 * delegated to `onSubmit` (caller wires it to W15 OSDK in G2).
 */

import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Loader2, AlertTriangle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { HelpTip } from "@/components/common/HelpTip";
import { request } from "@/lib/api/client";

interface DedicatedColumn {
  name: string;
  type: string;
  nullable?: boolean;
  searchable?: boolean;
  enum?: string[] | null;
  default?: unknown;
  description?: string;
}

interface OntologyManifest {
  metadata: { id: string; name_pl: string; name_en?: string };
  spec: { dedicated_columns: DedicatedColumn[] };
}

export interface ObjectFormEditorProps {
  typeId: string;
  instanceId?: string;
  initialValues?: Record<string, unknown>;
  onSubmit: (values: Record<string, unknown>) => Promise<void>;
  onCancel?: () => void;
}

const NUMERIC = new Set(["integer", "bigint", "numeric"]);
const INPUT_CLS =
  "rounded-md border border-foreground/15 bg-background px-2 py-1.5 text-sm outline-none transition focus:border-sylion-blue/60 focus:ring-1 focus:ring-sylion-blue/40";

export function ObjectFormEditor({
  typeId,
  instanceId,
  initialValues,
  onSubmit,
  onCancel,
}: ObjectFormEditorProps) {
  const [manifest, setManifest] = useState<OntologyManifest | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>(initialValues ?? {});
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    request<OntologyManifest>(`/api/v1/ontology/types/${encodeURIComponent(typeId)}`)
      .then((m) => active && setManifest(m))
      .catch((err: unknown) => active && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [typeId]);

  const isEdit = !!instanceId;

  const validationError = useMemo<string | null>(() => {
    if (!manifest) return null;
    for (const col of manifest.spec.dedicated_columns) {
      if (col.name === "id") continue;
      const v = values[col.name];
      const empty = v === undefined || v === null || v === "";
      if (col.nullable === false && empty) return `Pole "${col.name}" jest wymagane.`;
      if (col.enum && !empty && !col.enum.includes(String(v))) {
        return `Pole "${col.name}" musi być jedną z: ${col.enum.join(", ")}.`;
      }
    }
    return null;
  }, [manifest, values]);

  const setField = (name: string, value: unknown): void =>
    setValues((prev) => ({ ...prev, [name]: value }));

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    if (validationError) {
      setSubmitError(validationError);
      return;
    }
    setSubmitError(null);
    setSubmitting(true);
    try {
      await onSubmit(values);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  function renderField(col: DedicatedColumn, id: string, v: unknown): ReactNode {
    const onChg = (val: unknown): void => setField(col.name, val);
    const sv = String(v ?? "");
    if (col.name === "id" || col.type === "uuid") {
      return isEdit
        ? <input id={id} type="text" readOnly value={sv}
            className={`${INPUT_CLS} cursor-not-allowed text-muted-foreground`} />
        : null;
    }
    if (col.enum && col.enum.length > 0) return (
      <select id={id} value={sv} className={INPUT_CLS} onChange={(e) => onChg(e.target.value)}>
        <option value="">— wybierz —</option>
        {col.enum.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
    if (col.type === "boolean") return (
      <Switch id={id} checked={!!v} onCheckedChange={(c: boolean) => onChg(c)} />
    );
    if (NUMERIC.has(col.type)) return (
      <input id={id} type="number" className={INPUT_CLS}
        value={v === undefined || v === null ? "" : String(v)}
        onChange={(e) => onChg(e.target.value === "" ? null : Number(e.target.value))} />
    );
    if (col.type === "timestamptz" || col.type === "date") return (
      <input id={id} type={col.type === "date" ? "date" : "datetime-local"}
        value={sv} className={INPUT_CLS} onChange={(e) => onChg(e.target.value)} />
    );
    if (col.type === "text" && col.searchable) return (
      <textarea id={id} rows={3} value={sv} className={`${INPUT_CLS} resize-y`}
        onChange={(e) => onChg(e.target.value)} />
    );
    return <input id={id} type="text" value={sv} className={INPUT_CLS}
      onChange={(e) => onChg(e.target.value)} />;
  }

  return (
    <Card className="overflow-hidden">
      <header className="border-b border-foreground/10 px-4 py-2">
        <h3 className="text-sm font-semibold">
          {isEdit ? "Edycja" : "Nowy"}
          {manifest ? `: ${manifest.metadata.name_pl}` : ""}
        </h3>
      </header>

      {loading && (
        <div className="flex items-center justify-center gap-2 px-4 py-6 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Wczytywanie manifestu…
        </div>
      )}
      {error && !loading && (
        <div className="flex items-center gap-2 px-4 py-3 text-xs text-destructive">
          <AlertTriangle className="h-3.5 w-3.5" /> Błąd manifestu: {error}
        </div>
      )}

      {manifest && !loading && !error && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-3 px-4 py-3">
          {manifest.spec.dedicated_columns.map((col) => {
            if (col.name === "id" && !isEdit) return null;
            const id = `${typeId}-${col.name}`;
            return (
              <div key={col.name} className="flex flex-col gap-1">
                <label htmlFor={id} className="text-[11px] font-medium uppercase text-muted-foreground">
                  {col.name}
                  {col.nullable === false && <span className="ml-0.5 text-destructive">*</span>}
                  {col.description && <HelpTip text={col.description} />}
                </label>
                {renderField(col, id, values[col.name])}
              </div>
            );
          })}

          {(submitError || validationError) && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-[11px] text-destructive">
              {submitError ?? validationError}
            </div>
          )}

          <footer className="mt-1 flex items-center justify-end gap-2 border-t border-foreground/10 pt-3">
            {onCancel && (
              <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={submitting}>Anuluj</Button>
            )}
            <Button type="submit" size="sm" disabled={submitting || validationError !== null}>
              {submitting ? "Zapisywanie…" : "Zapisz"}
            </Button>
          </footer>
        </form>
      )}
    </Card>
  );
}
