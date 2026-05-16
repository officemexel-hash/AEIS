"use client";

/**
 * SYLION AEIS v2 — W16 G2 widget: CommandButton.
 *
 * Klik → opcjonalny native `confirm()` → POST /api/v1/terminal/exec
 * (przez `api.execTerminalCommand`). Spinner w trakcie, wynik do `onResult`,
 * błąd renderowany inline (brak globalnego toast utility w repo).
 */

import { useState } from "react";
import { Loader2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/common/HelpTip";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface CommandResult {
  kind: string;
  text?: string;
  rows?: Array<Record<string, unknown>> | null;
  headers?: string[] | null;
  target?: string | null;
  meta?: Record<string, unknown> | null;
}

export interface CommandButtonProps {
  command: string;
  label: string;
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  onResult?: (result: { kind: string; text?: string; rows?: unknown[] }) => void;
  confirmText?: string;
  disabled?: boolean;
  helpText?: string;
}

const VARIANT_MAP: Record<
  NonNullable<CommandButtonProps["variant"]>,
  "default" | "secondary" | "ghost"
> = {
  primary: "default",
  secondary: "secondary",
  ghost: "ghost",
};

const SIZE_MAP: Record<NonNullable<CommandButtonProps["size"]>, "sm" | "default" | "lg"> = {
  sm: "sm",
  md: "default",
  lg: "lg",
};

export function CommandButton({
  command,
  label,
  variant = "primary",
  size = "md",
  onResult,
  confirmText,
  disabled = false,
  helpText,
}: CommandButtonProps) {
  const [pending, setPending] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick(): Promise<void> {
    if (pending || disabled) return;
    if (confirmText) {
      // Native confirm — minimalna zależność, zgodne z brief.
      const ok = typeof window !== "undefined" && window.confirm(confirmText);
      if (!ok) return;
    }
    setPending(true);
    setError(null);
    try {
      const raw = (await api.execTerminalCommand(command)) as CommandResult;
      onResult?.({
        kind: raw.kind ?? "text",
        text: raw.text,
        rows: raw.rows ?? undefined,
      });
      if (raw.kind === "error" && raw.text) {
        setError(raw.text);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setPending(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-start gap-1" data-slot="command-button">
      <span className="inline-flex items-center gap-1">
        <Button
          type="button"
          variant={VARIANT_MAP[variant]}
          size={SIZE_MAP[size]}
          onClick={handleClick}
          disabled={disabled || pending}
          aria-label={label}
        >
          {pending && <Loader2 className="h-3 w-3 animate-spin" />}
          {label}
        </Button>
        {helpText && <HelpTip text={helpText} />}
      </span>
      {error && (
        <span
          className={cn(
            "inline-flex items-center gap-1 text-[11px] text-destructive",
          )}
          role="alert"
        >
          <AlertTriangle className="h-3 w-3" />
          {error}
        </span>
      )}
    </span>
  );
}
