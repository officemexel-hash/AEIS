"use client";

import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const HEALTH_URLS = API_BASE
  ? Array.from(new Set([
      `${API_BASE}/health`,
      `${API_BASE.replace("127.0.0.1", "localhost")}/health`,
      `${API_BASE.replace("localhost", "127.0.0.1")}/health`,
    ]))
  : ["/backend-health"];

type BackendStatus = "online" | "offline";

export function BackendOfflineGuard({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<BackendStatus>("online");

  useEffect(() => {
    let mounted = true;

    async function check() {
      let online = false;

      for (const url of HEALTH_URLS) {
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), 3000);

        try {
          const res = await fetch(url, {
            signal: controller.signal,
            cache: "no-store",
          });
          if (res.ok) {
            online = true;
            break;
          }
        } catch {
          // Try the next local alias before declaring the dashboard offline.
        } finally {
          window.clearTimeout(timer);
        }
      }

      if (mounted) setStatus(online ? "online" : "offline");
    }

    check();

    const interval = window.setInterval(check, 5000);
    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, []);

  if (status === "offline") {
    const target = API_BASE || "/backend-health";

    return (
      <div className="relative min-h-screen">
        <div className="pointer-events-none opacity-30 blur-sm select-none">{children}</div>

        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
          <div className="max-w-md rounded-xl border border-destructive/50 bg-card p-8 text-center shadow-2xl">
            <div className="mb-4 inline-flex size-16 items-center justify-center rounded-full bg-destructive/10">
              <WifiOff className="size-8 text-destructive" />
            </div>
            <h2 className="mb-2 text-xl font-semibold">Backend niedostępny</h2>
            <p className="mb-4 text-sm text-muted-foreground">
              Nie można połączyć się z serwerem SYLION. SprawdŹ status endpointu{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">{target}</code>.
            </p>
            <p className="mb-6 text-xs text-muted-foreground">
              Aplikacja będzie zablokowana, dopóki backend nie wróci do działania. Ponawiamy próbę co 5 sekund.
            </p>
            <div className="space-y-2 text-left text-xs text-muted-foreground">
              <p>
                <strong>Co sprawdźi?:</strong>
              </p>
              <ul className="list-disc space-y-1 pl-5">
                <li>Backend powinien odpowiadac na porcie 8010.</li>
                <li>Frontend powinien proxyowac /backend-health do backendu.</li>
                <li>Logi backendu i frontendu nie powinny pokazywac bledow CORS ani 500.</li>
              </ul>
            </div>
            <button
              onClick={() => window.location.reload()}
              className="mt-6 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Sprobuj ponownie
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
