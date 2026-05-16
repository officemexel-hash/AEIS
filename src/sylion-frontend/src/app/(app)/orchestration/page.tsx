"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { orchestrationApi } from "@/lib/api/orchestration";
import {
  Network, Scale, Clock, Wrench, Cpu, TestTube,
  Users, Share2, MessageSquare, Settings2, WifiOff,
} from "lucide-react";

const FEATURES = [
  { href: "/orchestration/llm-routing",   icon: Network,       badge: "J1", label: "Routing LLM Judge",      desc: "Macierz routingu modeli per typ rekomendacji × poziom ryzyka" },
  { href: "/orchestration/council-rules", icon: Scale,         badge: "J2", label: "Reguły Rady",             desc: "Wagi rang, bramka krytyka, kworum, wartowniki dla D3-D5" },
  { href: "/orchestration/auditor",       icon: Clock,         badge: "J3", label: "Rytm Audytora",           desc: "Częstotliwość ticków, 16 wymiarów, harmonogram audytów fazowych" },
  { href: "/orchestration/fixer",         icon: Wrench,        badge: "J4", label: "Protokół Fixera",         desc: "Budżety retry per typ agenta, ścieżki eskalacji, auto-revert" },
  { href: "/orchestration/dispatch",      icon: Cpu,           badge: "J5", label: "Dispatch Agentów",        desc: "Tryb wide/capped, alokacja agentów per etap, pułapy kosztowe" },
  { href: "/orchestration/tests",         icon: TestTube,      badge: "J6", label: "Katalog Testów",          desc: "Browser testów golden/integration/e2e, uruchamianie on-demand" },
  { href: "/orchestration/teams",         icon: Users,         badge: "J7", label: "Formowanie Zespołów",     desc: "Reguły commit-pattern → spawn team, aktywne zespoły" },
  { href: "/orchestration/event-map",     icon: Share2,        badge: "J8", label: "Mapa Zdarzeń",            desc: "Graf emiterów → zdarzeń → subskrybentów między modułami" },
  { href: "/orchestration/conversations", icon: MessageSquare, badge: "J9", label: "Rozmowy Modeli",          desc: "Agent-to-agent discussion, arbiter, log konwersacji" },
];

export default function OrchestrationHubPage() {
  const [live, setLive] = useState<boolean | null>(null);

  useEffect(() => {
    orchestrationApi.health()
      .then(() => setLive(true))
      .catch(() => setLive(false));
  }, []);

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent-blue-dim flex items-center justify-center">
              <Settings2 className="w-5 h-5 text-sylion-blue" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Meta-Orkiestracja</h1>
              <p className="text-sm text-muted-foreground">Kontrola działania systemu multi-agentowego AEIS</p>
            </div>
          </div>
          {live === null ? null : live ? (
            <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green">
              <span className="w-1.5 h-1.5 rounded-full bg-sylion-green mr-1.5" />LIVE
            </Badge>
          ) : (
            <Badge variant="outline" className="text-[10px] border-sylion-red/30 text-sylion-red">
              <WifiOff className="w-3 h-3 mr-1" />OFFLINE
            </Badge>
          )}
        </div>
      </motion.div>

      <div className="grid grid-cols-3 gap-3">
        {FEATURES.map((f, i) => {
          const Icon = f.icon;
          return (
            <motion.div
              key={f.href}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: i * 0.04 }}
            >
              <Link href={f.href}>
                <Card className="p-4 border-[rgba(148,163,184,0.08)] bg-[#0f1629] hover:border-sylion-blue/30 hover:bg-[#111827] transition-all duration-200 cursor-pointer h-full">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-accent-blue-dim flex items-center justify-center shrink-0 mt-0.5">
                      <Icon className="w-4 h-4 text-sylion-blue" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-semibold">{f.label}</span>
                        <span className="text-[8px] font-mono bg-accent-blue-dim text-sylion-blue px-1 py-0.5 rounded">{f.badge}</span>
                      </div>
                      <p className="text-[10px] text-muted-foreground leading-relaxed">{f.desc}</p>
                    </div>
                  </div>
                </Card>
              </Link>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
