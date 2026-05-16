"use client";

import React, { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";
import {
  BookOpen,
  Plus,
  Loader2,
  Download,
  ChevronDown,
  ChevronRight,
  Sparkles,
  WifiOff,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Book {
  book_id: string;
  title: string;
  description: string;
  status: string;
  chapter_count: number;
  created_at: number;
}

interface Chapter {
  chapter_number: number;
  title: string;
  content: string;
  hash: string;
}

export function BookGeneratorPanel() {
  const { data: health } = useHealth();
  const backendLive = health?.status === "ok";

  const [books, setBooks] = useState<Book[]>([]);
  const [selectedBook, setSelectedBook] = useState<string | null>(null);
  const [bookDetail, setBookDetail] = useState<any>(null);
  const [generating, setGenerating] = useState(false);
  const [exportContent, setExportContent] = useState<string | null>(null);
  const [expandedChapters, setExpandedChapters] = useState<Set<number>>(new Set());

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [sourceSessions, setSourceSessions] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!backendLive) return;
    api.listBooks()
      .then((d) => { setBooks(d.books ?? []); })
      .catch(() => {});
  }, [backendLive]);

  const loadBook = async (bookId: string) => {
    setSelectedBook(bookId);
    setExportContent(null);
    try {
      const detail = await api.getBook(bookId);
      setBookDetail(detail);
    } catch {
      setBookDetail(null);
    }
  };

  const handleCreate = async () => {
    if (!newTitle.trim() || creating) return;
    setCreating(true);
    try {
      const result = await api.createBook(newTitle, newDesc);
      if (sourceSessions.trim()) {
        setGenerating(true);
        await api.generateBookFromChat(result.book_id, sourceSessions.split(",").map((s) => s.trim()));
        setGenerating(false);
      }
      const d = await api.listBooks();
      setBooks(d.books ?? []);
      setSelectedBook(result.book_id);
      await loadBook(result.book_id);
      setNewTitle("");
      setNewDesc("");
      setSourceSessions("");
      setShowCreate(false);
    } catch {}
    setCreating(false);
  };

  const handleExport = async (bookId: string, format: string) => {
    try {
      const result = await api.exportBook(bookId, format);
      setExportContent(result.content);
    } catch {}
  };

  const toggleChapter = (num: number) => {
    setExpandedChapters((prev) => {
      const next = new Set(prev);
      if (next.has(num)) next.delete(num);
      else next.add(num);
      return next;
    });
  };

  if (!backendLive) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <WifiOff className="w-8 h-8 text-sylion-red/50 mb-3" />
        <p className="text-xs text-muted-foreground">Backend niedostępny</p>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Book list */}
      <div className="w-52 shrink-0 border-r border-[rgba(148,163,184,0.06)] p-2 space-y-1 overflow-y-auto">
        <Button variant="ghost" size="sm" className="w-full justify-start text-[11px] h-7" onClick={() => setShowCreate(!showCreate)}>
          <Plus className="w-3 h-3 mr-1.5" /> New Book
        </Button>
        {books.map((b) => (
          <button
            key={b.book_id}
            onClick={() => loadBook(b.book_id)}
            className={cn(
              "w-full text-left px-2.5 py-2 rounded-lg text-[11px] transition-colors",
              selectedBook === b.book_id
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted/20"
            )}
          >
            <span className="truncate block font-medium">{b.title}</span>
            <span className="text-[9px] text-muted-foreground">
              {b.chapter_count} ch. &middot; {b.status}
            </span>
          </button>
        ))}
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Create form */}
        {showCreate && (
          <Card className="p-3 mb-4 bg-card border-primary/15 space-y-2">
            <p className="text-[11px] font-medium">Create Book</p>
            <input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Book title"
              className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30"
            />
            <input
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Description (optional)"
              className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30"
            />
            <input
              value={sourceSessions}
              onChange={(e) => setSourceSessions(e.target.value)}
              placeholder="Chat session IDs (comma-separated, optional)"
              className="w-full bg-secondary/20 border border-[rgba(148,163,184,0.1)] rounded px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/30"
            />
            <div className="flex gap-2">
              <Button size="sm" className="h-7 text-[10px]" onClick={handleCreate} disabled={creating || generating}>
                {creating || generating ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Sparkles className="w-3 h-3 mr-1" />}
                {generating ? "Generating..." : "Create & Generate"}
              </Button>
              <Button variant="ghost" size="sm" className="h-7 text-[10px]" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
            </div>
          </Card>
        )}

        {/* Book detail */}
        {bookDetail ? (
          <div className="space-y-3">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-sm font-semibold">{bookDetail.title}</h3>
                {bookDetail.description && (
                  <p className="text-[11px] text-muted-foreground mt-0.5">{bookDetail.description}</p>
                )}
              </div>
              <div className="flex gap-1.5">
                <Button variant="ghost" size="sm" className="h-7 text-[10px] gap-1" onClick={() => handleExport(bookDetail.book_id, "markdown")}>
                  <Download className="w-3 h-3" /> MD
                </Button>
                <Button variant="ghost" size="sm" className="h-7 text-[10px] gap-1" onClick={() => handleExport(bookDetail.book_id, "json")}>
                  <Download className="w-3 h-3" /> JSON
                </Button>
              </div>
            </div>

            {/* Export preview */}
            {exportContent && (
              <Card className="p-3 bg-[#0a0f1e] border-primary/15">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] font-medium text-primary">Export Preview</p>
                  <Button variant="ghost" size="sm" className="h-5 text-[8px]" onClick={() => setExportContent(null)}>
                    Close
                  </Button>
                </div>
                <pre className="text-[10px] text-muted-foreground whitespace-pre-wrap font-mono max-h-60 overflow-y-auto">{exportContent}</pre>
              </Card>
            )}

            {/* Chapters accordion */}
            <div className="space-y-1">
              {(bookDetail.chapters || []).map((ch: Chapter) => (
                <Card key={ch.chapter_number} className="bg-card border-[rgba(148,163,184,0.06)]">
                  <button
                    className="w-full flex items-center gap-2 px-3 py-2 text-left"
                    onClick={() => toggleChapter(ch.chapter_number)}
                  >
                    {expandedChapters.has(ch.chapter_number) ? (
                      <ChevronDown className="w-3 h-3 text-muted-foreground shrink-0" />
                    ) : (
                      <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />
                    )}
                    <span className="text-[10px] font-medium text-primary shrink-0">Ch {ch.chapter_number}</span>
                    <span className="text-[11px] truncate">{ch.title}</span>
                  </button>
                  {expandedChapters.has(ch.chapter_number) && (
                    <div className="px-3 pb-3 border-t border-[rgba(148,163,184,0.06)] pt-2">
                      <p className="text-[11px] text-muted-foreground leading-relaxed whitespace-pre-wrap">{ch.content}</p>
                    </div>
                  )}
                </Card>
              ))}
              {(!bookDetail.chapters || bookDetail.chapters.length === 0) && (
                <p className="text-xs text-muted-foreground text-center py-4">
                  No chapters yet. Generate from chat or council sessions.
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full">
            <BookOpen className="w-8 h-8 text-primary/30 mb-3" />
            <p className="text-xs text-muted-foreground">Select or create a book</p>
          </div>
        )}
      </div>
    </div>
  );
}
