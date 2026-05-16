"use client";

/**
 * SYLION AEIS v2 — W19 security and policy layer.
 *
 * Catalogue of the policies that the future W19 evaluator will
 * enforce across the AEIS request lifecycle (auth -> authorization ->
 * policy evaluation -> audit log). Current view just lists what exists — DSL
 * editor, real evaluator with deny / warn / log_only branches, and the
 * field-level redaction engine come in G2 (charter §4 of
 * docs/v2/charters/W19_policy_plane.md).
 *
 * Source: GET /api/v1/policy/policies  (sylion.api.policy_routes).
 */

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/common/HelpTip";
import { request } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  Shield,
  AlertTriangle,
  Boxes,
  Edit3,
  Info,
  Loader2,
  RefreshCw,
  Tag,
  Target,
  Gauge,
} from "lucide-react";

/* ============================================================
   Types
   ============================================================ */

type PolicyCategory = "privacy" | "cost_control" | "rbac" | "audit";
type PolicyScope = "global" | "decision" | "node";
type PolicyEvaluationMode = "deny_on_violation" | "warn" | "log_only";

interface PolicyEntry {
  id: string;
  name: string;
  description: string;
  category: PolicyCategory | string;
  scope: PolicyScope | string;
  evaluation_mode: PolicyEvaluationMode | string;
  version: string;
}

interface PoliciesListResponse {
  count: number;
  policies: PolicyEntry[];
}

/* ============================================================
   Category palette
   ============================================================ */

const CATEGORY_CLASSES: Record<string, string> = {
  privacy: "border-sylion-blue/40 bg-sylion-blue/5 text-sylion-blue",
  cost_control: "border-amber-500/40 bg-amber-500/5 text-amber-500",
  rbac: "border-rose-500/40 bg-rose-500/5 text-rose-500",
  audit: "border-purple-500/40 bg-purple-500/5 text-purple-500",
};

const EVAL_MODE_LABEL: Record<string, string> = {
  deny_on_violation: "Blokuje przy naruszeniu",
  warn: "Ostrzeżenie",
  log_only: "Tylko log",
};

const EVAL_MODE_CLASSES: Record<string, string> = {
  deny_on_violation: "border-rose-500/40 bg-rose-500/5 text-rose-500",
  warn: "border-amber-500/40 bg-amber-500/5 text-amber-500",
  log_only: "border-slate-500/40 bg-slate-500/5 text-slate-400",
};

function categoryClass(category: string): string {
  return (
    CATEGORY_CLASSES[category] ??
    "border-sylion-border bg-muted/20 text-muted-foreground"
  );
}

function evalModeClass(mode: string): string {
  return (
    EVAL_MODE_CLASSES[mode] ??
    "border-sylion-border bg-muted/20 text-muted-foreground"
  );
}

function evalModeLabel(mode: string): string {
  return EVAL_MODE_LABEL[mode] ?? mode;
}

/* ============================================================
   Page
   ============================================================ */

export default function PolicyPlanePage() {
  const [policies, setPolicies] = useState<PolicyEntry[]>([]);
  const [count, setCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await request<PoliciesListResponse>(
        "/api/v1/policy/policies",
      );
      setPolicies(Array.isArray(data?.policies) ? data.policies : []);
      setCount(typeof data?.count === "number" ? data.count : 0);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Nie udało się pobrać polityk.",
      );
      setPolicies([]);
      setCount(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(refresh);
  }, [refresh]);

  /* ============================================================
     Render
     ============================================================ */
  return (
    <div className="space-y-5 p-6">
      {/* ===== Header ===== */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-start justify-between gap-3"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sylion-blue/10 border border-sylion-blue/20 flex items-center justify-center">
            <Shield className="w-4 h-4 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight flex items-center">
              Warstwa polityk (W19)
              <HelpTip
                text={
                  "W19 to warstwa bezpieczeństwa, autoryzacji i polityk dla SYLION AEIS. Każde zada?ie " +
                  "przechodzi przez uwierzytelnienie, autoryzację, ocenę polityk i dziennik audytu. " +
                  "Obecny widok pokazuje katalog polityk bez edycji i bez uruchamiania ewaluatora."
                }
                side="bottom"
              />
            </h1>
            <p className="text-sm text-muted-foreground">
              Katalog polityk dostępny tylko do podglądu.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-[11px]">
            {count} polityk
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refresh()}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            )}
            Odśwież
          </Button>
        </div>
      </motion.div>

      {/* ===== Status banner ===== */}
      <Card className="border-sylion-blue/30 bg-sylion-blue/5">
        <div className="p-3 flex items-start gap-2 text-xs">
          <Info className="w-4 h-4 text-sylion-blue mt-0.5 shrink-0" />
          <div>
            <span className="font-semibold text-sylion-blue">Status:</span>{" "}
            Katalog tylko do podglądu. Ewaluator, edytor DSL i silnik redakcji
            pól pojawią się w G2 (karta W19 <span className="font-mono">&sect;4</span>).
            Lista poniżej zostanie zastąpiona przez odczyt
            <span className="font-mono"> policy/rbac/policy_matrix.yaml</span>
            {" "}oraz reguł redakcyjnych z manifestów W15.
          </div>
        </div>
      </Card>

      {/* ===== Error ===== */}
      {error && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <div className="p-3 flex items-center gap-2 text-amber-600">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs">{error}</span>
          </div>
        </Card>
      )}

      {/* ===== Policy grid ===== */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-44 bg-muted/30 animate-pulse rounded-md border border-border/30"
            />
          ))}
        </div>
      ) : policies.length === 0 ? (
        <Card className="bg-[#0f1629] border-sylion-border">
          <div className="p-8 flex flex-col items-center justify-center text-muted-foreground">
            <Boxes className="w-7 h-7 mb-2 opacity-40" />
            <p className="text-xs">Brak polityk do wyswietlenia.</p>
            <p className="text-[10px] mt-1 opacity-60">
              Backend zwróci? pusta liste — sprawdź{" "}
              <span className="font-mono">/api/v1/policy/policies</span>.
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {policies.map((policy) => (
            <PolicyCard key={policy.id} policy={policy} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ============================================================
   PolicyCard
   ============================================================ */

function PolicyCard({ policy }: { policy: PolicyEntry }) {
  return (
    <Card className="bg-[#0f1629] border-sylion-border flex flex-col">
      <div className="p-4 space-y-3 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-sylion-blue shrink-0" />
            <h3 className="text-sm font-semibold">{policy.name}</h3>
          </div>
          <Badge variant="outline" className="font-mono text-[10px] shrink-0">
            v{policy.version}
          </Badge>
        </div>

        <p className="text-xs text-muted-foreground leading-relaxed">
          {policy.description}
        </p>

        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-[10px] uppercase text-muted-foreground tracking-wider">
            <Tag className="w-3 h-3" />
            <span>Kategoria</span>
          </div>
          <div>
            <Badge
              variant="outline"
              className={cn("font-mono text-[10px]", categoryClass(policy.category))}
            >
              {policy.category}
            </Badge>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-[10px] uppercase text-muted-foreground tracking-wider">
              <Target className="w-3 h-3" />
              <span>Zasieg</span>
            </div>
            <div>
              <Badge variant="outline" className="font-mono text-[10px]">
                {policy.scope}
              </Badge>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 text-[10px] uppercase text-muted-foreground tracking-wider">
              <Gauge className="w-3 h-3" />
              <span>Tryb</span>
            </div>
            <div>
              <Badge
                variant="outline"
                className={cn(
                  "font-mono text-[10px]",
                  evalModeClass(policy.evaluation_mode),
                )}
                title={policy.evaluation_mode}
              >
                {evalModeLabel(policy.evaluation_mode)}
              </Badge>
            </div>
          </div>
        </div>

        <div className="text-[10px] font-mono text-muted-foreground pt-1 border-t border-border/20">
          id: {policy.id}
        </div>
      </div>

      <div className="p-3 border-t border-border/30 flex items-center justify-between gap-2">
        <span className="text-[10px] text-muted-foreground">
          Edycja polityki (G2)
        </span>
        <Button variant="outline" size="sm" disabled title="Dostepne w G2">
          <Edit3 className="w-3.5 h-3.5 mr-1.5" />
          Edytuj
        </Button>
      </div>
    </Card>
  );
}
