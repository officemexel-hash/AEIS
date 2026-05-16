"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetTrigger,
} from "@/components/ui/sheet";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import {
  FileText,
  Plus,
  Loader2,
  Variable,
  Eye,
  Pencil,
} from "lucide-react";

interface Template {
  template_id: string;
  name: string;
  category: string;
  content: string;
  variables: string[];
  version: number;
  updated_at: number;
}

export function PromptManager() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";

  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [editTemplate, setEditTemplate] = useState<Template | null>(null);
  const [previewResolved, setPreviewResolved] = useState<string | null>(null);

  // New template form
  const [newName, setNewName] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [newContent, setNewContent] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!backendLive) return;
    setLoading(true);
    api.listPromptTemplates()
      .then((d) => { setTemplates(d.templates ?? []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [backendLive]);

  const extractVariables = (text: string): string[] => {
    const matches = text.match(/\{([^}]+)\}/g) || [];
    return [...new Set(matches.map((m) => m.slice(1, -1)))];
  };

  const handleCreate = async () => {
    if (!newName.trim() || !newContent.trim() || creating) return;
    setCreating(true);
    try {
      await api.createPromptTemplate(newName, newCategory || "general", newContent);
      const d = await api.listPromptTemplates();
      setTemplates(d.templates ?? []);
      setNewName("");
      setNewCategory("");
      setNewContent("");
    } catch {}
    setCreating(false);
  };

  const handleUpdate = async (templateId: string, content: string) => {
    try {
      await api.updatePromptTemplate(templateId, content);
      const d = await api.listPromptTemplates();
      setTemplates(d.templates ?? []);
      setEditTemplate(null);
    } catch {}
  };

  const handlePreview = async (templateId: string) => {
    const vars = editTemplate?.variables || [];
    const dummyVars: Record<string, string> = {};
    vars.forEach((v) => { dummyVars[v] = `[${v}]`; });
    try {
      const result = await api.resolvePromptTemplate(templateId, dummyVars);
      setPreviewResolved(result.resolved);
    } catch {
      setPreviewResolved(null);
    }
  };

  const categories = [...new Set(templates.map((t) => t.category))];

  return (
    <Sheet>
      <SheetTrigger
        render={<Button variant="ghost" size="sm" className="h-7 text-[10px] gap-1.5" />}
      >
        <FileText className="w-3 h-3" />
        Templates
      </SheetTrigger>
      <SheetContent side="right" className="w-[420px] bg-[#0d1224] border-l border-[rgba(148,163,184,0.08)]">
        <SheetHeader>
          <SheetTitle className="text-sm">Prompt Templates</SheetTitle>
          <SheetDescription className="text-[11px]">
            Create reusable prompts with {"{variable}"} placeholders
          </SheetDescription>
        </SheetHeader>

        <div className="px-4 pb-4 space-y-4 overflow-y-auto flex-1">
          {/* Category filter */}
          {categories.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {categories.map((cat) => (
                <Badge key={cat} variant="outline" className="text-[9px] border-primary/20 text-primary">
                  {cat}
                </Badge>
              ))}
            </div>
          )}

          {/* Template list */}
          {loading ? (
            <div className="flex justify-center py-6">
              <Loader2 className="w-4 h-4 text-muted-foreground animate-spin" />
            </div>
          ) : (
            <div className="space-y-2">
              {templates.map((t) => (
                <TemplateCard
                  key={t.template_id}
                  template={t}
                  onEdit={() => setEditTemplate(t)}
                  onPreview={() => handlePreview(t.template_id)}
                />
              ))}
              {templates.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-4">No templates yet</p>
              )}
            </div>
          )}

          {/* Create new */}
          <div className="border border-[rgba(148,163,184,0.08)] rounded-lg p-3 space-y-2">
            <p className="text-[11px] font-medium text-foreground">New Template</p>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Template name"
              className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30"
            />
            <input
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              placeholder="Category (e.g. analysis, review)"
              className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30"
            />
            <textarea
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              placeholder="Prompt content with {variable} placeholders..."
              rows={4}
              className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30 resize-none"
            />
            {newContent && extractVariables(newContent).length > 0 && (
              <div className="flex flex-wrap gap-1">
                {extractVariables(newContent).map((v) => (
                  <span key={v} className="inline-flex items-center gap-1 text-[9px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                    <Variable className="w-2.5 h-2.5" />
                    {v}
                  </span>
                ))}
              </div>
            )}
            <Button size="sm" className="h-7 text-[10px] w-full" onClick={handleCreate} disabled={creating || !newName.trim()}>
              {creating ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Plus className="w-3 h-3 mr-1" />}
              Create Template
            </Button>
          </div>

          {/* Preview */}
          {previewResolved && (
            <div className="border border-primary/20 rounded-lg p-3 space-y-1.5">
              <p className="text-[10px] font-medium text-primary flex items-center gap-1.5">
                <Eye className="w-3 h-3" /> Preview (dummy variables)
              </p>
              <pre className="text-[10px] text-muted-foreground whitespace-pre-wrap font-mono">{previewResolved}</pre>
              <Button variant="ghost" size="sm" className="h-6 text-[9px]" onClick={() => setPreviewResolved(null)}>
                Close
              </Button>
            </div>
          )}
        </div>

        {/* Edit dialog */}
        {editTemplate && (
          <PromptEditor
            template={editTemplate}
            onSave={(content) => handleUpdate(editTemplate.template_id, content)}
            onClose={() => setEditTemplate(null)}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

function TemplateCard({ template, onEdit, onPreview }: { template: Template; onEdit: () => void; onPreview: () => void }) {
  return (
    <Card className="p-2.5 bg-card border-[rgba(148,163,184,0.06)] hover:border-primary/15 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium truncate">{template.name}</p>
          <div className="flex items-center gap-1.5 mt-1">
            <Badge variant="outline" className="text-[8px] h-4 border-sylion-border">{template.category}</Badge>
            {template.variables?.slice(0, 3).map((v) => (
              <span key={v} className="text-[8px] text-primary/70">{"{" + v + "}"}</span>
            ))}
            {template.variables?.length > 3 && (
              <span className="text-[8px] text-muted-foreground">+{template.variables.length - 3}</span>
            )}
          </div>
        </div>
        <div className="flex gap-1 shrink-0">
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={onPreview} title="Preview">
            <Eye className="w-3 h-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={onEdit} title="Edit">
            <Pencil className="w-3 h-3" />
          </Button>
        </div>
      </div>
      <p className="text-[10px] text-muted-foreground mt-1.5 line-clamp-2">{template.content}</p>
      <p className="text-[8px] text-muted-foreground mt-1">v{template.version}</p>
    </Card>
  );
}

function PromptEditor({ template, onSave, onClose }: { template: Template; onSave: (content: string) => void; onClose: () => void }) {
  const [content, setContent] = useState(template.content);
  const [saving, setSaving] = useState(false);

  return (
    <div className="border-t border-[rgba(148,163,184,0.08)] p-4 space-y-2">
      <p className="text-[11px] font-medium">Edit: {template.name}</p>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={8}
        className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2.5 py-1.5 text-xs text-foreground font-mono focus:outline-none focus:border-primary/30 resize-none"
      />
      <div className="flex gap-2">
        <Button size="sm" className="h-7 text-[10px] flex-1" onClick={() => { setSaving(true); onSave(content); }} disabled={saving}>
          {saving ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
          Save
        </Button>
        <Button variant="ghost" size="sm" className="h-7 text-[10px]" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
