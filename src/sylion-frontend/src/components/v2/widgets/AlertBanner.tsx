"use client";

/**
 * SYLION AEIS v2 — W16 G2 widget: AlertBanner.
 *
 * Banner top-of-page: wariant info/success/warning/danger, opcjonalna lista
 * akcji po prawej, opcjonalny dismiss. Domyślne ikony lucide-react per wariant.
 */

import { useState, type ReactNode } from "react";
import {
  Info,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/common/HelpTip";
import { cn } from "@/lib/utils";

export type AlertVariant = "info" | "success" | "warning" | "danger";

export interface AlertAction {
  label: string;
  onClick: () => void;
  variant?: "primary" | "ghost";
}

export interface AlertBannerProps {
  variant: AlertVariant;
  title: string;
  description?: string;
  icon?: ReactNode;
  dismissable?: boolean;
  onDismiss?: () => void;
  actions?: AlertAction[];
  helpText?: string;
}

const VARIANT_CLS: Record<AlertVariant, string> = {
  info: "border-sky-500/40 bg-sky-500/10 text-sky-100 dark:text-sky-200",
  success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-100 dark:text-emerald-200",
  warning: "border-amber-500/40 bg-amber-500/10 text-amber-100 dark:text-amber-200",
  danger: "border-destructive/40 bg-destructive/10 text-destructive",
};

const ICON_CLS: Record<AlertVariant, string> = {
  info: "text-sky-500",
  success: "text-emerald-500",
  warning: "text-amber-500",
  danger: "text-destructive",
};

function DefaultIcon({ variant }: { variant: AlertVariant }) {
  const cls = cn("h-4 w-4", ICON_CLS[variant]);
  if (variant === "info") return <Info className={cls} />;
  if (variant === "success") return <CheckCircle2 className={cls} />;
  if (variant === "warning") return <AlertTriangle className={cls} />;
  return <AlertOctagon className={cls} />;
}

export function AlertBanner({
  variant,
  title,
  description,
  icon,
  dismissable = false,
  onDismiss,
  actions,
  helpText,
}: AlertBannerProps) {
  const [dismissed, setDismissed] = useState<boolean>(false);

  if (dismissed) return null;

  function handleDismiss(): void {
    setDismissed(true);
    onDismiss?.();
  }

  return (
    <div
      role="alert"
      data-slot="alert-banner"
      data-variant={variant}
      className={cn(
        "flex items-start gap-3 rounded-lg border px-3 py-2.5",
        VARIANT_CLS[variant],
      )}
    >
      <span className="mt-0.5 shrink-0">
        {icon ?? <DefaultIcon variant={variant} />}
      </span>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1 text-sm font-semibold leading-tight text-foreground">
          {title}
          {helpText && <HelpTip text={helpText} />}
        </div>
        {description && (
          <p className="mt-0.5 text-xs text-foreground/80">{description}</p>
        )}
      </div>

      {actions && actions.length > 0 && (
        <div className="flex shrink-0 items-center gap-1">
          {actions.map((a, i) => (
            <Button
              key={`${a.label}-${i}`}
              size="xs"
              variant={a.variant === "ghost" ? "ghost" : "default"}
              onClick={a.onClick}
            >
              {a.label}
            </Button>
          ))}
        </div>
      )}

      {dismissable && (
        <button
          type="button"
          onClick={handleDismiss}
          className="shrink-0 rounded p-1 text-foreground/60 transition hover:bg-foreground/10 hover:text-foreground"
          aria-label="Zamknij"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
