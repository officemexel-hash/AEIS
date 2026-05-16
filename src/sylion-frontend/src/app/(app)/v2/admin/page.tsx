"use client";

/**
 * SYLION AEIS v2 — /v2/admin operator overview page.
 *
 * Sprint 4 deliverable. Wraps the AdminOverview component with the
 * standard page chrome (title block + supporting copy) and the
 * existing v2 quick-jump links via AeisV2Summary so the operator
 * lands on a single screen with everything they need to drive the
 * canary rollout end-to-end.
 */

import { Card } from "@/components/ui/card";
import { AeisV2Summary } from "@/components/v2/AeisV2Summary";
import { AdminOverview } from "@/components/v2/AdminOverview";

export default function V2AdminPage() {
  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          AEIS v2 — Admin
        </h1>
        <p className="text-sm text-muted-foreground">
          Operator dashboard dla warstwy v2 (W7/W11/W13/W15-W19) —
          stan canary, audit chains, adapter bus, polityka W19.
        </p>
      </header>

      {/* Top: v2 quick-jump summary (existing component). */}
      <Card className="rounded-xl p-4 border-border/40 bg-muted/5">
        <AeisV2Summary />
      </Card>

      {/* Main: live W19 + audit + adapter bus telemetry. */}
      <Card className="rounded-xl p-4 border-border/40 bg-muted/5">
        <AdminOverview />
      </Card>

      <footer className="text-[10px] text-muted-foreground/60">
        Endpoint zrodlowy: <code>/api/v1/metrics/v2</code> (Prometheus
        text). Patrz <code>docs/v2/operations/w19_production_runbook.md</code>
        po pelne procedury rollout / rollback / incident response.
      </footer>
    </div>
  );
}
