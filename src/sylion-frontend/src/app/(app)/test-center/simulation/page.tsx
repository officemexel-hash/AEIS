"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/lib/api/hooks";
import { Beaker, ArrowLeft, RefreshCw } from "lucide-react";
import { HelpTip } from "@/components/common/HelpTip";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "";

interface SimRow {
  sim_branch_id: string;
  contract_id: string;
  state: string;
  snapshot_db_path: string | null;
  created_at: number | null;
  discard_reason: string | null;
  max_layer_executed: number;
  evidence_count: number;
}

interface SimData {
  as_of: number;
  total: number;
  active: number;
  discarded: number;
  branches: SimRow[];
}

const STATE_COLOR: Record<string, string> = {
  open: "bg-blue-500/15 text-blue-700",
  merged: "bg-emerald-500/15 text-emerald-700",
  discarded: "bg-gray-500/15 text-gray-700",
};

export default function SimulationCenterPage() {
  const backendLive =
    ((useHealth().data as { status?: string })?.status === "ok");
  const [data, setData] = useState<SimData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState("");
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const refresh = async () => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/v1/test-center/simulation`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e: unknown) {
      setError(String((e as Error)?.message || e));
    } finally {
      setLoading(false);
    }
  };

  const runSimulation = async () => {
    if (!backendLive) return;
    setLoading(true);
    setError(null);
    setActionMessage(null);
    try {
      const r = await fetch(`${API_BASE}/api/v1/test-center/simulation/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId.trim() || "proj_test_center_manual",
          actor: "operator-dashboard",
          scenario: "w14_self_test_dashboard",
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
      const body = await r.json();
      setActionMessage(`Symulacja L0-L4 zapisana: ${body.branch?.sim_branch_id ?? "branch"}`);
      setData(body.summary);
    } catch (e: unknown) {
      setError(String((e as Error)?.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendLive]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/test-center"
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Beaker className="w-6 h-6" />
            Centrum symulacji
          <HelpTip text="Centrum uruchamiania symulacji L0-L4 (kontrakt -> sandbox -> workflow -> decyzja -> błąd) na izolowanych gałęziach. Pozwala testówać scenariusze bez ryzyka dla produkcji. Default: model_mode=isolated, persistence=audit-profile, safety=opt-in destructive." />
          </h1>
          <Badge variant={backendLive ? "default" : "outline"}>
          {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground flex items-center" htmlFor="simulation-project-id">
            project_id
            <HelpTip text="Projekt, dla którego zostanie utworzona izolowana gałąź symulacji L0-L4 z dowodem W14." />
          </label>
          <input
            id="simulation-project-id"
            placeholder="project_id"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            className="text-xs px-2 py-1 border rounded font-mono w-56"
          />
          <Button onClick={runSimulation} disabled={loading} size="sm" variant="outline">
            Uruchom L0-L4
          </Button>
          <Button onClick={refresh} disabled={loading} size="sm" variant="outline">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            <span className="ml-2">Odśwież</span>
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700">
          Błąd: {error}
        </Card>
      )}

      {actionMessage && (
        <Card className="border-emerald-500/30 bg-emerald-500/5 p-3 text-sm text-emerald-700">
          {actionMessage}
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-xs text-muted-foreground flex items-center">
            Gałęzie łącznie
            <HelpTip text="Całkowita liczba gałęzi symulacyjnych w systemie: aktywnych (open), złączonych (merged) i odrzuconych (discarded). Każda gałąź to izolowane środowisko testówe z własnym snapshotem DB." />
          </div>
          <div className="text-2xl font-bold font-mono">
            {data?.total ?? "—"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground flex items-center">
            Aktywne (otwarte)
            <HelpTip text="Gałęzie, które aktualnie pracują: akceptują nowe operacje i można je dalej rozwijać. Tylko aktywne gałęzie zużywają zasoby RAM dla in-memory persistence." />
          </div>
          <div className="text-2xl font-bold font-mono text-blue-700">
            {data?.active ?? "—"}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground flex items-center">
            Odrzucone
            <HelpTip text="Gałęzie, które zostały zamknięte bez merge: przez niezaliczone testy, contract violation albo decyzję manualną. Pozostają w historii ze względu na audyt; można zobaczyć discard_reason." />
          </div>
          <div className="text-2xl font-bold font-mono text-gray-700">
            {data?.discarded ?? "—"}
          </div>
        </Card>
      </div>

      <Card className="p-4">
        <div className="font-semibold mb-3 flex items-center">
          Stack L0-L4
          <HelpTip text="5-warstwowy stos symulacyjny: L0 (kontrakt) -> L1 (sandbox) -> L2 (workflow) -> L3 (decyzja) -> L4 (błąd). Każda kolejna warstwa wymaga zaliczenia poprzedniej. max_layer_executed pokazuje, jak głęboko gałąź dotarła." />
        </div>
        <ol className="text-sm text-muted-foreground space-y-1 list-decimal pl-5">
          <li>L0: SimulationContract - izolacja/model_mode/persistence/safety</li>
          <li>L1: TransactionalSandbox - izolowany adapter LLM i audit-profile EventBus</li>
          <li>L2: PersonaRuntime.simulate_workflow - wieloetapowa praca operatora</li>
          <li>L3: PersonaRuntime.simulate_decision - wybory bramkowe pod obciążeniem</li>
          <li>
            L4: PersonaRuntime.inject_error - 14 podstawowych + 7 rozszerzonych klas błędów
          </li>
        </ol>
      </Card>

      <Card className="p-4">
        <div className="font-semibold mb-3 flex items-center">
          Gałęzie symulacji ({data?.branches.length ?? 0})
          <HelpTip text="Lista wszystkich gałęzi w wybranym kontekście: stan, kontrakt, maksymalnie wykonana warstwa i liczba dowodów (evidence). Kliknij wiersz, aby zobaczyć snapshot lub trace. Stan: open=aktywna, merged=zaakceptowana, discarded=odrzucona." />
        </div>
        <table className="w-full text-xs">
          <thead className="border-b text-muted-foreground">
            <tr>
              <th className="text-left py-1.5 font-normal">sim_branch_id</th>
              <th className="text-left py-1.5 font-normal">kontrakt</th>
              <th className="text-left py-1.5 font-normal">stan</th>
              <th className="text-right py-1.5 font-normal">warstwa</th>
              <th className="text-right py-1.5 font-normal">dowody</th>
              <th className="text-left py-1.5 font-normal">snapshot</th>
            </tr>
          </thead>
          <tbody>
            {(data?.branches || []).map((b) => (
              <tr key={b.sim_branch_id} className="border-b last:border-0">
                <td className="py-1.5 font-mono">
                  {b.sim_branch_id.slice(0, 18)}
                </td>
                <td className="py-1.5 font-mono">
                  {b.contract_id.slice(0, 14)}
                </td>
                <td className="py-1.5">
                  <Badge
                    variant="outline"
                    className={`text-[10px] ${STATE_COLOR[b.state] || ""}`}
                  >
                    {b.state}
                  </Badge>
                  {b.discard_reason && (
                    <span
                      className="ml-2 text-[10px] text-muted-foreground"
                      title={b.discard_reason}
                    >
                      ({b.discard_reason.slice(0, 24)})
                    </span>
                  )}
                </td>
                <td className="text-right py-1.5 font-mono">
                  L{b.max_layer_executed}
                </td>
                <td className="text-right py-1.5 font-mono">
                  {b.evidence_count}
                </td>
                <td className="py-1.5 font-mono text-muted-foreground">
                  {b.snapshot_db_path
                    ? b.snapshot_db_path.split(/[\\/]/).pop()
                    : "in-memory (RAM)"}
                </td>
              </tr>
            ))}
            {(data?.branches || []).length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="py-4 text-center text-muted-foreground"
                >
                    brak gałęzi symulacji - uruchom symulację, aby wypełnić
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      {data && (
        <div className="text-xs text-muted-foreground text-right">
          stan na {new Date(data.as_of * 1000).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
