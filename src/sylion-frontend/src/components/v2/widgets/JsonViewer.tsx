"use client";

/**
 * SYLION AEIS v2 — W16 G2 widget: JsonViewer.
 *
 * Read-only przeglądarka JSON z collapse/expand dla zagnieżdżonych obiektów
 * i tablic. Bez zewnętrznej biblioteki — własna rekursja, indent + monospace.
 * Wspiera: null/undefined/Date/number/string/boolean/object/array.
 */

import { useState } from "react";
import { ChevronRight, Copy, Check } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/common/HelpTip";
import { cn } from "@/lib/utils";

export interface JsonViewerProps {
  data: unknown;
  initiallyCollapsedDepth?: number;
  maxDepth?: number;
  copyButton?: boolean;
  helpText?: string;
}

interface NodeProps {
  value: unknown;
  depth: number;
  initialCollapse: number;
  maxDepth: number;
  keyName?: string;
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return (
    typeof v === "object" && v !== null && !Array.isArray(v) && !(v instanceof Date)
  );
}

function Primitive({ value }: { value: unknown }) {
  if (value === null) return <span className="text-muted-foreground">null</span>;
  if (value === undefined) return <span className="text-muted-foreground italic">undefined</span>;
  if (value instanceof Date) return <span className="text-amber-500">"{value.toISOString()}"</span>;
  if (typeof value === "string") return <span className="text-emerald-500">"{value}"</span>;
  if (typeof value === "number") return <span className="text-sylion-blue">{value.toString()}</span>;
  if (typeof value === "boolean") return <span className="text-fuchsia-500">{value ? "true" : "false"}</span>;
  return <span>{String(value)}</span>;
}

function JsonNode({ value, depth, initialCollapse, maxDepth, keyName }: NodeProps) {
  const isObj = isPlainObject(value);
  const isArr = Array.isArray(value);
  const isContainer = isObj || isArr;
  const [collapsed, setCollapsed] = useState<boolean>(depth >= initialCollapse);
  const keyLabel =
    keyName !== undefined ? <span className="text-foreground/80">"{keyName}": </span> : null;

  if (depth >= maxDepth && isContainer) {
    return (
      <span className="text-muted-foreground">
        {keyLabel}[..]
      </span>
    );
  }
  if (!isContainer) {
    return (
      <span>
        {keyLabel}
        <Primitive value={value} />
      </span>
    );
  }

  const entries: Array<[string, unknown]> = isArr
    ? (value as unknown[]).map((v, i) => [String(i), v])
    : Object.entries(value as Record<string, unknown>);
  const open = isArr ? "[" : "{";
  const close = isArr ? "]" : "}";

  if (entries.length === 0) {
    return (
      <span>
        {keyLabel}
        <span className="text-muted-foreground">{open}{close}</span>
      </span>
    );
  }

  return (
    <div className="flex flex-col">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="inline-flex items-center gap-0.5 text-left hover:text-sylion-blue"
        aria-expanded={!collapsed}
      >
        <ChevronRight className={cn("h-3 w-3 shrink-0 transition-transform", !collapsed && "rotate-90")} />
        {keyLabel}
        <span className="text-muted-foreground">
          {open}
          {collapsed ? `… ${entries.length} ${isArr ? "items" : "keys"} …${close}` : ""}
        </span>
      </button>
      {!collapsed && (
        <>
          <div className="ml-3 flex flex-col border-l border-foreground/10 pl-2">
            {entries.map(([k, v], i) => (
              <div key={`${k}-${i}`}>
                <JsonNode
                  value={v}
                  depth={depth + 1}
                  initialCollapse={initialCollapse}
                  maxDepth={maxDepth}
                  keyName={isArr ? undefined : k}
                />
                {i < entries.length - 1 && <span className="text-muted-foreground">,</span>}
              </div>
            ))}
          </div>
          <span className="text-muted-foreground">{close}</span>
        </>
      )}
    </div>
  );
}

export function JsonViewer({
  data,
  initiallyCollapsedDepth = 2,
  maxDepth = 5,
  copyButton = true,
  helpText,
}: JsonViewerProps) {
  const [copied, setCopied] = useState<boolean>(false);

  async function handleCopy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Card className="overflow-hidden">
      <header className="flex items-center justify-between border-b border-foreground/10 px-3 py-1.5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          JSON
          {helpText && <HelpTip text={helpText} />}
        </h3>
        {copyButton && (
          <Button size="xs" variant="ghost" onClick={handleCopy} aria-label="Kopiuj JSON">
            {copied ? (<><Check className="h-3 w-3" /> Skopiowano</>) : (<><Copy className="h-3 w-3" /> Kopiuj</>)}
          </Button>
        )}
      </header>
      <div className="overflow-auto px-3 py-2 font-mono text-[11px] leading-snug">
        <JsonNode
          value={data}
          depth={0}
          initialCollapse={initiallyCollapsedDepth}
          maxDepth={maxDepth}
        />
      </div>
    </Card>
  );
}
