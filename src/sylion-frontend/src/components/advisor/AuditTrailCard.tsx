"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface AuditEntry {
  id: string;
  action: string;
  actor: string;
  timestamp: number;
  module?: string;
}

function formatTs(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("pl-PL", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AuditTrailCard() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${API_BASE}/api/v1/advisor/audit/recent`, {
      signal: controller.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((data) => {
        setEntries(Array.isArray(data?.entries) ? data.entries.slice(0, 5) : []);
        setStatus("ready");
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setEntries([]);
          setStatus("error");
        }
      });

    return () => controller.abort();
  }, []);

  const emptyMessage =
    status === "loading"
      ? "Ładowanie zdarzeń audytu..."
      : status === "error"
        ? "Endpoint /api/v1/advisor/audit/recent niedostępny - brak danych audytu."
        : "Brak zdarzeń audytu dla aktualnego profilu.";

  return (
    <>
      {status !== "ready" || entries.length === 0 ? (
        <p
          style={{
            margin: "0 0 12px",
            fontSize: 11,
            color: "var(--ink-muted)",
            fontStyle: "italic",
          }}
        >
          {emptyMessage}
        </p>
      ) : null}
      <div className="audit-list">
        {entries.map((entry) => (
          <div key={entry.id} className="audit-item">
            <div className="audit-dot" />
            <div>
              <h4>{entry.action.replace(/_/g, " ")}</h4>
              <p>
                {entry.module ?? "-"} · {entry.actor}
              </p>
            </div>
            <span style={{ color: "var(--ink-muted)", fontSize: 11, whiteSpace: "nowrap" }}>
              {formatTs(entry.timestamp)}
            </span>
          </div>
        ))}
      </div>
    </>
  );
}
