"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { advisorApi, type AdvisorConfigurationCounts } from "@/lib/api/advisor";

export function ConfigurationControlCards() {
  const router = useRouter();
  const [counts, setCounts] = useState<AdvisorConfigurationCounts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    advisorApi
      .getConfigurationCounts()
      .then((value) => {
        if (cancelled) return;
        setCounts(value);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setCounts(null);
        setError(err instanceof Error ? err.message : "configuration_counts_failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const stat = (value: number | undefined) => {
    if (typeof value === "number") return String(value);
    return error ? "blad" : "...";
  };

  return (
    <div className="config-grid">
      <article className="config-card" onClick={() => router.push("/secrets")}>
        <div className="config-icon">
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
            <path
              d="M15 7a5 5 0 0 1 0 10H9a5 5 0 0 1 0-10h6z"
              stroke="#55e4ff"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <circle cx="9" cy="12" r="2" stroke="#55e4ff" strokeWidth="1.5" />
          </svg>
        </div>
        <h3>API keys i providerzy</h3>
        <p>Dodawanie, test, rotacja, fingerprint, scope, quota i koszt.</p>
        <div className="config-stat">
          {stat(counts?.api_keys)} <small>aktywnych</small>
        </div>
        <div style={{ marginTop: 8 }}>
          <span className="chip cyan" style={{ fontSize: 11 }}>Vault-safe</span>
        </div>
      </article>

      <article className="config-card" onClick={() => router.push("/ai-models")}>
        <div className="config-icon">
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="4" stroke="#a98dff" strokeWidth="1.5" />
            <path
              d="M12 2v4M12 18v4M2 12h4M18 12h4"
              stroke="#a98dff"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <h3>Modele lokalne</h3>
        <p>Ollama health, benchmark, fallback i kara confidence.</p>
        <div className="config-stat">
          {stat(counts?.local_models)} <small>ready</small>
        </div>
      </article>

      <article className="config-card" onClick={() => router.push("/orchestration/llm-routing")}>
        <div className="config-icon">
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
            <path
              d="M4 6h16M4 12h10M4 18h6"
              stroke="#55e4ff"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <circle cx="18" cy="18" r="3" stroke="#55e4ff" strokeWidth="1.5" />
          </svg>
        </div>
        <h3>Routing rol</h3>
        <p>rola x ryzyko x domena x strategia na konkretny model.</p>
        <div className="config-stat">
          {stat(counts?.routing_rules)} <small>regul</small>
        </div>
      </article>

      <article className="config-card" onClick={() => router.push("/skills")}>
        <div className="config-icon">
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24">
            <path
              d="M12 2l2.5 6.5H21l-5.5 4 2 6.5L12 15l-5.5 4 2-6.5L3 8.5h6.5z"
              stroke="#ffd27a"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <h3>Skills Registry</h3>
        <p>Manifest, testy, lifecycle i binding do projektów.</p>
        <div className="config-stat">
          {stat(counts?.skills)} <small>published</small>
        </div>
      </article>
    </div>
  );
}
