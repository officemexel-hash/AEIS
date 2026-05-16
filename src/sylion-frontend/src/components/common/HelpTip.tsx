"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * F-029: tiny, reusable "?" affordance for any label / section header /
 * configurable control. Renders a circled question mark; hovering it
 * surfaces a localised description so first-time operators don't have to
 * guess what each slider, dropdown or switch actually does.
 *
 * Note: this codebase uses Base UI (`@base-ui/react/tooltip`), not Radix —
 * so we DON'T use the Radix-style `asChild` pattern. We let TooltipTrigger
 * render its own <button> and style it via className.
 *
 * Usage:
 *   <label>
 *     R1 Associate <HelpTip text="Waga głosu rangi 1 — najmlodszy senior..." />
 *   </label>
 */
interface HelpTipProps {
  /** Short, plain-Polish description. Aim for 1-3 sentences. */
  text: string;
  /** Tooltip side; defaults to top. */
  side?: "top" | "right" | "bottom" | "left";
  /** Optional class for the trigger button (e.g. opacity tweak). */
  className?: string;
  /** Override icon size (px). */
  size?: number;
  /** Aria label override. */
  label?: string;
}

export function HelpTip({
  text,
  side = "top",
  className,
  size = 16,
  label,
}: HelpTipProps) {
  const id = useId();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const openRef = useRef(false);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ left: number; top: number; transform: string }>({
    left: 0,
    top: 0,
    transform: "translate(-50%, -100%)",
  });

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger || typeof window === "undefined") {
      return;
    }

    const rect = trigger.getBoundingClientRect();
    const gap = 10;
    const margin = 16;
    const maxTooltipWidth = Math.min(420, window.innerWidth - margin * 2);
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const safeCenterY = Math.min(Math.max(centerY, margin + 72), window.innerHeight - margin - 72);
    const sideWithRoom =
      side === "top" && rect.top < 120
        ? "bottom"
        : side === "bottom" && window.innerHeight - rect.bottom < 120
          ? "top"
          : side === "left" && rect.left < maxTooltipWidth + margin + gap
            ? "right"
            : side === "right" && window.innerWidth - rect.right < maxTooltipWidth + margin + gap
              ? "left"
              : side;

    if (sideWithRoom === "right") {
      const left = Math.min(rect.right + gap, window.innerWidth - maxTooltipWidth - margin);
      setPosition({ left: Math.max(margin, left), top: safeCenterY, transform: "translateY(-50%)" });
      return;
    }

    if (sideWithRoom === "left") {
      const left = Math.min(Math.max(rect.left - gap, maxTooltipWidth + margin), window.innerWidth - margin);
      setPosition({ left, top: safeCenterY, transform: "translate(-100%, -50%)" });
      return;
    }

    const left = Math.min(Math.max(centerX, margin + maxTooltipWidth / 2), window.innerWidth - margin - maxTooltipWidth / 2);
    if (sideWithRoom === "bottom") {
      const top = Math.max(rect.bottom + gap, margin);
      setPosition({ left, top, transform: "translateX(-50%)" });
      return;
    }

    if (rect.top - gap < margin + 72) {
      setPosition({ left, top: Math.max(rect.bottom + gap, margin), transform: "translateX(-50%)" });
      return;
    }

    setPosition({ left, top: rect.top - gap, transform: "translate(-50%, -100%)" });
  }, [side]);

  const setOpenState = useCallback((nextOpen: boolean) => {
    if (openRef.current === nextOpen) {
      return;
    }
    openRef.current = nextOpen;
    setOpen(nextOpen);
  }, []);

  useEffect(() => {
    updatePosition();
    const syncWithPointer = (event: PointerEvent | MouseEvent) => {
      const trigger = triggerRef.current;
      if (!trigger) {
        return;
      }

      const rect = trigger.getBoundingClientRect();
      const hitPadding = 3;
      const isOverTrigger =
        event.clientX >= rect.left - hitPadding &&
        event.clientX <= rect.right + hitPadding &&
        event.clientY >= rect.top - hitPadding &&
        event.clientY <= rect.bottom + hitPadding;

      if (isOverTrigger) {
        updatePosition();
        setOpenState(true);
        return;
      }

      setOpenState(false);
    };

    document.addEventListener("pointermove", syncWithPointer);
    document.addEventListener("mousemove", syncWithPointer);
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);

    return () => {
      document.removeEventListener("pointermove", syncWithPointer);
      document.removeEventListener("mousemove", syncWithPointer);
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [setOpenState, updatePosition]);

  useEffect(() => {
    if (!open) {
      return;
    }

    updatePosition();
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (triggerRef.current?.contains(event.target as Node)) {
        return;
      }
      setOpenState(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpenState(false);
      }
    };

    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);

    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open, setOpenState, updatePosition]);

  const show = () => {
    updatePosition();
    setOpenState(true);
  };

  const hide = () => setOpenState(false);
  const openFromClick = () => {
    updatePosition();
    setOpenState(true);
  };

  return (
    <span
      className="help-tip-shell relative z-[10001] inline-flex align-middle"
      data-open={open ? "true" : "false"}
      onMouseEnter={show}
      onMouseMove={show}
      onMouseOver={show}
      onPointerEnter={show}
      onPointerMove={show}
      onPointerOver={show}
    >
      <button
        ref={triggerRef}
        className={cn(
          "relative z-[10001] ml-1 inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-muted-foreground/40 text-muted-foreground/70 align-middle transition hover:border-sylion-blue/60 hover:text-sylion-blue focus:outline-none focus-visible:ring-1 focus-visible:ring-sylion-blue/60",
          className,
        )}
        aria-label={label ?? "Pomoc - opis funkcji"}
        aria-describedby={open ? id : undefined}
        data-help-tip="true"
        onBlur={hide}
        onClick={openFromClick}
        onFocus={show}
        onPointerEnter={show}
        onPointerOver={show}
        onPointerMove={show}
        onMouseEnter={show}
        onMouseOver={show}
        onMouseMove={show}
        type="button"
      >
        <HelpCircle className="pointer-events-none" style={{ width: size, height: size }} />
      </button>
      <span
        aria-hidden="true"
        className={cn(
          "help-tip-fallback pointer-events-none fixed z-[9999] max-w-[min(420px,calc(100vw-32px))] whitespace-pre-line rounded-md border border-slate-700/70 bg-slate-950 px-3 py-2 text-sm leading-relaxed text-slate-50 opacity-0 shadow-2xl shadow-black/40 transition-opacity duration-150",
        )}
        style={{
          left: position.left,
          top: position.top,
          transform: position.transform,
        }}
      >
        {text}
      </span>
      {open && typeof document !== "undefined"
        ? createPortal(
            <span
              id={id}
              role="tooltip"
              className="pointer-events-none fixed z-[10000] max-w-[min(420px,calc(100vw-32px))] whitespace-pre-line rounded-md border border-slate-700/70 bg-slate-950 px-3 py-2 text-sm leading-relaxed text-slate-50 shadow-2xl shadow-black/40"
              style={{
                left: position.left,
                top: position.top,
                transform: position.transform,
              }}
            >
              {text}
            </span>,
            document.body,
          )
        : null}
    </span>
  );
}
