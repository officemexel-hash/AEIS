"use client";

import { useHealth } from "@/lib/api/hooks";

export function ApiOfflineBanner() {
  const { error, loading, data } = useHealth();
  const isOffline = !loading && (error !== null || data.status !== "ok");
  if (!isOffline) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 max-w-sm rounded-md border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200 shadow-lg backdrop-blur"
    >
      <div className="font-medium">Backend niedostępny</div>
      <div className="mt-1 text-xs text-amber-200/80">
        Nie można połączyć się z API (<code>localhost:3001/api</code>). Dane mogą być nieaktualne lub zastępcze.
      </div>
    </div>
  );
}
