"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CheckCircle2, Clock3, ShieldAlert, XCircle } from "lucide-react";

import {
  decideMobileTicket,
  formatPriority,
  formatTimestamp,
  priorityTone,
  stateTone,
  useOperatorId,
  useOperatorMobileQueue,
} from "../_mobile";

export default function OperatorMobileQueuePage() {
  const { operatorId } = useOperatorId();
  const { data, error, refresh } = useOperatorMobileQueue(operatorId);
  const [busyTicketId, setBusyTicketId] = useState<string | null>(null);

  const backendLive = !error;
  const tickets = data.tickets;

  const handleDecision = async (ticketId: string, decision: "approved" | "rejected") => {
    setBusyTicketId(ticketId);
    try {
      await decideMobileTicket(ticketId, {
        decision,
        reviewer: operatorId,
        reason: `mobile ${decision}`,
      });
      refresh();
    } catch {
      // ignore and keep UI responsive when backend is offline or route not mounted yet
    } finally {
      setBusyTicketId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Kolejka mobilna</h1>
          <p className="text-sm text-muted-foreground">
            Pending approvals for <span className="font-mono text-foreground">{operatorId}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={backendLive ? "border-sylion-green/30 text-sylion-green" : "border-sylion-amber/30 text-sylion-amber"}>
            {backendLive ? "LIVE" : "OFFLINE"}
          </Badge>
          <Button variant="outline" size="sm" onClick={() => refresh()}>
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid gap-4">
        {tickets.map((ticket) => (
          <Card key={ticket.ticket_id} className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className={priorityTone(ticket.priority)}>
                    <ShieldAlert className="mr-1 h-3 w-3" />
                    {formatPriority(ticket.priority)}
                  </Badge>
                  <Badge variant="outline" className={stateTone(ticket.state)}>
                    <Clock3 className="mr-1 h-3 w-3" />
                    {ticket.state.toUpperCase()}
                  </Badge>
                  <Badge variant="outline" className="border-border/40 text-muted-foreground">
                    {ticket.decision_class}
                  </Badge>
                </div>
                <div>
                  <p className="text-base font-semibold">{ticket.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{ticket.summary}</p>
                </div>
                <div className="flex flex-wrap gap-4 text-[11px] text-muted-foreground">
                  <span>Origin: {ticket.origin}</span>
                  <span>Project: {ticket.project_id || "---"}</span>
                  <span>Created: {formatTimestamp(ticket.created_at)}</span>
                  <span>Targets: {ticket.delivery_targets ?? 0}</span>
                </div>
              </div>

              <div className="flex min-w-[240px] flex-col gap-2">
                <Link href={`/operator-mobile/queue/${ticket.ticket_id}`}>
                  <Button variant="outline" className="w-full justify-between">
                    Open Detail
                    <CheckCircle2 className="h-4 w-4" />
                  </Button>
                </Link>
                <Button
                  className="w-full justify-between bg-sylion-green/90 text-black hover:bg-sylion-green"
                  disabled={busyTicketId === ticket.ticket_id}
                  onClick={() => handleDecision(ticket.ticket_id, "approved")}
                >
                  Approve
                  <CheckCircle2 className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-between border-sylion-red/30 text-sylion-red hover:bg-sylion-red/10"
                  disabled={busyTicketId === ticket.ticket_id}
                  onClick={() => handleDecision(ticket.ticket_id, "rejected")}
                >
                  Reject
                  <XCircle className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>
        ))}

        {tickets.length === 0 && (
          <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-8 text-center">
            <p className="text-sm text-muted-foreground">No pending tickets for this operator.</p>
          </Card>
        )}
      </div>
    </div>
  );
}
