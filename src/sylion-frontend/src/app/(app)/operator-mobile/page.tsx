"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HelpTip } from "@/components/common/HelpTip";
import {
  BellRing,
  ChevronRight,
  QrCode,
  ShieldCheck,
  Smartphone,
  WifiOff,
} from "lucide-react";

import {
  formatPriority,
  priorityTone,
  useOperatorId,
  useOperatorMobileDevices,
  useOperatorMobileQueue,
} from "./_mobile";

export default function OperatorMobileLandingPage() {
  const { operatorId, setOperatorId } = useOperatorId();
  const { data: queueData, error: queueError, refresh: refreshQueue } = useOperatorMobileQueue(operatorId);
  const { data: devicesData, error: devicesError, refresh: refreshDevices } = useOperatorMobileDevices(operatorId);

  const backendLive = !queueError && !devicesError;
  const tickets = queueData.tickets;
  const devices = devicesData.devices;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-sylion-blue/20 bg-sylion-blue/10">
            <Smartphone className="h-5 w-5 text-sylion-blue" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Operator mobilny
              <HelpTip
                text="Ten ekran pokazuje mobilne przedłużenie Human Gate: kolejkę decyzji, zbindowane urządzenia i bezpieczne approvale. Działania wiążące nadal wymagają świadomej zgody operatora."
                side="right"
              />
            </h1>
            <p className="text-sm text-muted-foreground">
              Mobilny most akceptacji dla wspólnej kolejki governance.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-red/30 text-sylion-red"}>
            {backendLive ? "DZIAŁA" : "NIEDOSTĘPNY"}
          </Badge>
          <Button variant="outline" size="sm" onClick={() => { refreshQueue(); refreshDevices(); }}>
            Odśwież
          </Button>
        </div>
      </div>

      {!backendLive && (
        <Card className="border-sylion-red/20 bg-[#0f1629] p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sylion-red/10">
              <WifiOff className="h-5 w-5 text-sylion-red" />
            </div>
            <div>
              <p className="text-sm font-medium text-sylion-red">Backend niedostępny</p>
              <p className="text-xs text-muted-foreground">
                Kolejka mobilna nie używa danych zastępczych; uruchom backend, aby sprawdźić żywe decyzję i urządzenia.
              </p>
            </div>
          </div>
        </Card>
      )}

      <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">Tożsamość operatora</p>
            <p className="mt-1 text-sm text-foreground">Wszystkie wywołania kolejki i urządzeń są ograniczone do identyfikatora operatora.</p>
          </div>
          <div className="flex w-full max-w-md items-center gap-2">
            <input
              value={operatorId}
              onChange={(event) => setOperatorId(event.target.value)}
              className="h-10 flex-1 rounded-lg border border-border/40 bg-background/40 px-3 text-sm outline-none transition focus:border-sylion-blue/40"
              placeholder="operator-main"
            />
            <Button variant="outline" size="sm" onClick={() => { refreshQueue(); refreshDevices(); }}>
              Zastosuj
            </Button>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        {[
          {
            label: "Oczekujące decyzję",
            value: tickets.length,
            icon: BellRing,
            tone: "text-sylion-amber",
            bg: "bg-sylion-amber/10",
          },
          {
            label: "Zbindowane urządzenia",
            value: devices.length,
            icon: Smartphone,
            tone: "text-sylion-blue",
            bg: "bg-sylion-blue/10",
          },
          {
            label: "Pilne zgody",
            value: tickets.filter((ticket) => ticket.priority === "P0" || ticket.priority === "P1").length,
            icon: ShieldCheck,
            tone: "text-sylion-green",
            bg: "bg-sylion-green/10",
          },
        ].map((stat, index) => {
          const Icon = stat.icon;
          return (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.06, duration: 0.3 }}
            >
              <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{stat.label}</p>
                    <p className={`mt-2 text-3xl font-semibold ${stat.tone}`}>{stat.value}</p>
                  </div>
                  <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${stat.bg}`}>
                    <Icon className={`h-5 w-5 ${stat.tone}`} />
                  </div>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold">Podgląd kolejki akceptacji</p>
              <p className="text-[11px] text-muted-foreground">Najwyższe priorytety widoczne dla operatora mobilnego.</p>
            </div>
            <Link href="/operator-mobile/queue">
              <Button variant="outline" size="sm">
                Otwórz kolejkę
              </Button>
            </Link>
          </div>

          <div className="mt-4 space-y-3">
            {tickets.slice(0, 3).map((ticket) => (
              <div key={ticket.ticket_id} className="rounded-xl border border-border/30 bg-background/20 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">{ticket.title}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{ticket.summary}</p>
                  </div>
                  <Badge variant="outline" className={priorityTone(ticket.priority)}>
                    {formatPriority(ticket.priority)}
                  </Badge>
                </div>
                <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>{ticket.decision_class} • {ticket.gate_type}</span>
                  <Link href={`/operator-mobile/queue/${ticket.ticket_id}`}>
                    <span className="inline-flex items-center gap-1 text-sylion-blue">
                      Sprawdź
                      <ChevronRight className="h-3.5 w-3.5" />
                    </span>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sylion-blue/10">
              <QrCode className="h-5 w-5 text-sylion-blue" />
            </div>
            <div>
              <p className="text-xs font-semibold">Parowanie</p>
              <p className="text-[11px] text-muted-foreground">Użyj tego przepływu tokena, aby powiązać urządzenie z kolejką decyzji.</p>
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-dashed border-sylion-blue/30 bg-sylion-blue/5 p-5 text-center">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Kod parowania</p>
            <p className="mt-2 font-mono text-lg text-sylion-blue">{operatorId.replace(/[^a-zA-Z0-9]/g, "").slice(0, 8).toUpperCase()}-B5</p>
            <p className="mt-3 text-xs text-muted-foreground">
              Klient mobilny powinien wysłać `device_token`, `platform` oraz identyfikator operatora do `/api/v1/mobile/devices/bind`.
            </p>
          </div>

          <div className="mt-5 flex flex-col gap-2">
            <Link href="/operator-mobile/devices">
              <Button className="w-full justify-between">
                Zarządzaj urządzeniami
                <ChevronRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/operator-mobile/queue">
              <Button variant="outline" className="w-full justify-between">
                Przejrzyj kolejkę
                <ChevronRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
