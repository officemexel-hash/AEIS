"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { orchestrationApi } from "@/lib/api/orchestration";
import { HelpTip } from "@/components/common/HelpTip";
import { Share2, RefreshCw, Loader2, ChevronRight } from "lucide-react";

export default function EventMapPage() {
  const [eventMap, setEventMap] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [topicFilter, setTopicFilter] = useState("");
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<any | null>(null);

  const load = useCallback(async (prefix?: string) => {
    setLoading(true);
    try {
      setEventMap(await orchestrationApi.getEventMap(prefix || undefined));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleFilterApply = () => load(topicFilter || undefined);

  const edges = eventMap?.edges ?? [];
  const nodes = eventMap?.nodes ?? [];

  const nodeEmits = (moduleId: string) => edges.filter((e: any) => e.emitter === moduleId);
  const nodeSubscribes = (moduleId: string) => edges.filter((e: any) => e.subscriber === moduleId);

  const uniqueModules = Array.from(new Set([
    ...edges.map((e: any) => e.emitter),
    ...edges.map((e: any) => e.subscriber),
    ...nodes.map((n: any) => n.module_id),
  ])).filter(Boolean) as string[];

  const selectedNodeData = selectedNode ? {
    emits: nodeEmits(selectedNode),
    subscribes: nodeSubscribes(selectedNode),
  } : null;

  return (
    <div className="space-y-5">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent-blue-dim flex items-center justify-center">
              <Share2 className="w-4 h-4 text-sylion-blue" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Mapa Zdarzeń</h1>
              <p className="text-[11px] text-muted-foreground">Graf przepływu zdarzeń między modułami</p>
            </div>
          </div>
          <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={() => load()}><RefreshCw className="w-3 h-3 mr-1" />Odśwież</Button>
        </div>
      </motion.div>

      {/* Filter */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.04 }}>
        <Card className="p-3 border-[rgba(148,163,184,0.08)] bg-[#0f1629]">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground shrink-0">
              Filtruj topic:
              <HelpTip text="Pokazuje tylko zdarze?ia o topicu zaczynającym się od podanego prefiksu. Przykład: 'aeis.advisor' = wszystkie eventy z modułu advisor. Puste = pełna mapa (może być bardzo gęsta przy 100+ topiców). Enter aplikuje filtr." />
            </span>
            <input
              type="text"
              className="flex-1 px-2 py-1 rounded bg-background border border-border text-[11px] font-mono focus:outline-none focus:border-sylion-blue"
              placeholder="aeis.advisor..."
              value={topicFilter}
              onChange={e => setTopicFilter(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleFilterApply()}
            />
            <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={handleFilterApply}>Filtruj</Button>
            {topicFilter && (
              <Button variant="ghost" size="sm" className="h-7 text-[10px] text-muted-foreground"
                onClick={() => { setTopicFilter(""); load(); }}>Wyczyść</Button>
            )}
          </div>
        </Card>
      </motion.div>

      {loading ? (
        <Card className="p-8 bg-[#0f1629] border-[rgba(148,163,184,0.08)] text-center">
          <Loader2 className="w-5 h-5 animate-spin mx-auto text-sylion-blue" />
        </Card>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {/* Modules list */}
          <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.06 }}>
            <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] overflow-hidden">
              <div className="p-3 border-b border-[rgba(148,163,184,0.08)]">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Moduły ({uniqueModules.length})
                  <HelpTip text="Lista wszystkich modułów które emitują lub konsumują zdarze?ia. Klik wybiera moduł — prawa kolumna pokazuje TYLKO jego flow. ↑ = liczba topiców emitowanych, ↓ = liczba topiców subskrybowanych. Dobry moduł ma równowagę między tymi liczbami." />
                </p>
              </div>
              <div className="divide-y divide-[rgba(148,163,184,0.06)] max-h-96 overflow-y-auto">
                {uniqueModules.map(mod => (
                  <button
                    key={mod}
                    onClick={() => { setSelectedNode(mod); setSelectedEdge(null); }}
                    className={cn(
                      "w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-muted/10 transition-colors",
                      selectedNode === mod && "bg-accent-blue-dim"
                    )}
                  >
                    <span className={cn("text-[11px] font-mono truncate",
                      selectedNode === mod ? "text-sylion-blue" : "text-foreground"
                    )}>{mod}</span>
                    <div className="ml-auto flex items-center gap-1 shrink-0">
                      <span className="text-[8px] text-sylion-green">{nodeEmits(mod).length}↑</span>
                      <span className="text-[8px] text-sylion-amber">{nodeSubscribes(mod).length}↓</span>
                    </div>
                  </button>
                ))}
                {uniqueModules.length === 0 && (
                  <div className="p-4 text-center text-[11px] text-muted-foreground">Brak modułów</div>
                )}
              </div>
            </Card>
          </motion.div>

          {/* Edges / flows */}
          <motion.div className="col-span-2" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.08 }}>
            <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] overflow-hidden">
              <div className="p-3 border-b border-[rgba(148,163,184,0.08)]">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                  {selectedNode ? `Przepływy: ${selectedNode}` : `Wszystkie przepływy (${edges.length})`}
                  <HelpTip text="Każdy wiersz = jeden edge w grafie zdarzeń: emiter → topic → subskrybent. Liczba '/min' to przepustowość (ile eventów płynie). Klik wiersza pokazuje szczegóły niżej. Brak '/min' = topic zarejestrowany ale niewykorzystywany (martwy kod?)." />
                </p>
              </div>
              <div className="divide-y divide-[rgba(148,163,184,0.06)] max-h-96 overflow-y-auto">
                {(selectedNode
                  ? [...nodeEmits(selectedNode), ...nodeSubscribes(selectedNode)]
                  : edges
                ).map((edge: any, i: number) => (
                  <button
                    key={i}
                    onClick={() => setSelectedEdge(edge)}
                    className={cn(
                      "w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-muted/10 transition-colors",
                      selectedEdge === edge && "bg-accent-blue-dim"
                    )}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 text-[10px]">
                        <span className="font-mono text-sylion-green truncate max-w-[25%]">{edge.emitter}</span>
                        <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />
                        <code className="text-[9px] text-sylion-blue bg-accent-blue-dim px-1 rounded truncate flex-1">{edge.topic}</code>
                        <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />
                        <span className="font-mono text-sylion-amber truncate max-w-[25%]">{edge.subscriber}</span>
                      </div>
                    </div>
                    {edge.events_per_minute > 0 && (
                      <Badge variant="outline" className="text-[7px] border-muted-foreground/20 text-muted-foreground shrink-0">
                        {edge.events_per_minute}/min
                      </Badge>
                    )}
                  </button>
                ))}
                {edges.length === 0 && (
                  <div className="p-4 text-center text-[11px] text-muted-foreground">Brak przepływów zdarzeń</div>
                )}
              </div>
            </Card>

            {/* Edge detail */}
            {selectedEdge && (
              <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="mt-3">
                <Card className="p-3 border-sylion-blue/20 bg-[#0f1629]">
                  <p className="text-[9px] font-semibold text-sylion-blue uppercase tracking-wider mb-2">Szczegóły przepływu</p>
                  <div className="grid grid-cols-3 gap-3 text-[10px]">
                    <div>
                      <p className="text-muted-foreground mb-0.5">Emiter</p>
                      <p className="font-mono text-sylion-green">{selectedEdge.emitter}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground mb-0.5">Topic</p>
                      <p className="font-mono text-sylion-blue">{selectedEdge.topic}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground mb-0.5">Subskrybent</p>
                      <p className="font-mono text-sylion-amber">{selectedEdge.subscriber}</p>
                    </div>
                  </div>
                  {selectedEdge.events_per_minute > 0 && (
                    <p className="text-[10px] text-muted-foreground mt-2">Przepustowość: {selectedEdge.events_per_minute} zdarzeń/min</p>
                  )}
                </Card>
              </motion.div>
            )}
          </motion.div>
        </div>
      )}

      {eventMap?.generated_at && (
        <p className="text-[9px] text-muted-foreground">Wygenerowano: {eventMap.generated_at}</p>
      )}
    </div>
  );
}
