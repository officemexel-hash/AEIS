"use client";

import { WifiOff } from "lucide-react";

import { cn } from "@/lib/utils";

export function BackendErrorBanner({
  source,
  className,
}: {
  source: "live" | "error" | "loading";
  className?: string;
}) {
  if (source !== "error") return null;
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-md border border-sylion-red/30 bg-sylion-red/5 px-3 py-2 text-[11px] text-sylion-red",
        className,
      )}
    >
      <WifiOff className="h-3.5 w-3.5" />
      Backend niedostępny - dane nie sa podstawiane. Uruchom serwer API (
      <code>python -m uvicorn sylion.api.app:app</code>), aby zobaczyć dane na żywo.
    </div>
  );
}
