"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { FAQ_ENTRIES, FAQ_CATEGORY_LABELS, type FaqEntry } from "@/data/faq-entries";

function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/gs, "<ul>$&</ul>")
    .replace(/```[\w]*\n([\s\S]*?)```/g, "<pre><code>$1</code></pre>");
}

export function FaqEntryCard({ entry, defaultOpen = false }: { entry: FaqEntry; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);

  const related = FAQ_ENTRIES.filter(
    (e) => entry.relatedIds.includes(e.id) && e.id !== entry.id
  );

  return (
    <div
      id={entry.id}
      className="border rounded-lg overflow-hidden transition-colors duration-200"
      style={{ borderColor: "rgba(148,163,184,0.1)", backgroundColor: "oklch(0.13 0.005 280)" }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-3 px-5 py-4 text-left group"
        aria-expanded={open}
      >
        <motion.div
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.18 }}
          className="mt-0.5 shrink-0"
        >
          <ChevronDown
            className="w-4 h-4"
            style={{ color: "oklch(0.55 0.12 260)" }}
          />
        </motion.div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span
              className="text-sm font-medium"
              style={{ color: "oklch(0.93 0.01 260)" }}
            >
              {entry.question}
            </span>
            <Badge
              variant="outline"
              className="text-[10px] px-1.5 py-0 border-0 shrink-0"
              style={{
                backgroundColor: "oklch(0.55 0.2 260 / 10%)",
                color: "oklch(0.6 0.15 260)",
              }}
            >
              {FAQ_CATEGORY_LABELS[entry.category]}
            </Badge>
          </div>
          {!open && (
            <p className="text-xs leading-relaxed line-clamp-2" style={{ color: "oklch(0.52 0.01 260)" }}>
              {entry.shortAnswer}
            </p>
          )}
        </div>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div
              className="px-5 pb-5 pt-1 border-t"
              style={{ borderTopColor: "rgba(148,163,184,0.08)" }}
            >
              <p
                className="text-xs mb-3 leading-relaxed"
                style={{ color: "oklch(0.6 0.08 260)" }}
              >
                {entry.shortAnswer}
              </p>

              <div
                className="prose-faq text-sm leading-relaxed space-y-2"
                style={{ color: "oklch(0.75 0.01 260)" }}
                dangerouslySetInnerHTML={{
                  __html: `<p>${renderMarkdown(entry.fullAnswer)}</p>`,
                }}
              />

              {entry.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-4">
                  {entry.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-[10px] px-2 py-0.5 rounded-full"
                      style={{
                        backgroundColor: "oklch(0.2 0.005 280)",
                        color: "oklch(0.52 0.01 260)",
                      }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {related.length > 0 && (
                <div className="mt-5">
                  <p
                    className="text-[11px] uppercase tracking-widest font-semibold mb-2"
                    style={{ color: "oklch(0.5 0.01 260)" }}
                  >
                    Powiazane pytania
                  </p>
                  <div className="space-y-1">
                    {related.map((r) => (
                      <Link
                        key={r.id}
                        href={`/faq#${r.id}`}
                        className="flex items-center gap-1.5 text-xs group/link"
                        style={{ color: "oklch(0.6 0.15 260)" }}
                      >
                        <ArrowRight className="w-3 h-3 shrink-0 transition-transform group-hover/link:translate-x-0.5" />
                        {r.question}
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
