"use client";

import "./operating-advisor-v4.css";
import { useAdvisorFeed, useMonitoringSnapshot, useProjectLifecycle } from "@/lib/hooks/advisor";
import { AdvisorCore } from "@/components/advisor/AdvisorCore";
import { DecisionCommandCard } from "@/components/advisor/DecisionCommandCard";
import { LifecycleRail } from "@/components/advisor/LifecycleRail";
import { AgentTopology } from "@/components/advisor/AgentTopology";
import { ConfigurationControlCards } from "@/components/advisor/ConfigurationControlCards";
import { AuditTrailCard } from "@/components/advisor/AuditTrailCard";
import {
  ProjectHubProvider,
  ProjectHubHeroRow,
  ProjectHubStrip,
} from "@/components/advisor/ProjectHub";
import type { AdvisorCardEnvelope } from "@/lib/api/advisor";
import { HelpTip } from "@/components/common/HelpTip";

function dNum(card: AdvisorCardEnvelope): number {
  return parseInt(card.header.d_level.replace("D", ""), 10);
}

function MetricTile({
  label,
  value,
  sub,
  helpText,
}: {
  label: string;
  value: string;
  sub: string;
  helpText?: string;
}) {
  return (
    <div className="metric-tile">
      <span>
        {label}
        {helpText ? <HelpTip text={helpText} /> : null}
      </span>
      <b>{value}</b>
      <small>{sub}</small>
    </div>
  );
}

function CockpitInner({
  activeProjectId,
  setActiveProjectId,
  setShowNewModal,
}: {
  activeProjectId: string | null;
  setActiveProjectId: (id: string) => void;
  setShowNewModal: (v: boolean) => void;
}) {
  const { data: cards, loading: cardsLoading } = useAdvisorFeed({ refreshMs: 8000 });
  const { snapshot, loading: snapLoading } = useMonitoringSnapshot(30_000);

  const resolvedProjectId = activeProjectId ?? snapshot.projects[0]?.project_id ?? "default";
  const activeProjectName =
    snapshot.projects.find((p) => p.project_id === resolvedProjectId)?.project_name ??
    snapshot.projects[0]?.project_name ??
    "—";

  const { lifecycle } = useProjectLifecycle(resolvedProjectId);

  const criticalCard =
    cards.find((c) => dNum(c) >= 4) ??
    cards.find((c) => dNum(c) >= 3) ??
    cards[0] ??
    null;

  const otherCards = cards
    .filter((c) => c.header.card_id !== criticalCard?.header.card_id)
    .slice(0, 4);

  const pendingHgCount = cards.filter((c) => c.header.human_gate_required).length;

  const avgConfidence =
    cards.length > 0
      ? cards.reduce((acc, c) => acc + c.header.confidence_score, 0) / cards.length
      : null;

  const isLoading = cardsLoading || snapLoading;

  return (
    <div className="cockpit-v4">
      {/* ── Hero ────────────────────────────────────────────────── */}
      <section className="visual-hero">
        <div className="panel">
          <div className="panel-content">
            <div className="flex items-start justify-between gap-4">
              <span className="eyebrow">
                Operating Advisor · centrum prowadzenia projektów AI
              </span>
              <ProjectHubHeroRow
                activeProjectId={activeProjectId}
                onSelectProject={setActiveProjectId}
                onNewProject={() => setShowNewModal(true)}
              />
            </div>
            <h1 className="hero-title">
              <span className="grad">Strategiczny pilot</span>
              <br />
              zamiast plaskiego dashboardu.
              <HelpTip text="Kokpit Operating Advisor: agreguje decyzję, lifecycle, topologię agentów i audit w jeden ekran dowodzenia. Karty decyzyjne są sortowane po D-level (D4/D5 first), Lifecycle pokazuje 15 faz projektu." />
            </h1>
            <p className="hero-copy">
              AEIS analizuje modele, koszty, preferencje, ryzyko, funding, VPS,
              subskrypcje, testy i Council — operator dostaje konkretne decyzję,
              alternatywy, Evidence Pack i pelny audit trail.
            </p>
            <div className="hero-metrics">
              <MetricTile
                label="Tryb strategii"
                value="Zrownowazony"
                sub="jakość 0.52 · koszt 0.24 · szybkość 0.24"
                helpText="Aktualny rozk?ad osi Quality/Speed/Cost (suma = 1.0). Wpływa na ensemble modeli, agresywność cache, dobór providerów. Zmiana — sekcja 7 ustawień Doradcy."
              />
              <MetricTile
                label="Bramki czlowieka"
                value={isLoading ? "..." : String(pendingHgCount)}
                sub="wymagaj?ce decyzji operatora"
                helpText="Liczba kart, które zatrzymały się przed wykonaniem i czekają na zatwierdzenie operatora. D3+ zawsze wymaga Human Gate; D5 wymaga sygnatury."
              />
              <MetricTile
                label="Aktywne projekty"
                value={isLoading ? "..." : String(snapshot.projects.length)}
                sub="planner · workers · fixer"
                helpText="Liczba projektów z trwającym lifecyclem (>= 1 faza in_progress). Każdy projekt ma planera, pulę workerów i fixera dla auto-naprawy błędów."
              />
              <MetricTile
                label="Średnia pewnosc"
                value={
                  isLoading
                    ? "..."
                    : avgConfidence !== null
                    ? avgConfidence.toFixed(2)
                    : "—"
                }
                sub="historia + rada + pricing live"
                helpText="Średnia confidence ze wszystkich aktywnych kart Doradcy (0.0-1.0). Kombinacja: dane historyczne + głos rady + aktualne ceny providerów. Niska wartość = większa ostrożność."
              />
            </div>
          </div>
        </div>

        <AdvisorCore criticalCard={criticalCard} />
      </section>

      {/* ── Recent Projects Strip ───────────────────────────────── */}
      <section className="panel">
        <div className="panel-content">
          <div className="section-head">
            <div>
              <h2>
                Ostatnie projekty
                <HelpTip text="Pasek aktywnych projektów operatora. Kliknij aby przełączyć kontekst kokpitu — Lifecycle, decyzję, topologia i audit aktualizują się do wybranego projektu." />
              </h2>
              <p>Kliknij projekt aby przelaczac centrum dowodzenia.</p>
            </div>
          </div>
          <ProjectHubStrip
            activeProjectId={activeProjectId}
            onSelectProject={setActiveProjectId}
          />
        </div>
      </section>

      {/* ── Decisions ───────────────────────────────────────────── */}
      <section>
        <div className="section-head">
          <div>
            <h2>
              Co wymaga decyzji teraz
              <HelpTip text="Karty decyzyjne sortowane po D-level: D5 (krytyczne, sygnatura wymagana), D4 (Human Gate twardy), D3 (Human Gate mi?kki), D0-D2 (auto). Karta featured = najwy?szy priorytet." />
            </h2>
            <p>
              Najpierw decyzję blokuj?ce i ryzykowne. Potem koszty, konfiguracja,
              funding, batch low-risk.
            </p>
          </div>
          <span className="chip red">krytyczne najpierw</span>
        </div>

        {isLoading && (
          <div className="cv4-empty">Ładowanie kart Doradcy...</div>
        )}

        {!isLoading && cards.length === 0 && (
          <div className="cv4-empty">
            Brak aktywnych kart - backend działa, ale nie ma decyzji wymagających operatora.
          </div>
        )}

        {!isLoading && cards.length > 0 && (
          <div className="decision-grid">
            {criticalCard && (
              <DecisionCommandCard card={criticalCard} variant="featured" />
            )}
            {otherCards.length > 0 && (
              <div className="decision-stack">
                {otherCards.map((card) => (
                  <DecisionCommandCard
                    key={card.header.card_id}
                    card={card}
                    variant="compact"
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {/* ── Lifecycle Rail ──────────────────────────────────────── */}
      <section className="panel lifecycle-panel">
        <div className="panel-content">
          <div className="section-head">
            <div>
              <h2>
                Lifecycle projektu: {activeProjectName}
                <HelpTip text="Mapa 15 faz projektu (Plan → Build → Ship). Każda faza ma status (pending/in_progress/complete/blocked) i własne bramki. Kliknij fazę aby zobaczyć artefakty i karty Doradcy w kontekście tej fazy." />
              </h2>
              <p>
                15 faz jako komenda operacyjna, nie plaski pasek statusu.
              </p>
            </div>
            <span className="chip amber">
              {lifecycle?.phases.find((p) => p.status === "in_progress")
                ? lifecycle.phases
                    .findIndex((p) => p.status === "in_progress") + 1 + "/15"
                : "—"}
            </span>
          </div>
          <LifecycleRail projectId={resolvedProjectId} />
        </div>
      </section>

      {/* ── Topology + Audit ────────────────────────────────────── */}
      <div className="two-col">
        <section className="panel">
          <div className="panel-content">
            <div className="section-head">
              <div>
                <h2>
                  Topologia zespołów agentów
                  <HelpTip text="Graf agentów przypisanych do bieżącego projektu: planner zleca, workers wykonują, verifier waliduje, critic kwestionuje, council/human gate zatwierdza. Aktywne połączenia mrugają na żywo." />
                </h2>
                <p>Planner → Workers → Verifier/Critic → Council/Human Gate.</p>
              </div>
            </div>
            <AgentTopology />
          </div>
        </section>

        <section className="panel">
          <div className="panel-content">
            <div className="section-head">
              <div>
                <h2>
                  Sciezka audytu
                  <HelpTip text="Ostatnie 5 zdarze? z append-only audit logu: decyzję, sygnatury, zmiany konfiguracji. Pe?na historia w Evidence Spine; tutaj tylko skr?t dla orientacji." />
                </h2>
                <p>Ostatnie 5 zdarze? w systemie.</p>
              </div>
            </div>
            <AuditTrailCard />
          </div>
        </section>
      </div>

      {/* ── Configuration ───────────────────────────────────────── */}
      <section className="panel">
        <div className="panel-content">
          <div className="section-head">
            <div>
              <h2>
                Konfiguracja operator-facing
                <HelpTip text="Ustawienia widoczne dla operatora bez wchodzenia w architecture/owner: klucze API (maskowane), lokalne modele (Ollama/LocalAI), routing per-fase, Skills do włączenia/wyłączenia. Vault-safe — sekrety nigdy w cleartext." />
              </h2>
              <p>
                Klucze API, lokalne modele, routing i Skills sa w trybie operatora.
              </p>
            </div>
            <span className="chip green">Vault-safe</span>
          </div>
          <ConfigurationControlCards />
        </div>
      </section>
    </div>
  );
}

export default function CockpitV4Page() {
  return (
    <ProjectHubProvider>
      {({ activeProjectId, setActiveProjectId, setShowNewModal }) => (
        <CockpitInner
          activeProjectId={activeProjectId}
          setActiveProjectId={setActiveProjectId}
          setShowNewModal={setShowNewModal}
        />
      )}
    </ProjectHubProvider>
  );
}
