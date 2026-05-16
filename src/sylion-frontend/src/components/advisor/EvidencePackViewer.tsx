"use client";

import { useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CheckCircle2, FileSignature, ShieldCheck, AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { EvidencePack } from "@/lib/api/advisor";
import { advisorApi } from "@/lib/api/advisor";
import { ConfidenceMeter } from "./ConfidenceMeter";

interface Props {
  pack: EvidencePack;
  onSigned?: () => void;
  className?: string;
}

export function EvidencePackViewer({ pack, onSigned, className }: Props) {
  const [signing, setSigning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [edits, setEdits] = useState<{ rationale: string; rollback_plan: string; fidelity_test: string }>(() => ({
    rationale: pack.rationale,
    rollback_plan: pack.rollback_plan,
    fidelity_test: pack.fidelity_test,
  }));

  const wordCounts = useMemo(
    () => ({
      rationale: countWords(edits.rationale),
      rollback: countWords(edits.rollback_plan),
      fidelity: countWords(edits.fidelity_test),
    }),
    [edits],
  );

  const minimums = pack.pack_template === "d5_full"
    ? { rationale: 500, rollback: 300, fidelity: 100 }
    : { rationale: 200, rollback: 100, fidelity: 50 };

  async function sign() {
    setSigning(true);
    setError(null);
    try {
      const signaturePayload = JSON.stringify({
        type: "operator_ui_signature",
        evidence_pack_id: pack.evidence_pack_id,
        signed_at: new Date().toISOString(),
      });
      await advisorApi.signEvidencePack(pack.evidence_pack_id, signaturePayload, "operator");
      onSigned?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSigning(false);
    }
  }

  return (
    <Card className={cn("p-5", className)}>
      <header className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Evidence Pack</p>
          <h2 className="text-lg font-semibold">{pack.decision_class.replace(/_/g, " ")}</h2>
          <p className="text-xs text-muted-foreground">
            Template <span className="font-mono">{pack.pack_template}</span> · Domain {pack.domain} · Status{" "}
            <span className={cn(pack.status === "finalized" ? "text-sylion-green" : "text-sylion-amber")}>{pack.status}</span>
          </p>
        </div>
        <Badge variant="outline" className="border-sylion-red/30 font-mono text-[10px] text-sylion-red">
          {pack.d_level}
        </Badge>
      </header>

      <ConfidenceMeter
        score={pack.confidence_breakdown.final_score}
        breakdown={pack.confidence_breakdown}
        className="mb-4"
      />

      <Tabs defaultValue="rationale" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="rationale">Rationale</TabsTrigger>
          <TabsTrigger value="rollback">Rollback</TabsTrigger>
          <TabsTrigger value="fidelity">Fidelity</TabsTrigger>
        </TabsList>
        <TabsContent value="rationale" className="space-y-2">
          <Section
            text={edits.rationale}
            onChange={(v) => setEdits((e) => ({ ...e, rationale: v }))}
            wordCount={wordCounts.rationale}
            min={minimums.rationale}
          />
        </TabsContent>
        <TabsContent value="rollback" className="space-y-2">
          <Section
            text={edits.rollback_plan}
            onChange={(v) => setEdits((e) => ({ ...e, rollback_plan: v }))}
            wordCount={wordCounts.rollback}
            min={minimums.rollback}
          />
        </TabsContent>
        <TabsContent value="fidelity" className="space-y-2">
          <Section
            text={edits.fidelity_test}
            onChange={(v) => setEdits((e) => ({ ...e, fidelity_test: v }))}
            wordCount={wordCounts.fidelity}
            min={minimums.fidelity}
          />
        </TabsContent>
      </Tabs>

      {pack.pack_template === "d5_full" ? (
        <div className="mt-4 rounded-md border border-border/50 p-3">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5" />
            D5 multi-signature
          </p>
          <ul className="space-y-1 text-xs">
            <SigStatus role="operator" signed={pack.signatures.some((s) => s.signer_role === "operator")} />
            <SigStatus role="council_member" signed={pack.signatures.some((s) => s.signer_role === "council_member")} />
            <SigStatus role="sentinel" signed={pack.signatures.some((s) => s.signer_role === "sentinel")} />
          </ul>
        </div>
      ) : null}

      <Separator className="my-4" />

      <div className="flex flex-wrap items-center justify-between gap-3">
        {error ? (
          <span className="flex items-center gap-1 text-xs text-sylion-red">
            <AlertTriangle className="h-3.5 w-3.5" />
            {error}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">
            {pack.signatures.length} signature{pack.signatures.length === 1 ? "" : "s"} on file
          </span>
        )}
        <Button onClick={sign} disabled={signing || pack.status === "finalized"}>
          {signing ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <FileSignature className="mr-1 h-4 w-4" />}
          {pack.status === "finalized" ? "Finalized" : "Sign as operator"}
        </Button>
      </div>
    </Card>
  );
}

function Section({ text, onChange, wordCount, min }: { text: string; onChange: (v: string) => void; wordCount: number; min: number }) {
  const ok = wordCount >= min;
  return (
    <>
      <textarea
        value={text}
        onChange={(e) => onChange(e.target.value)}
        rows={8}
        className="w-full resize-y rounded-md border border-border/60 bg-background p-2 text-sm leading-relaxed focus:outline-none focus:ring-1 focus:ring-sylion-blue/50"
      />
      <div className={cn("flex items-center gap-2 text-[11px]", ok ? "text-sylion-green" : "text-sylion-amber")}>
        {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
        {wordCount} / {min} words
      </div>
    </>
  );
}

function SigStatus({ role, signed }: { role: string; signed: boolean }) {
  return (
    <li className="flex items-center justify-between rounded border border-border/40 bg-muted/10 px-2 py-1.5">
      <span>{role.replace("_", " ")}</span>
      <span className={cn(signed ? "text-sylion-green" : "text-muted-foreground")}>
        {signed ? "signed" : "pending"}
      </span>
    </li>
  );
}

function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}
