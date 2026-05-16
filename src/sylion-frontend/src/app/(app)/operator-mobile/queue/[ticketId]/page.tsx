"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ArrowLeft, CheckCircle2, Clock3, Shield, XCircle } from "lucide-react";

import {
  decideMobileTicket,
  formatPriority,
  formatTimestamp,
  priorityTone,
  stateTone,
  useOperatorId,
  useOperatorMobileTicket,
} from "../../_mobile";

export default function OperatorMobileTicketDetailPage() {
  const params = useParams<{ ticketId: string }>();
  const ticketId = String(params.ticketId || "");
  const { operatorId } = useOperatorId();
  const { data: ticket, loading, refresh } = useOperatorMobileTicket(ticketId, operatorId);
  const [busy, setBusy] = useState<"approved" | "rejected" | null>(null);

  const handleDecision = async (decision: "approved" | "rejected") => {
    setBusy(decision);
    try {
      await decideMobileTicket(ticketId, {
        decision,
        reviewer: operatorId,
        reason: `mobile ${decision}`,
      });
      refresh();
    } catch {
      // detail page keeps the last visible state if backend is offline
    } finally {
      setBusy(null);
    }
  };

  if (loading && !ticket) {
    return (
      <div className="space-y-6">
        <Link href="/operator-mobile/queue">
          <span className="inline-flex items-center gap-2 text-sm text-sylion-blue">
            <ArrowLeft className="h-4 w-4" />
            Back to queue
          </span>
        </Link>
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-8 text-center">
          <p className="text-sm text-muted-foreground">Loading mobile ticket...</p>
        </Card>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="space-y-6">
        <Link href="/operator-mobile/queue">
          <span className="inline-flex items-center gap-2 text-sm text-sylion-blue">
            <ArrowLeft className="h-4 w-4" />
            Back to queue
          </span>
        </Link>
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-8 text-center">
          <p className="text-sm font-medium">Ticket not found</p>
          <p className="mt-1 text-xs text-muted-foreground">
            No live mobile ticket with id <span className="font-mono">{ticketId}</span> is available for operator <span className="font-mono">{operatorId}</span>.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <Link href="/operator-mobile/queue">
            <span className="inline-flex items-center gap-2 text-sm text-sylion-blue">
              <ArrowLeft className="h-4 w-4" />
              Back to queue
            </span>
          </Link>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">{ticket.title}</h1>
            <p className="text-sm text-muted-foreground font-mono">{ticket.ticket_id}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={priorityTone(ticket.priority)}>
            {formatPriority(ticket.priority)}
          </Badge>
          <Badge variant="outline" className={stateTone(ticket.state)}>
            {ticket.state.toUpperCase()}
          </Badge>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-sylion-blue" />
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Decision Context</p>
          </div>
          <p className="mt-4 text-sm leading-6 text-foreground/90">{ticket.summary}</p>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {[
              ["Origin", ticket.origin],
              ["Decision Class", ticket.decision_class],
              ["Gate Type", ticket.gate_type],
              ["Project", ticket.project_id || "---"],
              ["Requested By", ticket.requested_by || "---"],
              ["Created", formatTimestamp(ticket.created_at)],
              ["SLA Deadline", formatTimestamp(ticket.sla_deadline)],
              ["Resolution Reason", ticket.resolution_reason || "---"],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-xl border border-border/30 bg-background/20 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
                <p className="mt-2 text-sm">{value}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Mobile Action</p>
          <div className="mt-4 space-y-3 rounded-2xl border border-border/30 bg-background/20 p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">Current state</span>
              <Badge variant="outline" className={stateTone(ticket.state)}>
                <Clock3 className="mr-1 h-3 w-3" />
                {ticket.state.toUpperCase()}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Operator</span>
              <span className="font-mono text-xs text-muted-foreground">{operatorId}</span>
            </div>
          </div>

          <div className="mt-5 flex flex-col gap-2">
            <Button
              className="w-full justify-between bg-sylion-green/90 text-black hover:bg-sylion-green"
              disabled={busy !== null}
              onClick={() => handleDecision("approved")}
            >
              Approve from Mobile
              <CheckCircle2 className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              className="w-full justify-between border-sylion-red/30 text-sylion-red hover:bg-sylion-red/10"
              disabled={busy !== null}
              onClick={() => handleDecision("rejected")}
            >
              Reject from Mobile
              <XCircle className="h-4 w-4" />
            </Button>
          </div>

          <div className="mt-5 rounded-2xl border border-dashed border-border/40 p-4 text-xs text-muted-foreground">
            Payload mirrors the unified governance ticket; mobile does not create its own approval plane.
          </div>
        </Card>
      </div>
    </div>
  );
}
